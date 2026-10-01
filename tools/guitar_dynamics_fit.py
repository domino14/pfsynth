"""Fit per-note pluck velocities to Kowalski's recording by analysis-by-synthesis.

The GAPS MIDI gives every note velocity 100. Here each note is rendered alone with
the exact audition model (same string, fret, timing, release and body), and one gain
per note is fitted so the sum of the notes' band-magnitude spectrograms explains the
recording (KL divergence, onset-weighted). Fitted jointly as nuisance terms, never
applied to the audio:
  * a per-band correction E_b: the model's timbre and the recording chain differ
    from Kowalski's guitar, and that mismatch must not be read as dynamics;
  * a per-band floor N_b: noise and room.
Ringing and overlapping strings are explained by their own templates, so a note is
credited only with what its own onset adds. Templates are re-rendered at the current
velocity estimate (the tension nonlinearity makes amplitude not exactly linear).
This estimates relative pluck strength under this model; it is not a recovered
measurement of Kowalski's finger force.

    build/body-venv/bin/python tools/guitar_dynamics_fit.py
"""
import json,copy,hashlib,sys
import numpy as np
from scipy.io import loadmat,wavfile
from scipy.signal import fftconvolve,stft
from stringlab_audition import ROOT,OUT,SR,library,write_clip,ptr
from string_gesture_audition import setup,render_guitar,export_midi
from guitar_material_audition import measured_body,loading

DOC=ROOT/'experiments/string-gestures'
V0=100;EXP=1.25          # pf_pluck_string: initial displacement grows as velocity^1.25
CAP=4                    # fitted notes may exceed MIDI 127 (opt-in uncapped path), bounded for safety
LIMIT_DB=9               # no note more than this far (pluck amplitude) from its local phrase trend
N_FFT,HOP=2048,512
ONSET=(-.02,.15)         # seconds around each onset weighted fully
QUIET_WEIGHT=.1


def bands():
    f=np.fft.rfftfreq(N_FFT,1/SR);centres=70*2**(np.arange(0,np.log2(7000/70)*6+1)/6)
    W=np.zeros((len(centres),len(f)))
    for k,c in enumerate(centres):
        lo,hi=c*2**(-1/6),c*2**(1/6)
        W[k]=np.clip(np.minimum((f-lo)/(c-lo),(hi-f)/(hi-c)),0,None)
        if W[k].sum()<1:W[k,np.argmin(abs(f-c))]=1   # low bands narrower than an FFT bin
    return centres,W
CENTRES,FILTERS=bands()


def spectrogram(x):
    _,_,Z=stft(x,SR,nperseg=N_FFT,noverlap=N_FFT-HOP,boundary=None,padded=False)
    return np.sqrt(FILTERS@(np.abs(Z)**2))+1e-12


class Model:
    def __init__(self,lib,name,guitar=None,with_loading=True):
        self.lib,self.name=lib,name
        self.body=None if guitar is None else measured_body(loadmat(ROOT/'research/strings/body/mores-qualified-selected-impulses.mat')['qualified_selected_impulses'],guitar)
        self.loading=loading(self.body,1) if self.body and with_loading else None
    def force(self,notes,duration,variation=0):
        return render_guitar(self.lib,notes,duration,True,variation,body=False,material=1,loading=self.loading,velocity_cap=CAP)
    def radiate(self,force):
        if self.body is not None:return fftconvolve(force,self.body['impulse'])[:len(force)]
        y=np.ascontiguousarray(force,dtype=np.float32);self.lib.pf_lab_body(ptr(y),len(y),0);return y.astype(float)
    def render(self,notes,duration,variation=0):return self.radiate(self.force(notes,duration,variation))


def templates(model,notes,velocities,duration):
    """Each note alone, at its own velocity; cut where a same-string onset re-plucks."""
    total=round(duration*SR);out=[]
    for i,n in enumerate(notes):
        later=[m['start'] for m in notes if m['string']==n['string'] and m['start']>n['start']]
        cut=min(later+[duration])
        length=min(cut,n['end']+.45,duration)-n['start']
        force=model.force([dict(n,start=0.,end=min(n['end'],cut)-n['start'],velocity=velocities[i])],length+.15)
        # The string state is replaced at the next same-string onset; the body still rings.
        a=round(n['start']*SR);force[round((cut-n['start'])*SR):]=0;y=model.radiate(force)
        full=np.zeros(total);b=min(total,a+len(y));full[a:b]=y[:b-a];out.append(full)
    return out


