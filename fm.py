#!/usr/bin/python3
# Copyright (c) 2019 Bart Massey
# [This program is licensed under the "MIT License"]
# Please see the file LICENSE in the source
# distribution of this software for license terms.

# MIDI synthesizer in Python.

# Sample rate.
rate = 48000

# Number of voices to play before compressing output volume
# to inhibit clipping.
compression = 5

import argparse, array, math, mido, sounddevice, toml, sys, wave
import numpy as np
import numpy.fft as fft

debugging = False
def debug(*args, **kwargs):
    """Print message if debugging."""
    if debugging:
        if "file" in kwargs:
            raise Exception("file argument to debug function")
        kwargs["file"] = sys.stderr
        print(*args, **kwargs)

# Sample Processing Strategy
#
# This code contains a set of note objects called `notemap`,
# maintained jointly by the main MIDI processing loop and
# the `mix()` function. It also contains a dict `keymap`
# mapping MIDI key numbers to note objects, maintained by
# the MIDI processing loop.
#
# When a MIDI note-on event is received, a note object for
# that key is put in the notemap and in the keymap. When
# `mix()` is called in `callback()` to get a block of
# samples, it runs through the notemap extracting a block of
# samples from each note. If a note has no more samples to
# give, because it has played completely, it is removed from
# the notemap by `mix()`. When a MIDI note-off event is
# received, the corresponding keymap entry's note object
# gets an `off()` message to tell it to start its release,
# and the keymap forgets the note so that it can be played
# again.

def make_times(t, tv, n):
    """Return a sequence of n time points for wave sampling."""
    times = np.linspace(
        t,
        t + n,
        num = n,
        endpoint = False,
        dtype = np.float32,
    )
    if tv is not None:
        times += tv
    return times

class Saw(object):
    """Sawtooth VCO."""
    def __init__(self, f):
        """Make a new sawtooth generator."""
        self.tmul = f / rate

    def samples(self, t, tv = None, n = 1):
        """Return the next n samples from this generator."""
        times = make_times(t, tv, n)
        # https://en.wikipedia.org/wiki/Sawtooth_wave
        a = self.tmul * times
        return 2.0 * (a - np.floor(0.5 + a))

class Triangle(object):
    """Triangle VCO."""
    def __init__(self, f):
        """Make a new triangle generator."""
        self.tmul = f / rate

    def samples(self, t, tv = None, n = 1):
        """Return the next n samples from this generator."""
        times = make_times(t, tv, n)
        # https://en.wikipedia.org/wiki/Triangle_wave
        a = times * self.tmul
        return 2.0 * np.abs(2.0 * (a - np.floor(a + 0.5))) - 1.0

class Sine(object):
    """Sine VCO."""
    def __init__(self, f):
        """Make a new sine generator."""
        self.period = 2 * math.pi * f / rate

    def samples(self, t, tv = None, n = 1):
        """Return the next n samples from this generator."""
        times = make_times(t, tv, n)
        return np.sin(times * self.period)


class Square(object):
    """Square VCO."""
    def __init__(self, f):
        """Make a new square generator."""
        self.tmul = f / rate

    def samples(self, t, tv = None, n = 1):
        """Return the next n samples from this generator."""
        times = make_times(t, tv, n)
        # https://en.wikipedia.org/wiki/Square_wave
        a = self.tmul * times
        return 2.0 * (2.0 * np.floor(a) - np.floor(2.0 * a)) + 1.0

class FM(object):
    """FM VCO."""
    def __init__(self, f, fmod, amod):
        """Make a new FM generator."""
        self.sine = Sine(f)
        # XXX It turns out to sound better to have the
        # modulation frequency adapt to the note frequency.
        self.lfo = Sine(f + fmod)
        self.amod = amod

    def samples(self, t, tv = None, n = 1):
        """Return the next n samples from this generator."""
        depth = control_modwheel.value()
        tmod = self.amod * depth * self.lfo.samples(t, n=n)
        return self.sine.samples(t, tv=tmod, n=n)

class GenFM(object):
    """FM VCO factory."""
    def __init__(self, fmod=2, amod=100):
        """Make a new FM generator generator."""
        self.fmod = fmod
        self.amod = amod

    def __call__(self, f):
        return FM(f, fmod=self.fmod, amod=self.amod)

