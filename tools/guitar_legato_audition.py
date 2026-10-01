"""Hammer-on / pull-off test cases: Apke's printed slurs rendered as left-hand legato.

Assumption chosen by the user: the edition's slurs are played as slurs (Kowalski's
actual articulation is unverified). pf_pluck_legato re-expands the ringing string onto
the new length; a hammer-on adds the finger's slam onto the fret (clearance jump,
low-passed by the fingertip contact time), a pull-off adds the leaving finger's
sideways pluck at the old fret. Designed parameters, no reference slurs. Clips:
hammer-ons vs all plucked, then pull-offs added on top of the hammer-ons (one change
per comparison), and exposed slow pairs for each technique.

    build/body-venv/bin/python tools/guitar_legato_audition.py
"""
import json,copy,hashlib
import numpy as np
from stringlab_audition import ROOT,OUT,SR,library,write_clip
from string_gesture_audition import setup,render_guitar
from guitar_dynamics_fit import Model

DOC=ROOT/'experiments/string-gestures'
CLEARANCE=7e-4      # string height above the fret that the finger closes (m), designed
CONTACT=5e-4        # fingertip contact time (s), designed
PULL=6e-4           # sideways pull of the leaving finger in a pull-off (m), designed


def level(x,n):
    a=round(n['start']*SR);b=round((n['start']+min(.1,max(.04,n['end']-n['start'])))*SR)
    return 10*np.log10(np.mean(x[a:b]**2)+1e-20)


