"""Let the listener choose the guitar body: all 65 measured guitars, the designed body,
or the bare string, applied in the browser.

For each flagship real-performance clip the string signal is rendered once before any
body (no bridge loading), and each body is a short impulse response the page convolves
in real time (WebAudio ConvolverNode). Measured bodies: Mores, Zenodo 4604577, CC BY 4.0
(force -> pressure responses with some room; guitars g34-g44 anechoic). Only radiation
changes with the choice: body-specific bridge damping is not modelled in this mode.
Per body, gains match each version's loudness to the clip's level-matched recording.

    build/body-venv/bin/python tools/guitar_body_choice.py
"""
import ctypes as ct,json,subprocess
import numpy as np
from scipy.io import loadmat,wavfile
from scipy.signal import fftconvolve
from stringlab_audition import ROOT,OUT,SR,library,ptr
from string_gesture_audition import setup,render_guitar
from guitar_material_audition import measured_body

ROOMS={'guitar-bach-dynamics':'guitar-room-fit-refined.json','guitar-sonatina-harmonics':'guitar-room-fit-sonatina-ring.json','guitar-bach-full':'guitar-room-fit-bach-full-ring.json'}
CLIPS={'guitar-bach-dynamics':('guitar-bach-performance-events.json','guitar-bach-dynamics-events.json'),
       'guitar-sonatina-harmonics':(None,'guitar-sonatina-harmonics-events.json'),
       'guitar-bach-full':('guitar-bach-full-plain-events.json','guitar-bach-full-events.json')}
RENDERED='As rendered: Gil de Avalle body with bridge damping'


def plain_from(notes):
    """Sonatina A version: the harmonics played as ordinary 12th-fret notes."""
    out=[]
    for n in notes:
        n=dict(n)
        if 'touch' in n:n.update(pitch=n.pop('sounding'),fret=12);n.pop('touch');n.pop('pluck_position',None)
        out.append(n)
    return out


def rank_bodies(force,ref,irs,room_report):
    """Which body makes the fitted performance sound most like the recording? Each body
    (with the room fitted to that recording) colours the same string signal; rank by
    the distance between long-term 1/6-octave spectra after one overall gain (dB RMS),
    with the frame-by-frame log-spectral distance as a cross-check."""
    from guitar_room_fit import power,room_impulse
    b=json.loads(room_report.read_text())['best'];room=room_impulse(b['rt_low'],b['rt_high'],b['ratio'])
    R=power(ref);ltas_ref=10*np.log10(R.mean(1));live=10*np.log10(R.sum(0))>10*np.log10(R.sum(0)).max()-40
    rows=[]
    for oid,ir in irs.items():
        y=force if ir is None else fftconvolve(force,ir)[:len(force)];y=fftconvolve(y,room)[:len(force)]
        P=power(y);d=10*np.log10(P.mean(1))-ltas_ref;d-=d.mean()
        f=10*np.log10(P[:,live]/R[:,live]);f-=np.median(f)
        rows.append(dict(id=oid,ltas_db=round(float(np.sqrt(np.mean(d**2))),2),frames_db=round(float(np.sqrt(np.mean(np.clip(f,-30,30)**2))),2)))
    return sorted(rows,key=lambda r:r['ltas_db'])


def write_mp3(path,x):
    wav=path.with_suffix('.wav');wavfile.write(wav,SR,np.round(np.clip(x,-1,1)*32767).astype(np.int16))
    subprocess.run(['/opt/homebrew/bin/lame','--quiet','-b','192',str(wav),str(path)],check=True);wav.unlink()


