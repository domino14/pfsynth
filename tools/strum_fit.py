"""Fit strums and rolls to the recording by analysis-by-synthesis.

Note-aligned MIDI can bucket a chord's notes onto one onset (Sonatina III's arpeggiated
final chord has five identical onsets). A peak-picking onset detector made chord timing
worse (its attack pattern correlated less with the recording than GAPS's), so here each
chord is fitted instead: every note is rendered alone and its attack envelope (positive
band-magnitude flux, 60 Hz-2.5 kHz) recorded; for each chord (notes within 30 ms, or
under an arpeggio mark) candidate strums - an offset, a total spread, and upward or
downward order across the strings - shift those envelopes, and the candidate whose
summed attack pattern best correlates with the recording's in the chord's window wins.
GAPS's own timing is always a candidate and a strum must beat it by a margin. Validation
uses a different band (2.5-8 kHz) on a full re-render.

    build/body-venv/bin/python tools/strum_fit.py
"""
import copy,json
import numpy as np
from scipy.io import wavfile
from scipy.signal import stft
from stringlab_audition import ROOT,OUT,SR,library
from string_gesture_audition import setup
from guitar_dynamics_fit import Model

DOC=ROOT/'experiments/string-gestures'
HOP=88;NFFT=1024;MARGIN=.05


def envelope(x,band=(60,2500)):
    f,t,Z=stft(x,SR,nperseg=NFFT,noverlap=NFFT-HOP,boundary=None,padded=False)
    L=np.log(np.abs(Z)+1e-6);m=(f>=band[0])&(f<band[1])
    return np.concatenate([[0],np.maximum(np.diff(L[m],axis=1),0).sum(0)])


def candidates(arp):
    spreads=[0,15,30,50,75,100,150,200,300,400] if arp else [0,10,20,30,45,60,80,100,120]
    offsets=range(-60,301,10) if arp else range(-50,61,10)
    for s in spreads:
        for o in offsets:
            for d in ('up','down') if s else ('up',):yield o/1000,s/1000,d


def mark_arpeggios(notes,xml):
    """Flag notes under an arpeggio mark in the score (events written before the flag existed)."""
    import xml.etree.ElementTree as ET
    from guitar_edition_fingering import part_notes,measure_order
    part=ET.parse(xml).getroot().findall('part')[0]
    marked={(e['tick'],e['pitch']) for e in part_notes(part,-12,measure_order(part)) if e['arpeggiate']}
    for n in notes:
        if (n.get('score_tick'),n['pitch']) in marked:n['score_arpeggiate']=True


