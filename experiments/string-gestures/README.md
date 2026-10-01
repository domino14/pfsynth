# Gesture and note-character audition

Built 2026-09-30. Adds five comparisons to the existing local listening room:

* GOAT example 1: notes/string identity versus imported gestures; third version
  adds controlled variation.
* GOAT note character: gestures held constant, fixed versus varying pluck
  character; third version is a second seed.
* Wohlfahrt étude 8: performed timing with steady pitch versus imported pitch
  contours; third version adds controlled bow variation.
* Wohlfahrt bow character: contours held constant, fixed versus varying bow
  character; third version is a second seed.
* Wohlfahrt steady bow: no vibrato or pitch contour in any version; fixed versus
  varying attack/tone; third version is another steady take.

All comparisons are level matched and use the existing blind A/B, synchronized
switching and saved judgments. A/B identities are randomized per clip. Third
versions are **synth alternatives**, not acoustic reference recordings. Earlier
audio and saved judgments remain intact.

## Imported data

Guitar input is GOAT's public `example1.gp5`, pinned in `research/strings`.
The imported file says **77 BPM**, while its text companion says 80; this
adapter follows the GP5 version consistently. Leading silence is removed and
the first 33 seconds retained, with one second of release tail. There are 55
logical notes after merging ties. Beat positions and velocities are retained.
String/fret assignments are from the source, not inferred. Bend graph horizontal
positions are normalized using PyGuitarPro's 12-position scale. Vertical units
are converted from 25 units in the raw GP bend graph per model unit, with 100
raw units denoting a whole tone: a parsed value of 4 becomes two semitones.

Hammer-on/pull-off annotations link the following note on the same string.
They preserve state, retune it, and add a small finger-excitation displacement;
this is a designed approximation, not measured finger contact. Legato slides
preserve state and cross discrete frets over the final 28% of the source note.
The source gives slide type and destination, not a measured trajectory. Slide
timing is therefore an explicit rendering choice. Source ties retain the string
without another pluck. Full tablature, including later notes, remains on disk.

