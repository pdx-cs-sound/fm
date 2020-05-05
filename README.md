# fm: Fun MIDI synthesizer demo in Python
Copyright (c) 2019 Bart Massey

This little cross-platform polyphonic synthesizer (a few
hundred lines of Python) is driven by a MIDI keyboard and
outputs to host native audio. It was built as a demo of FM
synthesis and synthesizer construction, but now includes
more general additive synth functions.

Here's a bit of what it sounds like as an FM synth
out-of-the-box:
[fm-demo.wav](https://raw.githubusercontent.com/pdx-cs-sound/fm/master/fm-demo.wav)

## Running

Prerequisites for this program are Python 3, PyAudio, and
Mido. Both `pyaudio` and `mido` can be installed using
`pip3`. Note that `mido` requires `python-rtmidi`: `rtmidi`
won't work.

To run the program, say `python3 fm.py`. If you want to
connect to a named keyboard (found by `aconnect -o` on
Linux) say `python3 fm.py -k` _keyboard_.

Note velocity modifies note volume; release modifies note
release time. A MIDI "panic" control message will turn off
the synthesizer and exit.

## Limitations

* There is currently no flowgraph, which severely limits
  what can be done without modifying the source code.

* The envelope generator is currently a fixed linear
  attack-release (AR) envelope. This should be extended to
  full ADSR and made configurable. Seperate envelopes should
  be able to be applied to separate operators where this
  makes sense.

* FM and its frequency and amplitude can be set only by
  editing the source. Other MIDI messages should be
  supported, particularly pitch wheel, mod wheel, pan,
  volume, pedal and program change.

* The keyboard by default currently tries to listen for a
  MIDI keyboard connection, behaving as a MIDI output
  device. This may not work on Windows or Mac. An optional
  command line argument can override this, though.

* JACK is not supported.

* One-channel (mono) output.

## Future Work

* Implement flowgraph setup.

* Add better user controls.

* Read synth config from a file at startup.

* Add stereo.

## License

This program is licensed under the "MIT License".  Please
see the file `LICENSE` in the source distribution of this
software for license terms.