def flux(S,lag=3):
    """Positive band-magnitude increase over ~35 ms: what an onset adds. Decaying
    tails give negative steps and drop out, so the model's decay rates (which differ
    from the real guitar's) cannot make earlier notes explain a later one."""
    return np.concatenate([np.zeros((S.shape[0],lag)),np.maximum(S[:,lag:]-S[:,:-lag],0)],1)+1e-9


def fit(ref,parts,onsets,iterations=400):
    V=flux(spectrogram(ref));T=np.array([flux(spectrogram(p)) for p in parts]);n,B,F=T.shape
    times=(np.arange(F)*HOP+N_FFT/2)/SR
    w=np.full(F,QUIET_WEIGHT)  # flux outside onset windows is mostly noise and vibrato
    for t in onsets:w[(times>=t+ONSET[0])&(times<=t+ONSET[1])]=1
    g=np.full(n,V.sum()/T.sum());E=np.ones(B);N=np.full(B,np.percentile(V,5,axis=1).mean()*.5)
    for _ in range(iterations):
        L=E[:,None]*np.tensordot(g,T,1)+N[:,None];R=w*V/L
        g*=np.einsum('ibf,bf->i',T,E[:,None]*R)/np.maximum(np.einsum('ibf,b,f->i',T,E,w),1e-30)
        L=E[:,None]*np.tensordot(g,T,1)+N[:,None];R=w*V/L;S=np.tensordot(g,T,1)
        E*=(S*R).sum(1)/np.maximum((S*w).sum(1),1e-30);E/=np.exp(np.mean(np.log(E)))
        L=E[:,None]*np.tensordot(g,T,1)+N[:,None];N*=(w*V/L).sum(1)/w.sum()
    L=E[:,None]*np.tensordot(g,T,1)+N[:,None]
    kl=float((w*(V*np.log(V/L)-V+L)).sum()/(w*V).sum())
    # How much of each note's own onset window its template explains (identifiability).
    share=[]
    for i,t in enumerate(onsets):
        m=(times>=t)&(times<=t+.1)
        share.append(float((E[:,None]*g[i]*T[i][:,m]).sum()/max(L[:,m].sum(),1e-30)))
    return dict(gain=g,eq=E,floor=N,kl=kl,share=np.array(share),V=V,L=L,w=w)


def velocities_from(gain,old,share,normalize=True,absolute=False):
    """Amplitude gain on a template rendered at `old` -> (regularized, raw) velocity.
    The median note stays at velocity 100, the same typical pluck amplitude as the
    constant-velocity version, so the comparison changes note-to-note dynamics only."""
    lv=np.log(np.array(old,float)*np.maximum(gain,1e-9)**(1/EXP));raw=lv.copy()
    # Weakly identified notes (their onset adds little to a busy mixture) shrink toward
    # the local phrase trend of well-identified neighbours; nothing strays beyond
    # ±LIMIT_DB of pluck amplitude from that trend.
    trusted=share>=.3;trend=[]
    for i in range(len(lv)):
        window=slice(max(0,i-4),i+5);pick=lv[window][trusted[window]]
        trend.append(np.median(pick if len(pick) else lv[window]))
    trend=np.array(trend);trust=np.clip((share-.1)/.3,0,1);span=LIMIT_DB/20/EXP*np.log(10)
    lv=trend+trust*np.clip(lv-trend,-span,span)
    if not normalize:return np.exp(lv),np.exp(raw)
    scale=np.log(V0)-np.median(lv)
    out=(np.minimum(np.exp(lv+scale),127*CAP),np.exp(raw+scale))
    # Before normalization the velocity is on the recording's absolute scale: the pluck
    # strength at which each note matches it. Windowed fits compare these across windows.
    return out+(np.exp(lv),np.exp(raw)) if absolute else out


def solve(model,notes,ref,duration,rounds=3):
    vel=np.full(len(notes),float(V0));onsets=[n['start'] for n in notes]
    for r in range(rounds):
        parts=templates(model,notes,vel,duration)
        result=fit(ref,parts,onsets)
        new,raw,absolute,absolute_raw=velocities_from(result['gain'],vel,result['share'],absolute=True)
        print(f'  {model.name}: round {r+1} weighted KL {result["kl"]:.4f}, velocity range {new.min():.0f}–{new.max():.0f}',flush=True)
        vel=new
    result['velocity']=vel;result['raw']=raw;result['absolute']=absolute;result['absolute_raw']=absolute_raw;return result


