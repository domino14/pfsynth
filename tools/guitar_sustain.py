"""When a guitarist's hands would stop each string (let strings ring).

Aligned MIDI durations are what was written or what a transcription heard as the note,
not how long the string vibrates: on a guitar a string rings until something stops it.
`let_ring` extends each note's end (never shortens it) to the first of:
  * the next note on the same string (a re-pluck or slur takes over the string);
  * for a fretted note, the moment the left hand must leave: the same finger is needed
    for another note (where the edition gives fingers), or a new fretted note lies
    outside the hand's reach (4 frets from the held one; with a finger number, the
    hand's position p = fret - finger + 1 covers p-1 .. p+4);
  * once its written length is over, a new note that would rub against it: a semitone
    (minor second / major seventh), and for the bass strings (4-6) also a whole tone -
    players damp those, and let consonances ring (open-string campanella);
  * the end of the render.
Stops then use the renderer's existing release (uniform damping, ~0.1 s to -60 dB).
"""
import bisect


def let_ring(notes,duration,reach=4):
    order=sorted(range(len(notes)),key=lambda i:notes[i]['start'])
    starts=[notes[i]['start'] for i in order]
    reasons={}
    for k,i in enumerate(order):
        n=notes[i];written=n['end'];stop=duration;why='rings to the end'
        for j in order[k+1:]:
            m=notes[j]
            if m['start']-n['start']<1e-4:continue                      # same chord
            if m['start']>=stop:break
            if m['string']==n['string']:stop,why=m['start'],'same string played';break
            fretted=n['fret']>0 and not n.get('touch')
            if fretted and m['fret']>0 and not m.get('touch'):
                fn,fm=n.get('finger'),m.get('finger')
                if isinstance(fn,int) and isinstance(fm,int) and 1<=fn<=4 and fn==fm and (m['fret'],m['string'])!=(n['fret'],n['string']):
                    stop,why=m['start'],'finger needed elsewhere';break
                if isinstance(fn,int) and 1<=fn<=4:
                    p=n['fret']-fn+1;out=not (p-1<=m['fret']<=p+4)
                else:out=abs(m['fret']-n['fret'])>=reach
                if out:stop,why=m['start'],'hand moved';break
            if m['start']>=written:
                pc=abs(m['pitch']-n.get('sounding',n['pitch']))%12
                clash={1,11}|({2,10} if n['string']>=4 else set())
                if pc in clash:stop,why=m['start'],'damped against a clash';break
        n['end_written']=written;n['end']=max(written,stop);n['ring_stop']=why;reasons[why]=reasons.get(why,0)+1
    return reasons


if __name__=='__main__':
    import json,sys
    import numpy as np
    from pathlib import Path
    out=Path(__file__).resolve().parents[1]/'build/stringlab'
    for f in sys.argv[1:] or ['guitar-bach-full-events.json','guitar-sonatina-harmonics-events.json']:
        ev=json.loads((out/f).read_text());duration=max(n['end'] for n in ev)+3
        before=np.array([n['end']-n['start'] for n in ev]);r=let_ring(ev,duration);after=np.array([n['end']-n['start'] for n in ev])
        print(f,'| ring median %.2f s -> %.2f s, p90 %.2f -> %.2f |'%(np.median(before),np.median(after),np.percentile(before,90),np.percentile(after,90)),r)
