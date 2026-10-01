"""What makes a natural harmonic sound like a harmonic: measured on real guitars.

Each harmonic is compared with an ordinary note at the same sounding pitch on the same
instrument (same session), so the guitar, microphone and room cancel and what remains is
the technique:
  - partial balance: level of partials 2-10 relative to partial 1 (0.15-0.6 s),
  - decay: per-partial decay rate (dB/s, 0.1-1.2 s),
  - attack: high-band (>4 kHz) energy in the first 40 ms relative to the 0.15-0.6 s body,
  - residue: energy between the harmonic's partials (the touched string's other modes)
    relative to partial 1.
Data: Philharmonia guitar samples (classical guitar, CC BY-SA 3.0) and AG-PT-set
(7 steel-string guitars, 6 players, CC BY 4.0; harmonics at frets 12/7/5, paired with
the same string fretted at the same sounding pitch over the soundhole).
Run on the model too (harmonic_fit.py) to compare.

    build/body-venv/bin/python tools/harmonic_measure.py
"""
import collections,csv,glob,json,os,re,subprocess
import numpy as np
from scipy.io import wavfile

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOWN=os.path.join(ROOT,'research/strings/downloads')
DOC=os.path.join(ROOT,'experiments/string-gestures')
NAMES='C C# D D# E F F# G G# A A# B'.split()
K=10
hz=lambda m:440*2**((m-69)/12)


def load(path,sr):
    raw=subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-i',path,'-f','f32le','-ac','1','-ar',str(sr),'-'],capture_output=True).stdout
    return np.frombuffer(raw,np.float32).astype(float)


def spectrum(seg,sr,n=1<<16):
    X=np.abs(np.fft.rfft(seg*np.hanning(len(seg)),n));return X,np.fft.rfftfreq(n,1/sr)


def refine_f0(x,sr,on,f0):
    """Sounding f0 near the label, from the partial-1..5 peaks (strings are slightly sharp)."""
    X,f=spectrum(x[on+int(.1*sr):on+int(.6*sr)],sr,1<<17);best=(-1e9,f0)
    for c in f0*2**(np.arange(-40,41)/1200):
        s=sum(np.log(X[(f>k*c*.995)&(f<k*c*1.005)].max()+1e-12) for k in range(1,6))
        if s>best[0]:best=(s,c)
    return best[1]


def features(x,sr,on,f0,open_f0=None):
    """Features of one note; x mono, on = onset sample, f0 = sounding pitch (Hz)."""
    out={}
    def level(t0,t1,freq):
        seg=x[on+int(t0*sr):on+int(t1*sr)]
        if len(seg)<int(.02*sr):return np.nan
        X,f=spectrum(seg,sr);m=(f>freq*.985)&(f<freq*1.015)
        return 20*np.log10(X[m].max()+1e-12) if m.any() else np.nan
    body=np.array([level(.15,.6,k*f0) for k in range(1,K+1)])
    out['balance']=(body-body[0]).tolist()
    # decay: partial track in 100 ms frames
    times=np.arange(.1,1.2,.05);tracks=np.array([[level(t,t+.1,k*f0) for t in times] for k in range(1,K+1)])
    out['decay_db_s']=[float(np.polyfit(times[np.isfinite(r)],r[np.isfinite(r)],1)[0]) if np.isfinite(r).sum()>4 and r[0]-body[0]>-50 else np.nan for r in tracks]
    def band(t0,t1,lo,hi):
        seg=x[on+int(t0*sr):on+int(t1*sr)];X,f=spectrum(seg,sr,1<<14);m=(f>=lo)&(f<hi);return 10*np.log10(np.mean(X[m]**2)+1e-20)
    out['attack_db']=band(0,.04,4000,12000)-band(.15,.6,4000,12000)
    out['attack_vs_body_db']=band(0,.04,4000,12000)-band(.15,.6,f0*.9,f0*1.1)
    if open_f0:
        # touched-string modes that are not partials of the harmonic (e.g. odd modes at fret 12)
        n=int(round(f0/open_f0));res=[level(.15,.6,m*open_f0) for m in range(1,3*n+1) if m%n and m*open_f0<6000]
        out['residue_db']=float(np.nanmax(res)-body[0]) if res else np.nan
    return out