def loudness_envelope(x):
    frames=np.lib.stride_tricks.sliding_window_view(x,round(.2*SR))[::round(.05*SR)]
    return 10*np.log10(np.mean(frames**2,axis=1)+1e-12)


def fit_dynamics(model,notes,ref,duration):
    """Reusable: velocities fitted to `ref` for `notes` under `model` (as in main for the
    Kowalski excerpt), with the contrast exponent chosen on the loudness envelope."""
    r=solve(model,notes,ref,duration);target=loudness_envelope(ref);live=target>target.max()-40
    def error(x):d=loudness_envelope(x)[live]-target[live];return float(np.sqrt(np.mean((d-np.median(d))**2)))
    with_velocity=lambda v:[dict(n,velocity=float(x)) for n,x in zip(notes,v)]
    calibration={g:error(model.render(with_velocity(V0*(r['velocity']/V0)**g),duration)) for g in (.3,.4,.5,.6,.7,.8,1.)}
    gamma=min(calibration,key=calibration.get)
    return V0*(r['velocity']/V0)**gamma,dict(gamma=gamma,calibration=calibration,kl=r['kl'],share=r['share'].tolist(),raw=(V0*(r['raw']/V0)**gamma).tolist(),
        constant_error_db=error(model.render(notes,duration)),fitted_error_db=calibration[gamma])


def fit_dynamics_long(model,notes,ref,duration,window=24.,context=4.,rounds=2):
    """Long pieces, window by window. Notes starting up to `context` s before a window are
    fitted with it so their ringing is explained, but only notes starting inside the
    window keep its estimate. Velocities stay on the recording's absolute scale (no
    per-window normalization); then one global normalization and contrast exponent."""
    lv=np.full(len(notes),np.log(V0));raw=lv.copy();share=np.zeros(len(notes));a=0.;windows=[]
    while a<duration-1e-6:
        b=min(duration,a+window);lo=max(0.,a-context);hi=min(duration,b+1.)
        idx=[i for i,n in enumerate(notes) if lo<=n['start']<b]
        if idx:
            local=[dict(notes[i],start=notes[i]['start']-lo,end=min(notes[i]['end'],hi)-lo) for i in idx]
            seg=ref[round(lo*SR):round(hi*SR)];r=solve(model,local,seg,len(seg)/SR,rounds)
            for j,i in enumerate(idx):
                if notes[i]['start']>=a:lv[i]=np.log(r['absolute'][j]);raw[i]=np.log(r['absolute_raw'][j]);share[i]=r['share'][j]
            windows.append(dict(start=a,end=b,notes=sum(notes[i]['start']>=a for i in idx),kl=r['kl']))
            print(f'  window {a:6.1f}–{b:6.1f} s: {windows[-1]["notes"]} notes, KL {r["kl"]:.3f}',flush=True)
        a=b
    scale=np.log(V0)-np.median(lv);velocity=np.minimum(np.exp(lv+scale),127*CAP)
    target=loudness_envelope(ref);live=target>target.max()-40
    def error(x):d=loudness_envelope(x)[live]-target[live];return float(np.sqrt(np.mean((d-np.median(d))**2)))
    with_velocity=lambda v:[dict(n,velocity=float(x)) for n,x in zip(notes,v)]
    calibration={g:error(model.render(with_velocity(V0*(velocity/V0)**g),duration)) for g in (.3,.4,.5,.6,.7,.8,1.)}
    gamma=min(calibration,key=calibration.get)
    return V0*(velocity/V0)**gamma,dict(gamma=gamma,calibration=calibration,windows=windows,share=share.tolist(),raw=(V0*(np.exp(raw+scale)/V0)**gamma).tolist(),
        constant_error_db=error(model.render(notes,duration)),fitted_error_db=calibration[gamma])


