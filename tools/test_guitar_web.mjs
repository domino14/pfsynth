// Guitar web release checks. Optional argv[2]: previous published pfi.wasm for bit-exact comparison.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import { preparePerformance } from '../docs/guitar/performance.js';
const base = new URL('../', import.meta.url);
const read = path => fs.readFileSync(new URL(path, base));
const fixture = {duration:3,tuning:[64,59,55,50,45,40],notes:[
  {start:0,end:2,pitch:40,velocity:80,string:6,fret:0},
  {start:.1,end:.5,pitch:64,velocity:72,string:1,fret:0},
  {start:.5,end:.9,pitch:67,velocity:85,string:1,fret:3,articulation:1},
  {start:.9,end:1.3,pitch:65,velocity:65,string:1,fret:1,articulation:2},
  {start:1.4,end:1.8,pitch:59,velocity:95,string:2,fret:0},
  {start:1.85,end:2.5,pitch:64,velocity:80,string:4,fret:14,articulation:5,art_param:12}
]};
for (const {slug} of JSON.parse(read('docs/guitar/pieces.json')).pieces) preparePerformance(JSON.parse(read(`docs/guitar/pieces/${slug}/score.json`)));
console.log('All built-in guitar scores: PASS');
const score = JSON.parse(read('docs/guitar/pieces/tarrega-recuerdos/score.json'));
const compiled = preparePerformance(score);
assert.equal(compiled.notes.length,3029);
assert.equal(compiled.duration,score.duration);
for (const [i,n] of compiled.notes.entries()) {
  assert.equal(n.start,score.notes[i].start); assert.equal(n.end,score.notes[i].end);
}
assert.deepEqual(preparePerformance(fixture).notes,fixture.notes);
const timed={...fixture,timing:{mode:'score',rubato:[{beat:0,seconds:0},{beat:1,seconds:.8},{beat:2,seconds:2}],tailSeconds:1},
  plucking:{a:{position:.2,toneTiltDbPerOctave:-.3}},notes:[{beat:0,durationBeats:.5,pitch:64,velocity:80,string:1,fret:0,pluck:'a'},{beat:1,durationBeats:1,pitch:67,velocity:80,string:1,fret:3}]};