def main(clip='guitar-sonatina-harmonics',xml=ROOT/'research/strings/midi/gaps/sonatina3/morel-sonatina3-D1wc.xml'):
    lib,_=library();setup(lib);model=Model(lib,'nylon / Gil de Avalle body + loading',5,True)
    notes=json.loads((OUT/f'{clip}-events.json').read_text());mark_arpeggios(notes,xml)
    print('arpeggio-marked notes:',sum(bool(n.get('score_arpeggiate')) for n in notes),flush=True)
    ref=wavfile.read(OUT/f'audio/{clip}-ref.wav')[1].astype(float);dur=len(ref)/SR
    E=envelope(ref);dt=HOP/SR;frame=lambda s:int(round(s/dt))
    # Each note's attack envelope, rendered alone from 0.05 s before its onset.
    env=[]
    for n in notes:
        span=min(.7,n['end']-n['start']+.3)+.05
        x=model.render([dict(n,start=.05,end=.05+n['end']-n['start'])],span);env.append(envelope(x))
    def placed(i,start,length):
        """Note i's envelope on the global grid at onset `start`, as an array of `length` from frame 0 offset."""
        return frame(start-.05),env[i]
    order=sorted(range(len(notes)),key=lambda i:notes[i]['start']);groups=[];cur=[order[0]]
    for i in order[1:]:
        if notes[i]['start']-notes[cur[0]]['start']<=.03:cur.append(i)
        else:groups.append(cur);cur=[i]
    groups.append(cur)
    groups=[g for g in groups if len(g)>1 or notes[g[0]].get('score_arpeggiate')]
    starts=[n['start'] for n in notes];results=[]
    for g in groups:
        arp=any(notes[i].get('score_arpeggiate') for i in g);t0=min(starts[i] for i in g)
        lo,hi=t0-.15,t0+(.75 if arp else .35);a,b=frame(lo),frame(hi);target=E[a:b]
        if target.std()==0:continue
        background=np.zeros(b-a)
        for k,n in enumerate(notes):
            if k in g or n['start']>hi or n['start']+.7<lo:continue
            s0,e=placed(k,starts[k],b-a);j0=max(a,s0);j1=min(b,s0+len(e))
            if j1>j0:background[j0-a:j1-a]+=e[j0-s0:j1-s0]
        up=sorted(g,key=lambda i:-notes[i]['string'])
        def score(times):
            m=background.copy()
            for i,tm in times.items():
                s0,e=placed(i,tm,b-a);j0=max(a,s0);j1=min(b,s0+len(e))
                if j1>j0:m[j0-a:j1-a]+=e[j0-s0:j1-s0]
            return np.corrcoef(target,m)[0,1] if m.std()>0 else -1
        base={i:starts[i] for i in g};best=(score(base),base,'GAPS timing')
        for o,s,d in candidates(arp):
            seq=up if d=='up' else up[::-1]
            times={i:t0+o+s*k/max(1,len(seq)-1) for k,i in enumerate(seq)}
            c=score(times)
            if c>best[0]+(MARGIN if best[2]=='GAPS timing' else 0):best=(c,times,f'strum {d}, {round(s*1000)} ms, offset {round(o*1000)} ms')
        results.append(dict(time=round(t0,3),notes=len(g),arpeggio=arp,choice=best[2],correlation=round(float(best[0]),3),gaps_correlation=round(float(score(base)),3),
            onsets={str(i):round(float(tm),4) for i,tm in best[1].items()}))
    refined=copy.deepcopy(notes)
    for r in results:
        for i,tm in r['onsets'].items():
            n=refined[int(i)]
            if abs(tm-n['start'])>1e-6:n['start_midi']=n['start'];n['start']=tm;n['end']=max(n['end'],tm+.05);n['onset_source']='strum fitted to the recording'
    # Validation on a different band, full re-renders.
    a=model.render(notes,dur);b=model.render(refined,dur);H=envelope(ref,(2500,8000));Ha=envelope(a,(2500,8000));Hb=envelope(b,(2500,8000))
    changed=[r for r in results if r['choice']!='GAPS timing'];val=[]
    for r in changed:
        w=slice(frame(r['time']-.15),frame(r['time']+(.75 if r['arpeggio'] else .35)))
        if H[w].std()>0:val.append((np.corrcoef(H[w],Ha[w])[0,1],np.corrcoef(H[w],Hb[w])[0,1]))
    val=np.array(val)
    report=dict(method=__doc__.strip().splitlines()[0],groups=len(results),changed=len(changed),
        validation_2_5_8khz=dict(gaps=float(np.nanmean(val[:,0])) if len(val) else None,fitted=float(np.nanmean(val[:,1])) if len(val) else None,better_fraction=float(np.mean(val[:,1]>val[:,0])) if len(val) else None),
        results=results)
    (DOC/f'strum-fit-{clip}.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'{len(results)} chords, {len(changed)} refitted as strums; validation (2.5-8 kHz attacks, full re-render): GAPS {report["validation_2_5_8khz"]["gaps"]:.3f} -> fitted {report["validation_2_5_8khz"]["fitted"]:.3f}, better in {100*report["validation_2_5_8khz"]["better_fraction"]:.0f}%',flush=True)
    for r in results:
        if r['arpeggio'] or r['time'] in (13.1,37.648,12.496,170.658):print('  ',r['time'],r['choice'],r['gaps_correlation'],'->',r['correlation'])
    return refined,report


if __name__=='__main__':main()