Violin input is
`Wohlfahrt_Op45-08_BernardChevalier_b_OfyqFc_kI-0000-0080.mid` from Tamer's
Violin MIDI Dataset. Leading silence is removed. Nineteen notes beginning
within the first 27 seconds are retained through the last selected note's
release, plus one second of tail. MIDI timing and note velocities are retained.
Imported bends stay attached to their original MIDI channel and note. The
[authors' pitch-estimator code](https://github.com/MTG/violin-transcription/blob/17e198cad1f355c566a26a6d58ee0559fd198ffa/musc/pitch_estimator.py)
uses `bends * 4096 / 100` for cents-to-MIDI conversion: 4096 units per semitone,
equivalent to the usual ±2-semitone bend range. The adapter reverses this scale
and interpolates the dense contour on a 128-frame synthesis control grid.
It adds no automatic vibrato and no random pitch drift.

Violin fingering is **inferred**, not supplied by the dataset. The current
constraint search preserves note durations and requires distinct strings for
simultaneously held notes. It retains held finger assignments and checks
pairwise physical reach, barre conflicts and position-change speed. String
numbers are G/D/A/E as 0/1/2/3. Four retained waveguide states represent these
strings. Note durations do not identify shared bows or portamento, so no such
labels are fabricated. The hand limits are designed adult-hand assumptions,
not measurements of a particular player or a guarantee of comfort.

## Physical and performance changes

New guitar APIs are opt-in. Six designed string masses/open tunings and shorter
speaking lengths replace the fixed-length/pitch-dependent-tension assumption
in these clips. Frequency-dependent modal loss and stiffness are designed
parameters, not fitted string measurements. Moving boundaries update modal
coefficients and re-anchor the auxiliary potential without clearing state.
This is not the full nonlinear moving-contact solver; the static SAV energy
guarantee does not establish conservation during boundary motion. Modes near
Nyquist fade out rather than being audibly aliased. Nut/fret compliance,
fret collisions and coupled longitudinal motion remain absent.

New controlled bow APIs vary contact fraction, friction-curve scale, attack
time and speed. String-dependent bridge-loss cutoffs and a small open/stopped
neck-loss difference are designed approximations. Finger compliance is not
physically modeled. Speed drifts slowly around the intended gesture; individual
notes vary slightly in contact/attack/friction without requiring vibrato.

Guitar variation: pluck position ±0.012 of speaking length, excitation scale
±3.5%. Violin variation: contact ±0.009, friction scale ±0.16 around 3, attack
±15 ms around 55 ms, speed ±4.5%, plus a slow ±1.8% speed motion. Seeds 7201
and 9031 produce reproducible alternative takes. These ranges are audition
choices, not learned statistics of performers. MIDI note timing is unchanged.
Body filters are the same designed prototypes used in the earlier experiment.

## Outputs and validation

`guitar-goat-events.json` and `violin-wohlfahrt-events.json` retain string,
articulation and continuous-pitch information. The listening folder also has
`guitar-goat-gestures.mid` and `violin-wohlfahrt-gestures.mid`, with explicit
RPN ±12-semitone ranges and approximately 200-Hz bend messages. Guitar uses
one channel per string; violin preserves original channels to avoid overwriting
overlapping note contours. Standard MIDI alone does not encode our hammer
excitation or inferred finger assignment; the event JSON is authoritative.

`report.json` records source/kernel hashes, checks and all audio levels.
Full excerpts are finite and bounded; seeded re-renders match exactly. Imported
gestures and variation each change the output. Exported MIDI reopens with the
expected note counts and nonzero bends. Existing kernel tests still pass for
finite output, block equivalence, and plucked-string static energy decay.
Level matching, duration, audible-signal occupancy and page JavaScript syntax
were checked. These checks do not establish acoustic realism.

Rebuild after creating the original listening set:

```sh
build/body-venv/bin/python tools/string_gesture_audition.py
build/body-venv/bin/python tools/stringlab_page.py
```

Host dependencies: the existing numpy/scipy environment plus mido 1.3.3 and
PyGuitarPro 0.11. Portable kernels still depend only on math/string. The piano
production path is unchanged. Data sources and rights notes are recorded in
`research/strings/README.md`; these outputs are local research auditions.

## Classical repertoire and real performance pairs (September 30)

`tools/classical_string_audition.py` adds Carcassi Op.60 No.1 (first 24 bars)
and Bach BWV1002 Corrente (24 bars plus pickup), from Mutopia public-domain
MIDI editions. `tools/string_hand_geometry.py` searches finger/string choices
then independently audits pitch, overlaps, four-finger reach and shift speed.
It uses 650 mm guitar / 328 mm violin scale lengths, designed pairwise reach
limits and index-only guitar barres. MIDI durations are retained. The Corrente
contains a three-note chord at 11.8 seconds requiring a rolled bow; the current
renderer sustains its notes simultaneously. Passing the left-hand audit does
not certify the bow interpretation. No player-specific biomechanical claim.

`tools/paired_string_audition.py` adds real Bach Prelude performances:

* Guitar: Mateusz Kowalski, BWV1006a, GAPS official demo `tw1wc`, 18 seconds.
  Published fine-aligned MIDI, audio, MusicXML source tablature and downbeat
  syncpoints are retained under `research/strings/midi/gaps/`. The audition
  tab is newly inferred and audited, not claimed to be the performer's choices.
  The first MIDI onset (2.502 s in source audio) defines the crop origin.
  A longer 29-second inference failed the hand constraints at 19.886 s;
  the 18-second excerpt passes without modifying note durations inside it.
* Violin: Karen Gomyo, BWV1006 Prelude, Bach Violin Dataset / Isabella Stewart
  Gardner Museum, 28 seconds. A MIDI excerpt is derived from the published
  note CSV and estimated start/end alignment CSV, cropped at first onset
  (0.576 s in source audio). This is estimated score alignment, not direct
  instrument-captured MIDI. It supplies no measured vibrato/bow controls.

The real recordings are cropped, downmixed, resampled to 44.1 kHz, level
matched, and faded over the final 80 ms for local comparison. The two synth
versions follow the same event times: fixed character and bounded variation.
The final boundary clips note tails in all versions. MIDI export timing is
quantized to 1/1920 second; download companion JSON retains exact event times.
Score graphics are timed transcriptions, not complete engraved editions.

Rights: GAPS permits noncommercial research and forbids redistribution without
written permission: https://aim-qmul.github.io/GAPS/ . Gomyo audio and derived
alignments are CC BY-NC-ND 4.0, attributed to Isabella Stewart Gardner Museum:
https://hermandong.com/bach-violin-dataset/download.html . Keep these pairs local;
they are not cleared for public hosting or commercial training.

Rebuild order: gesture adapter, classical adapter, paired-performance adapter,
then `tools/stringlab_page.py`. Reports and manifest contain hand audits,
source hashes, audio level checks, crop offsets and alignment provenance.

### IMSLP printed score

Stefan Apke's 2018 guitar edition, IMSLP #554880, CC BY-SA 4.0, is retained
under `research/strings/scores/` and linked from the listening room. Its PDF
page 7 (printed page 6) supplies the first 11 printed measures. The page was
rendered with Poppler; inspected measure regions are displayed above the tab
with shared downbeat boundaries and measure highlighting. Within-measure
printed spacing is not note timing. Horizontal stretching and cropping are
local display adaptations; attribution and source/license links are preserved.
Printed edition fingers are distinct from inferred renderer finger choices.
`tools/string_score_alignment.py` attaches the alignment and hashes the source.
The paired-performance rebuild retains this attachment when the assets exist.

### Guitar material/body ablations

Five additional Bach comparisons are built by `tools/guitar_material_audition.py`.
See `research/strings/GUITAR_SOUND.md` for sources, assumptions and the full
coupled-model implementation direction. Measured material values are opt-in;
the original string processing path remains unchanged. New static material
notes avoid redundant SAV re-anchoring when only the host block boundary changes.
Both new material modes render identically across 128/511-frame blocks, and
36 material/string/fret energy tests remain bounded. Audition files are finite
and level matched. No subjective sound-quality win is claimed before listening.

### Printed score, a whole system at a time (September 30, later)

The Kowalski clips now show Apke's printed page one **whole system at a time at its
natural proportions** (no cropping into measures, no stretching), with every tab number
placed directly under its own printed notehead. Pipeline:

1. `tools/score_geometry.py` (needs pdfminer: Homebrew `python3.14`) reads the IMSLP
   PDF's vectors: 9 staves, barlines, 323 noteheads (MuseScore glyph U+E12D, exact
   origins), 174 fingering digits, and placement hints (barre numerals and their dashed
   lines belong to the staff below, dynamics to the staff above). Output:
   `research/strings/scores/apke-bwv1006a-page7-geometry.json`.
2. **ClefScan** (`~/sources/sep23-omr`, `scripts/recognize_ir_page.py`, commit e1d1a34 with
   local changes) recognized the noteheads on the 1556×2200 page render in 70 s:
   323/323 found, 2 false positives (both in measures 19–21, outside the excerpt),
   F1 0.997. Saved as `apke-bwv1006a-page7-clefscan.json`. ClefScan is a piano OMR: it
   has no guitar 8vb clef, tablature, circled string numbers or left-hand guitar
   fingering, so only head positions and staff steps are used from it.
