"""Transfer Apke's published staff fingers and TAB positions to aligned GAPS notes."""
import xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'research/strings/midi/gaps/tw1wc.xml'

def measure_order(part):
    """Performance order of measure indices: simple repeats with 1st/2nd endings unfolded
    (MusicXML semantics; an ending covers the measures from its start to its stop)."""
    ms=part.findall('measure');ending=[None]*len(ms);current=None
    for i,m in enumerate(ms):
        for b in m.findall('barline'):
            e=b.find('ending')
            if e is not None and e.get('type')=='start':current=e.get('number')
        ending[i]=current
        for b in m.findall('barline'):
            e=b.find('ending')
            if e is not None and e.get('type') in ('stop','discontinue'):current=None
    rep=lambda m,d:any((b.find('repeat') is not None and b.find('repeat').get('direction')==d) for b in m.findall('barline'))
    # Exports sometimes close the first ending one bar early, leaving the bar that carries
    # the backward repeat outside it; that bar belongs to the ending (performers skip it).
    for i in range(1,len(ms)):
        if ending[i] is None and ending[i-1] is not None and rep(ms[i],'backward'):ending[i]=ending[i-1]
    order=[];i=0;start=0;used=set();passno=1
    while i<len(ms):
        if rep(ms[i],'forward') and i!=start:start=i;passno=1
        if ending[i] is not None and str(passno) not in ending[i].replace(' ','').split(','):i+=1;continue
        order.append(i)
        if rep(ms[i],'backward') and i not in used:used.add(i);passno+=1;i=start;continue
        i+=1
    return order

def part_notes(part,transpose=0,order=None):
    """Notes in performance order when `order` (measure indices) is given; `written_tick`
    always keeps the position in the score as printed."""
    ms=part.findall('measure');lengths=[];written=[]
    for measure in ms:
        cursor=0;end=0;previous=0
        for node in measure:
            if node.tag=='backup':cursor-=int(node.findtext('duration'))
            if node.tag=='forward':cursor+=int(node.findtext('duration'))
            if node.tag!='note':continue
            duration=int(node.findtext('duration','0'))
            if node.find('chord') is None:cursor+=duration;previous=duration
            end=max(end,cursor)
        written.append(sum(lengths));lengths.append(end)
    out=[];base=0
    for index in (order if order is not None else range(len(ms))):
        measure=ms[index]
        cursor=0;end=0;previous=0;words=None
        for node in measure:
            if node.tag=='direction':words=' '.join(w.text or '' for w in node.iter('words')).strip() or words
            if node.tag=='backup':cursor-=int(node.findtext('duration'))
            if node.tag=='forward':cursor+=int(node.findtext('duration'))
            if node.tag!='note':continue
            duration=int(node.findtext('duration','0'))
            onset=cursor-previous if node.find('chord') is not None else cursor
            pitch=node.find('pitch')
            if pitch is not None:
                midi=12*(int(pitch.findtext('octave'))+1)+dict(C=0,D=2,E=4,F=5,G=7,A=9,B=11)[pitch.findtext('step')]+int(pitch.findtext('alter','0'))+transpose
                # Diatonic staff position of the written note (C0 = 0), for engraving matches.
                diatonic=7*int(pitch.findtext('octave'))+'CDEFGAB'.index(pitch.findtext('step'))
                out.append(dict(tick=base+onset,written_tick=written[index]+onset,pitch=midi,finger=node.findtext('.//fingering'),string=node.findtext('.//string'),fret=node.findtext('.//fret'),measure=measure.get('number'),diatonic=diatonic,words=words,
                    tied=any(t.get('type')=='stop' for t in node.findall('tie')),   # continuation: no new onset
                    arpeggiate=node.find('.//arpeggiate') is not None))
                words=None   # a text direction (e.g. "Harm XII") belongs to the note after it
            if node.find('chord') is None:cursor+=duration;previous=duration
            end=max(end,cursor)
        base+=end
    return sorted(out,key=lambda n:(n['tick'],n['pitch']))

def edition_tuning(source=SOURCE):
    """Open-string MIDI pitches (string 1 first) from the TAB staff; standard if absent."""
    lines={int(t.get('line')):12*(int(t.findtext('tuning-octave'))+1)+dict(C=0,D=2,E=4,F=5,G=7,A=9,B=11)[t.findtext('tuning-step')]+int(t.findtext('tuning-alter') or 0)
           for t in ET.parse(source).getroot().iter('staff-tuning')}
    return [lines[k] for k in sorted(lines,reverse=True)] if len(lines)==6 else [64,59,55,50,45,40]

def apply_edition(notes,source=SOURCE,edition='Apke edition'):
    parts=ET.parse(source).getroot().findall('part');tuning=edition_tuning(source)
    order=measure_order(parts[0])
    staff=part_notes(parts[0],-12,order);tab=part_notes(parts[1],0,order)
    assert len(staff)==len(tab)
    entries=[]
    for a,b in zip(staff,tab):
        assert (a['tick'],a['pitch'])==(b['tick'],b['pitch'])
        entries.append(dict(a,string=int(b['string']),fret=int(b['fret'])))
    # One sounding note written in two voices (same beat, pitch, string and fret)
    # appears once in the performance MIDI: keep a single entry.
    entries=[e for e in entries if not e['tied']]   # tied continuations are not new onsets
    seen=set();entries=[e for e in entries if not ((e['tick'],e['pitch'],e['string'],e['fret']) in seen or seen.add((e['tick'],e['pitch'],e['string'],e['fret'])))]
    remaining=entries[:len(notes)]
    for note in notes:
        # Fine alignment can reorder simultaneous voices by a few ms. Match
        # pitch only within the earliest score onset, never across a later beat.
        tick=remaining[0]['tick']
        matches=[i for i,e in enumerate(remaining) if e['tick']==tick and e['pitch']==note['pitch']]
        if len(matches)!=1:raise ValueError(f'Unambiguous score alignment failed at {note["start"]}: {note["pitch"]}')
        e=remaining.pop(matches[0]);note.update(string=e['string'],fret=e['fret'],score_tick=e['tick'],score_measure=int(e['measure']))
        if e['written_tick']!=e['tick']:note['score_written_tick']=e['written_tick']   # repeated passage
        if e.get('words'):note['score_words']=e['words']
        if e.get('arpeggiate'):note['score_arpeggiate']=True
        note.pop('hand_position',None);note.pop('finger',None)
        if e['finger'] is not None:note['finger']=int(e['finger']);note['finger_source']=edition
        elif e['fret']==0:note['finger']=0;note['finger_source']='open string'
        else:note['finger_source']='not marked in edition'
        assert note['pitch']==tuning[note['string']-1]+note['fret']
    assert not remaining
    return notes
