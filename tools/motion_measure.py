"""Measure early partial-frequency motion in cached Pianoteq notes.

Complex demodulation followed by a phase fit separates constant tuning from a
decaying frequency offset. This is an observable fit, not proof of tension
modulation: unison beating and onset transients can also move the phase.
"""
from pathlib import Path
import json, hashlib
import numpy as np
from scipy import signal, optimize
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parents[1]
SR = 44100
OUT = ROOT / 'experiments/string-motion'
NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']

def measure(midi, velocity):
    name = NAMES[midi % 12] + str(midi // 12 - 1)
    path = ROOT / f'calib/pianoteq-ref/closemic/{name}v{velocity}.wav'
    sr, x = wavfile.read(path)
    assert sr == SR
    x = x.astype(float) / 32768
    if x.ndim == 2: x = x.mean(axis=1)
    hit = np.flatnonzero(np.abs(x) > np.max(np.abs(x)) * .01)
    x = x[hit[0]:hit[0]+2*SR]
    patch = np.fromfile(ROOT/'experiments/partial-piano-wide/pianoteq.bin', np.float32, count=60).reshape(30,2)
    u = (midi-21)/3; lo = int(u); a = u-lo
    tune = (1-a)*patch[lo]+a*patch[min(lo+1,29)]
    f0 = 440*2**((midi-69)/12)*tune[0]
    t = np.arange(len(x))/SR
    rows = []
    for h in range(1,9):
        f = f0*h*np.sqrt((1+tune[1]*h*h)/(1+tune[1]))
        sos = signal.butter(3, min(f0*.22, 80), fs=SR, output='sos')
        z = signal.sosfiltfilt(sos, x*np.exp(-2j*np.pi*f*t))[::88]
        tt = t[::88]; phase = np.unwrap(np.angle(z)); amp = np.abs(z)
        mask = (tt>.045)&(tt<1.5)&(amp>max(amp.max()*.12, 2e-5))
        if mask.sum()<80: continue
        times = tt[mask]; y = phase[mask]; w = np.sqrt(amp[mask]/amp[mask].max())
        def fit_tau(tau):
            A = np.column_stack([np.ones(len(times)),2*np.pi*times,2*np.pi*tau*(-np.expm1(-times/tau))])
            coef = np.linalg.lstsq(A*w[:,None],y*w,rcond=None)[0]
            residual = (A@coef-y)*w
            return coef, np.sqrt(np.mean(residual**2))
        candidates = [(tau,*fit_tau(tau)) for tau in [.04,.07,.12,.2,.35]]
        tau, coef, err = min(candidates,key=lambda p:p[2])
        A = np.column_stack([np.ones(len(times)),2*np.pi*times])
        c = np.linalg.lstsq(A*w[:,None],y*w,rcond=None)[0]
        flat_err = np.sqrt(np.mean(((A@c-y)*w)**2))
        cents = 1200*np.log2(max(.5,1+coef[2]/f))
        rows.append(dict(partial=h,initial_cents=float(cents),tau=tau,phase_error=float(err),flat_phase_error=float(flat_err),gain=float(1-err/max(flat_err,1e-10))))
    useful = [r for r in rows if abs(r['initial_cents'])<18 and r['gain']>.12 and r['phase_error']<.35]
    cents = float(np.median([r['initial_cents'] for r in useful])) if len(useful)>=3 else 0.0
    tau = float(np.median([r['tau'] for r in useful])) if useful else .12
    return dict(note=name,midi=midi,velocity=velocity,source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),initial_cents=cents,tau=tau,accepted_partials=len(useful),partials=rows)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rows = []
    for m in [33,36,45,48,57,60,69,72]:
        for v in [48,100]:
            r=measure(m,v); rows.append(r)
            print(r['note'],v,round(r['initial_cents'],2),'cents',r['tau'],'s',r['accepted_partials'],'partials',flush=True)
    (OUT/'measurement.json').write_text(json.dumps(dict(reference='Pianoteq 6 Steinway D Close Mic Classical; cached mono downmix',warning='Frequency motion may include unison interference. No causal physical identification is claimed.',notes=rows),indent=2)+'\n')
    training=[[next(r for r in rows if r['midi']==m and r['velocity']==v) for v in [48,100]] for m in [36,48,60,72]]
    def table(key,positive=False):
        return '{'+','.join('{'+','.join(f'{max(0,r[key]) if positive else r[key]:.9g}' for r in row)+'}' for row in training)+'}'
    (OUT/'motion_patch.h').write_text('/* C2..C5, velocities 48/100; positive shifts only (tension hypothesis). */\nstatic const double motion_cents[4][2]='+table('initial_cents',True)+';\nstatic const double motion_tau[4][2]='+table('tau')+';\n')
    holdout=[]
    for r in rows:
        if r['note'].startswith('A'):
            u=float(np.clip((r['midi']-36)/12,0,3));a=int(u);b=min(a+1,3);t=u-a;l=0 if r['velocity']==48 else 1
            predicted=(1-t)*max(0,training[a][l]['initial_cents'])+t*max(0,training[b][l]['initial_cents'])
            holdout.append(dict(note=r['note'],velocity=r['velocity'],measured_cents=r['initial_cents'],predicted_cents=predicted,accepted_partials=r['accepted_partials']))
    qualified=[r for r in holdout if r['accepted_partials']>=3]
    report=dict(notes=holdout,qualified_mae_baseline_cents=float(np.mean([abs(r['measured_cents']) for r in qualified])),qualified_mae_candidate_cents=float(np.mean([abs(r['measured_cents']-r['predicted_cents']) for r in qualified])))
    (OUT/'holdout.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