3. `tools/string_score_alignment.py` identifies ClefScan's heads against the MusicXML
   staff part, measure by measure: onsets in tick order take heads in x order, and every
   staff step must agree. Measures 1–12 match exactly; from measure 13 the GAPS MusicXML
   has extra notes that are not on Apke's page (13 vs 18 heads etc.), so those measures
   are reported, not forced. All 127 excerpt notes get a ClefScan head; the PDF vectors
   confirm each one (median 1.4 px, max 2.2 px on the 1556-px page). 93 of 97 MusicXML
   finger marks equal the printed digit beside the head; the other 4 are MusicXML
   open-string 0s with no printed digit.
4. Each system is cut from a 2× render as its own image. Connected ink components
   touching a staff (or reaching into its ledger zone) seed that system; floating marks
   join the nearest system's ink, closest pairs first, after the edition hints. So
   dynamics, fingerings, barre lines and ledger-line bass notes appear only with their own
   system. Frames share one height so the tab does not jump between systems.
5. The page interpolates a playhead between performed onsets (time → printed x), so
   it moves unevenly where Kowalski's timing departs from engraved spacing. Click a
   printed note or tab number to seek. **Wide score** hides the example list so a whole
   system fits a laptop screen (remembered per browser). The old timed tab/staff view
   remains under **Timeline**.

Tests: `build/body-venv/bin/python tools/test_string_score_alignment.py`.

### Dynamics fitted from the recording (September 30, later)

The GAPS MIDI gives all 1,736 notes velocity 100. `tools/guitar_dynamics_fit.py` fits a
velocity per note to Kowalski's recording by analysis-by-synthesis:

* Each note is rendered **alone** with the exact audition model (string, fret, timing,
  release; cut where a same-string onset re-plucks; body applied after the cut). The
  sum of these renders reproduces the full render (spectrogram residual 3.5e-4), so the
  templates are the model, not an approximation of it.
* Fitting target: positive band-magnitude **flux** (1/6-octave bands, 70 Hz–7 kHz, 35 ms
  lag), i.e. what each onset adds. A first fit on plain magnitudes let the model's
  too-slow tails "explain" soft notes (m5 fell 25–30 dB); flux is insensitive to how
  tails decay. KL divergence, onset-weighted; one gain per note, plus a **global per-band
  timbre correction** and floor as nuisance terms so tone mismatch is not read as
  dynamics. The correction is never applied to audio. Templates are re-rendered at the
  current estimate (3 rounds), because the tension nonlinearity makes level not exactly
  proportional to velocity.
* Weakly identified notes (onset share < 0.3: 25 of 127, mostly soft notes under
  ringing strings) shrink toward the local trend of well-identified neighbours; no note
  strays more than ±9 dB from that trend. Raw and final values are both in the report.
* Contrast calibration: one exponent on the fitted deviations, chosen so the rendered
  200-ms loudness envelope best follows the recording's: **0.5** (raw contrast halved;
  reverb masks soft onsets). The median note stays at velocity 100, the same typical
  pluck amplitude as the constant version. Louder notes use an opt-in path above MIDI 127
  (`render_guitar(..., velocity_cap=4)`; default behaviour byte-identical), so the
  string's tension nonlinearity follows the dynamics. Final range 48–200 (≈15 dB).

Model choice by fitted residual (weighted KL): **Gil de Avalle body + loading 0.886**,
designed body 0.901, DeVoe 0.920. The nuisance correction for the chosen model says the
recording's onsets carry ≈+12 dB more at 70–200 Hz than the model, −5.5 dB at
0.5–1.5 kHz, −8 dB at 4–7 kHz: our plucks are thin in the bass and too bright, the
clearest next model target (body low end, pluck position, nail/flesh contact).

Checks (in-sample, same recording): loudness-envelope error vs the recording 4.95 dB
constant, 4.96 dB random variation, **3.13 dB fitted**; per-note onset loudness
correlation 0.09 / 0.09 / **0.68**. The edition's dynamics were not used, yet the
fitted measure trend follows its echo markings: m1 +5.9 dB, m5 (*p*) −6.1, m7 (*f*) −1.0 → m8
+4.6, m11 (*p*) −0.9 (median note = 0). Renders are finite, block-size invariant
(128/511), decay monotonically for the loudest note, and are level matched within
0.005 dB. These are relative pluck strengths under this model, not measured finger
force; per-note tone colour (pluck position, nail versus flesh) is not fitted.

Clips: `guitar-bach-dynamics` (constant velocity vs fitted) and `guitar-bach-character`
(the earlier seeded random variation vs fitted), both on the chosen model without
random variation, with Kowalski's recording third. The fitted-level lane under the tab
shows each note's level at its printed note. Downloads: fitted-velocity MIDI (rescaled so
the loudest is 127; ratios kept) and exact velocities JSON. Report:
`guitar-dynamics-report.json`.

Rebuild order for the Bach guitar clips: `paired_string_audition.py` →
`guitar_material_audition.py` → `guitar_dynamics_fit.py --write` (≈2 min; without
`--write` it only fits and previews) → `stringlab_page.py`. Re-running
`string_score_alignment.py` alone is safe: it keeps per-clip fitted velocities.

### Hammer-ons: a test case (September 30, later)

