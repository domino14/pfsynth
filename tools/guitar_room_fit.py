"""Experiment: fit the recording's room together with the note velocities.

The velocity fit so far ignored the room: the recordings were made with microphones in
rooms, the synth is dry. Here each note's template (rendered alone, as in
guitar_dynamics_fit) gets an energy-domain room: the direct sound plus an exponentially
decaying reverberant tail per band (decay time RT60 varying smoothly with frequency, a
reverberant-to-direct energy ratio, a short pre-delay) — the usual statistical room
model. Band powers add across notes, so velocities are fitted on band power
(beta-divergence 0.5, onset-weighted) with the room applied, together with a per-band
timbre correction and floor. A grid over the room parameters picks the room that best
explains the recording. Test of the hypothesis that the room is "load-bearing": with
the room, does the fitted contrast still need squashing (exponent < 1)?

    build/body-venv/bin/python tools/guitar_room_fit.py
"""
import itertools,json,sys
import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter,stft,butter,sosfilt,fftconvolve
from stringlab_audition import ROOT,OUT,SR,library
from string_gesture_audition import setup
from guitar_dynamics_fit import Model,templates,FILTERS,CENTRES,N_FFT,HOP,EXP,V0,loudness_envelope

DOC=ROOT/'experiments/string-gestures'
BETA=.5
PREDELAY=1          # frames (~12 ms) between direct sound and tail


def power(x):
    _,_,Z=stft(x,SR,nperseg=N_FFT,noverlap=N_FFT-HOP,boundary=None,padded=False)
    return FILTERS@(np.abs(Z)**2)+1e-14


def roomify(P,rt_low,rt_high,ratio):
    """Band power through the statistical room: direct + ratio x exponential tail."""
    out=np.empty_like(P);hop=HOP/SR
    rts=np.exp(np.interp(np.log(CENTRES),np.log([200,4000]),np.log([rt_low,rt_high])))
    for b,rt in enumerate(rts):
        a=np.exp(-13.8155*hop/rt)          # energy decay per frame: -60 dB over RT60
        tail=lfilter([0]*PREDELAY+[1-a],[1,-a],P[...,b,:],axis=-1)
        out[...,b,:]=P[...,b,:]+ratio*tail
    return out


def room_impulse(rt_low,rt_high,ratio,seed=1):
    """Audible version of the fitted room: a direct impulse, then octave-band noise
    decaying with each band's RT60, each band's tail energy = ratio x the direct
    sound's energy in that band (the same statistical model the fit used)."""
    rng=np.random.default_rng(seed);rt=lambda f:float(np.exp(np.interp(np.log(f),np.log([200,4000]),np.log([rt_low,rt_high]))))
    n=round(1.3*max(rt_low,rt_high)*SR);t=np.arange(n)/SR;tail=np.zeros(n)
    edges=[44,88,177,355,710,1420,2840,5680,11360,20000]
    for lo,hi in zip(edges,edges[1:]):
        band=sosfilt(butter(4,[lo,min(hi,SR/2*.99)],'bandpass',fs=SR,output='sos'),rng.standard_normal(n))*np.exp(-6.9078*t/rt(np.sqrt(lo*hi)))
        band*=np.sqrt(ratio*2*(hi-lo)/SR/np.sum(band**2));tail+=band
    ir=np.zeros(n+round(PREDELAY*HOP));ir[0]=1;ir[round(PREDELAY*HOP):]+=tail
    return ir


