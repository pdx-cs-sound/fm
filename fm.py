#!/usr/bin/python3
# Copyright (c) 2019 Bart Massey
# [This program is licensed under the "MIT License"]
# Please see the file LICENSE in the source
# distribution of this software for license terms.

# MIDI synthesizer in Python.

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

import argparse, array, math, mido, pyaudio, toml, sys

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
args = ap.parse_args()

# Parameters
# 
# Current master volume in linear units.
volume = 0.5
# Number of voices to play before compressing output volume
# to inhibit clipping.
compression = 5

# Parse a TOML keyboard map if given.
button_stop = None
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
    # Open the named MIDI keyboard.
    inport = mido.open_input(keyboard_name)
assert inport != None

# Sample rate.
rate = 48000

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

class Square(object):
    """Square VCO."""
    def __init__(self, f):
        """Make a new square generator."""
        self.tmod = rate / f
        self.half = self.tmod / 2.0

    def sample(self, t, tv = 0.0):
        """Return the next sample from this generator."""
        return 2.0 * int(((t + tv + self.tmod) % self.tmod) > self.half) - 1.0

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

# Current tracked volume.
volume_state = volume

def mix():
    """Accumulate a composite sample from the active generators."""
    global volume_state
    # Sample value to be output.
    s = 0
    # Number of samples output.
    n = 0
    for note in set(notemap):
        e = note.envelope()
        if e == None:
            # Release is complete. Get rid of the note.
            notemap.remove(note)
            continue
        s += e * note.sample()
        n += 1
    if n == 0:
        return 0
    volume_state = 0.01 * volume + 0.99 * volume_state
    gain = volume_state
    if n > compression:
        gain = volume_state * compression / n
    return (1 / compression) * gain * s

def callback(in_data, frame_count, time_info, status):
    """Supply frames to PortAudio."""
    # Frames of waveform.
    data = [clamp(int(32767.0 * mix()), 32767)
            for _ in range(frame_count)]
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
        note = Note(key, velocity, FM)
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
            print('exiting')
            for key in set(keymap):
                keymap[key].off(1.0)
                del keymap[key]
            notemap = set()
            break
        elif mesg.control == knob_volume:
            volume = 2.0 ** (mesg.value / 127.0) - 1.0
            print(f'volume change: {volume}')
        elif mesg.control in control_suppressed:
            pass
        else:
            print(f'unknown control {mesg.control}')
    else:
        print('unknown message', mesg)

# Done, clean up and exit.
stream.stop_stream()
stream.close()