class Wave(object):
    """Wavetable VCO"""
    def __init__(self, wavetable, f0, f):
        self.step = f / f0
        self.wavetable = wavetable
        self.nwavetable = len(wavetable)

    def samples(self, t, tv = None, n = 1):
        """Return the next n samples from this generator."""
        times = make_times(t, tv, n)
        # XXX Should antialias
        t0 = (self.step * times) % self.nwavetable
        int_part = np.floor(t0)
        frac_part = t0 - int_part
        i0 = int_part.astype(int)
        i1 = (i0 + 1) % self.nwavetable
        x0 = self.wavetable[i0]
        x1 = self.wavetable[i1]
        return x0 * frac_part + x1 * (1.0 - frac_part)

def read_wave(filename):
    """Read samples from a wave file."""
    with wave.open(filename, "rb") as w:
        info = w.getparams()
        fbytes = w.readframes(info.nframes)
        w.close()
        sampletypes = {
            1: (np.uint8, -(1 << 7), 1 << 8),
            2: (np.int16, 0.5, 1 << 16),
            4: (np.int32, 0.5, 1 << 32),
        }
        if info.sampwidth not in sampletypes:
            raise IOException("invalid wave file format")
        if info.nchannels != 1:
            raise IOException("wave file must be mono (1 channel)")
        if info.framerate != rate:
            raise IOException(f"wave file frame rate must be {rate}")
        sampletype, sampleoff, samplewidth = sampletypes[info.sampwidth]
        samples = np.frombuffer(fbytes, dtype=sampletype).astype(np.float32)
        scale = 2.0 / samplewidth
        fsamples = scale * (samples + sampleoff)
        return samples

def write_wave(filename, samples):
    """Write samples to a wave file."""
    with wave.open(filename, "wb") as w:
        out = (samples * 32767).astype(np.int16)
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.setnframes(len(out))
        w.writeframesraw(out)

class GenWave(object):
    """Wavetable VCO factory."""
    def __init__(self, samplefile):
        """Make a new wave generator generator."""
        psignal = read_wave(samplefile)
        # Adjust global peak amplitude.
        peak = np.max(np.abs(psignal))
        psignal /= peak
        # XXX Should compress the signal hard.
        # Find fundamental frequency with DFT.
        npsignal = len(psignal)
        ndft = 2
        minsamples = int(0.1 * rate)
        if npsignal < minsamples:
            raise Exception("sample too short")
        while ndft < 16 * 1024 and 2 * ndft <= npsignal:
            ndft *= 2
        if npsignal > ndft:
            start = (npsignal - ndft) // 2
            fsignal = psignal[start:start + ndft]
        else:
            fsignal = psignal
        assert len(fsignal) == ndft
        window = np.blackman(ndft)
        dft = fft.fft(fsignal * window)
        maxbin = np.argmax(np.abs(dft))
        maxf = abs(fft.fftfreq(ndft, 1 / rate)[maxbin])
        if maxf < 100 or maxf > 4000:
            raise Exception(f"sample frequency {maxf} out of range")
        debug(f"maxf={maxf}")
        # XXX Should auto-truncate the signal to sustain (hard).
        # Loop the sample properly (if sufficient samples).
        # Heuristic considers first 8 vs last 16 periods' worth of
        # samples.
        p = rate / maxf
        debug(f"period={p}")
        w = int(p * 8)
        if npsignal >= 2 * w:
            ssignal = psignal[-2 * w:]
            tsignal = psignal[:w]
            corrs = np.correlate(ssignal, tsignal, mode='valid')
            maxc = np.argmax(corrs)
            debug(f"maxc={maxc} corr={corrs[maxc]}")
            trunc = w - maxc
            psignal = psignal[:-trunc]
            # Smooth the transition over a period.
            t = int(p)
            sweight = np.linspace(0, 1, t)
            ssignal = psignal[:t]
            tweight = np.linspace(1, 0, t)
            tsignal = psignal[-t:]
            smoothed = sweight * ssignal + tweight * tsignal
            psignal = np.append(psignal[:-t], smoothed)
            # write_wave("trunc.wav", psignal)
        # Save analysis results for Wave creation.
        self.f0 = maxf
        self.wavetable = psignal

    def __call__(self, f):
        return Wave(self.wavetable, self.f0, f)