def philharmonia(sr=44100):
    """Pairs (harmonic, ordinary) at the same sounding pitch; Philharmonia names sounding pitch."""
    D=os.path.join(DOWN,'philharmonia-guitar');notes=collections.defaultdict(dict)
    for p in sorted(glob.glob(D+'/*.mp3')):
        m=re.match(r'guitar_([A-G]s?)(\d)_[\w-]+?_(\w+?)_(harmonics|normal)\.mp3',os.path.basename(p))
        if m:notes[(NAMES.index(m.group(1).replace('s','#'))+12*(int(m.group(2))+1),m.group(4))][m.group(3)]=p
    pairs=[]
    for (pitch,tech),by in sorted(notes.items()):
        if tech!='harmonics' or (pitch,'normal') not in notes:continue
        nb=notes[(pitch,'normal')]
        for dyn,p in by.items():
            q=nb.get(dyn) or nb.get('forte') or next(iter(nb.values()))
            pairs.append(dict(source='Philharmonia',pitch=pitch,dynamic=dyn,harmonic=p,normal=q))
    rows=[]
    for pr in pairs:
        r=dict(source=pr['source'],pitch=pr['pitch'],dynamic=pr['dynamic'])
        for kind in ('harmonic','normal'):
            x=load(pr[kind],sr);on=int(np.argmax(np.abs(x)>.2*np.abs(x).max()));on=max(0,on-int(.005*sr))
            f0=refine_f0(x,sr,on,hz(pr['pitch']));r[kind]=features(x,sr,on,f0)
        rows.append(r)
    return rows


def agpt(max_pairs=None):
    """AG-PT harmonics (frets 12, 7, 5 -> partial 2, 3, 4 of the open string) paired with
    ordinary notes (over the soundhole) on the same string at the same sounding pitch, same
    player, guitar, session and intensity. Fret 12 pairs with fret 12; fret 7 with fret 19
    where the guitar has it."""
    D=os.path.join(DOWN,'ag-pt-set');lab=list(csv.DictReader(open(D+'/note_labels.csv')))
    files={r['filename']:r for r in csv.DictReader(open(D+'/files.csv'))}
    have=lambda f:os.path.exists(os.path.join(D,'techniques_4',f)) or os.path.exists(os.path.join(D,'techniques_7',f))
    path=lambda f:os.path.join(D,'techniques_4',f) if os.path.exists(os.path.join(D,'techniques_4',f)) else os.path.join(D,'techniques_7',f)
    # Same player, guitar, intensity and string; harmonic and ordinary sessions can be on different days.
    key=lambda r:(files[r['audio_file_path']]['player_id'],files[r['audio_file_path']]['guitar_id'],r['playing_intensity'],r['string_number'])
    normal=collections.defaultdict(list)
    for r in lab:
        if r['expressive_technique_id']=='7' and r['pitch_midi']!='None' and have(r['audio_file_path']):normal[key(r)+(int(r['pitch_midi']),)].append(r)
    rows=[];cache={}
    def audio(f):
        if f not in cache:
            if len(cache)>3:cache.pop(next(iter(cache)))
            sr,x=wavfile.read(path(f));x=x.astype(float);x=x.mean(1) if x.ndim>1 else x;cache[f]=(sr,x/(np.abs(x).max()+1e-12))
        return cache[f]
    harm=[r for r in lab if r['expressive_technique_id']=='4' and r['pitch_midi']!='None' and have(r['audio_file_path'])]
    harm.sort(key=lambda r:r['audio_file_path']);onsets=collections.defaultdict(list)
    for q in lab:onsets[q['audio_file_path']].append(float(q['onset_label_seconds']))
    for r in harm:
        op=int(r['string_openpitch_midi']);fret=int(round(12*np.log2(float(r['pitch_midi'])/hz(op))));n={12:2,7:3,5:4}.get(fret)
        if n is None:continue
        sounding=op+int(round(12*np.log2(n)));match=normal.get(key(r)+(sounding,))
        if not match:continue
        row=dict(source='AG-PT',player=files[r['audio_file_path']]['player_id'],guitar=files[r['audio_file_path']]['guitar_id'],intensity=r['playing_intensity'],string=int(r['string_number']),fret=fret,partial=n,pitch=sounding)
        sr,x=audio(r['audio_file_path']);on=int(float(r['onset_label_seconds'])*sr)
        nxt=[t for t in onsets[r['audio_file_path']] if t>float(r['onset_label_seconds'])]
        if nxt and min(nxt)-float(r['onset_label_seconds'])<1.25:continue      # need 1.2 s of clean ring
        f0=refine_f0(x,sr,on,hz(sounding));row['harmonic']=features(x,sr,on,f0,f0/n)
        clean=[q for q in match if not [t for t in onsets[q['audio_file_path']] if 0<t-float(q['onset_label_seconds'])<1.25]]
        if not clean:continue
        q=clean[0];sr,y=audio(q['audio_file_path']);on=int(float(q['onset_label_seconds'])*sr);f0=refine_f0(y,sr,on,hz(sounding));row['normal']=features(y,sr,on,f0,f0/n)
        rows.append(row)
        if max_pairs and len(rows)>=max_pairs:break
    return rows


def contrast(rows):
    """Median harmonic-minus-ordinary differences."""
    d=lambda k,i=None:np.array([(r['harmonic'][k][i] if i is not None else r['harmonic'][k])-(r['normal'][k][i] if i is not None else r['normal'][k]) for r in rows],float)
    med=lambda a:round(float(np.nanmedian(a)),1)
    return dict(n=len(rows),balance_db=[med(d('balance',i)) for i in range(1,K)],decay_db_s=[med(d('decay_db_s',i)) for i in range(K)],
        attack_db=med(d('attack_db')),attack_vs_body_db=med(d('attack_vs_body_db')),
        residue_db=dict(harmonic=med([r['harmonic'].get('residue_db',np.nan) for r in rows]),normal=med([r['normal'].get('residue_db',np.nan) for r in rows])))


