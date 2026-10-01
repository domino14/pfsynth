// Score importers for the guitar page: MusicXML and Standard MIDI -> pfsynth score
// (API.md): notes with start/end (s), pitch, velocity, string, fret, finger, articulation.
// Strings left at -1 are chosen by the instrument; "Let strings ring" extends notes to
// when a hand would stop them. No dependencies.
const STANDARD = [64, 59, 55, 50, 45, 40];
const STEP = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
const DYN = { ppp: 30, pp: 42, p: 56, mp: 70, mf: 84, f: 100, ff: 116, fff: 127, sf: 110, sfz: 112, fp: 100 };
const ART = { normal: 0, hammer: 1, pull: 2, slide: 3, harmonic: 4, muted: 5 };

// ---------- MIDI ----------
export function parseMIDI(buf) {
  const d = new DataView(buf); let p = 0;
  const str = (n) => { let s = ''; for (let i = 0; i < n; i++) s += String.fromCharCode(d.getUint8(p + i)); return s; };
  if (str(4) !== 'MThd') throw new Error('not a MIDI file');
  const division = d.getUint16(12); let ntracks = d.getUint16(10); p = 8 + d.getUint32(4);
  const events = []; let order = 0;
  for (let t = 0; t < ntracks && p < buf.byteLength; t++) {
    const len = d.getUint32(p + 4), end = p + 8 + len; p += 8; let tick = 0, status = 0;
    const vlq = () => { let v = 0, b; do { b = d.getUint8(p++); v = (v << 7) | (b & 127); } while (b & 128); return v; };
    while (p < end) {
      tick += vlq(); let s = d.getUint8(p);
      if (s & 128) p++; else s = status;
      if (s === 0xff) { const type = d.getUint8(p++), l = vlq(); if (type === 0x51) events.push({ tick, order: order++, tempo: (d.getUint8(p) << 16) | (d.getUint8(p + 1) << 8) | d.getUint8(p + 2) }); p += l; continue; }
      if (s === 0xf0 || s === 0xf7) { p += vlq(); continue; }
      status = s; const kind = s & 0xf0, ch = s & 15;
      if (kind === 0x90 || kind === 0x80) { const note = d.getUint8(p), vel = d.getUint8(p + 1); p += 2; events.push({ tick, order: order++, ch, note, vel: kind === 0x90 ? vel : 0 }); }
      else if (kind === 0xc0 || kind === 0xd0) p += 1; else p += 2;
    }
    p = end;
  }
  events.sort((a, b) => a.tick - b.tick || a.order - b.order);
  if (division & 0x8000) throw new Error('SMPTE time division is not supported');
  let tempo = 500000, lastTick = 0, sec = 0; const open = new Map(), notes = [];
  for (const e of events) {
    sec += (e.tick - lastTick) * tempo / 1e6 / division; lastTick = e.tick;
    if (e.tempo) { tempo = e.tempo; continue; }
    const key = e.ch * 128 + e.note;
    if (e.vel > 0) { if (!open.has(key)) open.set(key, []); const n = { start: sec, end: sec + 0.5, pitch: e.note, velocity: e.vel, ch: e.ch }; open.get(key).push(n); notes.push(n); }
    else { const q = open.get(key); if (q && q.length) q.shift().end = sec; }
  }
  notes.sort((a, b) => a.start - b.start || a.pitch - b.pitch);
  // one channel per string (MIDI guitar convention), either direction
  const chans = [...new Set(notes.map(n => n.ch))];
  let map = null;
  if (chans.length > 1 && chans.length <= 6) for (const f of [c => c + 1, c => 6 - c]) {
    const lo = Math.min(...chans); if (notes.every(n => { const s = f(n.ch - lo); return s >= 1 && s <= 6 && n.pitch - STANDARD[s - 1] >= 0 && n.pitch - STANDARD[s - 1] <= 24; })) { map = n => f(n.ch - lo); break; }
  }
  for (const n of notes) { n.string = map ? map(n) : -1; n.fret = map ? n.pitch - STANDARD[n.string - 1] : -1; n.finger = -1; n.articulation = 0; delete n.ch; }
  return { notes, tuning: STANDARD, duration: notes.length ? Math.max(...notes.map(n => n.end)) + 3 : 1, stringsFromChannels: !!map };
}