# Process command-line arguments.
ap = argparse.ArgumentParser()
ap.add_argument(
    "-k", "--keyboard",
    help="Connect to given keyboard.",
    type=str,
)
ap.add_argument(
    "-K", "--kbmap",
    help="Use given JSON keyboard map file.",
    type=str,
)
ap.add_argument(
    "--sine", "--sin",
    help="Use sine wave generator",
    action="store_true",
)
ap.add_argument(
    "--square",
    help="Use square wave generator",
    action="store_true",
)
ap.add_argument(
    "--saw", "--sawtooth",
    help="Use sawtooth wave generator",
    action="store_true",
)
ap.add_argument(
    "--tri", "--triangle",
    help="Use triangle wave generator",
    action="store_true",
)
ap.add_argument(
    "--fm", "--FM",
    help="Use FM generator with given mod delta-freq and depth",
    nargs=2,
    type=float,
    metavar=("FMOD", "DMOD"),
)
ap.add_argument(
    "--wave", "--sample",
    help="Use wave (sampling) generator with given .wav file",
    type=str,
    metavar="WAVFILE",
)
ap.add_argument(
    "--just",
    help="Use (five-limit) just intonation (root is BASE half-steps above A)",
    type=int,
    metavar="BASE",
)
ap.add_argument(
    "--pyth", "--pythagorean",
    help="Use Pythagorean (three-limit) just intonation (root is BASE half-steps above A)",
    type=int,
    metavar="BASE",
)
ap.add_argument(
    "-b", "--buffer-size",
    help="Sample buffer size",
    type=int,
    default=48,
    metavar="SAMPLES",
)
ap.add_argument(
    "--t-attack",
    help="Attack time in msecs",
    type=float,
    default=30,
    metavar="SAMPLES",
)
ap.add_argument(
    "--t-decay",
    help="Decay time in msecs",
    type=float,
    default=30,
    metavar="SAMPLES",
)
ap.add_argument(
    "--a-sustain",
    help="Sustain level as fraction",
    type=float,
    default=0.8,
    metavar="SAMPLES",
)
ap.add_argument(
    "--t-release",
    help="Release time in msecs",
    type=float,
    default=30,
    metavar="SAMPLES",
)
ap.add_argument(
    "-d", "--debug",
    help="Print debugging messages",
    action="store_true",
)
args = ap.parse_args()

tuning = None
for base, name in [(args.just, "just"), (args.pyth, "pyth")]:
    if base is not None:
        if tuning is not None:
            raise Exception("multiple tunings specified")
        tuning_base = base
        tuning = name

if args.debug:
    debugging = True

# Find a generator.
generator = None
def get_gen(name, gen, argstype="flag"):
    global generator
    if hasattr(args, name):
        values = getattr(args, name)
        mygen = None
        if argstype == "flag":
            if values == False:
                return
            mygen = gen
        elif argstype == "list":
            if values is None:
                return
            mygen = gen(*values)
        elif argstype == "string":
            if values is None:
                return
            mygen = gen(values)
        else:
            raise Exception(f"unknown generator argstype {argstype}")
        if mygen is not None:
            if generator is not None:
                raise Exception("multiple generators specified")
            generator = mygen
            debug(f"generator {name}")

basics = {"saw": Saw, "sine": Sine, "square": Square, "tri": Triangle}
for name in basics:
    get_gen(name, basics[name])
get_gen("fm", GenFM, argstype="list")
get_gen("wave", GenWave, argstype="string")
if generator is None:
    generator = GenFM()

# Global sample clock, indicating the number of samples
# played since synthesizer start (excluding underruns).
sample_clock = 0

# Parse a TOML keyboard map if given.
button_stop = None
control_stop = None
knob_volume = None
knob_modwheel = None
knob_param1 = None
keyboard_name = None
control_suppressed = set()
if args.kbmap is not None:
    try:
        kbmap = toml.load(args.kbmap)
    except Exception as e:
        debug("cannot load kbmap", e)
        exit(1)
    if "name" in kbmap:
        keyboard_name = kbmap["name"]
    if "suppressed" in kbmap:
        control_suppressed = set(kbmap["suppressed"])
    if "controls" in kbmap:
        controls = kbmap["controls"]
        if "stop" in controls:
            button_stop = controls["stop"]
        if "volume" in controls:
            knob_volume = controls["volume"]
        if "modwheel" in controls:
            knob_modwheel = controls["modwheel"]
        if "param1" in controls:
            knob_param1 = controls["param1"]

# Use a keyboard name if given. This will override
# the keyboard map.
if args.keyboard is not None:
    keyboard_name = args.keyboard

# Open an input port.
if keyboard_name is None:
    # Accept pending ALSA (or whatever) MIDI connection.
    inport = mido.open_input('fm', virtual=True)
else:
    # Open the named MIDI keyboard. XXX Linux kludge to find
    # the keyboard on whatever midi port it is on. Don't
    # know how Windows or Mac will handle this.
    ports = [""] + [f" MIDI {i}" for i in range (1, 9)]
    found = False
    for port in ports:
        try:
            inport = mido.open_input(f"{keyboard_name}{port}")
            found = True
            break
        except IOError as e:
            pass
    if not found:
        debug(f"cannot find keyboard {keyboard_name}")
        exit(1)
    
