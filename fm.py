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

# Connect to the keyboard. XXX Name hardwired for now.
inport = mido.open_input('Mobile Keys 49 MIDI 1')
assert inport != None

# Addition to carrier pitch for mod pitch.
kmod = float(sys.argv[1])
# Amplitude of modulation.
amod = float(sys.argv[2])

# Sample rate.
rate = 48000

# Keymap contains currently-held keys and their operators.
keymap = dict()

# Conversion factor for Hz to radians.
hz_to_rads = 2 * math.pi / rate

def note_to_freq(note):
    """Convert a note (pitch) to its corresponding frequency.
    Note 0 is A4 (440 Hz)."""
    return hz_to_rads * 440 * 2**((note - 69) / 12)

# Conversion table for keys to radian frequencies.
key_to_freq = [note_to_freq(key) for key in range(128)]

# Conversion table for keys to radian mod frequencies.
key_to_mod_freq = [note_to_freq(key + kmod) for key in range(128)]

class Op(object):
    """FM Operator"""
    def __init__(self, key):
        """Make a new operator for the given key."""
        self.t = 0
        self.key = key
        self.wc = key_to_freq[key]
        self.wm = key_to_mod_freq[key]

    def sample(self):
        """Get the next sample from this operator."""
        m = amod * math.sin(self.wm * self.t)
        result = math.sin(self.wc * (self.t + m))
        self.t += 1
        return result

def operate():
    """Accumulate a composite sample from the active operators."""
    # Sample to be output.
    s = 0
    keys = set(keymap)
    for key in keys:
        s += keymap[key].sample()
    return 0.5 * s / max(len(keys), 1)

def callback(in_data, frame_count, time_info, status):
    """Supply frames to PortAudio."""
    # Frames of waveform.
    data = [int(32767.0 * operate())
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
        keymap[key] = Op(key)
        # XXX Exit synth when B5 and C5 are held together.
        if 83 in keymap and 84 in keymap:
            break
    elif mesg.type == 'note_off':
        key = mesg.note
        print('note off', key)
        if key in keymap:
            del keymap[key]
    else:
        print('unknown message', mesg)

# Done, clean up and exit.
stream.stop_stream()
stream.close()