def main():
    out={}
    ph=philharmonia();out['philharmonia']=dict(contrast=contrast(ph),rows=ph)
    print('Philharmonia (classical guitar)',json.dumps(out['philharmonia']['contrast']),flush=True)
    ag=agpt();out['agpt']=dict(contrast=contrast(ag),by_partial={n:contrast([r for r in ag if r['partial']==n]) for n in (2,3,4) if any(r['partial']==n for r in ag)},rows=ag)
    print('AG-PT (steel-string)',json.dumps(out['agpt']['contrast']),flush=True)
    for n,c in out['agpt']['by_partial'].items():print(f'  partial {n}:',json.dumps(c),flush=True)
    with open(os.path.join(DOC,'harmonic-measure-report.json'),'w') as f:json.dump(out,f,indent=1,default=lambda v:None if isinstance(v,float) and not np.isfinite(v) else float(v))


if __name__=='__main__':main()


def pluck_point(max_files=None):
    """Where along the string the right hand plucks, from ordinary notes at every fret.

    A pluck at fraction p of the vibrating length comb-filters the partials,
    |sin(k pi p)|/k^2, with a null at partial k when k p is a whole number. If the hand
    stays at a fixed physical distance d from the bridge (fraction of the open string),
    p = d * 2^(fret/12): the nulls move across partials as the fret rises. If p were the
    same at every fret (our renderer's convention), the comb would not depend on the fret.
    Per string and partial, the mean over frets is removed (it holds the body, pickup and
    pitch colouring), and the remaining fret pattern is correlated with both predictions."""
    D=os.path.join(DOWN,'ag-pt-set');lab=list(csv.DictReader(open(D+'/note_labels.csv')))
    folder=os.path.join(D,'techniques_7');present=set(os.listdir(folder)) if os.path.isdir(folder) else set()
    onsets=collections.defaultdict(list)
    for q in lab:onsets[q['audio_file_path']].append(float(q['onset_label_seconds']))
    notes=[r for r in lab if r['expressive_technique_id']=='7' and r['audio_file_path'] in present and r['pitch_midi']!='None']
    by_file=collections.defaultdict(list)
    for r in notes:by_file[r['audio_file_path']].append(r)
    files=sorted(by_file)[:max_files] if max_files else sorted(by_file);out=[]
    for f in files:
        sr,x=wavfile.read(os.path.join(folder,f));x=x.astype(float);x=x.mean(1) if x.ndim>1 else x
        for r in by_file[f]:
            t=float(r['onset_label_seconds']);nxt=[u for u in onsets[f] if u>t]
            if nxt and min(nxt)-t<.35:continue
            on=int(t*sr);op=int(r['string_openpitch_midi']);fret=int(r['pitch_midi'])-op
            seg=x[on+int(.03*sr):on+int(.25*sr)]
            if len(seg)<int(.2*sr):continue
            X,fr=spectrum(seg,sr,1<<16);f0=hz(int(r['pitch_midi']))
            lv=[20*np.log10(X[(fr>k*f0*.98)&(fr<k*f0*1.02)].max()+1e-12) for k in range(1,9)]
            out.append(dict(file=f,string=int(r['string_number']),fret=fret,intensity=r['playing_intensity'],levels=lv))
    return out


def pluck_point_fit(rows):
    """Best d for the fixed-physical-point hypothesis and the fit of both hypotheses."""
    comb=lambda p,k:20*np.log10(np.abs(np.sin(k*np.pi*p))/(k*k)+1e-4)
    groups=collections.defaultdict(list)
    for r in rows:groups[(r['file'],r['string'])].append(r)
    def score(d,physical):
        a=[];b=[]
        for g in groups.values():
            frets=np.array([r['fret'] for r in g]);L=np.array([r['levels'] for r in g])
            if len(set(frets))<8:continue
            p=np.clip(d*2**(frets/12) if physical else np.full(len(frets),d),.02,.98)
            for k in range(2,9):
                m=L[:,k-1]-L[:,0];pred=comb(p,k)-comb(p,1)
                a+=list(m-m.mean());b+=list(pred-pred.mean())
        a=np.array(a);b=np.array(b);return float(np.corrcoef(a,b)[0,1]) if b.std()>0 else 0.,len(a)
    grid=np.round(np.arange(.06,.40,.01),2)
    phys={float(d):score(d,True)[0] for d in grid}
    best=max(phys,key=phys.get)
    return dict(best_d=best,best_r=phys[best],fixed_relative_r=0.0,curve=phys,n=score(best,True)[1],
        note='fixed-relative position predicts no fret dependence after removing the per-partial mean, so its correlation is 0 by construction; r > 0 for the physical hypothesis is the evidence')
