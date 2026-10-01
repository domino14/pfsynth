"""Build reproducible piano/guitar/violin listening experiments, pure-C kernels.

Run: build/body-venv/bin/python tools/stringlab_audition.py
Local audition: build/stringlab/index.html (serve build/stringlab over HTTP).
No production patch or existing audition audio is overwritten.
"""
from pathlib import Path
import ctypes as ct
import hashlib, json, subprocess, time
import numpy as np
from scipy.io import wavfile
from scipy import signal
from mkmidi import write_midi

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/stringlab'; DOC=ROOT/'experiments/string-motion'; SR=44100
P=ct.POINTER(ct.c_float)

def ptr(x): return x.ctypes.data_as(P)
def rms(x): return float(np.sqrt(np.mean(np.asarray(x,dtype=float)**2)))

def library():
    sources=['src/host/stringlab.c','src/host/midi.c']+[f'src/core/pf_{s}.c' for s in ['partial','attack','resonance','motion','pluck','bow','radiation']]
    subprocess.run(['cc','-O2','-std=c99','-Wall','-Wextra','-dynamiclib',*sources,'-o','build/stringlab.dylib'],cwd=ROOT,check=True)
    lib=ct.CDLL(str(ROOT/'build/stringlab.dylib'))
    lib.pf_lab_piano.argtypes=[ct.c_char_p,P,ct.c_int,ct.c_double,ct.c_int]
    lib.pf_lab_pluck.argtypes=[P,ct.c_int,ct.c_double,ct.c_double,ct.c_int,ct.c_int,ct.c_int]
    lib.pf_lab_partial.argtypes=[P,ct.c_int,ct.c_double,ct.c_double,ct.c_double,ct.c_int]
    lib.pf_lab_pluck_energy.argtypes=[ct.c_double,ct.c_double,ct.c_int,ct.c_int];lib.pf_lab_pluck_energy.restype=ct.c_double
    lib.pf_lab_bow_size.restype=ct.c_size_t
    lib.pf_lab_bow_init.argtypes=[ct.c_void_p,ct.c_double,ct.c_double,ct.c_int]
    lib.pf_lab_bow_note.argtypes=[ct.c_void_p,ct.c_double,ct.c_double]
    lib.pf_lab_bow_release.argtypes=[ct.c_void_p]
    lib.pf_lab_bow_process.argtypes=[ct.c_void_p,P,ct.c_int]
    lib.pf_lab_body.argtypes=[P,ct.c_int,ct.c_int]
    return lib,sources