The GAPS MusicXML has no slurs; Apke's printed page has six in the excerpt, all ligado
between consecutive notes on one string with different fingers (hammer-ons bars 2, 8, 8;
pull-offs bars 4, 6, 10). `score_geometry.py` now records the PDF's slur curves and
`string_score_alignment.py` maps each to its note pair (`edition_slur` on the second
note). By the user's choice, the edition's hammer-ons are **assumed** played as slurs
(Kowalski's articulation is unverified; a Vidović video seemed to show bar 2 plucked).

New opt-in kernel call `pf_pluck_legato` (`src/core/pf_pluck.c`), replacing the earlier
placeholder kick for these clips only (GOAT clips unchanged):
* The ringing string is re-expanded on the new speaking length (bridge end fixed; DST on
  a 512-point grid). A same-pitch, zero-strength call changes the output by 2.6e-4.
* Hammer-on: the finger slams the string onto the fret, a boundary jump of the fret
  clearance (designed ~0.5–1 mm) low-passed by the fingertip contact time (0.5 ms).
  Single polarization made the slam cancel or double the carried vibration by chance
  (7–13 dB); the slam is scaled so energies add as two orthogonal polarizations would,
  leaving ±1.5 dB. Exposed hammer-ons at 0.7 mm sit 4.7–5.8 dB below a pluck (the
  carried vibration alone 7–8.5 dB below); darker than a pluck.
* Pull-off: a sideways left-hand pluck at the old fret on the lengthened string, close
  to its new end, so brighter than a pluck. In-plane with plucks, so no energy
  correction: interference with the ringing note is genuine but its sign is arbitrary.
  Exposed pull-offs at 0.6 mm sit 3.5–4.9 dB below a pluck.
* A slurred note's predecessor keeps the string fretted across the 7–32 ms gap the
  aligned MIDI leaves between them (no damper).

Clips (`tools/guitar_legato_audition.py`, report `guitar-legato-report.json`):
`guitar-bach-hammer` (now *slurs in context*: fitted dynamics, all plucked vs. all six edition
slurs — three hammer-ons and three pull-offs, each level-matched as below; originally hammer-ons only;
each hammer's clearance chosen so the slurred pair alone matches the plucked pair's
level within 0.4 dB: 0.89, ≈0 and 2.31 mm — at bar 8's first slur the still-ringing
string is already as loud as the fitted pluck) and `guitar-hammer-exposed` (now *exposed
slurs*: three slow hammer-on pairs at a fixed 0.7 mm, then two pull-off pairs at 0.6 mm;
plucked vs slurred, third button the earlier placeholder).
`guitar-bach-slurs` adds the edition's three pull-offs on top of the hammer-ons (A =
hammer-ons only, so one change per comparison; pulls calibrated the same way: 1.26,
1.37, 1.63 mm, within 0.3 dB; the versions are identical until 6.153 s, where the first
pull-off's source note would have been damped) and `guitar-pulloff-exposed` (two slow
pairs at a fixed 0.6 mm). These two now duplicate parts of the updated clips above; the
Bach one still isolates the pull-offs (A = hammer-ons only). Arcs marked **HO** / **PO** in the tab show rendered slurs. No real slur recording is
available to fit or verify against; parameters are designed.

Run after `guitar_dynamics_fit.py --write`, then `string_score_alignment.py` and
`stringlab_page.py`.

### Natural harmonics (September 30, later)

New opt-in kernel call `pf_pluck_touch(s, position, rho)` (`src/core/pf_pluck.c`): the
left finger lightly touching the string is a point dashpot coupling every mode through
its shape at the touch point, solved implicitly with the SAV term (Sherman–Morrison).
Modes with a node under the finger ring on; the rest drain. `rho = 2R/(μL)` (1/s);
`rho = 0` lifts the finger and the original arithmetic runs unchanged (bit-identical,
tested). `render_guitar` accepts `touch=dict(position, rho, lift)` and `pluck_position`
per note.

**Calibration** (`tools/guitar_harmonics.py`, report `guitar-harmonics-report.json`):
36 recorded natural harmonics, all electric guitars — Guitar-TECHS (24, frets 5/7/4/12 on
all strings, CC BY 4.0, read from the local archive) and IDMT-SMT-Guitar (12, frets 4
and 7, Stratocaster, CC BY-NC-ND 4.0, copied to `research/strings/downloads/idmt-smt-guitar/`
for local use only). Measure: the open-string fundamental's level minus the harmonic
partial's, at 15 ms–0.5 s, relative to 5 ms after the onset — a per-partial change over
time, so pickup/microphone colouring cancels. Real harmonics (medians per fret): the
fundamental drains 13–28 dB in the first 30 ms, then settles 35–45 dB below where it started. Grid fit
(open nylon strings, plucked at 0.12, no body): **rho = 424 /s** (finger resistance ≈ a
third of the string impedance — a light touch), **lift after 50 ms**, **2 mm placement
error** from the node; mean error 3.8 dB. Players find the node rather than the fret wire
(for fret 4 the wire is 4 mm off and recorded 4th-fret harmonics are nearly as pure),
so the touch is placed at the node. Remaining misfit: the model drains the fret-7
fundamental faster than recorded in the first 30 ms, and its fret-4 harmonic stays ~10 dB
leakier (one lift time for all nodes). Steel electric strings, not nylon: the finger's
damping rate is assumed to carry over.

**Clips:**
* `guitar-harmonics-exposed` — the open D string touched over frets 5, 7, 4 and 12 at the
  timing of the Guitar-TECHS take; ordinary plucked notes at the sounding pitches vs
  touched harmonics; third button the real (electric, miked-amp) recording.
* `guitar-capricho-harmonics` — Tárrega, *Capricho Árabe* bars 1–8 from the Mutopia
  edition (`research/strings/scores/mutopia/`, CC BY-SA 4.0), score timing at 90 bpm.
  Bars 1 and 5's fret-7 harmonic chord on strings 6 (in D), 5 and 4 sounds A3/E4/A4; the
  Mutopia MIDI plays the touched-fret pitches (A2/E3/A3) and is converted. Ordinary notes
  vs harmonics; third button the same strings plucked open without the touch. Touching
  lowers the open fundamentals by 45–54 dB and keeps the harmonic pitches. Other strings
  and frets inferred with the scordatura tuning (`infer(..., tuning=...)`, new optional
  argument). The 6th string in D is modelled as a longer string at E-string tension.