assert inport != None

class Knob(object):
    """Knob-controlled parameter."""
    def __init__(self, name, scaling="log", initial=63):
        """New knobbed parameter with given scaling ("log" or
        "linear") and initial control value.
        """
        self.knob_name = name
        # Knob scaling.
        if scaling == "log":
            # "log" scaling is actually exponential, to
            # compensate for log response.
            self.scaler = lambda v: 2.0 ** (v / 127.0) - 1.0
        elif scaling == "linear":
            self.scaler = lambda v: v / 127.0
        else:
            raise Exception(f"unknown knob scaling {scaling}")
        # Target control value.
        self.cvalue = initial
        # Current interpolation between previous and target
        # control value.
        self.ivalue = self.cvalue
        # Interpolation time constant (per second).
        self.irate = 1.0 / (0.005 * rate)
        # Current time.
        self.t = sample_clock

    def set(self, cvalue):
        """Set new knob target value at current time."""
        self.cvalue = cvalue
        self.t = sample_clock

    def value(self):
        """Update and return knob interpolated value at time t."""
        ds = min((sample_clock - self.t) * self.irate, 1.0)
        assert ds >= 0
        self.ivalue = self.cvalue * ds + self.ivalue * (1.0 - ds)
        self.t = sample_clock
        return self.scaler(self.ivalue)
    
    def name(self):
        """Canonical name of knob."""
        return self.knob_name

# Index of controls by MIDI control message code.
controls = dict()

# Set up the volume control.
control_volume = Knob("volume")
if knob_volume is not None:
    controls[knob_volume] = control_volume

# Set up the parameter controls.
control_modwheel = Knob("modwheel")
if knob_modwheel is not None:
    controls[knob_modwheel] = control_modwheel
control_param1 = Knob("param1")
if knob_param1 is not None:
    controls[knob_param1] = control_param1

# Set up the stop control if needed. XXX This is a kludge to
# make a knob turned to zero exit the synth.
if type(button_stop) == str:
    found = False
    for k, c in controls.items():
        if c.name() == button_stop:
            found = True
            control_stop = k
            break
    if not found:
        raise Exception(f"unknown stop control {button_stop}")

# Keymap contains currently-held notes for keys.
keymap = dict()

# Note map contains currently-playing notes.
notemap = set()

class ADSR(object):
    """Attack-Decay-Sustain-Release envelope."""
    def __init__(self, attack=30, decay=30, sustain=0.8, release=30):
        """Make a new ADSR envelope. attack, decay, release are in ms.
        Sustain is fraction of full volume."""
        self.attack = int(attack * 0.001 * rate)
        self.decay = int(decay * 0.001 * rate)
        self.sustain = sustain
        self.release = int(release * 0.001 * rate)

just_ratios = [
    1, 16/15, 9/8, 6/5, 5/4, 4/3, 45/32, 3/2, 8/5, 5/3, 9/5, 15/8,
]

pyth_ratios = [
    1/1, # C
    256/243, # Db
    9/8, # D
    32/27, # Eb
    81/64, # E
    4/3, # F
    # 729/512, # F# Pythagorean
    # 1024/729, # Gb Pythagorean
    # Arbitrarily split the comma
    math.sqrt(2), # Gb / F#
    3/2, # G
    128/81, # Ab
    27/16, # A
    16/9, # Bb
    243/128, # B
]

# Set up for alternate tunings.
if tuning is not None:
    base_freq = 440 * 2**((tuning_base - 72) / 12)
    if tuning == "just":
        # debug("just tuning")
        ratios = just_ratios
    elif tuning == "pyth":
        # debug("pyth tuning")
        ratios = pyth_ratios
    else:
        raise Exception("unknown tuning", tuning)

def key_to_freq(key):
    """Convert MIDI key number to frequency in Hz.
    Key 69 is A4 (440 Hz)."""
    if tuning is None:
        return 440 * 2**((key - 69) / 12)
    octave = (key - tuning_base + 3) // 12
    offset = key - tuning_base + 3 - octave * 12
    # debug("just", key, octave, offset)
    return base_freq * 2**octave * ratios[offset]

key_freq = [key_to_freq(key) for key in range(128)]
# if debugging:
#     for i, f in enumerate(key_freq):
#         debug(f"key {i} = {f}")

