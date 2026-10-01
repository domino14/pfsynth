"""Re-render the harmonic clips with the finger fitted to real harmonics, and compare
against real classical-guitar harmonics.

harmonic_fit.py fits a finger of finite width (pf_pluck_touch_width) to how real
harmonics differ from ordinary notes on the same string (116 steel-string pairs from
AG-PT-set, 29 nylon pairs from the Philharmonia samples). Here:
  * guitar-harmonics-nylon (new): the six 12th-fret harmonics, strings 6 to 1, as the
    earlier point finger (A), the fitted finger (B) and real Philharmonia harmonics;
  * guitar-sonatina-harmonics: the four "Harm XII" notes get the fitted finger (B);
    velocities and everything else are kept;
  * guitar-harmonics-exposed and guitar-capricho-harmonics (debug page): B re-rendered.
Run guitar_body_choice.py, guitar_room_choice.py and stringlab_page.py afterwards.

    build/body-venv/bin/python tools/guitar_harmonics_refit.py
"""
import json,re
import numpy as np
from scipy.io import wavfile
from stringlab_audition import ROOT,OUT,SR,library,write_clip
from string_gesture_audition import setup
from guitar_dynamics_fit import Model
from guitar_harmonics import STANDARD,NODE,touch_at,hz
from harmonic_measure import load

DOC=ROOT/'experiments/string-gestures'
PHIL=ROOT/'research/strings/downloads/philharmonia-guitar'
SLOT=2.4;LEAD=.3


def existing(cid,key):
    return wavfile.read(OUT/f'audio/{cid}-{key}.wav')[1].astype(float)/32768


def touch(finger,string,open_midi,fret):
    return dict(position=touch_at(string,open_midi,fret,finger['offset_mm']*1e-3),rho=finger['rho_per_s'],lift=finger['lift_s'],width=finger['width_fraction'])