* Known effect: the measured body's resistive loading drains partials near its ~220 Hz
  resonance at 8–10 /s, so the 6th string's A3 harmonic dies within about a second. A
  real body resonance does this too, but the weak-coupling approximation (clipped at
  10 /s) may exaggerate it.

Tests: `tools/test_string_physics.py` (legato re-expansion, hammer/pull pitch and decay,
touch-off identity, 12th-fret selection). No nylon harmonic recording has been measured.

### A harmonic in a real performance: Morel, Sonatina III (October 1)

GAPS (`-D1wc`, Inon Međugorac, alignment f-measure 0.97) supplies MusicXML with strings
and frets, fine-aligned MIDI and downbeats; files in `research/strings/midi/gaps/sonatina3/`
(see `SOURCE.txt`). GAPS does not distribute audio: at the user's request the recording
was fetched from YouTube with yt-dlp using the user's own Chrome cookies (anonymous
requests were blocked by YouTube's PO-token check) and is kept local. The GAPS MIDI fits
it as-is (onset cross-correlation lag −10 ms; 79% of MIDI onsets within 50 ms of an
audible onset).

Importer changes (`guitar_edition_fingering.py`, Kowalski import verified unchanged): the
tuning is read from the TAB staff (this piece is in drop D), notes written twice in two
voices (same beat, pitch, string, fret: 118 here) are collapsed, tied continuations are
skipped (no new onset), and the text direction preceding a note is kept (`score_words`).

`tools/guitar_sonatina_audition.py`, clip `guitar-sonatina-harmonics`: the first 18 s
(bars 0–16). Bar 11 ends on a 12th-fret natural harmonic on the D string ("Harm XII";
the TAB writes fret 12, which is also the sounding D4). Velocities are fitted to the
recording (new reusable `fit_dynamics` in `guitar_dynamics_fit.py`; contrast exponent
0.5; loudness-envelope error 4.12 dB constant → 3.58 dB fitted). A frets the note at
12, B plays the open string touched at its midpoint with the calibrated finger; the
third button is the recording. The tab marks the note `<12>`.

At the harmonic (0.03–0.45 s after its onset), relative to D4: the recording's D5
(second partial of the harmonic) is +0.5 dB, ours −10 dB — our harmonic is too dull
(pluck nearer the bridge or a brighter nail attack would raise it). The recording's
D3 is −18.6 dB vs −60 dB in B, but in drop D the low string's second partial is that
D3 and real players let basses ring while our renderer damps each note at its MIDI
end, so this is not evidence of finger leakage. The score gives strings/frets and some
fingers (40 of 108 notes) but no complete left hand, so no hand audit is run.
GAPS terms: noncommercial research, no redistribution.

### Listening room: real performances only, and every measured body (October 1)

The listening room now lists only examples whose third button is a real performance of
the same piece (Kowalski's Bach clips, Gomyo's violin Bach, Međugorac's Sonatina III);
diagnostics and synth-only studies remain on `debug.html`, and any clip still opens by
URL (`?clip=`).

**Body menu** (`tools/guitar_body_choice.py`; Bach *dynamics from the recording* and the
Sonatina): besides "as rendered" (Gil de Avalle with bridge damping), the listener can
pick the bare string, the designed body, or any of the measured guitars in Robert
Mores's set (CC BY 4.0; `research/strings/body/guitars.json` lists maker, year, place,
style and woods as spelled in his list). 63 of 65 are offered: g07 (Aaron Garcia, closed
side hole) and g30 (Jose Ramirez, 1986) have no usable data (NaN) in the archive. Each
clip ships its two versions' string signals before any body (no bridge loading) and
each body as a 0.15 s impulse response (`bodies/`, 1.9 MB); the page convolves them in
real time (WebAudio ConvolverNode, unnormalized) and switches without stopping. Per body
and version a gain matches the level-matched recording; one headroom factor per clip
(0.92 Bach, 0.96 Sonatina) keeps every body below full scale, applied to the recording
too. Only radiation changes with the choice — body-specific bridge damping is not
modelled in this mode — and the measured responses include some room (g34–g44 were
measured anechoically). The choice is remembered per clip in the browser.

