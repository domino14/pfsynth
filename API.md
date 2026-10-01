# pfsynth API

pfsynth's instruments share one interface: load a **score** (notes with start and end
times, plus optional strings, frets, techniques and pedal controls), set **parameters**
by name, and **render** stereo audio. The piano and the classical guitar implement it
today. Everything is portable C with no allocation inside the library (the host
provides memory), so the same code runs natively, in Python through ctypes, and in the
browser as WebAssembly.

Nothing existing changes: `pfplayer.h` (`pf_player_*`, used by the macOS app and
`pfrender`), the web demo's `pfw_*` exports and the core voices (`pf_partial`,
`pf_attack`, `pf_resonance`, `pf_pluck`) keep working as before. The piano behind
this interface is an adapter over `pf_player` and renders sample-identically to it
(`build/apitest`); the only rule it adds is an order for events at the very same
instant — releases, then pedal changes, then strikes — where MIDI files are inconsistent.

## Files

| File | What |
|---|---|
| `src/host/pf_score.h` | the score format (`pf_note`, `pf_control`, `pf_bend_point`, `pf_score`) |
| `src/host/pf_instrument.h` | the interface (`pf_instrument`, `pf_param_info`, `pf_sounding`), `pf_instrument_find`, `pf_param_find` |
| `src/host/pf_piano_instrument.c` | `pf_instrument_piano` (adapter over `pf_player`) |
| `src/host/pf_guitar.{h,c}` | `pf_instrument_guitar` (six `pf_pluck` strings) |
| `src/host/pf_score_io.{h,c}` | `pf_score_from_midi`: a parsed MIDI file → notes and pedal controls |
| `src/host/pfi.c` | flat functions for language bindings (`pfi_*`) |
| `src/host/pfiwasm.c` | WebAssembly exports (`pfiw_*`), built to `docs/pfi.wasm` by `tools/build_wasm.sh` |

## The score

A performance is a list of notes sorted by start, optional pedal controls and optional
pitch curves. Instruments read what they understand and ignore the rest.

| `pf_note` field | Type | Offset | Meaning |
|---|---|---|---|
| `start`, `end` | double | 0, 8 | seconds; `end` is when the player stops the sound (key up, string damped) |
| `pitch` | float | 16 | MIDI note number; fractions are cents. For a harmonic, the sounding pitch |
| `velocity` | float | 20 | MIDI scale, 1–127 nominal; above 127 where the model has headroom (fitted dynamics) |
| `art_param` | float | 24 | see articulations |
| `slide_to` | float | 28 | > 0: the note slides fret by fret to this pitch over its last 28% |
| `bend_first`, `bend_count` | int | 32, 36 | this note's points in `pf_score.bends` |
| `string`, `fret`, `finger` | int8 | 40, 41, 42 | −1 = not given: the instrument chooses |
| `articulation` | uint8 | 43 | `PF_ART_*` |
| `reserved` | int | 44 | 0 (48 bytes in all) |

| Articulation | Value | `art_param` |
|---|---|---|
| `PF_ART_NORMAL` | 0 | — |
| `PF_ART_HAMMER_ON` | 1 | finger clearance in m (0 = default) |
| `PF_ART_PULL_OFF` | 2 | pull distance in m (0 = default) |
| `PF_ART_SLIDE` | 3 | arrived by sliding: no pluck |
| `PF_ART_HARMONIC` | 4 | touched fret (12, 7, 5, 4) |
| `PF_ART_MUTED` | 5 | palm-muted |
| `PF_ART_TIE` | 6 | continues the previous note on its string |

`pf_control` (16 bytes: `t` double at 0, `value` float at 8, `kind` int at 12) carries
pedals: `PF_CTL_SUSTAIN`, `PF_CTL_SOSTENUTO`, `PF_CTL_SOFT`, value 0–1.
`pf_bend_point` (16 bytes: `t` double, seconds after the note's start; `semitones`
float) draws a pitch curve. The articulation says what made a curve: a bend is
continuous, a slide steps fret by fret. `pf_score.tuning` gives the open strings as MIDI
notes, string 1 first (NULL = standard EADGBE).

Pitch curves are kept in the score rather than in MIDI pitch bend: MIDI bend is per
channel and doesn't say whether a curve is a bend or a slide. One channel per string
plus pitch bend (or MPE) is still the right way to export curves to other synths.