// ---------- MusicXML ----------
function measureOrder(ms) {
  const rep = (m, dir) => [...m.querySelectorAll(':scope > barline > repeat')].some(r => r.getAttribute('direction') === dir);
  const ending = []; let current = null;
  ms.forEach((m, i) => {
    for (const e of m.querySelectorAll(':scope > barline > ending')) if (e.getAttribute('type') === 'start') current = e.getAttribute('number');
    ending[i] = current;
    for (const e of m.querySelectorAll(':scope > barline > ending')) if (['stop', 'discontinue'].includes(e.getAttribute('type'))) current = null;
  });
  for (let i = 1; i < ms.length; i++) if (ending[i] == null && ending[i - 1] != null && rep(ms[i], 'backward')) ending[i] = ending[i - 1];
  const order = []; let i = 0, start = 0, pass = 1; const used = new Set();
  while (i < ms.length && order.length < 4 * ms.length) {
    if (rep(ms[i], 'forward') && i !== start) { start = i; pass = 1; }
    if (ending[i] != null && !ending[i].replace(/\s/g, '').split(',').includes(String(pass))) { i++; continue; }
    order.push(i);
    if (rep(ms[i], 'backward') && !used.has(i)) { used.add(i); pass++; i = start; continue; }
    i++;
  }
  return order;
}

function partNotes(part, order) {
  const ms = [...part.querySelectorAll(':scope > measure')];
  let divisions = 1, transpose = 0, base = 0, dyn = 84, tempo = null, words = '';
  const tempos = [], out = [];
  // measure lengths for performance-order offsets
  for (const mi of order) {
    const m = ms[mi]; let cursor = 0, end = 0, prevStart = 0;
    for (const node of m.children) {
      const tag = node.tagName;
      if (tag === 'attributes') {
        const dv = node.querySelector('divisions'); if (dv) divisions = +dv.textContent;
        const tr = node.querySelector('transpose');
        if (tr) transpose = +(tr.querySelector('chromatic')?.textContent || 0) + 12 * +(tr.querySelector('octave-change')?.textContent || 0);
        else { const oc = node.querySelector('clef > clef-octave-change'); if (oc) transpose = 12 * +oc.textContent; }
      } else if (tag === 'direction' || tag === 'sound') {
        const snd = tag === 'sound' ? node : node.querySelector('sound');
        if (snd?.getAttribute('tempo')) tempos.push({ q: base + cursor / divisions, bpm: +snd.getAttribute('tempo') });
        const met = node.querySelector('metronome > per-minute'); if (met && !snd?.getAttribute('tempo')) tempos.push({ q: base + cursor / divisions, bpm: parseFloat(met.textContent) * (node.querySelector('metronome > beat-unit')?.textContent === 'half' ? 2 : 1) });
        const dy = node.querySelector('dynamics'); if (dy && dy.firstElementChild) { const v = DYN[dy.firstElementChild.tagName]; if (v) dyn = v; }
        const w = [...node.querySelectorAll('words')].map(x => x.textContent).join(' ').trim(); if (w) words = w;
      } else if (tag === 'backup') cursor -= +node.querySelector('duration').textContent;
      else if (tag === 'forward') cursor += +node.querySelector('duration').textContent;
      else if (tag === 'note') {
        const dur = +(node.querySelector(':scope > duration')?.textContent || 0);
        if (node.querySelector(':scope > grace')) continue;
        const chord = !!node.querySelector(':scope > chord'), onset = chord ? prevStart : cursor;
        if (!chord) { prevStart = cursor; cursor += dur; }
        end = Math.max(end, cursor);
        if (node.querySelector(':scope > rest')) continue;
        const pe = node.querySelector(':scope > pitch'); if (!pe) continue;
        const midi = 12 * (+pe.querySelector('octave').textContent + 1) + STEP[pe.querySelector('step').textContent] + +(pe.querySelector('alter')?.textContent || 0) + transpose;
        const tech = node.querySelector('notations > technical');
        out.push({
          id: node.getAttribute('id'), q: base + onset / divisions, qlen: dur / divisions, pitch: midi, dyn,
          string: tech?.querySelector('string') ? +tech.querySelector('string').textContent : -1,
          fret: tech?.querySelector('fret') ? +tech.querySelector('fret').textContent : -1,
          finger: tech?.querySelector('fingering') ? +tech.querySelector('fingering').textContent : -1,
          tieStop: [...node.querySelectorAll(':scope > tie')].some(t => t.getAttribute('type') === 'stop'),
          tieStart: [...node.querySelectorAll(':scope > tie')].some(t => t.getAttribute('type') === 'start'),
          slurStart: [...node.querySelectorAll('notations > slur[type="start"]')].map(s => s.getAttribute('number') || '1').concat(tech?.querySelector('hammer-on[type="start"], pull-off[type="start"]') ? ['ho'] : []),
          slurStop: [...node.querySelectorAll('notations > slur[type="stop"]')].map(s => s.getAttribute('number') || '1').concat(tech?.querySelector('hammer-on[type="stop"], pull-off[type="stop"]') ? ['ho'] : []),
          harmonic: !!tech?.querySelector('harmonic') || /\b(harm|arm)\.?/i.test(words),
          arpeggiate: !!node.querySelector('notations > arpeggiate'),
        });
        words = '';
      }
    }
    const meter = ms[mi].querySelector('attributes > time');
    base += Math.max(end, 0) / divisions;
  }
  return { notes: out, tempos };
}

