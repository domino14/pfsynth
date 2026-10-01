# pfsynth

**Web demos:** https://olaugh.github.io/pfsynth/ — the partial-model piano as WebAssembly, playing (n)ASAP performances with Verovio score following (`docs/`).
https://olaugh.github.io/pfsynth/guitar/ — the physically modelled classical guitar, live in the browser: real performances (GAPS) with fitted dynamics, score and tab following, a fretboard view, measured guitar bodies; open your own MusicXML or MIDI (`docs/guitar/`).

**API:** [API.md](API.md) — one instrument-independent interface (score format, self-describing parameters, stereo render) for the piano and the guitar, in C, Python (ctypes) and WebAssembly. The existing piano interfaces are unchanged.

## License

pfsynth is released under the MIT License (see `LICENSE`).

Guitar demo data (`docs/guitar/`): performance timing and scores from GAPS (Riley, Guo, Edwards &
Dixon, ISMIR 2024; CC BY-NC-SA 4.0) with dynamics fitted by pfsynth — no recordings are included;
Stefan Apke's BWV 1006a arrangement (IMSLP, CC BY-SA 4.0); guitar body responses measured by
Robert Mores (Zenodo 4604577, CC BY 4.0).

Fitted parameter sets under `experiments/` were derived by measuring third-party sources, none
of which are redistributed here: the Salamander Grand Piano samples by Alexander Holm (CC BY 3.0)
and headless renders of Pianoteq 6 (Modartt), used as a black-box measurement target. Piece
lists and pedal statistics refer to MAESTRO v3 and ASAP/(n)ASAP performances (CC BY-NC-SA 4.0)
by path only; the MIDI and audio stay in their own datasets.