assert.equal(preparePerformance(timed).notes[0].end,.4);
assert.equal(preparePerformance(timed).notes[1].start,.8);
assert.equal(preparePerformance(timed).notes[0].pluck_tilt,-.3);
assert.throws(()=>preparePerformance({...timed,timing:{...timed.timing,rubato:[{beat:0,seconds:1},{beat:1,seconds:.5}]}}),/increase/);
assert.throws(()=>preparePerformance({...timed,timing:{...timed.timing,subdivision:{cycleBeats:1,ratios:[.25,.25,.25,.25]},minPluckGapSeconds:.3},notes:timed.notes.map(n=>({...n,subdivide:true}))}),/too fast/);
assert.throws(()=>preparePerformance({...fixture,notes:[{...fixture.notes[0],finger:'a'}]}),/left-hand/);
console.log('Timing, minimum gap, fingers, legacy score and all cached Recuerdos times: PASS');
async function engine(path,sr) {
  const wasi=new Proxy({},{get:()=>()=>0});
  const {instance}=await WebAssembly.instantiate(fs.readFileSync(path),{wasi_snapshot_preview1:wasi});
  const x=instance.exports;x._initialize?.();assert.equal(x.pfiw_init(1,sr),0);return x;
}
function load(x,p) {
  const dv=new DataView(x.memory.buffer),base=x.pfiw_notes(),ib=x.pfiw_guitar_inputs?.();
  assert.equal(x.pfiw_note_size(),48);
  for(let k=0;k<p.notes.length;k++) {
    const n=p.notes[k],o=base+48*k;
    new Uint8Array(x.memory.buffer,o,48).fill(0);
    dv.setFloat64(o,n.start,true);dv.setFloat64(o+8,n.end,true);dv.setFloat32(o+16,n.pitch,true);dv.setFloat32(o+20,n.velocity,true);
    dv.setFloat32(o+24,n.art_param||0,true);dv.setFloat32(o+28,n.slide_to||0,true);
    dv.setInt8(o+40,n.string??-1);dv.setInt8(o+41,n.fret??-1);dv.setInt8(o+42,n.finger??-1);dv.setInt8(o+43,n.articulation||0);
    if(ib){dv.setFloat64(ib+24*k,n.pluck_position||0,true);dv.setFloat64(ib+24*k+8,n.pluck_tilt||0,true);dv.setInt32(ib+24*k+16,n.loadingProfile==null?0:n.loadingProfile+1,true);}
  }
  p.tuning.forEach((n,k)=>dv.setInt8(x.pfiw_tuning()+k,n));
  if(x.pfiw_guitar_set_loading){const profiles=p.loadingProfiles||[];x.pfiw_guitar_set_loading(profiles.length);profiles.forEach((row,k)=>new Float32Array(x.memory.buffer,x.pfiw_guitar_loading()+k*80*4,80).set(row));}
  assert.equal(x.pfiw_load(p.notes.length,0,0,6,p.duration),0);
}
function render(x,p,sr) {
  load(x,p);const out=new Float32Array(Math.ceil(p.duration*sr));
  for(let k=0;k<out.length;k+=128){const n=Math.min(128,out.length-k);x.pfiw_render(n);out.set(new Float32Array(x.memory.buffer,x.pfiw_left(),n),k);}
  assert(out.every(Number.isFinite),'nonfinite audio');return out;
}
for(const sr of [44100,48000]) {
  const x=await engine(new URL('docs/guitar/pfguitar.wasm',base),sr),a=render(x,fixture,sr);
  if(process.argv[2]){const old=await engine(process.argv[2],sr);assert.deepEqual(a,render(old,fixture,sr));console.log(`Published legacy guitar ${sr}: BIT-EXACT`);}
  for(const control of [{pluck_position:.3},{pluck_tilt:.5},{loadingProfile:0}]) {
    const p={...fixture,notes:fixture.notes.map(n=>({...n,...control})),loadingProfiles:[Array(80).fill(2)]};
    const b=render(x,p,sr);assert.notDeepEqual(b,a);
  }
  // Restart must reproduce plucking controls and string losses. Mid-piece seeks reset tails, as in the existing API.
  const p={...fixture,notes:fixture.notes.map(n=>({...n,pluck_tilt:.4}))};const full=render(x,p,sr);x.pfiw_seek(0);x.pfiw_render(128);
  assert.deepEqual(new Float32Array(x.memory.buffer,x.pfiw_left(),128),full.subarray(0,128));
  console.log(`Per-note position, tone, loading and seek ${sr}: PASS`);
}
const x=await engine(new URL('docs/guitar/pfguitar.wasm',base),44100);
// This piece uses its explicit damping gates.
const cstr=p=>{const u=new Uint8Array(x.memory.buffer);let s='';while(u[p])s+=String.fromCharCode(u[p++]);return s;};
for(let i=0;i<x.pfiw_param_count();i++)if(cstr(x.pfiw_param_name(i))==='Let strings ring')x.pfiw_set(i,0);
const t=performance.now(),full=render(x,compiled,44100);
let peak=0,e=0;for(const v of full){peak=Math.max(peak,Math.abs(v));e+=v*v;}
console.log(`Full Recuerdos ${compiled.duration.toFixed(2)} s / ${compiled.notes.length} notes: finite; bridge-force peak ${peak.toFixed(4)}, RMS ${Math.sqrt(e/full.length).toFixed(4)}; rendered in ${((performance.now()-t)/1000).toFixed(2)} s`);
if(process.env.GUITAR_TEST_AUDIO)fs.writeFileSync(process.env.GUITAR_TEST_AUDIO,Buffer.from(full.buffer));