export function parseMusicXML(text) {
  const doc = new DOMParser().parseFromString(text, 'application/xml');
  if (doc.querySelector('parsererror')) throw new Error('could not read the MusicXML');
  if (!doc.querySelector('score-partwise')) throw new Error('only score-partwise MusicXML is supported (export uncompressed .musicxml)');
  const parts = [...doc.querySelectorAll('score-partwise > part')].filter(p => p.querySelector('note > pitch'));
  if (!parts.length) throw new Error('no notes in the score');
  parts.forEach((p, k) => [...p.querySelectorAll('note')].forEach((n, i) => { if (!n.getAttribute('id')) n.setAttribute('id', `p${k}n${i}`); }));
  const isTab = (p) => !!p.querySelector('clef > sign')?.textContent.match(/TAB/i);
  const staff = parts.find(p => !isTab(p)) || parts[0], tab = parts.find(p => p !== staff && isTab(p));
  // tuning
  let tuning = STANDARD.slice();
  const st = [...(tab || staff).querySelectorAll('staff-details > staff-tuning')];
  if (st.length === 6) { const lines = {}; for (const t of st) lines[+t.getAttribute('line')] = 12 * (+t.querySelector('tuning-octave').textContent + 1) + STEP[t.querySelector('tuning-step').textContent] + +(t.querySelector('tuning-alter')?.textContent || 0); tuning = [6, 5, 4, 3, 2, 1].map(l => lines[l]); }
  const order = measureOrder([...staff.querySelectorAll(':scope > measure')]);
  const A = partNotes(staff, order), B = tab ? partNotes(tab, order) : null;
  let notes = A.notes;
  // Guitar is written an octave above where it sounds. Files differ in whether they say so
  // (<transpose>, a treble-8 clef) or just write it: with a tab staff, take the octave from
  // the tab; otherwise read an unmarked guitar part an octave down.
  if (B) {
    const at = new Map(); for (const n of B.notes) { const k = n.q.toFixed(4); if (!at.has(k)) at.set(k, []); at.get(k).push(n.pitch); }
    const votes = new Map(); for (const n of notes) for (const p of at.get(n.q.toFixed(4)) || []) { const d = p - n.pitch; if (d % 12 === 0) votes.set(d, (votes.get(d) || 0) + 1); }
    const shift = [...votes.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] || 0; for (const n of notes) n.pitch += shift;
  } else if (!staff.querySelector('attributes transpose') && !staff.querySelector('clef > clef-octave-change')) {
    const id = staff.getAttribute('id'), sp = doc.querySelector(`score-part[id="${id}"]`), prog = +(sp?.querySelector('midi-program')?.textContent || 0);
    if (/guitar|gtr/i.test(sp?.textContent || '') || (prog >= 25 && prog <= 32)) for (const n of notes) n.pitch -= 12;
  }
  if (B) {   // pair notation with tab by onset and pitch
    const key = n => `${n.q.toFixed(4)}:${n.pitch}`, pool = new Map();
    for (const n of B.notes) { if (!pool.has(key(n))) pool.set(key(n), []); pool.get(key(n)).push(n); }
    for (const n of notes) { const m = pool.get(key(n))?.shift(); if (m) { n.string = m.string; n.fret = m.fret; n.tabId = m.id; if (m.harmonic) n.harmonic = true; } }
  }
  // ties: continuations extend the note they continue
  const live = new Map(), merged = [];
  for (const n of notes.sort((a, b) => a.q - b.q || a.pitch - b.pitch)) {
    if (n.tieStop && live.has(n.pitch)) { const h = live.get(n.pitch); h.qlen = n.q + n.qlen - h.q; if (!n.tieStart) live.delete(n.pitch); continue; }
    merged.push(n); if (n.tieStart) live.set(n.pitch, n); else live.delete(n.pitch);
  }
  // doubled voices (same onset, pitch and string) sound once
  const seen = new Set(); notes = merged.filter(n => { const k = `${n.q}:${n.pitch}:${n.string}`; if (seen.has(k)) return false; seen.add(k); return true; });
  // tempo map: quarter notes -> seconds
  const tempos = (A.tempos.length ? A.tempos : [{ q: 0, bpm: 90 }]).sort((a, b) => a.q - b.q);
  if (tempos[0].q > 0) tempos.unshift({ q: 0, bpm: tempos[0].bpm });
  const sec = (q) => { let s = 0; for (let i = 0; i < tempos.length; i++) { const a = tempos[i].q, b = i + 1 < tempos.length ? Math.min(tempos[i + 1].q, q) : q; if (b <= a) break; s += (b - a) * 60 / tempos[i].bpm; } return s; };
  const out = notes.map(n => {
    const r = { start: sec(n.q), end: sec(n.q + Math.max(n.qlen, 0.05)), pitch: n.pitch, velocity: n.dyn, string: n.string, fret: n.fret >= 0 && n.string >= 1 ? n.fret : -1,
      finger: n.finger >= 0 && n.finger <= 4 ? n.finger : -1, articulation: 0, art_param: 0, ids: [n.id, n.tabId].filter(Boolean), _n: n };
    if (r.string >= 1 && r.fret < 0) r.fret = n.pitch - tuning[r.string - 1];
    if (n.harmonic) { r.articulation = ART.harmonic; r.art_param = [12, 7, 5, 4].includes(r.fret) ? r.fret : 12; }
    return r;
  });
  // slurs between consecutive notes on one string are left-hand ligados
  out.forEach((r, i) => {
    const n = r._n; if (!n.slurStart.length || r.string < 1) return;
    const next = out.slice(i + 1).find(x => x.string === r.string); if (!next) return;
    if (!n.slurStart.some(k => next._n.slurStop.includes(k)) || next.pitch === r.pitch || next.start - r.start > 1) return;
    const up = next.pitch > r.pitch; if (up && next.fret === 0) return;
    next.articulation = up ? ART.hammer : ART.pull;
  });
  // arpeggio marks: roll upward, 25 ms per string
  const groups = new Map(); out.forEach(r => { if (r._n.arpeggiate) { const k = r.start.toFixed(4); if (!groups.has(k)) groups.set(k, []); groups.get(k).push(r); } });
  for (const g of groups.values()) g.sort((a, b) => (b.string - a.string) || (a.pitch - b.pitch)).forEach((r, k) => { r.start += 0.025 * k; r.end = Math.max(r.end, r.start + 0.05); });
  out.forEach(r => delete r._n);
  out.sort((a, b) => a.start - b.start || a.pitch - b.pitch);
  const title = doc.querySelector('work-title')?.textContent || doc.querySelector('movement-title')?.textContent || '';
  const composer = doc.querySelector('identification > creator[type="composer"]')?.textContent || '';
  return { notes: out, tuning, duration: out.length ? Math.max(...out.map(n => n.end)) + 3 : 1, xml: new XMLSerializer().serializeToString(doc), title, composer };
}