def nylon_clip(model,finger,old,fitted=None):
    """12th-fret harmonics on strings 6..1 against the Philharmonia classical-guitar samples.
    A is the fitted finger when B is the exaggerated one, else the earlier point finger."""
    names=['E3','A3','D4','G4','B4','E5'];total=round((LEAD+SLOT*6)*SR)
    ref=np.zeros(total);a=np.zeros(total);b=np.zeros(total);notes=[]
    for k,(s,name) in enumerate(zip(range(6,0,-1),names)):
        x=load(str(PHIL/f'guitar_{name}_very-long_forte_harmonics.mp3'),SR);on=int(np.argmax(np.abs(x)>.2*np.abs(x).max()))
        # start 10 ms before the attack so the onset lands at the slot's time
        seg=x[max(0,on-round(.01*SR)):][:round(SLOT*SR)-round(.01*SR)];at=round((LEAD+k*SLOT)*SR)-round(.01*SR)
        seg=seg*np.concatenate([np.ones(len(seg)-round(.15*SR)),np.linspace(1,0,round(.15*SR))]);ref[at:at+len(seg)]+=seg
        op=STANDARD[s-1];start=LEAD+k*SLOT;end=start+SLOT-.2
        base=dict(start=start,end=end,pitch=op,velocity=100,string=s,fret=0,bend=[],mute=False,sounding=op+12)
        old_note=dict(base,pluck_position=fitted['pluck'],touch=touch(fitted,s,op,12)) if fitted else dict(base,pluck_position=.12,touch=dict(position=touch_at(s,op,12,old['offset_mm']*1e-3),rho=old['rho_per_s'],lift=old['lift_s']))
        new_note=dict(base,pluck_position=finger['pluck'],touch=touch(finger,s,op,12))
        notes.append(new_note)
        w=slice(round(start*SR),round((start+SLOT)*SR))
        for out,n in ((a,old_note),(b,new_note)):
            y=model.render([dict(n,start=.01,end=n['end']-n['start']+.01)],SLOT+.01)[:w.stop-w.start+round(.01*SR)][round(.01*SR):]
            # level-match each note to the recorded one (the recordings set the balance across strings)
            y*=np.sqrt(np.mean(ref[w]**2)/max(np.mean(y**2),1e-30));out[w.start:w.start+len(y)]+=y
    if fitted:
        desc=('Six natural harmonics touched over the 12th fret, low E string to high E, each against a real one played on a classical guitar (Philharmonia Orchestra samples, CC BY-SA 3.0). '
            f'A is the finger fitted to real harmonics ({fitted["width_mm_on_650"]:.0f} mm effective contact, lifted after {fitted["lift_s"]*1000:.0f} ms); B exaggerates it at your request: {finger.get("scale",1)}× the contact width ({finger["width_mm_on_650"]:.0f} mm) and touch time ({finger["lift_s"]*1000:.0f} ms), so the harmonic is purer — partials 2–4 about as weak, relative to an ordinary note, as on real steel-string guitars, and purer than any recording above that. '
            'The fit used how real harmonics differ from ordinary notes at the same pitch on the same string (116 pairs on 7 steel-string guitars from AG-PT-set, 29 nylon pairs from these samples). Each note is level-matched to the recorded one. Nylon strings, measured Gil de Avalle body, no room.')
        return write_clip('guitar-harmonics-nylon','Guitar · harmonics against real ones','12th-fret harmonics, strings 6 to 1 · Philharmonia classical guitar',
            dict(current=a,fitted=b,ref=ref),dict(current='Fitted finger',fitted=f'Exaggerated ({finger.get("scale",1)}× wider, longer touch)',ref='Real harmonics · classical guitar (Philharmonia)'),
            desc,'Real harmonics','Which sounds more like real harmonics, and is B too much?'),notes
    desc=('Six natural harmonics touched over the 12th fret, low E string to high E, each against a real one played on a classical guitar (Philharmonia Orchestra samples, CC BY-SA 3.0). '
        'A is the earlier model: a point-sized finger at the node, lifted after 50 ms, plucked near the bridge. B is the finger fitted to real harmonics: '
        f'{finger["width_mm_on_650"]:.0f} mm of contact (an effective width), damping {finger["rho_per_s"]:.0f}/s, {finger["offset_mm"]:.0f} mm off the node, lifted after {finger["lift_s"]*1000:.0f} ms, plucked where the hand plucks ordinary notes. '
        'It was fitted to how real harmonics differ from ordinary notes at the same pitch on the same string (116 pairs on 7 steel-string guitars from AG-PT-set, 29 nylon pairs from these samples): '
        'their partials above the second are 14–27 dB weaker, their upper partials ring longer, and their pluck click is about 10 dB softer. Each note is level-matched to the recorded one. Nylon strings, measured Gil de Avalle body, no room.')
    return write_clip('guitar-harmonics-nylon','Guitar · harmonics against real ones','12th-fret harmonics, strings 6 to 1 · Philharmonia classical guitar',
        dict(current=a,fitted=b,ref=ref),dict(current='Earlier model (point finger)',fitted='Fitted finger',ref='Real harmonics · classical guitar (Philharmonia)'),
        desc,'Real harmonics','Which sounds more like the real harmonics?'),notes


