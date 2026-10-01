/* pf_score_io.h - building a pf_score from files a host has already parsed.
 * Portable C, no allocation: the caller provides the arrays. */
#ifndef PF_SCORE_IO_H
#define PF_SCORE_IO_H
#include "pf_score.h"
#include "midi.h"

/* MIDI events (pf_midi_load) -> notes + pedal controls. Each note-on is paired with the
 * next note-off of its key (first in, first out). Returns the number of notes, or -1 if
 * the arrays are too small. */
int pf_score_from_midi(const pf_midi_event *ev, int n, double duration,
                       pf_note *notes, int max_notes, pf_control *controls, int max_controls,
                       pf_score *out);
#endif