class Note(object):
    """Note generator with envelope processing."""
    def __init__(self, key, velocity, gen):
        """Make a new note with envelope."""
        self.t = 0
        self.key = key
        self.velocity = velocity
        self.gen = gen(key_freq[key])
        self.release_time = None
        self.release_length = None
        self.env = ADSR(
            attack = args.t_attack,
            decay = args.t_decay,
            sustain = args.a_sustain,
            release = args.t_release,
        )


    def off(self, velocity):
        """Note is turned off. Start release."""
        self.release_time = self.t
        if velocity == 0.0:
            velocity = 1.0
        self.release_length = int(self.env.release * (1.0 - 0.5 * velocity))

    def envelope(self, n = 1):
        """Return the envelope for n samples from the given note at
        the given time.  Returns None when note should be
        dropped."""
        t = self.t
        rt = self.release_time
        if rt is not None:
            # Release is special.
            rl = self.release_length
            sus = self.env.sustain
            end = rt + rl
            # 0...a...d......rt..t..end
            if t >= end:
                return None
            m = min(n, end - t)
            levels = np.linspace(
                sus * (end - t) / rl,
                sus * (end - t + m) / rl,
                num = m,
                endpoint = False,
                dtype = np.float32,
            )
            if m < n:
                np.append(times, np.zeros(m - n))
            return levels
        # Piece together attack, decay, sustain.
        a = self.env.attack
        times = np.array(dtype=np.float32)
        if t < at:
            # Attack.
            # 0...a...d...
            m = min(a - t, n)
            alevels = np.linspace(
                t / a,
                (t + m) / a,
                num = m,
                endpoint = False,
                dtype = np.float32,
            )
            times.append(alevels)
            t += m
        # XXX HERE
        d = self.env.decay
        if len(times) < n and t < a + d:
            # Decay.
            # ..a...d...
            m = min(a + d - t, n)
            alevels = np.linspace(
                t / a,
                (t + m) / a,
                num = m,
                endpoint = False,
                dtype = np.float32,
            )
                
    def samples(self, n = 1):
        """Return the next n samples for this key."""
        samples = self.gen.samples(self.t, n = n)
        self.t += n
        return self.velocity * samples

def mix(n = 1):
    """Accumulate n composite samples from the active generators."""
    # Gather samples and count notes.
    s = np.zeros(n, dtype=np.float32)
    n_notes = 0
    for note in set(notemap):
        e = note.envelope()
        if e == None:
            # Release is complete. Get rid of the note.
            notemap.remove(note)
            continue
        s += e * note.samples(n = n)
        n_notes += 1

    # Do gain adjustments based on number of playing notes.
    if n_notes == 0:
        return np.array([0] * n)
    return control_volume.value() * s / max(n_notes, compression)

def callback(out_data, frame_count, time_info, status):
    """Supply frames to PortAudio."""
    if debugging and status != 0:
        print("cb", status)
    # Get frames of waveform.
    frames = mix(n = frame_count)
    # Adjust the sample clock.
    global sample_clock
    sample_clock += frame_count
    # Return frames and continue signal.
    out_data[:] = np.reshape(frames, (frame_count, 1))

# Set up the audio output stream.
stream = sounddevice.OutputStream(
    samplerate=48000,
    channels=1,
    blocksize=args.buffer_size,
    callback=callback,
)
stream.start()

# Process key events and modify the PA play freq.
while True:
    mesg = inport.receive()
    mesg_type = mesg.type
    if mesg_type == 'note_on' and mesg.velocity == 0:
        mesg_type = 'note_off'
    if mesg_type == 'note_on':
        key = mesg.note
        velocity = mesg.velocity / 127
        debug('note on', key, mesg.velocity, round(velocity, 2))
        assert key not in keymap
        note = Note(key, velocity, generator)
        keymap[key] = note
        notemap.add(note)
    elif mesg_type == 'note_off':
        key = mesg.note
        velocity = mesg.velocity / 127
        debug('note off', key, mesg.velocity, round(velocity, 2))
        if key in keymap:
            keymap[key].off(velocity)
            del keymap[key]
    elif mesg.type == 'control_change':
        if mesg.control == button_stop:
            break
        elif mesg.control in controls:
            # XXX Kludge to stop the synth when a knob is
            # turned to zero.
            if mesg.control == control_stop and mesg.value == 0:
                break
            c = controls[mesg.control]
            debug(f"control {c.name()} = {mesg.value}")
            c.set(mesg.value)
        elif mesg.control in control_suppressed:
            pass
        else:
            debug(f'unknown control {mesg.control}')
    else:
        debug('unknown message', mesg)

# Done, clean up and exit.
debug('exiting')
for key in set(keymap):
    keymap[key].off(1.0)
    del keymap[key]
notemap = set()
stream.stop()
stream.close()
