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
t_release = 0.10
s_release = int(rate * t_release)

def note_to_freq(key):
    """Convert a key number to its corresponding frequency.
    Key 69 is A4 (440 Hz)."""
    return 440 * 2**((key - 69) / 12)

# Conversion table for keys to radian frequencies.
key_to_freq = [note_to_freq(key) for key in range(128)]

class Saw(object):
    """Sawtooth generator"""
    def __init__(self, f, a):
        """Make a new sawtooth operator."""
        self.tmod = rate / f
        self.a = a

    def sample(self, t):
        """Return the next sample from this generator."""
        return self.a * ((t % self.tmod) / self.tmod)

class Key(object):
    def __init__(self, key, velocity):
        self.t = 0
        self.key = key
        self.release_time = None
        self.release_length = None
        self.op = Saw(key_to_freq[key], velocity)

    def off(self, velocity):
        """Note is turned off. Start release."""
        self.release_time = self.t
        self.release_length = s_release / velocity

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
    mesg_type = mesg.type
    if mesg_type == 'note_on' and mesg.velocity == 0:
        mesg_type = 'note_off'
    if mesg_type == 'note_on':
        key = mesg.note
        velocity = (mesg.velocity + 23) / 150
        print('note on', key, round(velocity, 2))
        assert key not in keymap
        note = Key(key, velocity)
        keymap[key] = note
        notemap.add(note)
    elif mesg_type == 'note_off':
        key = mesg.note
        velocity = (mesg.velocity + 23) / 150
        print('note off', key, round(velocity, 2))
        if key in keymap:
            keymap[key].off(velocity)
            del keymap[key]
    elif (mesg.type == 'control_change') and (mesg.control == 123):
        print('panic: exiting')
        for key in set(keymap):
            keymap[key].off(1.0)
            del keymap[key]
        notemap = set()
        break
    elif (mesg.type == 'control_change') and (mesg.control == 10):
        pass
    else:
        print('unknown message', mesg)

# Done, clean up and exit.
stream.stop_stream()
stream.close()