def main():
    lib,_=library();setup(lib);model=Model(lib,'nylon / Gil de Avalle body + loading',5,True)
    fit=json.loads((DOC/'harmonic-fit-report.json').read_text());fitted=fit['finger']
    finger=fit[fit['finger_used']] if fit.get('finger_used') else fitted        # 'exaggerated' at the user's request
    old=json.loads((DOC/'guitar-harmonics-report.json').read_text())['calibration']
    print('finger',finger,flush=True)
    data=json.loads((OUT/'stringlab.json').read_text());clips={c['id']:c for c in data['clips']};new=[]
    nylon,nylon_notes=nylon_clip(model,finger,old,fitted if finger is not fitted else None);new.append(nylon)
    # Sonatina: the four harmonics get the fitted finger; nothing else changes.
    cid='guitar-sonatina-harmonics';path=OUT/f'{cid}-events.json';notes=json.loads(path.read_text())
    for n in notes:
        if 'touch' in n:
            n.update(pluck_position=finger['pluck'],touch=touch(finger,n['string'],n['pitch'],12))
            # Show-off level at the user's request: pluck harder than the fitted velocity.
            n.setdefault('velocity_fitted',n['velocity']);n['velocity']=round(n['velocity_fitted']*finger.get('velocity_boost',1),1)
    path.write_text(json.dumps(notes,indent=2,default=float)+'\n')
    old_clip=clips[cid];b=model.render(notes,old_clip['duration'])
    c=write_clip(cid,old_clip['note'],old_clip['dynamic'],dict(current=existing(cid,'current'),fitted=b,ref=existing(cid,'ref')),old_clip['labels'],
        re.sub(r'\(a finger of \d+ mm effective width[^)]*\)|\(finger damping, lift time and placement calibrated on recorded electric-guitar harmonics\)',
            f'(a finger fitted to 145 recorded harmonics against ordinary notes on the same strings, then exaggerated at your request to {finger.get("scale",1)}× its contact width, {finger["width_mm_on_650"]:.0f} mm, and touch time, {finger["lift_s"]*1000:.0f} ms, plucked nearer the bridge (at {finger["pluck"]:.2f} of the string, which gives the recording’s strong octave partial) and {finger.get("velocity_boost",1)}× harder than fitted, to show them off; see the “harmonics against real ones” clip)',old_clip['description']).replace('near the bridge ',''),
        old_clip['thirdLabel'],old_clip['question'])
    c.update({k:v for k,v in old_clip.items() if k not in c});new.append(c)
    # Debug-page clips: re-render B with the fitted finger.
    rep=json.loads((DOC/'guitar-harmonics-report.json').read_text())
    if 'guitar-harmonics-exposed' in clips:
        ex=[dict(n) for n in rep['exposed_notes']]
        for n in ex:
            fret={v:k for k,v in NODE.items()}[round(1/n['touch']['position'])];n.update(pluck_position=finger['pluck'],touch=touch(finger,n['string'],n['pitch'],fret))
        o=clips['guitar-harmonics-exposed'];b=model.render(ex,o['duration'])
        e=write_clip(o['id'],o['note'],o['dynamic'],dict(current=existing(o['id'],'current'),fitted=b,ref=existing(o['id'],'ref')),dict(o['labels'],fitted='Natural harmonics (exaggerated fitted finger)' if finger is not fitted else 'Natural harmonics (fitted finger)'),
            o['description'].replace('with the touch damping, lift time and placement calibrated on 36 recorded harmonics','with the finger fitted to 145 real harmonics against ordinary notes (width, damping, lift time, placement)').replace('plucks the open string near the bridge','plucks the open string'),o['thirdLabel'],o['question'])
        e.update({k:v for k,v in o.items() if k not in e});new.append(e)
    if 'guitar-capricho-harmonics' in clips:
        from guitar_harmonics import capricho
        _,harm,_,_,span=capricho(dict(offset=old['offset_mm']*1e-3,rho=old['rho_per_s'],lift=old['lift_s']))
        for n in harm:
            if 'written' in n:n.update(pluck_position=finger['pluck'],touch=touch(finger,n['string'],n['pitch'],7))
        o=clips['guitar-capricho-harmonics'];b=model.render(harm,o['duration'])
        e=write_clip(o['id'],o['note'],o['dynamic'],dict(current=existing(o['id'],'current'),fitted=b,ref=existing(o['id'],'ref')),dict(o['labels'],fitted='Natural harmonics (exaggerated fitted finger)' if finger is not fitted else 'Natural harmonics (fitted finger)'),
            o['description'].replace('plucks the open strings near the bridge with the calibrated finger touch','plucks the open strings with the finger fitted to real harmonics'),o['thirdLabel'],o['question'])
        e.update({k:v for k,v in o.items() if k not in e});new.append(e)
    ids={c['id'] for c in new};order=[c['id'] for c in data['clips']]
    data['clips']=[next(x for x in new if x['id']==c['id']) if c['id'] in ids else c for c in data['clips']]+[c for c in new if c['id'] not in order]
    if 'Philharmonia' not in data['attribution']:
        data['attribution']+=' Real harmonics: Philharmonia Orchestra guitar samples (CC BY-SA 3.0); harmonic fit also on AG-PT-set (CC BY 4.0), local.'
    tmp=OUT/'stringlab.tmp';tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(OUT/'stringlab.json')
    (DOC/'guitar-harmonics-refit.json').write_text(json.dumps(dict(finger=finger,clips=sorted(ids),nylon_notes=nylon_notes),indent=2,default=float)+'\n')
    print('re-rendered',sorted(ids),flush=True)


if __name__=='__main__':main()
