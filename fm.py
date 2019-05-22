#!/usr/bin/python3
# Copyright (c) 2019 Bart Massey
# [This program is licensed under the "MIT License"]
# Please see the file LICENSE in the source
# distribution of this software for license terms.

# MIDI FM synthesizer in Python.

import mido
import sys
import numpy as np
import math
import pyaudio
import array

# Open an input port.
inport = mido.open_input('fm', virtual=True)
assert inport != None

# Addition to carrier pitch for mod pitch.
fmod = float(sys.argv[1])
# Amplitude of modulation.
amod = float(sys.argv[2])

# Sample rate.
rate = 48000

# Keymap contains currently-held notes for keys.
keymap = dict()

# Note map contains currently-playing operators.
notemap = set()

# Conversion factor for Hz to radians.
hz_to_rads = 2 * math.pi / rate

# Attack time in secs and samples for AR envelope.
t_attack = 0.010
s_attack = int(rate * t_attack)

# Release time in secs and samples for AR envelope.
t_release = 0.30
s_release = int(rate * t_release)

def note_to_freq(note):
    """Convert a note (pitch) to its corresponding frequency.
    Note 0 is A4 (440 Hz)."""
    return 440 * 2**((note - 69) / 12)

# Conversion table for keys to radian frequencies.
key_to_freq = [note_to_freq(key) for key in range(128)]

# Conversion table for keys to radian mod frequencies.
key_to_mod_freq = [key_to_freq[key] + fmod for key in range(128)]

class Op(object):
    """FM Operator"""
    def __init__(self, fcarrier, acarrier, fmod, amod):
        """Make a new FM operator."""
        self.wc = hz_to_rads * fcarrier
        self.ac = acarrier
        self.wm = hz_to_rads * fmod
        self.am = amod

    def sample(self, t):
        """Return the next sample from this operator."""
        m = self.am * math.sin(self.wm * t)
        return self.ac * math.sin(self.wc * (t + m))

class Key(object):
    def __init__(self, key):
        self.t = 0
        self.key = key
        self.release_time = None
        self.op = Op(key_to_freq[key], 1.0, key_to_mod_freq[key], amod)

    def off(self):
        """Note is turned off. Start release."""
        self.release_time = self.t

    def envelope(self):
        """Return the envelope for the given note at the given time.
        Returns None when note should be dropped."""
        t = self.t
        if self.release_time != None:
            rt = t - self.release_time
            if rt >= s_release:
                return None
            return 1.0 - rt / s_release
        if t < s_attack:
            return t / s_attack
        return 1.0

    def sample(self):
        """Return the next sample for this key."""
        sample = self.op.sample(self.t)
        self.t += 1
        return sample

def clamp(v, c):
    """Clamp a value v to +- c."""
    return min(max(v, -c), c)

def operate():
    """Accumulate a composite sample from the active operators."""
    # Sample to be output.
    s = 0
    for note in set(notemap):
        e = note.envelope()
        if e == None:
            # Release is complete. Get rid of the note.
            notemap.remove(note)
            continue
        s += e * note.sample()
    return 0.1 * s

def callback(in_data, frame_count, time_info, status):
    """Supply frames to PortAudio."""
    # Frames of waveform.
    data = [clamp(int(32767.0 * operate()), 32767)
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
    if mesg.type == 'note_on':
        key = mesg.note
        print('note on', key)
        assert key not in keymap
        note = Key(key)
        keymap[key] = note
        # XXX Exit synth when B5 and C5 are held together
        # and keyboard is near-silent.
        if 83 in keymap and 84 in keymap and len(notemap) == 1:
            break
        notemap.add(note)
    elif mesg.type == 'note_off':
        key = mesg.note
        print('note off', key)
        if key in keymap:
            keymap[key].off()
            del keymap[key]
    else:
        print('unknown message', mesg)

# Done, clean up and exit.
stream.stop_stream()
stream.close()