def fit(V,T,onsets,iterations=150):
    """Power gains a_i with beta-divergence MU; per-band correction E and floor N."""
    n,B,F=T.shape;times=(np.arange(F)*HOP+N_FFT/2)/SR;w=np.full(F,.25)
    for t in onsets:w[(times>=t-.02)&(times<=t+.25)]=1
    a=np.full(n,V.sum()/T.sum());E=np.ones(B);N=np.full(B,np.percentile(V,3,axis=1).mean()*.3)
    for _ in range(iterations):
        S=np.tensordot(a,T,1);L=E[:,None]*S+N[:,None]
        num=w*V*L**(BETA-2);den=w*L**(BETA-1)
        a*=np.einsum('ibf,bf->i',T,E[:,None]*num)/np.maximum(np.einsum('ibf,bf->i',T,E[:,None]*den),1e-300)
        S=np.tensordot(a,T,1);L=E[:,None]*S+N[:,None]
        E*=(S*w*V*L**(BETA-2)).sum(1)/np.maximum((S*w*L**(BETA-1)).sum(1),1e-300);E/=np.exp(np.mean(np.log(E)))
        L=E[:,None]*S+N[:,None];N*=(w*V*L**(BETA-2)).sum(1)/np.maximum((w*L**(BETA-1)).sum(1),1e-300)
    L=E[:,None]*np.tensordot(a,T,1)+N[:,None]
    d=(V**BETA+(BETA-1)*L**BETA-BETA*V*L**(BETA-1))/(BETA*(BETA-1))
    return dict(a=a,E=E,N=N,loss=float((w*d).sum()/(w*V**BETA).sum()))


def main():
    lib,_=library();setup(lib)
    arg=lambda k,d=None:sys.argv[sys.argv.index(k)+1] if k in sys.argv else d
    cid=arg('--clip','guitar-bach-dynamics');clip=next(c for c in json.loads((OUT/'stringlab.json').read_text())['clips'] if c['id']==cid)
    duration=float(arg('--seconds',clip['duration']))
    if cid=='guitar-bach-dynamics':notes=json.loads((OUT/'guitar-bach-performance-events.json').read_text());ref=wavfile.read(OUT/'audio/guitar-bach-performance-ref.wav')[1].astype(float)/32768
    else:notes=[dict(n,velocity=100) for n in json.loads((OUT/f'{cid}-events.json').read_text()) if n['start']<duration-.5];ref=wavfile.read(OUT/f'audio/{cid}-ref.wav')[1].astype(float)/32768
    ref=ref[:round(duration*SR)]
    model=Model(lib,clip['dynamics']['model'],5,True)
    V=power(ref);onsets=[n['start'] for n in notes]
    dry=np.array([power(p) for p in templates(model,notes,np.full(len(notes),float(V0)),duration)])
    if 'refine' in sys.argv or arg('--around'):
        coarse=json.loads((DOC/arg('--around','guitar-room-fit-report.json')).read_text());c=coarse['best']
        k=(1,1.35,1.8) if 'refine' in sys.argv else (.7,1,1.4)
        grid=dict(rt_low=[.0]+[round(c['rt_low']*f,2) for f in k],rt_high=[round(c['rt_high']*f,2) for f in k],ratio=[round(c['ratio']*f,2) for f in (.6,1,1.6)])
    else:grid=dict(rt_low=[.0,.4,.9,1.5],rt_high=[.3,.7,1.2],ratio=[.1,.3,1.,3.])
    rows=[];best=None
    for rl,rh,ratio in itertools.product(*grid.values()):
        if rl==0 and (rh,ratio)!=(grid['rt_high'][0],grid['ratio'][0]):continue
        T=dry if rl==0 else roomify(dry,rl,rh,ratio);r=fit(V,T,onsets)
        rows.append(dict(rt_low=rl,rt_high=rh,ratio=ratio,loss=r['loss']))
        if best is None or r['loss']<best[0]['loss']:best=(rows[-1],r)
        print(('dry' if rl==0 else f'RT60 {rl:.1f}→{rh:.1f} s, reverb/direct {ratio:.1f}')+f': loss {r["loss"]:.4f}',flush=True)
    room,r=best;dry_row=rows[0]
    velocity=V0*np.maximum(r['a'],1e-12)**(1/(2*EXP))   # power gain -> pluck strength
    velocity*=V0/np.median(velocity)
    report=dict(method=__doc__.strip().splitlines()[0],beta=BETA,grid=rows,dry=dry_row,best=room,
        velocity=dict(p5=float(np.percentile(velocity,5)),median=float(np.median(velocity)),p95=float(np.percentile(velocity,95))),
        timbre_correction_db=dict(zip([round(float(c)) for c in CENTRES],[round(float(10*np.log10(e)),2) for e in r['E']])),
        velocities=velocity.tolist())
    # Hypothesis test: with the fitted room applied to the rendered audio, which contrast
    # exponent best matches the recording's loudness envelope? (1 = no squashing needed.)
    ir=room_impulse(room['rt_low'],room['rt_high'],room['ratio'])
    target=loudness_envelope(ref);live=target>target.max()-40
    def error(x):d=loudness_envelope(x)[live]-target[live];return float(np.sqrt(np.mean((d-np.median(d))**2)))
    def render(v,with_room=True):
        x=model.render([dict(n,velocity=float(u)) for n,u in zip(notes,v)],duration)
        return fftconvolve(x,ir)[:len(x)] if with_room else x
    events=OUT/('guitar-bach-dynamics-events.json' if cid=='guitar-bach-dynamics' else f'{cid}-events.json')
    flux=np.array([n['velocity'] for n in json.loads(events.read_text())][:len(notes)])
    report['exponent_with_room']={g:error(render(V0*(velocity/V0)**g)) for g in (.3,.5,.7,.85,1.,1.2)}
    report['envelope_error_db']=dict(constant_dry=error(render(np.full(len(notes),V0),False)),constant_room=error(render(np.full(len(notes),V0))),
        flux_fit_dry=error(render(flux,False)),flux_fit_room=error(render(flux)),room_fit_room=report['exponent_with_room'][1.])
    report['room_impulse_seconds']=len(ir)/SR
    report['clip']=cid;report['seconds']=duration
    (DOC/arg('--out','guitar-room-fit-refined.json' if 'refine' in sys.argv else 'guitar-room-fit-report.json')).write_text(json.dumps(report,indent=2)+'\n')
    print('best',room,'dry loss',dry_row['loss'],flush=True)
    print('exponent sweep with room',{k:round(v,2) for k,v in report['exponent_with_room'].items()},flush=True)
    print('envelope error dB',{k:round(v,2) for k,v in report['envelope_error_db'].items()},flush=True)