**Update — the whole Sonatina (October 1).** `guitar-sonatina-harmonics` now covers the
whole performance (203.4 s, 1,231 notes, harmonics at bars 11, 35, 142 and 166). The score
has one repeat (bars 39–62, first ending 61–62, second 63); `measure_order` unfolds it,
and since the export closes the first ending a bar early, a backward-repeat bar right after
a first ending is treated as part of it (Međugorac skips bar 62 on the repeat; onset counts
then match exactly, 1,231). The whole GAPS score (170 bars) is engraved with Verovio
(`tools/score_engrave.py`, ClefScan's pinned build), one system per SVG; notes are matched
by measure, onset order and written pitch (all 170 measures, all 1,231 notes), and a
repeated passage revisits its system (21 systems, 25 visits). Dynamics are fitted window by
window (`fit_dynamics_long`: 24 s windows with 4 s of context, templates normalized within
each window, absolute pluck strengths compared across windows): contrast exponent 0.6;
whole-piece loudness-envelope error 8.56 dB constant → 8.20 dB fitted (the recording ends in
applause the synth cannot match, and no room is modelled).

### The room is load-bearing for the velocity fit (October 1)

The renders are dry; the recordings were made with microphones in rooms. The measured
body responses keep only ~0.1 s of their rooms, so effectively no reverberation reaches
the synth. Earlier velocity fits showed the symptoms: the raw contrast had to be halved
(exponent 0.5), soft notes after loud ones collapsed (bar 5 fitted 25–30 dB down), and
the per-band "timbre correction" was large.

`tools/guitar_room_fit.py` fits the room together with the velocities: each note's
template (rendered alone) passes through a statistical room in the band-power domain —
direct sound plus an exponentially decaying tail per band (RT60 interpolated between
200 Hz and 4 kHz, reverberant/direct energy ratio, 12 ms pre-delay) — and power gains are
fitted with a β = 0.5 divergence (band powers add across notes, unlike the onset-flux
representation, whose decaying tails cancel part of a later note's attack). Grid search
over the room on Kowalski's excerpt (`guitar-room-fit-report.json`, refined in
`guitar-room-fit-refined.json`):

* loss 0.887 dry → **0.626** with RT60 2.7 s at 200 Hz falling to 1.2 s at 4 kHz and a
  reverberant/direct ratio of 1.0 (a live showroom; the bass RT60 is at the grid edge and
  may partly compensate for model strings that decay too fast);
* the timbre correction shrinks from +12 / −5.5 / −8 dB (low / mid / high) to
  +4 / −1 / −7 dB — part of the old "tone mismatch" was room;
* **hypothesis test** — rendering the room-fitted velocities through the fitted room
  (`room_impulse`: direct impulse + octave-band noise tails), the contrast exponent that
  best matches the recording's loudness envelope is **0.85 (≈ 1)**, not 0.5: the room was
  what squashed the contrast. Loudness-envelope error vs the recording: constant velocity
  dry 4.95 dB, room alone 5.26, earlier flux fit dry 3.13, **room-aware fit + room 1.93**.
* still to do: the room-fit velocities need the identifiability shrinkage (a few notes
  go to zero), and the clips' B versions have not yet been re-rendered with them.

Međugorac's recording (Sonatina, first 24 s, `guitar-room-fit-sonatina.json`) tells the
same story: loss 0.762 dry → 0.572 with RT60 3.8 s at 200 Hz, 0.84 s at 4 kHz, ratio 1.0;
best contrast exponent with the room 0.85 again; loudness-envelope error 3.58 dB (flux fit,
dry) → 1.98 dB (room-aware fit + room). **Caveat:** in both fits the 200 Hz RT60 ends at
the grid edge. Our renderer damps every note at its MIDI note-off while players let bass
strings ring, so the low-frequency "room" probably absorbs missing string ringing; treat
the bass RT60 as an upper bound, not a property of the room.

**Room menu** (`tools/guitar_room_choice.py`): every real-performance guitar clip offers
Dry (default, as rendered) or a room fitted to a recording (Kowalski's or Međugorac's), convolved in the browser
after the body, on the synth versions only; per-clip gains keep levels matched.

**Re-rendered with room-aware velocities (October 1).** `tools/guitar_room_dynamics.py`
refits the Bach excerpt with Kowalski's fitted room (`fit_room_dynamics`: band power,
templates through the room, β = 0.5, the usual identifiability shrinkage and ±9 dB limit)
and re-renders the B versions of *dynamics from the recording* and *fitted versus random
variation*; the slur clips (built on these velocities) were recalibrated and re-rendered.
With the room applied the contrast exponent is **1.00** — no squashing — and the
loudness-envelope error (room applied) is 2.62 dB fitted vs 5.26 dB constant (the
unregularized fit reached ≈2.0; shrinkage keeps every note audible). Measure medians:
m1 +6.1, m5 −4.5, m8 +3.6, m11 −5.2 dB. After the refit, bar 8's two hammer-ons sit
1.8–2.2 dB above their (now softer) plucked levels even with no slam: the still-ringing
string alone is that loud. The Sonatina is refitted the same way with Međugorac's room,
window by window (`fit_room_dynamics_long`, 18 s windows, 6 s context for the reverb).
The audio files stay dry; choose the matching room in the Room menu to hear them as fitted.

**Closest body per piece (October 1).** `guitar_body_choice.py` now ranks every body for
each piece: the fitted (B) string signal through each body and the room fitted to that
recording, compared with the recording's long-term 1/6-octave spectrum after one overall
gain (RMS dB; frame-by-frame log-spectral distance as a cross-check). The best match is
that clip's default body; the menu lists the eight closest first (★ = best).

* Bach / Kowalski: g27 Do Santos DS120SG650 3.62 dB, g28 Mundo Flamenco 2015 4.01,
  g49 Enrique Garcia 1913 4.09 … g05 Gil de Avalle (used so far) rank 20 (5.26), designed
  body rank 33 (5.62), bare string rank 56 (7.02).
* Sonatina / Međugorac: g54 Josef Pages 1806 (early romantic) 3.16 dB, g40 Faustino Conde
  1964 3.43, g33 Antonio Lorca 3.80 … g05 rank 24 (4.47), designed 27, bare string 32.

