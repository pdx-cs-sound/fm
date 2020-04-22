# fm: FM MIDI synthesizer demo in Python
Copyright (c) 2019 Bart Massey

This little cross-platform polyphonic synthesizer (about 200
lines of Python) is driven by a MIDI keyboard and outputs to
host native audio. It was built as a demo of FM synthesis
and synthesizer construction.

Here's a bit of what it sounds like:
[fm-demo.wav](https://raw.githubusercontent.com/pdx-cs-sound/fm/master/fm-demo.wav)

## Running

Prerequisites for this program are Python 3, PyAudio, and
Mido. Both `pyaudio` and `mido` can be installed using
`pip3`. Note that `mido` requires `python-rtmidi`: `rtmidi`
won't work.

To run the program, say "`python3 fm.py` *fmod* *amod*"
where *fmod* is the offset in Hz of the key carrier
frequency used for modulation frequency, and *amod* is the
modulation amplitude. A reasonable starting value is
"`python3 fm.py 3 40`" (which was used to produce the demo
above).

Note velocity modifies note volume; release modifies note
release time. A MIDI "panic" control message will turn off
the synthesizer and exit.

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

* The keyboard currently tries to listen for a MIDI keyboard
  connection, behaving as a MIDI output device. This may not
  work on Windows or Mac. A keyboard can be hardwire to the
  program, but uggh. A command line argument would be
  better.

* JACK is not supported.

* One-channel (mono) output.

## Future Work

* Generalize to flowgraphs with more operators: maybe start
  with a DX7-ish setup.

* Add better user controls.

* Read synth config from a file at startup.

* Add stereo.

## License

This program is licensed under the "MIT License".  Please
see the file `LICENSE` in the source distribution of this
software for license terms.