def fit_room_dynamics(model,notes,ref,duration,room,rounds=3):
    """Velocities fitted with the recording's room (see guitar_room_fit.py): each note's
    template, rendered alone at its current velocity, passes through the fitted
    statistical room in the band-power domain; power gains are fitted with the
    beta-divergence, then turned into velocities with the usual identifiability shrinkage."""
    from guitar_room_fit import power,roomify,fit as power_fit
    vel=np.full(len(notes),float(V0));V=power(ref);onsets=[n['start'] for n in notes]
    times=(np.arange(V.shape[1])*HOP+N_FFT/2)/SR
    for _ in range(rounds):
        T=roomify(np.array([power(p) for p in templates(model,notes,vel,duration)]),room['rt_low'],room['rt_high'],room['ratio'])
        r=power_fit(V,T,onsets);L=r['E'][:,None]*np.tensordot(r['a'],T,1)+r['N'][:,None]
        # Identifiability: the share of the modelled power in a note's first 100 ms that is its own.
        share=np.array([float((r['E'][:,None]*r['a'][i]*T[i][:,(times>=t)&(times<=t+.1)]).sum()/max(L[:,(times>=t)&(times<=t+.1)].sum(),1e-300)) for i,t in enumerate(onsets)])
        new,raw,absolute,absolute_raw=velocities_from(np.sqrt(r['a']),vel,share,absolute=True);vel=new
    return dict(velocity=vel,raw=raw,absolute=absolute,absolute_raw=absolute_raw,share=share,loss=r['loss'],E=r['E'])


def room_calibration(model,notes,ref,duration,velocity,room):
    """Contrast exponent chosen on the loudness envelope with the fitted room applied."""
    from guitar_room_fit import room_impulse
    ir=room_impulse(room['rt_low'],room['rt_high'],room['ratio'])
    target=loudness_envelope(ref);live=target>target.max()-40
    def error(x):d=loudness_envelope(x)[live]-target[live];return float(np.sqrt(np.mean((d-np.median(d))**2)))
    def render(v):x=model.render([dict(n,velocity=float(u)) for n,u in zip(notes,v)],duration);return fftconvolve(x,ir)[:len(x)]
    calibration={g:error(render(V0*(velocity/V0)**g)) for g in (.5,.7,.85,1.,1.2)}
    gamma=min(calibration,key=calibration.get)
    return V0*(velocity/V0)**gamma,dict(gamma=gamma,calibration=calibration,constant_error_db=error(render(np.full(len(notes),float(V0)))),fitted_error_db=calibration[gamma],room=room)


def fit_room_dynamics_long(model,notes,ref,duration,room,window=18.,context=6.,rounds=2):
    """Long pieces, as fit_dynamics_long but with the room; context covers the reverb tail."""
    lv=np.full(len(notes),np.log(V0));raw=lv.copy();share=np.zeros(len(notes));a=0.;windows=[]
    while a<duration-1e-6:
        b=min(duration,a+window);lo=max(0.,a-context);hi=min(duration,b+1.)
        idx=[i for i,n in enumerate(notes) if lo<=n['start']<b]
        if idx:
            local=[dict(notes[i],start=notes[i]['start']-lo,end=min(notes[i]['end'],hi)-lo) for i in idx]
            r=fit_room_dynamics(model,local,ref[round(lo*SR):round(hi*SR)],hi-lo,room,rounds)
            for j,i in enumerate(idx):
                if notes[i]['start']>=a:lv[i]=np.log(r['absolute'][j]);raw[i]=np.log(r['absolute_raw'][j]);share[i]=r['share'][j]
            windows.append(dict(start=a,end=b,notes=sum(notes[i]['start']>=a for i in idx),loss=r['loss']))
            print(f'  window {a:6.1f}–{b:6.1f} s: {windows[-1]["notes"]} notes, loss {r["loss"]:.3f}',flush=True)
        a=b
    velocity=np.minimum(np.exp(lv+np.log(V0)-np.median(lv)),127*CAP)
    velocity,info=room_calibration(model,notes,ref,duration,velocity,room)
    info.update(windows=windows,share=share.tolist());return velocity,info