def checks(lib):
    report=[]
    for midi in [21,36,60,84,108]:
        for vel in [.01,1]:
            for cents in [0,3,18]:
                xs=[]
                for block in [127,4096]:
                    x=np.zeros(SR//2,np.float32);lib.pf_lab_partial(ptr(x),len(x),midi,vel,cents,block)
                    assert np.isfinite(x).all();xs.append(x)
                assert np.array_equal(*xs)
    report.append('Piano frequency-motion output is finite and bit-identical across block sizes at keyboard/velocity extremes, 0/3/18 cents.')
    for midi in [40,57,76]:
        for nonlinear in [0,1]:
            xs=[]
            for block in [127,2048]:
                x=np.zeros(SR,np.float32);lib.pf_lab_pluck(ptr(x),len(x),midi,1,SR//2,nonlinear,block);assert np.isfinite(x).all();xs.append(x)
            assert np.array_equal(*xs)
            energy=lib.pf_lab_pluck_energy(midi,1,nonlinear,SR)
            assert 0<=energy<=1.000001,(midi,energy)
    report.append('Linear/nonlinear plucked-string output is finite, block-identical, and total SAV energy decreases after one second at E2/A3/E5.')
    for m in [55,69,88]:
        for expressive in [0,1]:
            xs=[]
            for block in [127,2048]:
                v=ct.create_string_buffer(lib.pf_lab_bow_size());lib.pf_lab_bow_init(v,m,.8,expressive);x=np.zeros(SR,np.float32)
                for i in range(0,len(x),block):lib.pf_lab_bow_process(v,ptr(x[i:]),min(block,len(x)-i))
                assert np.isfinite(x).all() and np.max(np.abs(x))<3;xs.append(x)
            assert np.array_equal(*xs)
    report.append('Bowed-string output is finite and block-identical at G3/A4/E6, with/without expressive controls.')
    return report

def piano(lib,mid,seconds,amount=0,block=512):
    x=np.zeros(round(seconds*SR),np.float32)
    assert lib.pf_lab_piano(str(mid).encode(),ptr(x),len(x),amount,block)==0
    return x

def guitar(lib,score,duration,nonlinear=1,body=True):
    x=np.zeros(round(duration*SR),np.float32)
    for t,m,v,hold in score:
        start=round(t*SR);n=min(len(x)-start,round((hold+.7)*SR));a=np.zeros(n,np.float32)
        lib.pf_lab_pluck(ptr(a),n,m,v/127,round(hold*SR),nonlinear,512);x[start:start+n]+=a
    if body:lib.pf_lab_body(ptr(x),len(x),0)
    return x

def violin(lib,score,duration,expressive=1,body=True):
    x=np.zeros(round(duration*SR),np.float32)
    v=ct.create_string_buffer(lib.pf_lab_bow_size());lib.pf_lab_bow_init(v,score[0][1],score[0][2]/127,expressive)
    schedule=[]
    for t,m,vel,hold in score:schedule.extend([(round(t*SR),'on',m,vel),(round((t+hold)*SR),'off',m,0)])
    schedule.sort(key=lambda e:(e[0],e[1]!='off'))
    pos=0
    for at,typ,m,vel in schedule+[(len(x),'end',0,0)]:
        at=min(at,len(x))
        if at>pos:lib.pf_lab_bow_process(v,ptr(x[pos:]),at-pos);pos=at
        if typ=='on':lib.pf_lab_bow_note(v,m,vel/127)
        elif typ=='off':lib.pf_lab_bow_release(v)
    if body:lib.pf_lab_body(ptr(x),len(x),1)
    return x

def write_clip(id,title,dynamic,audio,labels,description,third='Reference',question='Which sounds more like the reference?'):
    sizes={len(x) for x in audio.values()};assert len(sizes)==1
    matched={k:x.astype(float)/max(rms(x),1e-12) for k,x in audio.items()}
    gain=min(.12,.89/max(np.abs(x).max() for x in matched.values()));urls={};metrics={}
    for k,x in matched.items():
        x*=gain;x[-round(.08*SR):]*=np.linspace(1,0,round(.08*SR))
        assert np.isfinite(x).all() and np.abs(x).max()<=.9
        wav=OUT/'audio'/f'{id}-{k}.wav';wavfile.write(wav,SR,np.round(x*32767).astype(np.int16))
        subprocess.run(['/opt/homebrew/bin/lame','--quiet','-b','192',str(wav),str(wav.with_suffix('.mp3'))],check=True)
        urls[k]=f'audio/{id}-{k}.mp3';metrics[k]=dict(peak_dbfs=float(20*np.log10(np.abs(x).max()+1e-12)),rms_dbfs=float(20*np.log10(rms(x)+1e-12)),sha256=hashlib.sha256(wav.read_bytes()).hexdigest())
    assert max(v['rms_dbfs'] for v in metrics.values())-min(v['rms_dbfs'] for v in metrics.values())<.05
    return dict(id=id,note=title,dynamic=dynamic,split='music',duration=next(iter(sizes))/SR,audio=urls,labels=labels,experiment='Experiment 05 · strings',description=description,thirdLabel=third,question=question,metrics=metrics)

def main():
    (OUT/'audio').mkdir(parents=True,exist_ok=True)
    lib,sources=library(); verified=checks(lib);print('Kernel checks passed',flush=True)
    score=json.loads((ROOT/'experiments/partial-piano/beethoven-score.json').read_text());cut=score['source_cutoff']-score['source_start'];ev=[]
    for n in score['notes']:
        ev.extend([(n['start'],0x90,n['note'],n['velocity']),(min(n['key_release'] if n['key_release'] is not None else cut,cut),0x80,n['note'],0)])
    ev.extend((p['time'],0xB0,64,p['value']) for p in score['pedal_events'] if p['time']<cut)
    ev.extend([(cut,0xB0,64,0),(score['duration']-.01,0xB0,123,0)]);mid=OUT/'beethoven.mid';write_midi(mid,ev)
    a=piano(lib,mid,score['duration']);b=piano(lib,mid,score['duration'],1)
    # Strong zero-motion regression against the unchanged production player.
    subprocess.run(['make','pfrender'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    subprocess.run([str(ROOT/'build/pfrender'),str(mid),str(OUT/'production-check.wav'),'0',str(score['duration']),'--raw'],check=True,stdout=subprocess.DEVNULL)
    sr,prod=wavfile.read(OUT/'production-check.wav');assert sr==SR
    assert np.array_equal(prod,np.round(np.clip(a.astype(float),-1,1)*32767).astype(np.int16))
    verified.append('Zero-motion Beethoven render matches the production pfrender PCM exactly (same events, 512-frame blocks).')
    sr,ref=wavfile.read(ROOT/'calib/pianoteq-ref/closemic/beethoven-op2-no1-ptq.wav');assert sr==SR
    ref=ref.astype(float)/32768
    if ref.ndim>1:ref=ref.mean(axis=1)
    ref=np.pad(ref[:len(a)],(0,max(0,len(a)-len(ref))))
    clips=[write_clip('motion-beethoven','Beethoven · Sonata No. 1','I. Allegro',dict(current=a,fitted=b,ref=ref),dict(current='Current piano',fitted='Measured string motion',ref='Pianoteq Steinway D'),'Same Beethoven events, fitted tone, attack, continuous pedals and sympathetic resonance. B adds a positive, exponentially decaying frequency offset fitted on C2/C3/C4/C5 at two velocities. This is a compact approximation, not the DAFx guitar solver.')]
    print('Beethoven comparison rendered',flush=True)
    # A-note notes/velocities are held out from the C-note motion table.
    ev=[]
    for j,(m,v) in enumerate([(33,48),(33,100),(45,75),(57,100),(69,75)]):
        ev.extend([(j*2.3,0x90,m,v),(j*2.3+1.4,0x80,m,0)])
    mid=OUT/'motion-holdout.mid';write_midi(mid,ev)
    clips.append(write_clip('motion-holdout','Piano · exposed notes','Soft / loud',dict(current=piano(lib,mid,13),fitted=piano(lib,mid,13,1),ref=piano(lib,mid,13,4)),dict(current='Current piano',fitted='Measured string motion',ref='4× motion diagnostic'),'A1, A2, A3 and A4. These pitches and velocity 75 were not used in the motion table. The third version exaggerates the effect; it is not a reference recording.','4× diagnostic','Which piano version do you prefer?'))
    # Original A-minor fingerpicking, four bars, 88 BPM. Avoid borrowed performance data.
    guitar_score=[];beat=60/88
    chords=[[45,52,57,60,64,60,57,52],[41,48,53,57,60,57,53,48],[43,50,55,59,62,59,55,50],[40,47,52,56,59,56,52,47]]
    for bar,chord in enumerate(chords):
        for j,m in enumerate(chord):guitar_score.append(((bar*4+j*.5)*beat,m,[92,65,72,76,84,69,73,62][j],beat*2.4))
    for i,m in enumerate([45,52,57,60,64]):guitar_score.append((16*beat+i*.015,m,88,2.7))
    gd=15
    clips.append(write_clip('guitar-study','Guitar · late afternoon','Fingerpicked nylon',dict(current=guitar(lib,guitar_score,gd,0),fitted=guitar(lib,guitar_score,gd,1),ref=guitar(lib,guitar_score,gd,1,False)),dict(current='Linear string + body',fitted='Nonlinear string + body',ref='Nonlinear string, dry'),'Original fingerpicked study. B adds energy-dependent tension using a SAV modal update. Both share the same analytic body resonances. Body parameters are designed, not fitted to a recorded guitar.','Dry string','Which guitar version do you prefer?'))
    singles=[(0,40,60,2),(3,40,120,2),(6,57,60,2),(9,57,120,2)]
    clips.append(write_clip('guitar-dynamics','Guitar · pluck dynamics','E2 / A3 · soft / hard',dict(current=guitar(lib,singles,12,0),fitted=guitar(lib,singles,12,1),ref=guitar(lib,singles,12,1,False)),dict(current='Linear string + body',fitted='Nonlinear string + body',ref='Nonlinear string, dry'),'Same pluck shape and body. Listen for a stronger initial pitch rise on hard low notes, settling as string energy dissipates.','Dry string','Which guitar version do you prefer?'))
    melody=[(0,69,78,1.2),(1.2,72,82,.6),(1.8,71,72,.6),(2.4,69,80,1.2),(3.6,64,68,1.2),(4.8,67,75,.6),(5.4,69,82,.6),(6,72,87,1.2),(7.2,74,90,.6),(7.8,72,81,.6),(8.4,71,74,.6),(9,69,70,2.5)]
    clips.append(write_clip('violin-study','Violin · evening line','Legato / vibrato',dict(current=violin(lib,melody,13,0),fitted=violin(lib,melody,13,1),ref=violin(lib,melody,13,1,False)),dict(current='Steady bow + body',fitted='Expressive bow + body',ref='Expressive bow, dry'),'Original melody, sustained by a nonlinear bow junction between travelling-wave string segments. B adds delayed vibrato and gentle bow-speed movement. The violin body is an analytic prototype, not a measured instrument.','Dry string','Which violin version do you prefer?'))
    articulated=[(i*.55,m,70+(i%3)*9,.25) for i,m in enumerate([69,71,72,74,76,74,72,71,69,67,64,69])]
    clips.append(write_clip('violin-articulation','Violin · short bows','Detached notes',dict(current=violin(lib,articulated,8,0),fitted=violin(lib,articulated,8,1),ref=violin(lib,articulated,8,1,False)),dict(current='Steady bow + body',fitted='Expressive bow + body',ref='Expressive bow, dry'),'Short bows test starting and stopping the self-sustained string rather than a prerecorded attack.','Dry string','Which violin version do you prefer?'))
    data=dict(clips=clips,sections=4,attribution='Piano reference: user-licensed Pianoteq 6 Steinway D Close Mic Classical. Beethoven MIDI: ASAP/(n)ASAP KimG01, CC BY-NC-SA 4.0; excerpt synthesized/cropped/level matched. Guitar and violin compositions are original; every candidate is generated by portable C kernels, without audio samples.')
    (OUT/'stringlab.json').write_text(json.dumps(data,indent=2)+'\n')
    (DOC/'audition-report.json').write_text(json.dumps(dict(created='2026-09-30',checks=verified,sources={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},motion_patch_sha256=hashlib.sha256((DOC/'motion_patch.h').read_bytes()).hexdigest(),clips=clips),indent=2)+'\n')
    print('Complete:',len(clips),'comparisons;',OUT,flush=True)

if __name__=='__main__':main()