## The instrument interface

```c
typedef struct {
    const char *id;                                     /* "piano", "guitar" */
    unsigned long (*size)(void);                        /* bytes of state */
    void   (*init)(void *self, double sample_rate);     /* parameters at defaults */
    int    (*param_count)(void);
    const pf_param_info *(*param_info)(int i);          /* name, unit, group, min, max, def, integer */
    double (*get)(const void *self, int i);
    void   (*set)(void *self, int i, double v);
    int    (*load)(void *self, const pf_score *score);  /* score must stay valid; 0 = ok */
    void   (*seek)(void *self, double t);
    int    (*render)(void *self, float *left, float *right, int frames); /* overwrites; right may be NULL */
    double (*time)(const void *self);
    int    (*sounding)(const void *self, pf_sounding *out, int max);   /* for displays */
} pf_instrument;
```

`pf_sounding` (16 bytes: `note_index` int, `pitch` float, `level` float 0–1,
`string` and `fret` int8) answers "what is sounding now" for both the piano's lit keys
and the guitar's vibrating strings.

### Example (C)

```c
#include "pf_instrument.h"
#include <stdlib.h>

const pf_instrument *gtr = pf_instrument_find("guitar");
void *g = malloc(gtr->size());
gtr->init(g, 48000);
gtr->set(g, pf_param_find(gtr, "Let strings ring"), 1);

pf_note notes[] = {   /* an E minor arpeggio; strings and frets left to the guitar */
    {.start = 0.0, .end = 0.4, .pitch = 40, .velocity = 90, .string = -1, .fret = -1, .finger = -1},
    {.start = 0.4, .end = 0.8, .pitch = 59, .velocity = 70, .string = -1, .fret = -1, .finger = -1},
    {.start = 0.8, .end = 1.2, .pitch = 64, .velocity = 80, .string = -1, .fret = -1, .finger = -1},
};
pf_score score = {.notes = notes, .n_notes = 3, .duration = 4};
gtr->load(g, &score);
float left[4096], right[4096];
gtr->render(g, left, right, 4096);   /* repeat until gtr->time(g) >= score.duration */
```

A MIDI file for the piano: `pf_midi_load` (midi.h), then `pf_score_from_midi` into
caller-provided note and control arrays, then `pf_instrument_piano.load`.

### The guitar

Six `pf_pluck` strings (modal, energy-stable nonlinear, measured nylon materials) with:
- **plucks** at a chosen position;
- **hammer-ons and pull-offs** that re-shape the vibrating string instead of plucking;
- **natural harmonics** from a finger touching the string over a contact width, fitted to recorded harmonics;
- **palm muting**;
- **bends and slides** from the pitch curves;
- **strings ringing** until a hand would stop them. That happens when the string is played again, when the fretting finger is needed elsewhere or out of reach, or when a clashing note arrives after the written length.

When a score gives no strings, as from plain MIDI, the guitar chooses them with a search over hand positions. The output is the strings' bridge force. Hosts apply the guitar body and room by convolution (the web demo uses the measured bodies), as `tools/stringlab_page.py` and the demo page do. It matches the offline Python renderer sample for sample (`tools/test_instrument_api.py`).

## Parameters

### piano

| # | Name | Unit | Group | Range | Default |
|---|---|---|---|---|---|
| 0 | Output gain | x | Output | 0 … 16 | 4 |
| 1 | Tone | 0 Salamander-fitted, 1 Pianoteq-fitted | Tone | 0 … 1 | 1 |
| 2 | Onset | 1 = soundboard thump and noise | Onset | 0 … 1 | 1 |
| 3 | Pedal mode | 0 switch, 1 continuous damper | Pedals | 0 … 1 | 1 |
| 4 | Una corda | 1 = soft pedal shifts the hammer | Pedals | 0 … 1 | 1 |
| 5 | Body | dB | Onset | -40 … 12 | -18 |
| 6 | Knock | dB | Onset | -40 … 12 | -22 |
| 7 | Noise | dB | Onset | -40 … 12 | -17 |
| 8 | Treble onset | dB | Onset | -24 … 12 | 0 |
| 9 | Top knock decay | x | Onset | 0.05 … 3 | 0.25 |
| 10 | Top knock level | dB | Onset | -24 … 12 | 0 |
| 11 | Top knock from | x fundamental | Onset | 0.1 … 1 | 0.5 |
| 12 | Limiter | 1 = lookahead peak limiter | Output | 0 … 1 | 1 |
| 13 | Sympathetic resonance | 1 = on | Resonance | 0 … 1 | 1 |
| 14 | Resonance level | dB | Resonance | -24 … 12 | 0 |

