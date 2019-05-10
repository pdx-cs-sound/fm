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

# Current carrier frequency, for silence detection.
fcarrier = None

# Current tick in current waveform.
t = 0

def op():
    """FM operator. (Technically two operators.)"""
    global t
    # Don't call this while silenced.
    assert fcarrier != None
    # Carrier frequency in radians.
    wc = 2 * math.pi * fcarrier / rate
    # Mod frequency in radians.
    wm = 2 * math.pi * fcarrier * qmod / rate
    # Next sample.
    result = 0.5 * math.sin(wc * (t + amod * math.sin(wm * t)))
    # Advance tick.
    t += 1
    return result

def callback(in_data, frame_count, time_info, status):
    """Supply frames to PortAudio."""
    if fcarrier == None:
        # Frames of silence.
        data = [0]*frame_count
    else:
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

# Keymap is True for currently-held keys.
keymap = [False] * 128
# Key of current note.
cur_on = None
# Process key events and modify the PA play freq.
while True:
    mesg = inport.receive()
    if mesg.type == 'note_on':
        keymap[mesg.note] = True
        # XXX Exit synth when B5 and C5 are held together.
        if keymap[83] and keymap[84]:
            break
        print('key on', mesg.note)
        # Start a new note even if already held (same key).
        cur_on = mesg.note
        # Set carrier frequency based on key.
        fcarrier = 440 * 2**((mesg.note - 69) / 12)
    elif mesg.type == 'note_off':
        print('key off', mesg.note)
        keymap[mesg.note] = False
        # Don't clear current note on legato.
        if cur_on != mesg.note:
            continue
        # Silence the synth.
        cur_on = None
        fcarrier = None

# Done, clean up and exit.
stream.stop_stream()
stream.close()
