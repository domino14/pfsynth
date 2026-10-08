// Optional, additive performance controls for pfsynth score 1. Legacy second-based
// files pass through unchanged. Beat coordinates use quarters in performed order.
export function preparePerformance(piece) {
  if (!Array.isArray(piece.notes) || !piece.notes.length) throw new Error('The score has no notes.');
  const timing = piece.timing, profiles = piece.plucking || {};
  const scoreTime = timing?.mode === 'score';
  if (piece.tuning && (!Array.isArray(piece.tuning) || piece.tuning.length !== 6 || piece.tuning.some(n => !Number.isInteger(n) || n < 0 || n > 127))) throw new Error('Guitar tuning needs six MIDI pitches, highest string first.');
  if (timing?.minPluckGapSeconds != null && (!Number.isFinite(timing.minPluckGapSeconds) || timing.minPluckGapSeconds < 0)) throw new Error('The minimum pluck gap must be nonnegative seconds.');
  if (timing?.tailSeconds != null && (!Number.isFinite(timing.tailSeconds) || timing.tailSeconds < 0)) throw new Error('The tail must be nonnegative seconds.');
  let map, endBeat;
  if (scoreTime) {
    map = timing.rubato;
    if (!Array.isArray(map) || map.length < 2) throw new Error('Rubato needs at least two beat/seconds anchors.');
    map.forEach((p, i) => {
      if (!Number.isFinite(p.beat) || !Number.isFinite(p.seconds) || p.beat < 0 || p.seconds < 0 ||
          (i && (p.beat <= map[i - 1].beat || p.seconds <= map[i - 1].seconds))) throw new Error('Rubato anchors must increase in both beats and seconds.');
    });
    endBeat = map.at(-1).beat;
  }
  const seconds = beat => {
    if (!Number.isFinite(beat) || beat < map[0].beat - 1e-8 || beat > endBeat + 1e-8) throw new Error('A note lies outside the rubato map.');
    let lo = 0, hi = map.length - 1;
    while (hi - lo > 1) { const k = (lo + hi) >> 1; if (map[k].beat <= beat) lo = k; else hi = k; }
    const a = map[lo], b = map[hi]; return a.seconds + (b.seconds - a.seconds) * (beat - a.beat) / (b.beat - a.beat);
  };
  const sub = scoreTime && timing.subdivision;
  let phases;
  if (sub) {
    if (!Number.isFinite(sub.cycleBeats) || !(sub.cycleBeats > 0) || !Array.isArray(sub.ratios) || sub.ratios.length !== 4 ||
        sub.ratios.some(r => !Number.isFinite(r) || r <= 0) || Math.abs(sub.ratios.reduce((a,b) => a+b, 0) - 1) > 1e-6)
      throw new Error('Tremolo subdivision needs four positive gap ratios adding to one.');
    phases = [0]; sub.ratios.forEach(r => phases.push(phases.at(-1) + r));
  }
  const onset = n => {
    if (!sub || !n.subdivide) return seconds(n.beat);
    const cycle = Math.floor((n.beat + 1e-8) / sub.cycleBeats) * sub.cycleBeats;
    const a = seconds(cycle), b = seconds(cycle + sub.cycleBeats), slot = (n.beat - cycle) / sub.cycleBeats * 4;
    if (Math.abs(slot - Math.round(slot)) > 1e-6) throw new Error('Ornaments must opt out of regular tremolo subdivision.');
    if ((b - a) * Math.min(...sub.ratios) < (timing.minPluckGapSeconds || 0) - 1e-6)
      throw new Error('The tempo is too fast for the specified minimum tremolo gap.');
    return a + (b - a) * phases[Math.round(slot)];
  };
  const notes = piece.notes.map(n => {
    const r = { ...n };
    if (n.pluck != null && !['p','i','m','a','c'].includes(n.pluck)) throw new Error('Pluck must be p, i, m, a or c.');
    if (n.finger != null && (!Number.isInteger(n.finger) || n.finger < -1 || n.finger > 4)) throw new Error('Finger is the left-hand number; use pluck for p/a/m/i.');
    if (scoreTime) { r.start = onset(n) + (n.startOffset || 0); r.end = seconds(n.gateBeat ?? (n.beat + n.durationBeats)); }
    const profile = { ...(profiles[n.pluck] || {}), ...(n.pluckControls || {}) };
    for (const [key, min, max, output] of [['position', .04, .45, 'pluck_position'], ['toneTiltDbPerOctave', -2, 2, 'pluck_tilt']]) {
      if (profile[key] == null) continue;
      if (!Number.isFinite(profile[key]) || profile[key] < min || profile[key] > max) throw new Error(`Pluck ${key} must be ${min}…${max}.`);
      r[output] = profile[key];
    }
    if (![r.start,r.end,r.pitch,r.velocity].every(Number.isFinite) || r.start < 0 || r.end <= r.start || r.velocity < 0)
      throw new Error('Each note needs a finite pitch, nonnegative velocity, and end after start.');
    if (r.string >= 1 && r.fret >= 0 && Math.abs((piece.tuning || [64,59,55,50,45,40])[r.string - 1] + r.fret - r.pitch) > .01 && !r.articulation)
      throw new Error('String/fret does not match the sounding pitch.');
    return r;
  }).sort((a,b) => a.start - b.start || b.string - a.string);
  if (scoreTime) {
    const starts = new Map();
    for (const n of notes) if (!n.startOffset) starts.set(n.beat.toFixed(7), n.start);
    for (const n of notes) if (n.gateBeat != null) {
      n.end = starts.get(n.gateBeat.toFixed(7)) ?? seconds(n.gateBeat);
      if (n.end <= n.start) throw new Error('A damping gate must follow its pluck.');
    }
  }
  if (scoreTime && piece.ringing === 'next-pluck') {
    for (let i = 0; i < notes.length; i++) {
      const n = notes[i];
      if (!(n.string >= 1 && n.string <= 6)) throw new Error('Next-pluck ringing needs an explicit string.');
      let end = map.at(-1).seconds;
      for (let j = i + 1; j < notes.length; j++) {
        const m = notes[j];
        if (m.string === n.string || (n.fret > 0 && m.fret > 0 && Math.abs(m.fret - n.fret) > 4 && m.start > n.start + .0001)) { end = m.start; break; }
      }
      if (end <= n.start) throw new Error('Two simultaneous notes cannot use the same string.');
      n.end = end;
    }
  }
  const duration = scoreTime ? map.at(-1).seconds + (timing.tailSeconds ?? 3) : piece.duration;
  if (!Number.isFinite(duration) || duration <= 0 || notes.some(n => n.end > duration + 1e-6)) throw new Error('Performance duration must contain all notes.');
  return { ...piece, notes, duration };
}