### guitar

| # | Name | Unit | Group | Range | Default |
|---|---|---|---|---|---|
| 0 | Output gain | dB | Output | -60 … 60 | 0 |
| 1 | Treble strings | 1 nylon, 2 carbon | Strings | 1 … 2 | 1 |
| 2 | Pluck position | fraction of the vibrating length | Right hand | 0.04 … 0.45 | 0.19 |
| 3 | Hand stays put | 1 = pluck point fixed on the string (high notes rounder) | Right hand | 0 … 1 | 0 |
| 4 | Let strings ring | 1 = until a hand would stop them; 0 = at each note's end | Left hand | 0 … 1 | 1 |
| 5 | Velocity headroom | x MIDI 127 | Right hand | 1 … 4 | 4 |
| 6 | Slur contact time | ms | Left hand | 0.1 … 3 | 0.5 |
| 7 | Hammer-on clearance | mm | Left hand | 0 … 3 | 0.7 |
| 8 | Pull-off distance | mm | Left hand | 0 … 3 | 0.6 |
| 9 | Harmonic touch width | mm | Harmonics | 0 … 60 | 29.25 |
| 10 | Harmonic touch damping | 1/s | Harmonics | 0 … 2000 | 424 |
| 11 | Harmonic touch time | ms | Harmonics | 5 … 300 | 60 |
| 12 | Harmonic touch offset | mm from the node | Harmonics | 0 … 8 | 2 |
| 13 | Harmonic pluck position | fraction | Harmonics | 0.04 … 0.45 | 0.12 |
| 14 | Palm-mute damping | 1/s | Right hand | 0 … 200 | 25 |

## Bindings

**Flat C (`pfi.c`)**, for ctypes and the like: `n = pfi_size("guitar")`; allocate n
bytes; `pfi_init(mem, "guitar", sr)`; `pfi_param_count / name / unit / group / min /
max / default / integer / find`, `pfi_get / pfi_set`, `pfi_load(mem, &score)`,
`pfi_seek`, `pfi_render(mem, left, right, frames)`, `pfi_time`, `pfi_sounding`.
`tools/test_instrument_api.py` shows the ctypes structures.

**WebAssembly (`docs/pfi.wasm`, `pfiw_*`)**: one instrument at a time in static memory.
`pfiw_init(0 piano | 1 guitar, sampleRate)`; parameters as above (`pfiw_param_name(i)`
returns a pointer to a C string); write notes into `pfiw_notes()` (48-byte records),
controls into `pfiw_controls()`, bends into `pfiw_bends()`, the tuning into
`pfiw_tuning()`, then `pfiw_load(n_notes, n_controls, n_bends, n_strings, duration)`;
`pfiw_render(frames)` fills `pfiw_left()` / `pfiw_right()`; `pfiw_seek`, `pfiw_time`,
`pfiw_sounding()` with `pfiw_sounding_buffer()`. Record sizes are exported
(`pfiw_note_size` etc.) so pages can check the layout. `docs/guitar/guitar-worklet.js` is a
complete AudioWorklet host.

## Score files

`docs/guitar/import.js` reads **MusicXML** and **MIDI** in the browser:
- **From MusicXML:** strings and frets from a tab staff or `<technical>`, repeats unrolled, ties merged, slurs between consecutive notes on one string as hammer-ons and pull-offs, harmonics, dynamics marks as velocity, arpeggio marks as rolls, the tempo map.
- **From MIDI:** strings when a file uses one channel per string.

The demo's performances are stored as **pfsynth score JSON** (`format: "pfsynth score 1"`): the
notes as above plus the ids of their notehead and tab number in the accompanying
MusicXML, the tuning, and the fitted room and body. Guitar Pro files are read by the
offline tools (PyGuitarPro, versions 3–5); newer ones via MusicXML export. TuxGuitar
exports MusicXML and MIDI.