if __name__=='__main__':main()


def fit_room(model,notes,ref,duration,log=print):
    """Room for `notes` (velocities ignored; fitted jointly) on a coarse grid, then a finer
    one around its best. Returns dict(best, dry, rows)."""
    V=power(ref[:round(duration*SR)]);onsets=[n['start'] for n in notes]
    dry=np.array([power(p) for p in templates(model,notes,np.full(len(notes),float(V0)),duration)])
    rows=[]
    def run(rl,rh,ratio):
        r=fit(V,dry if rl==0 else roomify(dry,rl,rh,ratio),onsets);rows.append(dict(rt_low=rl,rt_high=rh,ratio=ratio,loss=r['loss']));return rows[-1]
    run(0,0,0)
    for rl,rh,ratio in itertools.product([.3,.6,1.,1.6,2.5,4.],[.3,.6,1.,1.5],[.2,.5,1.,2.]):run(rl,rh,ratio)
    c=min(rows[1:],key=lambda r:r['loss'])
    for rl,rh,ratio in itertools.product([c['rt_low']*f for f in (.8,1,1.25)],[c['rt_high']*f for f in (.8,1,1.25)],[c['ratio']*f for f in (.7,1,1.4)]):run(round(rl,3),round(rh,3),round(ratio,3))
    best=min(rows[1:],key=lambda r:r['loss']);log(f"room: RT60 {best['rt_low']:.2f} s at 200 Hz, {best['rt_high']:.2f} s at 4 kHz, reverb/direct {best['ratio']:.2f}; loss {best['loss']:.4f} (dry {rows[0]['loss']:.4f})")
    return dict(best=best,dry=rows[0],rows=rows)
