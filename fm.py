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
# `mix()` is called in `callback()` to get a sample, it runs
# through the notemap extracting a sample from each note. If
# a note has no more samples to give, because it has played
# completely, it is removed from the notemap by
# `mix()`. When a MIDI note-off event is received, the
# corresponding keymap entry's note object gets an `off()`
# message to tell it to start its release, and the keymap
# forgets the note so that it can be played again.

import argparse, array, math, mido, pyaudio, toml, sys, wave
import numpy as np

class Saw(object):
    """Sawtooth VCO."""
    def __init__(self, f):
        """Make a new sawtooth generator."""
        self.tmod = rate / f

    def sample(self, t, tv = 0.0):
        """Return the next sample from this generator."""
        return 2.0 * (((t + tv + self.tmod) % self.tmod) / self.tmod) - 1.0

class Sine(object):
    """Sine VCO."""
    def __init__(self, f):
        """Make a new sine generator."""
        self.period = 2 * math.pi * f / rate

    def sample(self, t, tv = 0.0):
        """Return the next sample from this generator."""
        return math.sin((t + tv) * self.period)


class Square(object):
    """Square VCO."""
    def __init__(self, f):
        """Make a new square generator."""
        self.tmod = rate / f
        self.half = self.tmod / 2.0

    def sample(self, t, tv = 0.0):
        """Return the next sample from this generator."""
        return 2.0 * int(((t + tv + self.tmod) % self.tmod) > self.half) - 1.0

class FM(object):
    """FM VCO."""
    def __init__(self, f, fmod = 3.0, amod = 40.0):
        """Make a new FM generator."""
        self.sine = Sine(f)
        # XXX It turns out to sound better to have the
        # modulation frequency adapt to the note frequency.
        self.lfo = Sine(f + fmod)
        self.amod = amod

    def sample(self, t, tv = 0.0):
        """Return the next sample from this generator."""
        tmod = self.amod * self.lfo.sample(t, tv=tv)
        return self.sine.sample(t, tv=tmod)

class GenFM(object):
    """FM VCO factory."""
    def __init__(self, fmod, amod):
        """Make a new FM generator generator."""
        self.fmod = fmod
        self.amod = amod

    def __call__(self, f):
        return FM(f, fmod=self.fmod, amod=self.amod)

class Wave(object):
    """Wavetable VCO"""
    def __init__(self, wavetable, f):
        self.step = f / 440.0
        self.wavetable = wavetable
        self.nwavetable = len(wavetable)

    def sample(self, t, tv = None):
        """Return the next sample from this generator."""
        assert tv is None
        # XXX Should antialias
        t0 = (self.step * t) % self.nwavetable
        i = int(t0)
        frac = t0 % 1.0
        x0 = self.wavetable[i]
        x1 = self.wavetable[(i + 1) % self.nwavetable]
        return x0 * frac + x1 * (1.0 - frac)

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
        samples = np.frombuffer(fbytes, dtype=sampletype).astype(np.float64)
        scale = 2.0 / samplewidth
        fsamples = scale * (samples + sampleoff)
        return samples

class GenWave(object):
    """Wavetable VCO factory."""
    def __init__(self, samplefile):
        """Make a new wave generator generator."""
        psignal = read_wave(samplefile)
        # Adjust global peak amplitude.
        peak = np.max(np.abs(psignal))
        psignal /= peak
        # XXX Should find fundamental frequency with DFT.
        # XXX Should loop the sample properly
        self.wavetable = psignal

    def __call__(self, f):
        return Wave(self.wavetable, f)

# Process command-line arguments.
class ParseGenerator(argparse.Action):
    """Parse the various generator arguments."""
    def __init__(self, option_strings, dest, **kwargs):
        parent = super(ParseGenerator, self)
        parent.__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        if hasattr(namespace, "generator"):
            raise ValueError("multiple generators")
        dest = self.dest
        basics = {"sine": Sine, "saw": Saw, "square": Square}
        if dest in basics:
            gen = basics[dest]
        elif dest == "wave":
            gen = GenWave(*values)
        elif dest == "fm":
            gen = GenFM(*values)
        else:
            raise ValueError(f"unknown generator {dest}")
        setattr(namespace, "generator", gen)

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
    nargs = 0,
    action=ParseGenerator,
    dest="sine",
)
ap.add_argument(
    "--square",
    help="Use square wave generator",
    nargs = 0,
    action=ParseGenerator,
)
ap.add_argument(
    "--saw", "--sawtooth",
    help="Use sawtooth wave generator",
    nargs = 0,
    action=ParseGenerator,
    dest="saw",
)
ap.add_argument(
    "--fm", "--FM",
    help="Use FM generator with given mod delta-freq and depth",
    nargs = 2,
    action=ParseGenerator,
    type = float,
    metavar=("FMOD", "DMOD"),
    dest="fm",
)
ap.add_argument(
    "--wave", "--sample",
    help="Use wave (sampling) generator with given .wav file",
    nargs = 1,
    action=ParseGenerator,
    metavar="WAVFILE",
    dest="wave",
)
args = ap.parse_args()

if hasattr(args, "generator"):
    generator = args.generator
