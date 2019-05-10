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

# Multiplier to carrier frequency for mod frequency.
qmod = float(sys.argv[1])
# Amplitude of modulation.
amod = float(sys.argv[2])

# Sample rate.
rate = 48000

# Keymap contains currently-held keys.
keymap = set()

# Current tick in current waveform.
t = 0

# Conversion factor for Hz to radians.
hz_to_rads = 2 * math.pi / rate

# Conversion table for keys to Hz.
key_to_hz = [440 * 2**((key - 69) / 12)
             for key in range(128)]

def op():
    """FM operator. (Technically two operators.)"""
    global t
    # Sample to be output.
    s = 0
    keys = set(keymap)
    for key in keys:
        # Set carrier frequency based on key.
        fcarrier = key_to_hz[key]
        # Carrier frequency in radians.
        wc = fcarrier * hz_to_rads
        # Mod frequency in radians.
        wm = qmod * wc
        # Next sample.
        s += math.sin(wc * (t + amod * math.sin(wm * t)))
    # Advance tick.
    t += 1
    return 0.5 * s / max(len(keys), 1)

def callback(in_data, frame_count, time_info, status):
    """Supply frames to PortAudio."""
    # Zero tick on every silence.
    if len(keymap) == 0:
        global t
        t = 0
    # Frames of waveform.
    data = [int(32767.0 * op())
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
        print('note on', mesg.note)
        keymap.add(mesg.note)
        # XXX Exit synth when B5 and C5 are held together.
        if 83 in keymap and 84 in keymap:
            break
    elif mesg.type == 'note_off':
        print('note off', mesg.note)
        if mesg.note in keymap:
            keymap.remove(mesg.note)
    else:
        print('unknown message', mesg)

# Done, clean up and exit.
stream.stop_stream()
stream.close()
