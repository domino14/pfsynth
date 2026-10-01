# Expressive guitar and violin inputs

Acquired and inspected 2026-09-30 for the string-model experiments. Original
downloads and extracted data are ignored by Git; source documentation and the
SMF event inventory are retained. GOAT example 1 and a performed Wohlfahrt
étude are now rendered in five local listening comparisons; implementation and
limitations are documented in `experiments/string-gestures/README.md`.

## Start here

### Violin: performed pitch contours

[Violin MIDI Dataset](https://zenodo.org/records/13736820), Nazif Can Tamer;
associated paper: Tamer, Özer, Müller & Serra, *High-Resolution Violin
Transcription Using Weak Labels*, ISMIR 2023.

`midi/violin/` contains the unmodified performance-aligned MIDI files from
`downloads/violin_MIDI_dataset.zip`. These represent actual performed timing
and dense pitch-bend contours, including vibrato and intonation. They are
transcription/alignment results, not direct MIDI-controller captures. The
authors report 5.8 ms frame resolution and 10-cent pitch resolution.

Initial inspection: 1,021 MIDI files, all with nonzero pitch-bend messages;
24,138,347 pitch-bend messages total. No CC events were found. These are useful
for pitch-contour playback, but do not provide bow pressure, contact point,
explicit articulation switches, or explicit portamento labels. Do not interpret
every pitch transition as a deliberate portamento. Verify the intended bend
range against the authors' reconstruction method before converting to cents;
the files inspected contain no RPN bend-sensitivity setup.

Suggested first comparison: three renditions of Wohlfahrt Op.45 No.8, with
54 note-ons each:

* `Wohlfahrt/Wohlfahrt_Op45-08_BernardChevalier_b_OfyqFc_kI-0000-0080.mid`
* `Wohlfahrt/Wohlfahrt_Op45-08_JPRafferty_U_PPK3MORKc-0000-0077.mid`
* `Wohlfahrt/Wohlfahrt_Op45-08_MichaelPijoan_PiKsZfuAi0k-0000-0065.mid`

The filenames preserve the source performance video IDs and crop times. The
landing-page etude opus description and archive filenames differ; retain the
original filenames rather than silently relabeling. The record describes
Creative Commons source MIDIs but does not clearly identify one blanket license
for the complete collection. Keep local research use distinct from release of
these inputs in a product.

### Guitar: technique-preserving examples

[GOAT authors' repository](https://github.com/JackJamesLoth/GOAT-Dataset), Loth
et al., *GOAT: A Large Dataset of Paired Guitar Audio Recordings and Tablatures*,
ISMIR 2025; [paper](https://arxiv.org/abs/2509.22655).

`midi/guitar/goat/audio-examples/example{1,2}/` contains two public examples,
each with `.mid`, `.gp`, `.gp5` and `.txt` companions, pinned to commit
`55c6e6668ef4546e4635c5e7eaad3062cf7f036b`. The recursive source tree is saved
alongside them.

**Important: the supplied ordinary MIDI loses the techniques.** Our inspection
finds 106 and 892 note-ons respectively, with zero pitch-bend and zero CC events.
The companion token tablature DOES retain:

* Example 1: bends and bend control points, slides, hammer effects, ties,
  explicit string/fret positions.
* Example 2: slides, hammer effects, palm mute, dead notes, ghost notes,
  explicit string/fret positions.

Import the tablature into our own performance-event representation rather than
rendering the bare `.mid` and expecting slides to appear. Preserve fret/string
identity; interpret the Guitar Pro technique semantics before distinguishing
hammer-ons from pull-offs. No audio was downloaded from this repository. The
full dataset requires an access request; the public examples are downloaded,
but public availability alone is not a redistribution license.

### Guitar: performed techniques

[Guitar-TECHS](https://zenodo.org/records/14963133), Pedroza et al., ICASSP 2025;
[project](https://guitar-techs.github.io/). The P1 techniques archive was
downloaded and checksum-verified. Five MIDI files were extracted to
`midi/guitar/guitar-techs/P1_techniques/midi/`: `midi_Bendings.mid`,
`midi_Vibrato.mid`, `midi_PalmMute.mid`, `midi_Harmonics.mid`, and
`midi_PinchHarmonics.mid`, with 205, 141, 148, 36 and 99 note-ons respectively.
All five have zero pitch-bend and zero CC events. Track names retain the six
string identities (`e`, `B`, `G`, `D`, `A`, `E`); the technique is identified
by its file/category, not a universal articulation switch. Even the
bends/vibrato files are **not continuous gesture MIDI**. Reference audio is
retained in the archive, from which contours could be extracted; audio was not
separately unpacked or rendered. This is electric guitar data,
useful for gestures but not a nylon-guitar timbre target. License: CC BY 4.0.
The authors note possible audio/MIDI alignment offsets up to 100 ms.

### Violin: explicit articulation categories

[Capriccio-MIDI](https://zenodo.org/records/21670078), Zou et al., *VioLM: A
Neural Language Model for Violin Synthesis with Articulation*, ISMIR 2026.
`capriccio/Capriccio-MIDI/` contains 49,243 symbolic segments with note-level
legato, detaché, staccato, harmonic and pizzicato labels. These are NumPy token
arrays, **not ready-to-play articulation-controlled MIDI**. There is no
portamento category or continuous pitch-bend column. Source material is adapted
from GigaMIDI; labels are heuristic/manual and velocity may be generated.
It is not captured violin-performance gesture data.

The included MIDI converter deliberately drops articulation labels. Build our
own adapter retaining the seventh column instead. Token values are vocabulary
IDs, not raw MIDI pitches. Reconstruction uses quantized timing, default
120 BPM and 4/4, not arbitrary original tempo maps. Dataset license: CC BY-NC
4.0 with underlying-composition caveats. The linked VioLM GitHub repository
returned 404 during this search; the archive does contain tokenizer/converter
source and its configuration. Nothing from that downloaded source was executed.

## Model implications and next audition

Keep steady bow and expressive bow as available gestures. Add a performance
layer with explicit string, open/stopped status, contact position, excitation,
release/muting, and optional pitch contour. Separate intentional expression
from bounded repeat variation, with a reproducible seed. Slow correlated
variation across a phrase should accompany small note-to-note changes; avoid
independent random pitch or timbre jumps at every note.

For guitar, pluck position, displacement, nail/pick contact and release vary
the attack and modal balance. Use six physical strings with shortened speaking
length at frets, rather than the current fixed length/pitch-dependent tension.
Open strings terminate at the nut; fretted strings at a fret with different
neck coupling. Modal decay differences depend on instrument and stopping
location, not a universal 'open = brighter' rule. [Measured neck admittance
study](https://isma2017.cirmmt.mcgill.ca/proceedings/pdf/ISMA_2017_paper_71.pdf)
supports position-dependent termination losses (electric-guitar measurements).

For violin, a stopped string terminates at a compliant/dissipative finger
contact instead of the nut. String identity and contact point matter. Ordinary
left-hand vibrato is unavailable on an open string; do not apply our current
automatic vibrato to every note. [UNSW violin acoustics](https://newt.phys.unsw.edu.au/jw/violintro.html)
explains how stopped-note vibrato also changes the radiated spectrum through
body resonances. Bow speed, force, position and bow changes should shape attacks
and sustained sound. Same MIDI pitch can be played open on one string or
stopped on a lower string; pitch alone cannot disambiguate fingering.

Next comparison should hold notes/timing constant and independently test:
correct string/fingering; continuous gesture playback; bounded repeat variation.
For slides, preserve vibration through the transition instead of restarting
every destination pitch. A fretted guitar slide crosses successive fret
contacts; violin finger slides are continuous. Neither is just generic pitch
smoothing on every legato note. Pitch bends need channel-aware routing and a
documented range; polyphonic guitar needs independent string channels or an
equivalent internal event stream.

## Inspection

`tools/inspect_string_midi.py` inventories note-ons, bends, controller numbers,
channel use and text/marker events without changing the source files. Counts
do not prove specific playing techniques. `midi-inventory.json` records SHA-256
hashes and per-file results. Downloads are checksum-checked against their
Zenodo records; extracted archive paths are checked to remain within the
destination. Neither prototype currently implements full MIDI gesture import.

## Real audio paired with symbolic performance (local September 30 additions)

[GAPS](https://aim-qmul.github.io/GAPS/) provides real classical-guitar audio
with aligned MIDI and scores/tab. Its official BWV1006a demonstration is
local in `midi/gaps/`, including audio, fine-aligned MIDI, MusicXML and syncpoints.
The metadata identifies Mateusz Kowalski / Guitar Salon International.
Research-only license; no redistribution or commercial training authorization.

[Bach Violin Dataset](https://hermandong.com/bach-violin-dataset/download.html)
provides recordings and estimated score alignments. The release archive is in
`downloads/`; Karen Gomyo's BWV1006 audio and movement-one notes/alignment CSVs
are extracted into `midi/bach-performance/`. Audio and derived alignments retain
source-specific licenses (this recording: Isabella Stewart Gardner Museum,
CC BY-NC-ND 4.0). The listening-room MIDI is derived from these alignments;
it is not directly captured MIDI and does not encode measured bow/vibrato.