else:
    generator = GenFM(3.0, 40.0)

# Global sample clock, indicating the number of samples
# played since synthesizer start (excluding underruns).
sample_clock = 0

# Parse a TOML keyboard map if given.
button_stop = None
control_stop = None
knob_volume = None
keyboard_name = None
control_suppressed = set()
if args.kbmap is not None:
    try:
        kbmap = toml.load(args.kbmap)
    except Exception as e:
        print("cannot load kbmap", e, file=sys.stderr)
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
        print(f"cannot find keyboard {keyboard_name}", file=sys.stderr)
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
        self.cvalue = self.scaler(initial)
        # Current interpolation between previous and target
        # control value.
        self.ivalue = self.cvalue
        # Interpolation time constant (per second).
        self.irate = 1.0 / (0.005 * rate)
        # Current time.
        self.t = sample_clock

    def set(self, cvalue):
        """Set new knob target value at current time."""
        self.cvalue = self.scaler(cvalue)
        self.t = sample_clock

    def value(self, t):
        """Update and return knob interpolated value at time t."""
        ds = (t - self.t) * self.irate
        assert ds >= 0
        self.ivalue = self.cvalue * ds + self.ivalue * (1.0 - ds)
        self.t = t
        return self.ivalue

    def name(self):
        """Canonical name of knob."""
        return self.knob_name

# Index of controls by MIDI control message code.
controls = dict()

# Set up the volume control.
control_volume = Knob("volume")
if knob_volume is not None:
    controls[knob_volume] = control_volume

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

# Attack time in secs and samples for AR envelope.
t_attack = 0.010
s_attack = int(rate * t_attack)

# Release time in secs and samples for AR envelope.
t_release = 0.01
s_release = int(rate * t_release)

# Conversion table: MIDI key numbers to frequencies in Hz.
# Key 69 is A4 (440 Hz).
key_to_freq = [440 * 2**((key - 69) / 12) for key in range(128)]

class Note(object):
    """Note generator with envelope processing."""
    def __init__(self, key, velocity, gen):
        """Make a new note with envelope."""
        self.t = 0
        self.key = key
        self.velocity = velocity
        self.release_time = None
        self.release_length = None
        self.gen = gen(key_to_freq[key])

    def off(self, velocity):
        """Note is turned off. Start release."""
        self.release_time = self.t
        if velocity == 0.0:
            velocity = 1.0
        self.release_length = s_release * (1.05 - velocity)

    def envelope(self):
        """Return the envelope for the given note at the given time.
        Returns None when note should be dropped."""
        t = self.t
        if self.release_time != None:
            rt = t - self.release_time
            if rt >= self.release_length:
                return None
            return 1.0 - rt / self.release_length
        if t < s_attack:
            return t / s_attack
        return 1.0

    def sample(self):
        """Return the next sample for this key."""
        sample = self.gen.sample(self.t)
        self.t += 1
        return self.velocity * sample

def clamp(v, c):
    """Clamp a value v to +- c."""
    return min(max(v, -c), c)

def mix(t):
    """Accumulate a composite sample from the active generators."""
    # Gather samples and count notes.
    s = 0
    n = 0
    for note in set(notemap):
        e = note.envelope()
        if e == None:
            # Release is complete. Get rid of the note.
            notemap.remove(note)
            continue
        s += e * note.sample()
        n += 1

    # Do gain adjustments based on number of playing notes.
    if n == 0:
        return 0
    return control_volume.value(t) * s / max(n, compression)

def callback(in_data, frame_count, time_info, status):
    """Supply frames to PortAudio."""
    # Get frames of waveform.
    global sample_clock
    data = [ clamp(int(32767.0 * mix(sample_clock + i)), 32767)
             for i in range(frame_count) ]
    sample_clock += frame_count
    # Get the frames into the right format for PA.
    frames = bytes(array.array('h', data))
    # Return frames and continue signal.
    return (frames, pyaudio.paContinue)

# Set up the audio output stream.
pa = pyaudio.PyAudio()
stream = pa.open(
    format=pa.get_format_from_width(2),
    channels=1,
    rate=48000,
    output=True,
    stream_callback=callback)

# Process key events and modify the PA play freq.
while True:
    mesg = inport.receive()
    mesg_type = mesg.type
    if mesg_type == 'note_on' and mesg.velocity == 0:
        mesg_type = 'note_off'
    if mesg_type == 'note_on':
        key = mesg.note
        velocity = mesg.velocity / 127
        print('note on', key, mesg.velocity, round(velocity, 2))
        assert key not in keymap
        note = Note(key, velocity, generator)
        keymap[key] = note
        notemap.add(note)
    elif mesg_type == 'note_off':
        key = mesg.note
        velocity = mesg.velocity / 127
        print('note off', key, mesg.velocity, round(velocity, 2))
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
            controls[mesg.control].set(mesg.value)
        elif mesg.control in control_suppressed:
            pass
        else:
            print(f'unknown control {mesg.control}')
    else:
        print('unknown message', mesg)

# Done, clean up and exit.
print('exiting')
for key in set(keymap):
    keymap[key].off(1.0)
    del keymap[key]
notemap = set()
stream.stop_stream()
stream.close()