def main():
    lib,_=library();setup(lib)
    data=json.loads((OUT/'stringlab.json').read_text());perf=next(c for c in data['clips'] if c['id']=='guitar-bach-performance')
    notes=json.loads((OUT/'guitar-bach-performance-events.json').read_text());duration=perf['duration']
    sr,ref=wavfile.read(OUT/'audio/guitar-bach-performance-ref.wav');assert sr==SR;ref=ref.astype(float)/32768
    models=[Model(lib,'nylon / designed body'),Model(lib,'nylon / Gil de Avalle body + loading',5),Model(lib,'nylon / DeVoe body + loading',21)]
    fits={m.name:solve(m,notes,ref,duration) for m in models}
    # Model choice: the body whose fitted mixture best explains the recording, and
    # whose nuisance correction has to bend the spectrum least.
    for name,r in fits.items():r['eq_db_rms']=float(np.sqrt(np.mean((20*np.log10(r['eq']))**2)))
    best=min(models,key=lambda m:fits[m.name]['kl']);r=fits[best.name]
    print('chosen',best.name,{k:(round(v['kl'],4),round(v['eq_db_rms'],2)) for k,v in fits.items()},flush=True)
    if '--write' not in sys.argv:
        np.save(DOC/'.dynamics-fit-preview.npy',dict(fits={k:dict(velocity=v['velocity'],raw=v['raw'],share=v['share'],eq=v['eq'],kl=v['kl']) for k,v in fits.items()}),allow_pickle=True);return
    with_velocity=lambda v:[dict(n,velocity=float(x)) for n,x in zip(notes,v)]
    fixed=best.render(notes,duration);variation=best.render(notes,duration,1)
    # Range calibration. Reverb masks soft onsets, so the flux fit can exaggerate
    # contrast; choose one exponent on the fitted deviations so the rendered loudness
    # envelope (200 ms windows, a different measure from the fit) follows the recording.
    def envelope(x):
        frames=np.lib.stride_tricks.sliding_window_view(x,round(.2*SR))[::round(.05*SR)]
        return 10*np.log10(np.mean(frames**2,axis=1)+1e-12)
    target=envelope(ref);live=target>target.max()-40
    def envelope_error(x):
        d=envelope(x)[live]-target[live];return float(np.sqrt(np.mean((d-np.median(d))**2)))
    calibration={}
    for gamma in (.3,.4,.5,.6,.7,.8,1.):
        v=V0*(r['velocity']/V0)**gamma;calibration[gamma]=envelope_error(best.render(with_velocity(v),duration))
    gamma=min(calibration,key=calibration.get);velocity=V0*(r['velocity']/V0)**gamma
    print('range calibration',{k:round(e,2) for k,e in calibration.items()},'chosen',gamma,flush=True)
    fitted=[dict(n,velocity=float(round(v,1)),velocity_source='fitted to Kowalski recording (model estimate)') for n,v in zip(notes,velocity)]
    dynamic=best.render(fitted,duration)
    for x in (fixed,dynamic,variation):assert np.isfinite(x).all() and len(x)==len(ref) and np.abs(x).max()<10
    # Linearity check: full render vs the sum of separately rendered fitted notes.
    mix=np.sum(templates(best,fitted,velocity,duration),axis=0)
    linear=float(np.linalg.norm(spectrogram(dynamic)-spectrogram(mix))/np.linalg.norm(spectrogram(dynamic)))
    envelope_db=dict(constant=envelope_error(fixed),random_variation=envelope_error(variation),fitted=envelope_error(dynamic))
    # Per-note onset loudness (first 100 ms) against the recording's, as a correlation.
    def onset_db(x):return np.array([10*np.log10(np.mean(x[round(n['start']*SR):round((n['start']+.1)*SR)]**2)+1e-12) for n in notes])
    rn=onset_db(ref);onset_corr={k:float(np.corrcoef(onset_db(x),rn)[0,1]) for k,x in dict(constant=fixed,random_variation=variation,fitted=dynamic).items()}
    print('envelope error dB',{k:round(e,2) for k,e in envelope_db.items()},'onset loudness r',{k:round(e,3) for k,e in onset_corr.items()},'linearity',round(linear,3),flush=True)
    # Standard MIDI cannot hold the louder-than-127 notes; rescale (ratios kept).
    top=max(n['velocity'] for n in fitted)
    mid=OUT/'guitar-bach-dynamics.mid';export_midi([dict(n,velocity=max(1,int(round(n['velocity']*127/top)))) for n in fitted],mid)
    events=OUT/'guitar-bach-dynamics-events.json';events.write_text(json.dumps(fitted,indent=2)+'\n')
    downloads=[dict(label='Fitted-velocity MIDI (loudest = 127)',url=mid.name),dict(label='Fitted velocities / string assignments',url=events.name)]+[d for d in perf['downloads'] if d['url'].endswith(('.musicxml','.pdf'))]
    shared=f'Same Kowalski timing, Apke strings/frets and model ({best.name}, no random variation) throughout. Each note was rendered alone, and note velocities were fitted so the notes\u2019 onsets match the recording\u2019s intensity across frequency, with a separate timbre correction so the model\u2019s tone mismatch is not read as dynamics (that correction is not applied to the audio). The contrast was then scaled to the recording\u2019s loudness envelope. Louder notes also pluck harder, so the string\u2019s tension nonlinearity changes with dynamics. Estimates under this model, not measured finger force; weakly audible notes lean on their neighbours.'
    labels=dict(fitted='Velocities fitted to Kowalski',ref='Real performance · Mateusz Kowalski')
    clips=[write_clip('guitar-bach-dynamics','Guitar · dynamics from the recording','Bach Prelude · fitted note velocities',dict(current=fixed,fitted=dynamic,ref=ref),dict(labels,current='Constant velocity (source MIDI: all 100)'),shared+' A keeps the source MIDI\u2019s constant velocity.','Real recording','Which synth phrases more like the real performance?'),
           write_clip('guitar-bach-character','Guitar · fitted versus random variation','Bach Prelude · where note differences come from',dict(current=variation,fitted=dynamic,ref=ref),dict(labels,current='Random seeded variation (±3.5% level, ±0.012 pluck point)'),shared+' A instead adds the earlier bounded random variation around velocity 100.','Real recording','Which note-to-note variation sounds more like the performance?')]
    for c in clips:c['downloads']=downloads;c['dynamics']=dict(model=best.name,range_exponent=gamma,envelope_error_db=envelope_db,onset_loudness_r=onset_corr)
    ids={c['id'] for c in clips};data['clips']=[c for c in data['clips'] if c['id'] not in ids]+clips
    from string_score_alignment import attach
    data,_=attach(data)   # copies the note-level printed score to these clips
    for c in data['clips']:
        if c['id'] in ids:
            for n,f in zip(c['score']['notes'],fitted):n['velocity']=f['velocity']
    tmp=OUT/'stringlab.tmp';tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(OUT/'stringlab.json')
    db=lambda v:20*EXP*np.log10(np.asarray(v)/V0)
    measures={m:dict(fitted_db=round(float(np.median(db(velocity)[[n['score_measure']==m for n in notes]])),1),raw_db=round(float(np.median(db(V0*(r['raw']/V0)**gamma)[[n['score_measure']==m for n in notes]])),1)) for m in sorted({n['score_measure'] for n in notes})}
    report=dict(method='Analysis-by-synthesis. KL fit of positive band-magnitude flux (1/6-octave, 70 Hz–7 kHz, 35 ms lag), onset-weighted; per-note gain plus global per-band timbre correction and floor; templates re-rendered at the current velocity (3 rounds); velocity = old × gain^(1/1.25); weakly identified notes shrink toward the local trend, ±9 dB limit; median note at velocity 100; contrast exponent chosen on the 200 ms loudness envelope.',
        reference_sha256=hashlib.sha256((OUT/'audio/guitar-bach-performance-ref.wav').read_bytes()).hexdigest(),
        models={k:dict(weighted_kl=v['kl'],timbre_correction_rms_db=v['eq_db_rms']) for k,v in fits.items()},chosen=best.name,
        timbre_correction_db=dict(zip([round(float(c)) for c in CENTRES],[round(float(20*np.log10(e)),2) for e in r['eq']])),
        range_calibration=dict(envelope_error_db_by_exponent=calibration,chosen_exponent=gamma),envelope_error_db=envelope_db,onset_loudness_r=onset_corr,
        template_sum_vs_full_render=linear,measure_median_db=measures,edition_dynamics=dict(f=[1,7],p=[5,11]),
        velocity=dict(min=float(velocity.min()),median=float(np.median(velocity)),max=float(velocity.max())),
        notes=[dict(start=n['start'],pitch=n['pitch'],string=n['string'],fret=n['fret'],measure=n['score_measure'],velocity=f['velocity'],raw_velocity=round(float(V0*(w/V0)**gamma),1),onset_share=round(float(s),3)) for n,f,w,s in zip(notes,fitted,r['raw'],r['share'])],clips=clips)
    (DOC/'guitar-dynamics-report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()


MAX_PLUCK_MM=3.0     # beyond ~3 mm at the plucking point a string buzzes on the frets


def physical_cap(velocity):
    """Fitted pluck strengths above what a string can take (pf_pluck: displacement
    1.5 mm x (velocity/127)^1.25) only make the tension nonlinearity misbehave (pitch
    glides, blooming partials); clip them. Returns (velocity, number clipped)."""
    v=np.asarray(velocity,float);cap=127*(MAX_PLUCK_MM/1.5)**(1/1.25)
    return np.minimum(v,cap),int((v>cap).sum())
