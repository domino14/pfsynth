"""Natural harmonics: a finger-touch model calibrated on recorded harmonics, and test clips.

Physics (pf_pluck_touch): the left finger lightly touching the string over a node is a
point dashpot; modes with a node under it ring on, the others drain. Calibrated on real
natural harmonics by matching how the open-string fundamental falls relative to the
harmonic partial over the first half second. That is a per-partial change over time,
so pickup / microphone colouring cancels. References are electric guitars
(Guitar-TECHS, CC BY 4.0; IDMT-SMT-Guitar, CC BY-NC-ND 4.0, local only), not nylon:
the finger's damping rate and placement are assumed to carry over.

    build/body-venv/bin/python tools/guitar_harmonics.py
"""
import ctypes as ct,copy,hashlib,io,itertools,json,shutil,zipfile
import xml.etree.ElementTree as ET
import numpy as np
import mido
from fractions import Fraction
from scipy.io import wavfile
from scipy.signal import butter,sosfiltfilt,hilbert,resample_poly
from stringlab_audition import ROOT,OUT,SR,library,write_clip,ptr
from string_gesture_audition import setup
from string_hand_geometry import infer,audit
from guitar_dynamics_fit import Model

DOC=ROOT/'experiments/string-gestures'
TECHS=ROOT/'research/strings/downloads/P1_techniques.zip'
IDMT=ROOT/'research/strings/downloads/idmt-smt-guitar'
MUTOPIA=ROOT/'research/strings/scores/mutopia'
STANDARD=[64,59,55,50,45,40]          # open strings, string 1 first
NODE={12:2,7:3,5:4,4:5}               # touched fret -> partial that survives
TIMES=[.015,.03,.06,.12,.25,.5]       # s after onset
FLOOR=-45                             # dB; below this both curves are noise / irrelevant
PLUCK=.12                             # harmonics are plucked nearer the bridge (designed)
SCALE=.65


def hz(midi):return 440*2**((midi-69)/12)


def touch_at(string,open_midi,fret,offset):
    """Players find the node (1/n of the string), not the fret wire: for fret 4 the
    wire is 4 mm from the node and recorded 4th-fret harmonics are nearly as pure as
    the others. `offset` (m) is the calibrated placement error along the string."""
    length=SCALE*hz(STANDARD[string-1])/hz(open_midi)
    return 1/NODE[fret]+offset/length


def curve(x,sr,onset,f0,n):
    """Fundamental minus harmonic partial (dB) at TIMES, relative to 5 ms after onset."""
    x=np.concatenate([np.zeros(sr),x,np.zeros(sr)]);onset+=1
    seg=x[round((onset-.05)*sr):round((onset+1.2)*sr)]
    def env(f,bw):return np.abs(hilbert(sosfiltfilt(butter(4,[f*(1-bw),f*(1+bw)],'bandpass',fs=sr,output='sos'),seg)))
    e1,en=env(f0,.2),env(n*f0,.08)
    rel=lambda t:20*np.log10((e1[round((.05+t)*sr)]+1e-12)/(en[round((.05+t)*sr)]+1e-12))
    base=rel(.005);return [max(FLOOR,rel(t)-base) for t in TIMES]


def techs(name):
    with zipfile.ZipFile(TECHS) as z:sr,x=wavfile.read(io.BytesIO(z.read(f'P1_techniques/audio/{name}')))
    x=x.astype(float);x=x.mean(1) if x.ndim>1 else x;return sr,x/np.abs(x).max()


