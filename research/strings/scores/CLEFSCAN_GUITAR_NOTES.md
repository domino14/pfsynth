# ClefScan on a guitar page — what worked, what a guitar mode would need

Test page: Apke's BWV 1006a Prelude, IMSLP #554880 PDF page 7 (MuseScore engraving,
single treble-8 staff per system, two voices, 4 sharps, 16th beams, no tab staff).
Rendered 1556×2200 (≈13 px staff space). ClefScan `scripts/recognize_ir_page.py`, commit
e1d1a34 (+ working-tree changes), 70 s CPU.

Ground truth available locally (exact, from the PDF vectors):
`research/strings/scores/apke-bwv1006a-page7-geometry.json` — staff lines, barlines,
323 noteheads with staff steps, 174 fingering digits, barre/dynamics placements. Pitch,
rhythm, voice, finger, string and fret for every note: `research/strings/midi/gaps/tw1wc.xml`
(GAPS; identical to the page through measure 12).

Worked: noteheads 323/323, 2 false positives (small heads at a natural-sign + finger
pair, measures 19–21), F1 0.997, median position error 1.4 px. At a 16-px-space render
(1905×2695): 323/323 with 9 false positives.

Gaps for guitar scores (from code inspection; not run end-to-end on guitar):
- Treble clef with 8 below (guitar clef): not detected; pitches would be an octave high.
- Tablature staves (6 lines, fret numbers): not supported; 5-line staff assumption.
- Left-hand fingering digits beside noteheads (0–4), right-hand p/i/m/a, circled string
  numbers (⑤ ③), barre indications ("VII" + dashed extension): not recognized.
- Glyph-level geometry above makes these measurable without hand labelling.
