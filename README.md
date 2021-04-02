# fm: Fun MIDI synthesizer demo in Python
Copyright (c) 2019 Bart Massey

Fun MIDI (FM) is a little cross-platform polyphonic
synthesizer (a few hundred lines of Python). FM is driven by
a MIDI keyboard and outputs to host native audio. FM was
originally built as a demo of Frequency Modulation (also FM)
synthesis and synthesizer construction, but now includes
more general synthesis.

Here's a bit of what it sounds like as an FM synth
out-of-the-box:
[fm-demo.wav](https://raw.githubusercontent.com/pdx-cs-sound/fm/master/fm-demo.wav)

## Running

Prerequisites for this program are Python 3, PyAudio, Mido,
NumPy and TOML. `pyaudio`, `mido`, `numpy` and `toml` can be
installed using `pip3`. Note that `mido` requires
`python-rtmidi`: `rtmidi` won't work, so make sure it is not
installed. Then you can install the remaining dependencies
with

    pip3 install -r requirements.txt

To run the program, say `python3 fm.py`.

### MIDI Keyboard

By default the synth will wait to be connected to a keyboard
manually. On Linux you can use `aconnect`; don't know about
Windows or Mac.

If you want to use a
[TOML](https://en.wikipedia.org/wiki/TOML) keyboard
configuration file say `python3 fm.py -K` _conffile_.
Example keyboard configurations are provided for the M-Audio
Oxygen 8 and Line 6 Mobile Keys 49.

If you just want to connect to a named keyboard (found by
`aconnect -o` on Linux) say `python3 fm.py -k` _keyboard_.

### Sounds

A small selection of sounds can be chosen from the command line.

* `--sine`, `--square`, `--saw`, `--tri`: Simple wave generators

* `--fm <fmod> <dmod>`: Single FM operator. *fmod* is the
  difference between the key frequency and the modulation
  frequency. *dmod* is the modulation depth (amplitude).

  If no sound argument is given on the command line, the
  synth defaults to FM with reasonably pleasing default
  parameters.

* `--wave <wavefile>`: Very crude sampling synthesis. The
  wave file must be a 48000 sample-per-second single-channel
  integer (8, 16 or 24 bit) `.wav`. The entire file will be
  treated as a loop. The envelope will be derived from the
  built-in envelope generator.

  A couple of sample wave files have been included to get
  started:

  * `voice-long.wav`: The author singing something vaguely
    like a 440 A

  * `car-horn.wav`: The author's car horn

### Tuning

[Five-limit Just intonation](https://en.wikipedia.org/wiki/Just_intonation#Five-limit_tuning)
can be chosen using `--just BASE`. The `BASE` argument is
the scale base in half-steps above A.

[Three-limit Just intonation](https://en.wikipedia.org/wiki/Just_intonation#Five-limit_tuning)
can be chosen using `--pyth BASE`. The `BASE` argument is
the scale base in half-steps above A. The Pythagorean comma
between 4♯/5♭ is split close to the mean ratio
(1055729/373248, about 1.41425:1), at a ratio of `sqrt(2):1`
(1.41421:1). (Yes, this is a poke at Pythagoreans, who never
would have done that. Sue me.)

## Status

* [x] The keyboard by default tried to listen for a MIDI
  keyboard connection, behaving as a MIDI output
  device. This may not work on Windows or Mac, and is
  inconvenient. Added a command-line keyboard argument and a
  config file to use a particular keyboard and its
  controllers.

* [x] Added volume knob support.

* [x] Sound generators and their parameters could be set
  only by editing the source. Added command-line generator
  argument handling.

* [x] Support alternate tunings.

* [ ] Support other MIDI control messages, particularly
  pitch wheel, mod wheel, sustain pedal. In short, provide
  reasonably full MIDI controls. *(In progress.)*

* [ ] Extend the fixed linear attack-release (AR) envelope,
  to full ADSR and make configurable. Seperate envelopes
  should be able to be applied to separate operators where
  this makes sense.

* [ ] Add a VCF.

* [ ] Add a synthesizer config file to set sound parameters,
  control mappings and program assignments.

* [ ] Allow synthesizer config to have a flowgraph to
  combine generators.

* [ ] Provide better multiple simultaneous controller
  support via MIDI channels.

* [ ] Support JACK MIDI (?).

* [ ] Do stereo.

## Notes

Note velocity modifies note volume; release velocity
modifies note release time. A MIDI "panic" control message
will turn off the synthesizer and exit.

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
