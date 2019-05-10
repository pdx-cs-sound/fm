#!/usr/bin/python3
# Copyright (c) 2019 Bart Massey

# Calculate a frequency from MIDI note information.

a4_note = 69  # Note number of 440 Hz A
a4_hz = 440  # Frequency of 440 Hz A

semitone = 2**(1/12)  # Ratio between semitones

def note_to_hz(note):
    return a4_hz * semitone**(note - a4_note)

# Unit tests.
if __name__ == '__main__':

    def equalish(x, y):
        return abs(x - y) <= 0.01

    assert a4_hz == note_to_hz(a4_note)
    assert equalish(27.5, note_to_hz(21))
    assert equalish(415.30, note_to_hz(68))
    assert equalish(4186.0, note_to_hz(108))

tuning_frac = 1 / (2**14)
# tuning_frac = 0.000061
# tuning_frac = 0.00006103

def pitch_to_hz(pitch):

    # Check inputs.
    no_change = True
    for i in range(3):
        assert pitch[i] & 0x80 == 0
        if pitch[i] != 0x7f:
            no_change = False
    if no_change:
        return None

    frac = pitch[2] + (pitch[1] << 7)
    return note_to_hz(pitch[0] + tuning_frac * frac)

# Unit tests.
if __name__ == '__main__':

    def equalish(x, y):
        return abs(x - y) <= 0.1

    def fromhex(x):
        bytes = [(x >> (8 * (2 - i))) & 0xff for i in range(3)]
        result = pitch_to_hz(bytearray(bytes))
        return result

    assert 440 == fromhex(0x450000)

    tests = [
        (0x000000, 8.1758),
        (0x000001, 8.2104),
        (0x010000, 8.6620),
        (0x0c0000, 16.3516),
        (0x3c0000, 261.6256),
        (0x3d0000, 277.1827),
        (0x447f7f, 439.9984),
        (0x450000, 440),
        (0x780000, 8372.0190),
        (0x780001, 8372.0630),
        (0x7f0000, 12543.8800),
        (0x7f0001, 12543.9200),
        (0x7f7f7e, 13289.7300),
    ]

    assert equalish(439.9984, fromhex(0x447f7f))
    assert equalish(12543.9200, fromhex(0x7f0001))
    assert equalish(13289.7300, fromhex(0x7f7f7e))
    assert None == fromhex(0x7f7f7f)

# Scale frequencies.
if __name__ == '__main__':
    for k in range(69, 69+13):
        print(k, note_to_hz(k))