def main():
    lib,_=library();setup(lib)
    data=json.loads((OUT/'stringlab.json').read_text())
    dyn=next(c for c in data['clips'] if c['id']=='guitar-bach-dynamics')
    fitted=json.loads((OUT/'guitar-bach-dynamics-events.json').read_text());duration=dyn['duration']
    marks={(n['start'],n['pitch']):n.get('edition_slur') for n in dyn['score']['notes']}
    model=Model(lib,dyn['dynamics']['model'],5,True)
    assert model.name==dyn['dynamics']['model']=='nylon / Gil de Avalle body + loading'
    plucked=model.render(fitted,duration)
    def slur(notes,kind,amount):
        chosen=[]
        for n in notes:
            if marks.get((n['start'],n['pitch']))==kind:
                n.update(transition='legato',legato_amount=amount,legato_contact=CONTACT,articulation=f'{kind} (Apke slur, assumed)');chosen.append(n)
        return chosen
    # Controlled comparison: each slurred note's strength is chosen so that the
    # slurred pair, rendered alone, matches the plucked pair's level over the slurred
    # note's first 100 ms; only the articulation then differs. (The mix is the wrong
    # control: other strings dominate it.) The carried-over vibration alone may match.
    def calibrate(notes,targets):
        errors=[]
        for n in targets:
            source=[m for m in notes if m['string']==n['string'] and m['start']<n['start']][-1];t0=source['start']
            first=dict(source,start=0.,end=source['end']-t0);local=dict(n,start=n['start']-t0,end=n['end']-t0);span=n['end']+.3-t0
            want=level(model.render([first,{k:v for k,v in local.items() if k not in ('transition','legato_amount','legato_contact')}],span),local)
            grid=np.geomspace(5e-5,3e-3,48);got=[level(model.render([first,dict(local,legato_amount=h)],span),local) for h in grid]
            k=int(np.argmin(np.abs(np.array(got)-want)));n['legato_amount']=float(grid[k]);errors.append(got[k]-want)
        return errors
    slurred=copy.deepcopy(fitted);targets=slur(slurred,'hammer-on',CLEARANCE)
    assert len(targets)==3
    errors=calibrate(slurred,targets)
    hammered=model.render(slurred,duration)
    assert np.isfinite(hammered).all()
    # The two renders must differ only on the hammered strings around those notes.
    diff=np.abs(hammered-plucked)>1e-6*np.abs(plucked).max()
    first=np.argmax(diff)/SR
    both=copy.deepcopy(slurred);pulls=slur(both,'pull-off',PULL)
    assert len(pulls)==3
    pull_errors=calibrate(both,pulls)
    pulled=model.render(both,duration)
    assert np.isfinite(pulled).all()
    sr,ref=wavfile_read(OUT/'audio/guitar-bach-performance-ref.wav')
    description=('Same fitted velocities, timing and measured-body model in both. B plays all six slurs Apke marks as left-hand legato. '
        'Hammer-ons (bar 2 E→F♯, bar 8 G♯→B and D♯→E): the ringing string is shortened without a new pluck, and the finger’s slam onto the fret excites it. '
        'Pull-offs (bars 4 and 6 E→D♯ on the 2nd string, bar 10 E→D♯ on the 1st): the string lengthens, and the leaving finger plucks it sideways at the old fret, so the note is bright and thin. '
        'Each slurred note is matched to its fitted plucked level, so only the articulation differs. Assumption: Kowalski slurs these notes (unverified). Designed physics, not fitted.')
    clips=[write_clip('guitar-bach-hammer','Guitar · slurs in context','Bach Prelude · edition slurs as hammer-ons and pull-offs',dict(current=plucked,fitted=pulled,ref=ref),
        dict(current='Every note plucked (fitted dynamics)',fitted='Edition slurs: hammer-ons (bars 2, 8) + pull-offs (bars 4, 6, 10)',ref='Real performance · Mateusz Kowalski'),description,'Real recording','Which sounds closer to the performance at the slurs?'),
        write_clip('guitar-bach-slurs','Guitar · pull-offs in context','Bach Prelude · edition pull-offs added',dict(current=hammered,fitted=pulled,ref=ref),
        dict(current='Edition hammer-ons only (bars 2, 8)',fitted='Hammer-ons + edition pull-offs (bars 4, 6, 10)',ref='Real performance · Mateusz Kowalski'),
        'Both versions play Apke’s three hammer-ons as slurs. B also plays its three pull-offs (bars 4 and 6 E→D♯ on the 2nd string, bar 10 E→D♯ on the 1st) as left-hand legato: the ringing string lengthens without a right-hand pluck, and the leaving finger plucks it sideways at the old fret, close to the string’s new end, so the note is bright and thin. Each pulled note is matched to its fitted plucked level. Assumption: Kowalski slurs these notes (unverified). Designed physics, not fitted.',
        'Real recording','Do the pull-offs sound closer to the performance?')]
    hammer_marks={(n['start'],n['pitch']) for n in targets};pull_marks={(n['start'],n['pitch']) for n in pulls}
    for c,keys in zip(clips,[hammer_marks|pull_marks,hammer_marks|pull_marks]):
        c['score']=copy.deepcopy(dyn['score']);c['downloads']=dyn['downloads'];c['dynamics']=dyn['dynamics']
        for n in c['score']['notes']:
            key=(n['start'],n['pitch'])
            if key in keys:n['legato']='HO' if key in hammer_marks else 'PO'
    # Exposed pairs: the same slurs, slow, on the same strings and frets.
    def exposed(pairs):
        notes=[]
        for k,(string,a,b,fa,fb) in enumerate(pairs):
            t=.3+k*1.9
            notes+=[dict(start=t,end=t+.45,pitch=a,velocity=100,string=string,fret=fa,bend=[],mute=False),dict(start=t+.45,end=t+1.55,pitch=b,velocity=100,string=string,fret=fb,bend=[],mute=False)]
        return notes
    def variants(base,amounts):
        out={}
        for kind in ('pluck','legato','placeholder'):
            notes=copy.deepcopy(base)
            for n,amount in zip(notes[1::2],amounts):
                if kind=='legato':n.update(transition='legato',legato_amount=amount,legato_contact=CONTACT)
                if kind=='placeholder':n.update(transition='hammer')
            out[kind]=notes
        return out
    exposed_levels={}
    for name,pairs,amounts,title,sub,labelb,desc,question in [
        ('guitar-hammer-exposed',[(2,64,66,5,7),(1,68,71,4,7),(1,75,76,11,12),(2,64,63,5,4),(1,76,75,12,11)],[CLEARANCE]*3+[PULL]*2,'Guitar · exposed slurs','Bach slurs, slow · pluck versus hammer-on / pull-off','Second note slurred: three hammer-ons, then two pull-offs',
         'Five slow pairs on the Bach strings and frets. Hammer-ons: E→F♯ (2nd string, frets 5→7), G♯→B (1st, 4→7), D♯→E (1st, 11→12). Then pull-offs: E→D♯ on the 2nd string (frets 5→4, bars 4 and 6) and on the 1st (12→11, bar 10). A plucks both notes; B slurs to the second with fixed designed strengths (hammer-on: 0.7 mm fret clearance, 0.5 ms fingertip contact; pull-off: 0.6 mm sideways pull at the old fret), so its natural level differs from a pluck. The third button is the earlier legato placeholder (a small extra pluck-shaped kick), kept as a diagnostic. No real slur recording is available yet.','Do the slurs sound like hammer-ons and pull-offs?'),
        ('guitar-pulloff-exposed',[(2,64,63,5,4),(1,76,75,12,11)],[PULL]*2,'Guitar · exposed pull-offs','Bars 4/6 and 10 slurs, slow · pluck versus pull-off','Second note pulled off (new legato physics)',
         'Two slow pairs on the Bach strings and frets: E→D♯ on the 2nd string (frets 5→4, bars 4 and 6) and on the 1st string (frets 12→11, bar 10). A plucks both notes; B pulls off to the second with a fixed designed strength (0.6 mm sideways pull at the old fret), so its natural level differs from a pluck. The third button is the earlier legato placeholder, kept as a diagnostic. No real slur recording is available yet.','Does the pull-off sound like a pull-off?')]:
        span=.3+len(pairs)*1.9+.1;v=variants(exposed(pairs),amounts)
        ex={k:model.render(notes,span) for k,notes in v.items()}
        for x in ex.values():assert np.isfinite(x).all()
        exposed_levels[name]={k:[round(level(x,n)-level(ex['pluck'],n),2) for n in v[k][1::2]] for k,x in ex.items()}
        clips.append(write_clip(name,title,sub,dict(current=ex['pluck'],fitted=ex['legato'],ref=ex['placeholder']),
            dict(current='Second note plucked',fitted=labelb,ref='Earlier placeholder legato (diagnostic)'),desc,'Placeholder',question))
    ids={c['id'] for c in clips};data['clips']=[c for c in data['clips'] if c['id'] not in ids]+clips
    tmp=OUT/'stringlab.tmp';tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(OUT/'stringlab.json')
    report=dict(assumption='Edition slurs played as slurs; Kowalski unverified',clearance_m=CLEARANCE,contact_s=CONTACT,pull_m=PULL,
        hammer_notes=[dict(start=n['start'],pitch=n['pitch'],string=n['string'],fret=n['fret'],clearance_mm=round(n['legato_amount']*1e3,3),level_error_db=round(e,3)) for n,e in zip(targets,errors)],
        pull_notes=[dict(start=n['start'],pitch=n['pitch'],string=n['string'],fret=n['fret'],pull_mm=round(n['legato_amount']*1e3,3),level_error_db=round(e,3)) for n,e in zip(pulls,pull_errors)],
        first_sample_differing_s=float(first),exposed_level_vs_pluck_db=exposed_levels,clips=clips,
        kernel_sha256=hashlib.sha256((ROOT/'src/core/pf_pluck.c').read_bytes()).hexdigest())
    (DOC/'guitar-legato-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('hammer_notes','pull_notes','first_sample_differing_s','exposed_level_vs_pluck_db')},indent=1))


def wavfile_read(path):
    from scipy.io import wavfile
    sr,x=wavfile.read(path);assert sr==SR;return sr,x.astype(float)/32768

if __name__=='__main__':main()
