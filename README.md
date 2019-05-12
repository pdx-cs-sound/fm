# fm: FM MIDI synthesizer demo in Python
Copyright (c) 2019 Bart Massey

This little cross-platform polyphonic synthesizer (about 150
lines of Python) is driven by a MIDI keyboard and outputs to
host native audio. It was built as a demo of FM synthesis
and synthesizer construction.

Here's a bit of what it sounds like: [fm-demo.wav](fm-demo.wav)

## Running

Prerequisites for this program are Python 3, PyAudio, and
Mido. Both `pyaudio` and `mido` can be installed using
`pip3`.

To run the program, say "`python3 fm.py` *fmod* *amod*"
where *fmod* is the offset in Hz of the key carrier
frequency used for modulation frequency, and *amod* is the
modulation amplitude. A reasonable starting value is
"`python3 fm.py 3 40`" (which was used to produce the demo
above).

To stop the program, press the B5 and C5 keys on the
musical keyboard (the topmost keys on a 49-key keyboard)
simultaneously.

## Limitations

* The FM synthesizer is a textbook 2-operator unit. More
  general operators and flowgraphs are planned.

* The envelope generator is currently a fixed linear
  attack-release (AR) envelope. This should be extended to
  full ADSR and made configurable. Seperate envelopes should
  be able to be applied to separate operators where this
  makes sense.

* The modulation parameters (frequency and amplitude) can be
  set only from the command line. Other MIDI messages should
  be supported, particularly pitch wheel, mod wheel, pan,
  volume, pedal and program change.

* Note velocity and release velocity are not supported.

* The keyboard currently auto-connects to "Mobile Keys 49
  MIDI 1". This should not be hardwired in software. Better
  would be to have the synth listen for a MIDI keyboard
  connection, behaving as a MIDI output device.

* JACK is not supported.

* One-channel (mono) output.

## Future Work

* Use note on and off velocities.

* Generalize to flowgraphs with more operators: maybe start
  with a DX7-ish setup.

* Add better user controls.

* Read synth config from a file at startup.

* Add stereo.

## License

This program is licensed under the "MIT License".  Please
see the file `LICENSE` in the source distribution of this
software for license terms.
