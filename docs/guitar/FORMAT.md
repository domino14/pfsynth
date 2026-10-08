# Guitar performance JSON

The browser guitar accepts `format: "pfsynth score 1"`. Existing files with note
`start` / `end` times in seconds keep working. The optional additions below are
compiled by `performance.js` before notes reach the instrument.

## Written time and rubato

With `timing.mode: "score"`, notes use quarter-note `beat` and `durationBeats`.
`timing.rubato` maps beats to seconds, with linear interpolation between anchors.
Both coordinates must increase strictly. Beats count through **performed order**,
including repeats; note `ids` can still point to the same written note on each pass.
Notation is engraved using its original rhythm; playback follows the timing map.

```json
{
  "format": "pfsynth score 1",
  "tuning": [64, 59, 55, 50, 45, 40],
  "timing": {
    "mode": "score",
    "rubato": [
      {"beat": 0, "seconds": 0},
      {"beat": 1, "seconds": 0.8},
      {"beat": 2, "seconds": 1.7}
    ],
    "tailSeconds": 3
  },
  "plucking": {
    "a": {"position": 0.19, "toneTiltDbPerOctave": -0.34},
    "m": {"position": 0.19, "toneTiltDbPerOctave": 0.38}
  },
  "notes": [
    {"beat": 0, "durationBeats": 1, "pitch": 64, "velocity": 80,
     "string": 1, "fret": 0, "finger": 0, "pluck": "a"},
    {"beat": 1, "durationBeats": 1, "pitch": 67, "velocity": 84,
     "string": 1, "fret": 3, "finger": 3, "pluck": "m"}
  ]
}
```

Optional `gateBeat` specifies a physical release independently of the written
length. It can end earlier for a hand shift or later for a ringing bass. A gate
at another note's beat follows that note's subdivided onset. `startOffset` is a
small additional offset in **seconds**, for example for a rolled chord.
`tailSeconds` defaults to 3. Cached `start`, `end` and top-level `duration` are
provided in the downloadable Recuerdos JSON for older clients, but score-mode
playback recomputes them: editing the timing map changes the sound.

For a repeating four-pluck pattern, `timing.subdivision` has `cycleBeats` and four
positive `ratios` adding to 1. They describe **gaps**: p→a, a→m, m→i, i→next p.
Only notes with `subdivide: true` use this warp; ornaments and independent
polyphony may opt out. `timing.minPluckGapSeconds` rejects cycles that would
violate the specified floor. The floor is a performance constraint, not a
universal physiological constant. Rubato changes cycle lengths while these
ratios stay regular; no random jitter is added automatically.

## The two hands

- `finger`: **left hand**, 0 open, 1 index through 4 little, -1 unspecified.
- `pluck`: **right hand**, `p` thumb, `i` index, `m` middle, `a` ring, `c` little.
- `plucking`: optional tone/position profiles keyed by right-hand letter.
- `pluckControls`: per-note overrides of the corresponding profile.

`position` is 0.04–0.45 of the speaking string length, measured from the bridge
(the instrument's optional fixed-hand setting further adjusts it for the fret).
`toneTiltDbPerOctave` is -2…2 dB/octave relative to the fundamental; the total
spectral change is capped at ±2 dB and normalized for predicted modal energy.
It changes radiation of string modes, not MIDI velocity. Omit these controls to
preserve the existing pluck sound. Letters alone are labels: there are no assumed
universal anatomical differences between fingers. Recuerdos uses modest measured
cycle-position slopes, a streaming approximation of the auditioned FIR correction.

Per-note `velocity` still drives pluck strength and the model's nonlinear response.
Zero is permitted for silent events in existing scores. `inferredFinger` in the
Recuerdos file records the tab solver's assignment; displayed source fingerings
remain separate. See its `SOURCE.txt` for the edition and hand-audit assumptions.

## Optional instrument settings and measured loading

`instrumentSettings` sets parameters by name when a piece loads. Recuerdos sets
`"Let strings ring": 0` because its explicit `gateBeat` values already describe
ringing and necessary hand releases. `body` selects the radiation response;
`defaultRoom` selects the room, for example `"dry"`.

`loadingProfiles` is an optional bank of 80-element arrays of additional modal
loss rates in 1/s (0…10); a note's zero-based `loadingProfile` selects one. These
are a passive diagonal approximation of bridge loading. The page disables the
piece's fitted loading when another body is selected. Radiation and room
convolution remain in Web Audio after the synthesis worklet.

The dedicated `pfguitar.wasm` uses the existing 48-byte `pf_note` ABI plus an
optional host-owned `pf_guitar_note_input` sidecar; it does not alter shared
`pfi.wasm`. Right-hand controls must be compiled by the JSON host; they are not
new fields in the generic C score reader. As before, seeking clears ringing tails
and resumes from subsequent events rather than reconstructing past audio.

Build with `bash tools/build_guitar_wasm.sh` (set `WASI_SDK` when needed). Check with
`node tools/test_guitar_web.mjs [previous-pfi.wasm]`; the optional reference checks
legacy guitar output bit for bit at 44.1 and 48 kHz. The full Recuerdos score is
rendered to check finite audio and that cached times match the timing inputs.