The leaders sit within ~0.5 dB and the frame-level distance barely separates them, so the
ranking is a guide, not an identification: it also absorbs the string model's own
colouring (an 1806 guitar "matching" a modern performance probably says more about our
too-bright plucks than about Međugorac's instrument). Sonatina headroom is 0.64 because
some bodies peak higher. The whole-piece Sonatina was refitted with Međugorac's room:
contrast exponent 1.0, loudness-envelope error (room applied) 6.65 dB constant → 5.91 dB
fitted (dry fit before: 8.56 → 8.20).

### Strums: what the recordings actually do (October 1)

The GAPS fine-aligned MIDI is, note for note, the GAPS transcription model's onsets: the
released model (`xavriley/midi-transcription-models`, `guitar-gaps.pth`, MIT; run locally
from `build/amt-venv` with `hf_midi_transcription`) transcribes Međugorac's recording
to 1,230 notes against GAPS's 1,231, onsets within 2.5 ms median (95th percentile 7 ms);
Kowalski's to 1,773 against 1,736 (2.7 / 8.9 ms). So chord notes in GAPS are not bucketed
by the score: the fine stage moved each to its own activation, and the chords checked
(13.1, 37.65, 12.5, 170.66 s) are played within 1–15 ms — together, not rolled. Two
detectors of our own (`tools/onset_refine.py`, partial-tracking; `tools/strum_fit.py`,
analysis-by-synthesis) made chord timing *worse* on an independent band check
(`strum-fit-guitar-sonatina-harmonics.json`) and were not applied. The arpeggiated final
chord is the exception: GAPS has five identical onsets because its score alignment put
the chord **0.65 s late**, where nothing is played (no pluck clicks; the >2.5 kHz band is
quieter there than before). The transcription finds the real chord earlier as an
**upward strum**: D3 −713, D4 −641, F♯4 −609, D5 −585 ms relative to the GAPS time, with
pluck clicks at −703 and −565 ms; D2's fundamental jumps ~20 dB at the same moment
(re-plucked; not detected by the model, placed 20 ms before D3). The user heard the strum
in the recording and its absence in ours. (An earlier note here, from activations read
only at the GAPS time, wrongly said it was played together.) `guitar_sonatina_audition.py`
now re-times arpeggio-marked chords from the transcription (`strum_from_transcription`:
densest cluster of the chord's pitches within 250 ms, misses filled in string order).
The other GAPS notes the transcription does not confirm (inner-voice notes at 2.8, 67.8,
68.1, 68.7, 160.6 s) look like misses, not misalignments, and are left. The model's
guitar velocities are a constant 100 (no dynamics). Transcriptions:
`research/strings/midi/gaps/*-amt.mid`.

Score view (October 1): hairpins are not engraved; three-voice bars (76–83, 120–127, an
inner voice doubling the arpeggio) hide their filler rests; each repeat pass dims the
measures it does not play (first pass: second ending and continuation; second pass: the
first ending; a jump back to bar 39: the bars before it on that system).

### Harmonics fitted to real harmonics (October 1)

Complaint: the harmonics sounded like fretted notes. Physics says why: with a point finger
at the node, the surviving modes of a 12th-fret harmonic have exactly the relative
strengths of the fretted octave plucked at the same spot, so only the decay and the onset
differ. Measured (`tools/harmonic_measure.py`, `harmonic-measure-report.json`,
`harmonic-agpt-pairs.json`): each real harmonic against an ordinary note at the same
sounding pitch on the same string, player, guitar and intensity. **AG-PT-set** (CC BY 4.0;
7 steel-string guitars, 6 players, 116 pairs at frets 12/7 — fetched file by file with
range requests, `tools/agpt_fetch.py`): partial 2 −4 dB, **partials 3–10 −14 to −27 dB**,
upper partials decay 8–22 dB/s slower, the >4 kHz click relative to partial 1 ~10 dB lower,
the touched string's other modes at −44 dB. **Philharmonia** classical-guitar samples
(CC BY-SA 3.0, 29 pairs, sounding-pitch labels, string unknown): the same direction but
weaker (partials 6–10 −6 to −16 dB; partials 2–3 +4 dB).

**Right-hand position.** The same AG-PT data (2,100 ordinary notes, frets 0–20) shows the
pluck comb moving across partials with the fret as for a hand fixed at **0.19 of the open
string from the bridge** (fret-pattern correlation peaks sharply there, r = 0.32; 0.01 at
0.14). Our renderer plucks every note at 0.19 of its *vibrating* length, so high-position
notes are plucked too near the bridge (too bright). Used for the harmonic fit's ordinary
reference; not yet applied to ordinary notes in the clips.

**Finger of finite width** (`pf_pluck_touch_width`, opt-in; width 0 is bit-identical): a
fingertip damps over a few millimetres, rho × the mode shape squared averaged over the
contact; the point dashpot keeps what a point sees and the remainder goes on the diagonal,
rho/4·cos(2πkx0)·(1 − sinc(πkw)) per mode — growing as k²w² for modes with a node under
the finger. `tools/harmonic_fit.py` (`harmonic-fit-report.json`) fits width, damping, lift
time and placement to both datasets' contrasts: **19.5 mm effective width, 424 /s, 2 mm off
the node, lifted after 40 ms, plucked at the hand's point**. Contrast error AG-PT 26.1 →
11.3, Philharmonia 16.7 → 14.2. The width is an effective value (a real light touch is
nearer 8–12 mm); it also stands in for what the model lacks — e.g. a fretted note's
faster decay (real harmonics outlast fretted notes at the same frequency by more than ours
do: the longer open string loses energy to the bridge more slowly).

Clips (`tools/guitar_harmonics_refit.py`): new **guitar-harmonics-nylon** — six 12th-fret
harmonics, strings 6→1: A the earlier point finger, B the fitted finger, third the real
Philharmonia harmonics (each note level-matched). Directly against the real ones (medians):
partials 3–8 re partial 1 — real −20/−19/−36/−47/−40/−57, fitted −25/−23/−36/−31/−38/−55,
earlier −16/−36/−24/−20/−27/−36 dB; click (>4 kHz, first 40 ms, re partial 1) real −69.5,
fitted −61.4, earlier −54.7 dB. Still off: partial 2 too weak (−15 vs −3 dB) and the model
decays faster (partials 1–3 −19/−16/−18 vs −15/−12/−10 dB/s). The Sonatina's four harmonics,
the exposed-harmonics and Capricho debug clips were re-rendered with the fitted finger.

**Exaggerated for show (October 1, user request).** The user found the fitted harmonic not
different enough, then asked for "louder yet more harmonic finger-touch timbre". Measured
against the four real Sonatina harmonics (g54 body, levels re the 1.5 s before each), the
fitted render had the overall level right but the octave partial (D5) 4 dB weak and the
fundamental 4 dB strong; Međugorac's harmonics have the octave above the fundamental.
Plucking nearer the bridge (0.12 of the string) with a 1.5× finger (29 mm effective
contact, 60 ms touch) gives D4 −5.8 / D5 −7.4 dB (recording −10.2 / −7.8) and keeps the
upper partials down; the four Sonatina harmonics are then plucked 1.6× harder than fitted
(velocities 143–186 → 229–298), about +6.5 dB above the recording's level relative to
their context. `harmonic-fit-report.json` keeps both `finger` (fitted) and `exaggerated`
(`finger_used`); the nylon comparison clip now plays fitted (A) against exaggerated (B).
At the higher velocity the tension nonlinearity starts the harmonic 4–8 cents sharp,
settling within half a second.

### Performance videos (October 1): Sonatina III and the Bach Prelude

Scripts generalised to `tools/piece_video_audio.py <piece>` and `tools/piece_video.py
--piece <piece>`; titles, bodies, rooms and credits per piece in `tools/video_pieces.py`.
The audio script renders the fitted performance string by
string (sum = the usual render to 6e-8), through the g54 body response and a stereo
version of Međugorac's fitted room (two noise seeds, shared direct sound), peak −1 dBFS,
and saves each string's envelope at 30 fps. `tools/piece_video.py` (`build/video-venv`,
skia-python; Source Serif/Sans, OFL, in `build/video/fonts`) draws 1920×1080 frames: whole
Verovio systems at a fixed staff height, tab, playhead, notes coloured by pluck strength
(OKLCH hue, blue soft → red loud; no level bars, at the user's request), unplayed bars
dimmed per repeat pass, and a fretboard whose strings vibrate with their simulated
envelopes (two-lobe shape and touch at the node for harmonics). Output
`build/video/sonatina-iii.mp4`: H.264 CRF 17 + AAC 256 kb/s, 3:30, 42 MB, audio offset
0 ms. `--stills T,...` renders check frames.

**Bach, whole Prelude** (`tools/guitar_bach_full.py`, clip `guitar-bach-full`): all 1,736
notes of Kowalski's performance with the Apke edition's strings, frets and fingers,
velocities fitted window by window with his room (envelope error 6.44 dB constant →
5.33 dB fitted, exponent 0.8), Apke's six first-page slurs as hammer-ons/pull-offs (the
later pages' slurs are not extracted), Verovio engraving of the GAPS score (1,736/1,736
placed). Closest body for the whole piece: g27 Do Santos (3.43 dB). Videos:
`build/video/bach-prelude-bwv1006a.mp4` (4:09, 49 MB) and `-discord.mp4` (19.2 MB,
two-pass 480 kb/s + AAC 128 kb/s); `sonatina-iii-discord.mp4` 19.0 MB (590 kb/s).
The fretboard makes one limitation visible: the renderer damps each string at its MIDI
note-off, and GAPS's transcribed durations are short (0.1 s sixteenths in bars 70–72),
so strings a guitarist would let ring until re-plucked fall silent at once.

### Strings ring until a hand stops them (October 1)

Aligned MIDI durations are short (median 0.12 s in the Bach, 0.15 s in the Sonatina) and
the renderer damped every string at note-off. `tools/guitar_sustain.py` (`let_ring`)
extends each note to the first of: the same string played again; for a fretted note,
the fretting finger needed elsewhere (edition fingers) or a fretted note out of the
hand's reach (finger-aware window p−1..p+4, else ±3 frets); after the written length, a
note a semitone away (bass strings: also a whole tone); the end. Median sounding length
0.12 → 0.27 s (Bach), 0.15 → 0.35 s (Sonatina); stops mostly "same string played". The
stop itself is still the old release (uniform 65/s, ~0.1 s to −60 dB): there is no
physical mute yet (palm/finger dashpot with broad contact would be the model; AG-PT's
staccato takes could calibrate it).

**The rooms were partly standing in for strings that stopped too soon.** Same first 24 s,
same grid (`tools/guitar_ring_room.py`, `guitar-room-fit-<piece>-ring.json`):

| | dry loss | best loss | RT60 200 Hz | RT60 4 kHz | reverb/direct |
|---|---|---|---|---|---|
| Kowalski, stopped at note-off | 0.971 | 0.640 | 5.0 s (grid edge) | 0.48 s | 1.00 |
| Kowalski, strings ring | 0.699 | 0.628 | 5.0 s (grid edge) | 0.24 s | 0.35 |
| Međugorac, stopped | 0.762 | 0.570 | 3.2 s | 0.38 s | 1.40 |
| Međugorac, strings ring | 0.639 | 0.558 | 3.1 s | 0.24 s | 0.70 |

Ringing strings explain much of what the room had absorbed (dry loss drops a lot; the
reverberant share falls 2–3×), but the low-frequency decay still wants several seconds:
our bass may decay faster than the real instruments'. The full-piece clips now use the
ringing rooms (Room menu: "…, strings ringing").

**Pluck cap.** The Sonatina's final strum was fitted at velocities 265–360, i.e. 4–5.5 mm
plucks (pf_pluck: 1.5 mm × (v/127)^1.25), where the tension nonlinearity makes the top D5
start 16 cents sharp, the 60–300 Hz band sustain ~7 dB longer and the 1.5–6 kHz band rise
after the strum — the "swell" the user heard. Fitted velocities are now clipped at a 3 mm
pluck (velocity 221, `physical_cap`); the four show-off harmonics are exempt (user
request).