def techs_onsets(x,sr):
    """24 natural harmonics on a 4 s grid: low E to high E, touched frets 5, 7, 4, 12."""
    env=np.sqrt(np.convolve(x**2,np.ones(240)/240,'same'));out=[]
    for k in range(24):
        a=max(0,round((k*4-.3)*sr));b=round((k*4+3.8)*sr);seg=env[a:b]
        out.append(dict(onset=(a+np.argmax(seg>.2*seg.max()))/sr,string=6-k//4,fret=[5,7,4,12][k%4]))
    return out


def references():
    notes=[]
    sr,x=techs('directinput/directinput_Harmonics.wav')
    for e in techs_onsets(x,sr):
        notes.append(dict(e,source='Guitar-TECHS',curve=curve(x,sr,e['onset'],hz(STANDARD[e['string']-1]),NODE[e['fret']])))
    for name in ('FS_NH_IV','FS_NH_VII'):
        sr,x=wavfile.read(IDMT/f'{name}.wav');x=x.astype(float);x/=np.abs(x).max()
        root=ET.parse(IDMT/f'{name}.xml').getroot();tuning=[int(v) for v in root.findtext('.//instrumentTuning').split()]
        for e in root.iter('event'):
            string=int(e.findtext('stringNumber'));fret=int(e.findtext('fretNumber'));onset=float(e.findtext('onsetSec'))
            notes.append(dict(source='IDMT '+name,onset=onset,string=7-string,fret=fret,
                curve=curve(x,sr,onset,hz(tuning[string-1]),NODE[fret])))
    return notes


def median_by_node(notes):
    return {f:np.median([n['curve'] for n in notes if n['fret']==f],axis=0) for f in NODE}


class Lab:
    def __init__(self,lib):self.lib=lib
    def harmonic(self,string,fret,rho,lift,offset,open_midi=None,seconds=1.25):
        """One open-string natural harmonic, string output only (no body)."""
        lib=self.lib;st=ct.create_string_buffer(lib.pf_lab_string_size());midi=open_midi or STANDARD[string-1]
        lib.pf_lab_string_material(st,midi,.7,string,PLUCK,1);lib.pf_lab_string_touch(st,touch_at(string,midi,fret,offset),rho)
        out=np.zeros(round(seconds*SR),np.float32);at=round(lift*SR)
        for a in range(0,len(out),64):
            if a<=at<a+64:lib.pf_lab_string_touch(st,0,0)
            lib.pf_lab_string_process(st,ptr(out[a:a+64]),min(64,len(out)-a))
        return out.astype(float)


def calibrate(lab,target):
    grid=dict(rho=np.geomspace(150,1200,7),lift=[.03,.04,.05,.065,.08,.1,.13],offset=[0,5e-4,1e-3,1.5e-3,2e-3,3e-3,4e-3])
    best=None;table=[]
    for rho,lift,offset in itertools.product(*grid.values()):
        model={f:np.median([curve(lab.harmonic(s,f,rho,lift,offset),SR,0,hz(STANDARD[s-1]),NODE[f]) for s in range(1,7)],axis=0) for f in NODE}
        err=float(np.mean([np.abs(model[f]-target[f]).mean() for f in NODE]))
        table.append(dict(rho=float(rho),lift=lift,offset_mm=offset*1e3,error_db=err))
        if best is None or err<best[0]:best=(err,dict(rho=float(rho),lift=lift,offset=offset),model)
    return best,table


def exposed_clip(lab,model,cal,ref_notes):
    """D-string harmonics at the Guitar-TECHS timing, against its recording."""
    sr,mic=techs('micamp/micamp_Harmonics.wav');_,di=techs('directinput/directinput_Harmonics.wav')
    take=[e for e in techs_onsets(di,sr) if e['string']==4]
    t0=take[0]['onset']-.3;span=take[-1]['onset']-t0+3.6
    ref=mic[round(t0*sr):round((t0+span)*sr)+sr];r=Fraction(SR,sr);ref=resample_poly(ref,r.numerator,r.denominator)[:round(span*SR)]
    ref[-round(.08*SR):]*=np.linspace(1,0,round(.08*SR))
    harm,plain=[],[]
    for k,e in enumerate(take):
        start=e['onset']-t0;end=(take[k+1]['onset']-t0-.05) if k+1<len(take) else span-.1
        n=NODE[e['fret']];sounding=STANDARD[3]+12*np.log2(n)
        harm.append(dict(start=start,end=end,pitch=STANDARD[3],velocity=100,string=4,fret=0,bend=[],mute=False,pluck_position=PLUCK,
            touch=dict(position=touch_at(4,STANDARD[3],e['fret'],cal['offset']),rho=cal['rho'],lift=cal['lift']),sounding=float(sounding)))
        p=round(sounding);s=next(s for s in range(1,7) if 0<=p-STANDARD[s-1]<=15)
        plain.append(dict(start=start,end=end,pitch=p,velocity=100,string=s,fret=p-STANDARD[s-1],bend=[],mute=False))
    a=model.render(plain,span);b=model.render(harm,span)
    return write_clip('guitar-harmonics-exposed','Guitar · exposed harmonics','D string, frets 5, 7, 4, 12 · ordinary notes versus touched harmonics',
        dict(current=a,fitted=b,ref=ref),dict(current='Same pitches as ordinary plucked notes',fitted='Natural harmonics (finger-touch physics)',ref='Real harmonics · electric guitar (Guitar-TECHS)'),
        'Four natural harmonics on the open D string, touched over frets 5, 7, 4 and 12, at the timing of a real recording. A plays the same sounding pitches as ordinary fretted notes (what a plain MIDI renderer does); B plucks the open string near the bridge while a finger lightly touches the node, then lifts it, with the touch damping, lift time and placement calibrated on 36 recorded harmonics. The third button is that recording: an electric guitar through a miked amp, so judge the harmonic mechanism (purity, the brief onset thump, the 4th-fret harmonic’s weakness), not the timbre. Nylon strings, measured Gil de Avalle body.',
        'Real harmonics (electric)','Which sounds more like real harmonics?'),harm


def capricho(cal):
    """Bars 1–8 of the Mutopia MIDI (score timing). Bars 1 and 5 open with a fret-7
    harmonic chord on strings 6 (tuned to D), 5 and 4 (LilyPond source lines 131/256)."""
    m=mido.MidiFile(MUTOPIA/'capricho-arabe.mid');tpb=m.ticks_per_beat;tempo=next(x.tempo for x in m.tracks[0] if x.type=='set_tempo')
    sec=lambda tick:tick/tpb*tempo/1e6;bar=3*tpb;notes=[];on={};tick=0
    for x in m.tracks[1]:
        tick+=x.time
        if x.type=='note_on' and x.velocity:on[x.note]=(tick,x.velocity)
        elif x.type in ('note_off','note_on') and x.note in on:
            a,v=on.pop(x.note)
            if a<8*bar:notes.append(dict(start=sec(a),end=sec(tick),pitch=x.note,velocity=v,tick=a,beats=(tick-a)/tpb))
    notes.sort(key=lambda n:(n['start'],n['pitch']));tuning=[64,59,55,50,45,38]
    harmonic={45:6,52:5,57:4}   # written (touched-fret) pitch -> string; touched over fret 7
    marked=[n for n in notes if n['tick']%(4*bar)==0 and n['beats']==3 and n['pitch'] in harmonic]
    assert len(marked)==6 and {n['tick']//bar for n in marked}=={0,4}
    for n in marked:
        s=harmonic[n['pitch']];n.update(written=n['pitch'],string=s,fret=0,pitch=tuning[s-1],sounding=tuning[s-1]+19.02,harmonic='fret 7 (Mutopia: harm. 7)')
    rest=[n for n in notes if 'written' not in n];infer(rest,tuning=tuning)
    report=audit(rest,tuning=tuning);assert report['passed'],report
    for n in notes:
        n.update(bend=[],slides=[],hammer_to=False,mute=False);n.pop('tick');n.pop('beats')
    harm=copy.deepcopy(notes);plain=copy.deepcopy(notes);open_=copy.deepcopy(notes)
    for n in harm:
        if 'written' in n:n.update(pluck_position=PLUCK,touch=dict(position=touch_at(n['string'],n['pitch'],7,cal['offset']),rho=cal['rho'],lift=cal['lift']))
    # Ordinary-note version: the harmonic chord's sounding pitches, fingered with the rest.
    chord=[n for n in plain if 'written' in n]
    for n in chord:n['pitch']=round(n.pop('sounding'));[n.pop(k) for k in ('written','harmonic','string','fret')]
    infer(plain,tuning=tuning);assert audit(plain,tuning=tuning)['passed']
    return notes,harm,plain,open_,max(n['end'] for n in notes)+1.5


def main():
    lib,_=library();setup(lib);lab=Lab(lib)
    refs=references();target=median_by_node(refs)
    print('reference medians (dB at',TIMES,')',{f:np.round(v,1).tolist() for f,v in target.items()},flush=True)
    (err,cal,model_curves),table=calibrate(lab,target)
    print('calibration',cal,'mean error %.2f dB'%err,{f:np.round(v,1).tolist() for f,v in model_curves.items()},flush=True)
    body=Model(lib,'nylon / Gil de Avalle body + loading',5,True)
    clips=[];exposed,exposed_notes=exposed_clip(lab,body,cal,refs);clips.append(exposed)
    notes,harm,plain,open_,span=capricho(cal)
    a=body.render(plain,span);b=body.render(harm,span);c=body.render(open_,span)
    for x in (a,b,c):assert np.isfinite(x).all()
    shutil.copyfile(MUTOPIA/'capricho-arabe-a4.pdf',OUT/'scores/mutopia-capricho-arabe.pdf')
    clip=write_clip('guitar-capricho-harmonics','Guitar · harmonics in context','Tárrega, Capricho Árabe, bars 1–8 · score timing',dict(current=a,fitted=b,ref=c),
        dict(current='Harmonic chords as ordinary notes',fitted='Natural harmonics (finger-touch physics)',ref='Same strings plucked open, no touch (diagnostic)'),
        'Bars 1 and 5 open with a three-note harmonic chord touched over fret 7 on strings 6 (tuned to D), 5 and 4, sounding A3, E4 and A4 (the Mutopia MIDI plays the touched-fret pitches an octave and a fifth too low; they are converted). A plays those sounding pitches as ordinary fretted notes; B plucks the open strings near the bridge with the calibrated finger touch; the third button plucks the same open strings untouched, to hear what the touch removes. Score timing at the MIDI’s 90 bpm, no performance dynamics; other strings and frets inferred for the scordatura. Measured Gil de Avalle body. The 6th string in D is modelled as a longer string at E-string tension.',
        'No touch','Do the harmonic chords sound like real harmonics?')
    clip['downloads']=[dict(label='Mutopia score PDF (CC BY-SA 4.0)',url='scores/mutopia-capricho-arabe.pdf')];clips.append(clip)
    data=json.loads((OUT/'stringlab.json').read_text());ids={c['id'] for c in clips}
    data['clips']=[c for c in data['clips'] if c['id'] not in ids]+clips
    if 'Guitar-TECHS' not in data['attribution']:
        data['attribution']+=' Harmonics references: Guitar-TECHS (Pedroza et al., CC BY 4.0) and IDMT-SMT-Guitar (Fraunhofer IDMT, CC BY-NC-ND 4.0), local calibration only. Capricho Árabe: Mutopia Project (CC BY-SA 4.0).'
    tmp=OUT/'stringlab.tmp';tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(OUT/'stringlab.json')
    report=dict(method='Fundamental minus harmonic-partial level (band envelopes) at '+str(TIMES)+' s, relative to 5 ms after onset, floor '+str(FLOOR)+' dB; median per touched fret over 6 strings; model = open nylon strings (no body) plucked at '+str(PLUCK)+' with a point-dashpot finger at the node + placement error; grid search.',
        references=[{k:v for k,v in n.items()} for n in refs],reference_median=dict((str(f),v.tolist()) for f,v in target.items()),
        calibration=dict(rho_per_s=cal['rho'],lift_s=cal['lift'],offset_mm=cal['offset']*1e3,mean_error_db=err),
        model_median=dict((str(f),v.tolist()) for f,v in model_curves.items()),grid=table,
        capricho_notes=[{k:v for k,v in n.items() if k!='touch'} for n in harm],exposed_notes=exposed_notes,clips=clips,
        kernel_sha256=hashlib.sha256((ROOT/'src/core/pf_pluck.c').read_bytes()).hexdigest())
    (DOC/'guitar-harmonics-report.json').write_text(json.dumps(report,indent=2,default=float)+'\n')


if __name__=='__main__':main()
