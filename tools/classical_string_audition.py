"""Classical repertoire, playable string assignment and synchronized score data."""
import itertools
import json
import hashlib
import mido
import numpy as np
from stringlab_audition import ROOT,OUT,library,write_clip
from string_gesture_audition import setup,render_guitar,render_violin
from string_hand_geometry import infer,audit

DOC=ROOT/'experiments/string-gestures'
INPUT=ROOT/'research/strings/midi/classical'


def read_notes(path,limit):
    notes=[];active={};t=0;tempo=500000;signature=(4,4)
    for msg in mido.MidiFile(path):
        t+=msg.time
        if msg.type=='set_tempo' and t<.001:tempo=msg.tempo
        if msg.type=='time_signature':signature=(msg.numerator,msg.denominator)
        if msg.type=='note_on' and msg.velocity:
            key=(msg.channel,msg.note);assert key not in active
            active[key]=dict(start=t,pitch=msg.note,velocity=msg.velocity,channel=msg.channel)
        elif msg.type=='note_off' or msg.type=='note_on' and not msg.velocity:
            n=active.pop((msg.channel,msg.note),None)
            if n:n['end']=t;notes.append(n)
    assert not active
    notes.sort(key=lambda n:(n['start'],n['pitch']))
    origin=notes[0]['start']
    for n in notes:n['start']-=origin;n['end']-=origin
    notes=[n for n in notes if n['start']<limit-.00001]
    for n in notes:n['end']=min(n['end'],limit)
    return notes,tempo/1e6,signature


def fingering(notes,violin=False):
    infer(notes,violin)
    for n in notes:
        if violin:n['curve']=[(0,0)]
        else:n.update(bend=[],slides=[],hammer_to=False,mute=False)
    report=audit(notes,violin);assert report['passed'],report
    return notes


def score(notes,kind,title,quarter,meter,url,pickup=0,inferred=True):
    end=max(n['end'] for n in notes);bar=meter*quarter if quarter else 6
    measures=[0]
    if pickup:measures.append(pickup*quarter)
    while measures[-1]+bar<end:measures.append(measures[-1]+bar)
    measures.append(end)
    return dict(kind=kind,title=title,quarter=quarter,meter=meter,pickup=pickup,measures=measures,
                inferred=inferred,source=url,audit=audit(notes,kind=='violin'),notes=[{k:n[k] for k in ['start','end','pitch','string','fret','finger','hand_position','finger_source','score_tick','score_written_tick','score_measure'] if k in n} for n in notes])


def main():
    lib,_=library();setup(lib)
    # Finish on source bar boundaries: first 24 Carcassi bars, first 24 Bach bars.
    gp=INPUT/'carcassi-op60-01.mid';vp=INPUT/'bach/violin-2.mid'
    gn,q,gs=read_notes(gp,36);gn=fingering(gn)
    vn,vq,vs=read_notes(vp,(24*3+.5)*60/130);vn=fingering(vn,True)
    assert gs==(4,4) and vs==(3,4)
    for name,notes in [('carcassi-op60-01',gn),('bach-bwv1002-corrente',vn)]:
        (DOC/(name+'-events.json')).write_text(json.dumps(notes,indent=2)+'\n')
    gd=37;vd=max(n['end'] for n in vn)+1
    ga=render_guitar(lib,gn,gd,True);gb=render_guitar(lib,gn,gd,True,1);gc=render_guitar(lib,gn,gd,True,1,9031)
    print('Carcassi rendered:',len(gn),'notes',flush=True)
    va=render_violin(lib,vn,vd,False);vb=render_violin(lib,vn,vd,False,1)
    expressive=json.loads(json.dumps(vn))
    for n in expressive:
        hold=n['end']-n['start']
        # Score supplies no measured pitch curve. Add designed mild vibrato
        # only to sustained stopped notes; never pretend it is source data.
        n['curve']=[(float(t),float(.12*(1-np.exp(-t/.3))*np.sin(2*np.pi*5.2*t))) for t in np.arange(0,hold,.006)] if n['stopped'] and hold>.3 else [(0,0)]
    vc=render_violin(lib,expressive,vd,True,1)
    print('Bach rendered:',len(vn),'notes',flush=True)
    assert all(np.isfinite(x).all() for x in [ga,gb,gc,va,vb,vc])
    assert not np.array_equal(ga,gb) and not np.array_equal(va,vb)
    gu='https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=13'
    vu='https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=180'
    clips=[write_clip('guitar-carcassi','Guitar · Carcassi Étude No. 1','Op. 60 · first 24 bars',dict(current=ga,fitted=gb,ref=gc),dict(current='Fixed pluck character',fitted='Varying pluck character',ref='Another varied take'),'Carcassi Op.60 No.1, first 24 bars, source MIDI timing at 160 BPM. B adds small pluck-position and excitation variation. The tab displays the inferred string/fret choices actually used by the renderer. No slides or bends were invented.','Another take','Which guitar interpretation do you prefer?'),
           write_clip('violin-bach-corrente','Violin · Bach Corrente','Partita No. 1 · BWV 1002',dict(current=va,fitted=vb,ref=vc),dict(current='Steady bow, fixed character',fitted='Steady bow, varying character',ref='Expressive interpretation'),'Bach Corrente from Partita No.1 BWV1002, first 24 bars plus pickup, source score MIDI at 130 BPM. B varies attack and tone with steady pitch. The third version adds designed mild vibrato on sustained stopped notes. Fingering is inferred; bowing and expression are synth interpretations, not captured performance.','Expressive take','Which violin interpretation do you prefer?')]
    clips[0]['score']=score(gn,'guitar','Carcassi · Op. 60 No. 1',q,4,gu)
    clips[1]['score']=score(vn,'violin','Bach · Corrente, BWV 1002',vq,3,vu,.5)
    data=json.loads((OUT/'stringlab.json').read_text());ids={c['id'] for c in clips}
    data['clips']=[c for c in data['clips'] if c['id'] not in ids]+clips
    # Also give the earlier imported examples synchronized string diagrams.
    for c in data['clips']:
        if c['id'].startswith('guitar-goat'):
            ns=json.loads((DOC/'guitar-goat-events.json').read_text())
            c['score']=score(ns,'guitar','GOAT example 1',60/77,4,'https://github.com/JackJamesLoth/GOAT-Dataset',inferred=False)
        elif c['id'].startswith('violin-wohlfahrt'):
            ns=json.loads((DOC/'violin-wohlfahrt-events.json').read_text())
            c['score']=score(ns,'violin','Wohlfahrt · Op.45 No.8',None,None,'https://zenodo.org/records/13736820')
    data['attribution']+=' Classical repertoire: Mutopia public-domain editions, Carcassi Op.60 No.1 (Jeff Covey) and Bach BWV1002 (Erik Sandberg). Fingering and synth interpretations added locally.' if 'Classical repertoire:' not in data['attribution'] else ''
    tmp=OUT/'stringlab.tmp';tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(OUT/'stringlab.json')
    (DOC/'classical-report.json').write_text(json.dumps(dict(sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [gp,vp]},checks=['All string assignments reproduce MIDI pitches. Simultaneous notes use distinct strings. Outputs finite; varied takes differ.'],clips=clips),indent=2)+'\n')
    print('Classical comparisons and score data ready',flush=True)


if __name__=='__main__':main()
