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

Prerequisites for this program are Python 3, PyAudio, Mido
and TOML. `pyaudio` and `mido` and `toml` can be installed
using `pip3`. Note that `mido` requires `python-rtmidi`:
`rtmidi` won't work.

To run the program, say `python3 fm.py`. If you want to
connect to a named keyboard (found by `aconnect -o` on
Linux) say `python3 fm.py -k` _keyboard_. If you want to use
a [TOML](https://en.wikipedia.org/wiki/TOML) keyboard
configuration file say `python3 fm.py -K` _conffile_.
Example keyboard configurations are provided for the M-Audio
Oxygen 8 and Line 6 Mobile Keys 49.

Note velocity modifies note volume; release velocity
modifies note release time. A MIDI "panic" control message
will turn off the synthesizer and exit.

## Status

* [x] The keyboard by default currently tries to listen for a
  MIDI keyboard connection, behaving as a MIDI output
  device. This may not work on Windows or Mac. Add a config
  file to use a particular keyboard and its controllers.

* [x] Add volume knob support.

* [ ] FM frequency and amplitude can be set only by editing
  the source. Other MIDI messages should be supported,
  particularly pitch wheel, mod wheel, sustain pedal. In
  short, full MIDI controls.

* [ ] Extend the fixed linear attack-release (AR) envelope,
  to full ADSR and make configurable. Seperate envelopes
  should be able to be applied to separate operators where
  this makes sense.

* [ ] Add a VCF.

* [ ] Add a flowgraph for general configuration, with
  its own config file.

* [ ] Better multiple simultaneous controller support via
  MIDI channels.

* [ ] Support JACK MIDI (?).

* [ ] Stereo.

## Notes

The choice of TOML is as a least-common-denominator config
file that is actually usable. Here's a nice explanation of
why I
[didn't choose JSON](https://www.lucidchart.com/techblog/2018/07/16/why-json-isnt-a-good-configuration-language/).

This largeish single-file program is not generally best
software engineering practice. However, it does make this
synth much easier to distribute and deploy; also, if it gets
way too big for one file that's a good sign that it needs to
be simplified.

## License

This program is licensed under the "MIT License".  Please
see the file `LICENSE` in the source distribution of this
software for license terms.
