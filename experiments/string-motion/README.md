# Experiment 05: piano frequency motion, plucked guitar, bowed violin

Built 2026-09-30. Six level-matched musical comparisons live in
`build/stringlab/index.html`; serve that directory over HTTP. The existing
production piano, patches, app, and earlier audition files are unchanged.

## Piano

`pf_motion` adds an opt-in exponentially decaying fractional-frequency offset
to the existing partial oscillators, without changing their amplitude envelopes.
Four C-note anchors, C2–C5, and velocities 48/100 supply eight initial offsets and
eight decay times. Values interpolate in pitch and velocity; outlying registers
use the nearest anchor. Negative measured motion is clamped to zero for the
tension-modulation hypothesis. This is a fitted approximation, **not** the
DAFx26 nonlinear solver or a hammer-contact simulation. It adds no phantom
partials. High-partial shifts currently share the same fractional offset, rather
than explicitly recalculating tension against stiffness.

`tools/motion_measure.py` analyzes cached Pianoteq 6 Steinway D Close Mic
Classical notes. Complex demodulation and weighted phase regression separate a
constant frequency error from a transient frequency offset. It searches five
decay times and rejects poorly supported partials. The late constant-frequency
fit is not used to retune the production patch. Phase motion can also come from
unison interference; causality is not established. Some soft notes and the upper
register fail the acceptance threshold and therefore receive zero motion.

Qualified A-note holdouts have mean absolute motion-prediction error 1.38 cents
with zero motion and 0.97 cents with the interpolated table. This small, selected
phase metric is **not evidence of a perceptual improvement**. Details and
source hashes are in `measurement.json` and `holdout.json`.

The experiment harness compiles the original player implementation with only
its partial-processing call routed through the motion overlay. This keeps the
same onset, continuous pedals, una corda, voice management, and sympathetic bank.
Zero motion matches the production Beethoven render exactly after PCM conversion.
This host-only harness is static and not reentrant; it does not change the app ABI.

* Beethoven Op. 2 No. 1: current piano / measured motion / cached Pianoteq reference.
* Exposed A1/A2/A3/A4: current piano / measured motion / 4× motion diagnostic.
  Velocity 75 is also absent from the motion training table. These notes are held
  out from **motion** fitting, not from the existing full-keyboard tonal patch.

## Guitar

`pf_pluck` is a modal, nylon-like plucked string with a triangular initial
displacement. A Kirchhoff–Carrier quartic potential changes the tension with
string displacement. A scalar auxiliary variable (SAV), trapezoidal update and
Sherman–Morrison rank-one inverse give an explicit O(N) update. The unforced
discrete energy is bounded; damping dissipates it. Trapezoidal frequency prewarp
reduces high-mode numerical pitch error.

This adapts the numerical idea from Ducceschi, Russo & Webb,
[Measurement-Informed Nonlinear Modal Synthesis of 65 Classical Guitars,
DAFx26](https://dafx26.mit.edu/assets/papers/DAFx26_paper_40.pdf), using a simpler
potential. It does not reproduce their geometrically exact model, measured
bridge compliance, radiation data, or interior bridge coupling. Their
[companion repository](https://github.com/Nemus-Project/65_modelled_guitars)
currently exposes samples; no solver code was imported.

`pf_radiation` supplies eight designed body resonances. These are analytic
prototype parameters, not measured/ERA-fitted guitar parameters. Pitch varies
through tension at fixed length; a full fretboard, string-specific materials,
finger contact, longitudinal modes and fret buzz remain absent. Both A/B versions
use identical body filters. The third version removes the body for diagnosis.
The fingerpicked study and soft/hard notes are original event lists.

## Violin

`pf_bow` sustains a string with two travelling-wave segments joined by a nonlinear
bow friction table. The analytic friction curve and architecture follow the
classic approach described by Smith / McIntyre, Schumacher & Woodhouse and
[STK Bowed (Perry Cook and Gary Scavone)](https://github.com/thestk/stk/blob/master/src/Bowed.cpp).
This is an independent compact C prototype, not a new violin-paper reproduction.
Frequency compensation accounts for the bridge loss filter's low-frequency delay.
The expressive variant adds delayed 5.3 Hz vibrato and a small bow-speed variation;
pitch transitions reuse the string state. Both variants use the same designed body
filter. The third version removes that filter. The melody and detached-note study
are original.

Not included: measured violin modes, bidirectional body mobility, thermal or
elasto-plastic rosin friction, bow-hair compliance, a player's finger model, or
validated acoustic-instrument matching. No ERA fitting is claimed. All instrument
candidates are sample-free; the piano's separate comparison reference is audio.

## Reproduce and judge

```sh
build/body-venv/bin/python tools/motion_measure.py
build/body-venv/bin/python tools/stringlab_audition.py
build/body-venv/bin/python tools/stringlab_page.py
build/body-venv/bin/python -m http.server 8765 --bind 127.0.0.1 --directory build/stringlab
```

The C kernels depend only on math/string and use no dynamic allocation. Host tools
use numpy/scipy and the installed MP3 encoder. The generator checks finite output,
block equivalence, plucked-string energy dissipation, and exact zero-motion piano
bypass; output WAVs are level matched and peak checked before MP3 encoding. Build
hashes, checks, PCM levels and identities are recorded in `audition-report.json`.
Saved judgments and stable randomized A/B mappings use their own browser storage
key, separate from previous auditions, and can be exported. Blind mode hides the
description's A/B identities too. Playback starts only when the listener presses Play.

Piano MIDI attribution: ASAP/(n)ASAP KimG01, CC BY-NC-SA 4.0. Synthesized/cropped
Beethoven excerpts use that license. Pianoteq references are existing renders
from the user's licensed installation; no Pianoteq internals or weights are used.

Listen before promoting any candidate into the production piano. The initial
motion effect is deliberately small in Beethoven. The 4× diagnostic is there to
identify the effect, not to claim a better piano.