def main():
    lib,_=library();setup(lib)
    meta=json.loads((ROOT/'research/strings/body/guitars.json').read_text())['guitars']
    raw=loadmat(ROOT/'research/strings/body/mores-qualified-selected-impulses.mat')['qualified_selected_impulses']
    (OUT/'bodies').mkdir(exist_ok=True)
    impulse=np.zeros(round(.5*SR),np.float32);impulse[0]=1;lib.pf_lab_body(ptr(impulse),len(impulse),0)
    irs={'none':None,'designed':impulse.astype(float)/np.sqrt(np.sum(impulse.astype(float)**2))}
    options=[dict(id='none',label='Bare string, no body'),dict(id='designed',label='Designed body (two-resonance prototype)',ir='bodies/designed.wav')]
    excluded=[]
    for g in meta:
        if np.isnan(raw[g['index']-1,96000:144000,:]).any():excluded.append(g['id']);continue   # no usable measurement (g07, g30)
        irs[g['id']]=measured_body(raw,g['index'])['impulse'];assert np.isfinite(irs[g['id']]).all()
        label=f"{g['id']} · {g['maker']}{', '+g['year'] if g['year'] else ''} · {g['category']}"+(' · anechoic' if g['room']=='anechoic' else '')
        options.append(dict(id=g['id'],label=label,ir=f"bodies/{g['id']}.wav",wood=g['wood'],place=g['place'],remarks=g.get('remarks','')))
    for f in (OUT/'bodies').glob('*.wav'):f.unlink()
    for o in options:
        if o.get('ir'):wavfile.write(OUT/o['ir'],SR,irs[o['id']].astype(np.float32))
    data=json.loads((OUT/'stringlab.json').read_text());summary={}
    for cid,(a_file,b_file) in CLIPS.items():
        clip=next(c for c in data['clips'] if c['id']==cid)
        b=json.loads((OUT/b_file).read_text());a=json.loads((OUT/a_file).read_text()) if a_file else plain_from(b)
        if a_file:a=[dict(n,velocity=100) for n in a]
        ref=wavfile.read(OUT/f'audio/{cid}-ref.wav')[1].astype(float)/32768;target=np.sqrt(np.mean(ref**2))
        force={}
        for key,notes in (('current',a),('fitted',b)):
            x=render_guitar(lib,notes,clip['duration'],True,0,body=False,material=1,loading=None,velocity_cap=4).astype(float)
            assert np.isfinite(x).all() and len(x)==len(ref)
            x*=.5/np.abs(x).max();x=np.round(x*32767)/32767;force[key]=x
            write_mp3(OUT/f'audio/{cid}-{key}-force.mp3',x)
        gains={};peak=0
        for o in options:
            gains[o['id']]={}
            for key,x in force.items():
                y=x if irs[o['id']] is None else fftconvolve(x,irs[o['id']])[:len(x)]
                g=target/np.sqrt(np.mean(y**2));gains[o['id']][key]=round(float(g),6);peak=max(peak,g*np.abs(y).max())
        headroom=round(min(1.,.95/peak),4)
        ranking=rank_bodies(force['fitted'],ref,irs,ROOT/'experiments/string-gestures'/ROOMS[cid])
        clip['bodyChoice']=dict(force={k:f'audio/{cid}-{k}-force.mp3' for k in force},gains=gains,headroom=headroom,rendered=RENDERED,ranking=ranking,default=ranking[0]['id'],
            note='Each body here is its measured radiation response, applied in your browser; bridge damping is not body-specific in this mode (none applied). Guitars '+' and '.join(excluded)+' are left out: the dataset has no usable measurement for them.')
        summary[cid]=dict(headroom=headroom,peak=round(float(peak),3),closest=ranking[:5])
        print(cid,'headroom',headroom,flush=True)
    data['bodies']=options
    data['attribution']=data['attribution'] if 'Mores' in data['attribution'] else data['attribution']+' Measured guitar bodies: Robert Mores (CC BY 4.0).'
    tmp=OUT/'stringlab.tmp';tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(OUT/'stringlab.json')
    (ROOT/'experiments/string-gestures/guitar-body-choice-report.json').write_text(json.dumps(dict(options=len(options),excluded=excluded,clips=summary),indent=2)+'\n')


if __name__=='__main__':main()
