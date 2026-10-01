"""Export fitted guitar performances for the public demo (docs/guitar/).

Per piece, docs/guitar/pieces/<slug>/:
  score.json          the performance in pfsynth's score format (API.md): notes with
                      start/end, pitch, velocity, string, fret, finger, articulation, plus
                      the ids of their notehead and tab number in the MusicXML; tuning,
                      fitted room, closest body, credits
  score.musicxml.gz   the GAPS score (notation + tab) for display: tab rhythm marks and
                      part names hidden, hairpins removed, filler rests in three-voice bars
                      hidden; <note id="n…"> (notation) and "t…" (tab)
Plus docs/guitar/pieces.json (index), docs/guitar/bodies/ (measured body responses,
R. Mores, CC BY 4.0) and bodies.json. Never any recording.

    build/body-venv/bin/python tools/guitar_web_export.py
"""
import gzip,json,shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from classical_string_audition import read_notes
from guitar_edition_fingering import apply_edition,edition_tuning
from stringlab_audition import ROOT,OUT

GAPS=ROOT/'research/strings/midi/gaps';WEB=ROOT/'docs/guitar';DOC=ROOT/'experiments/string-gestures'
ART={'hammer':1,'pull':2}
GAPS_CREDIT='GAPS v1 fine-aligned MIDI and score (Riley, Guo, Edwards & Dixon, ISMIR 2024), CC BY-NC-SA 4.0'
TITLES={'sor-op35-17':'Study in D, Op. 35 No. 17','sor-op35-22':'Study in B minor, Op. 35 No. 22','giuliani-op100-11':'Study, Op. 100 No. 11',
        'carulli-op241-5':'Andantino, Op. 241 No. 5','carcassi-op60-7':'Study in A minor, Op. 60 No. 7','mertz-gebeth':'Gebeth (Bardenklänge)',
        'mertz-unruhe':'Unruhe (Bardenklänge)','molino-romanza':'Romanza','legnani-caprice-7':'Caprice No. 7, Op. 20','paganini-sonata-34':'Sonata No. 34'}


def tidy(meta,slug):
    import re
    m=dict(meta);m['composer']=re.sub(r'^(www\.)?classclef\.com\s*','',m['composer'],flags=re.I).strip();m['title']=TITLES.get(slug,m['title']);return m


def pieces():
    """(slug, events, xml, edition, meta, room, body)"""
    out=[]
    tw=GAPS/'tw1wc.xml';data=json.loads((OUT/'stringlab.json').read_text());clips={c['id']:c for c in data['clips']}
    if 'guitar-bach-full' in clips:
        c=clips['guitar-bach-full']
        out.append(('bach-bwv1006a-prelude',json.loads((OUT/'guitar-bach-full-events.json').read_text()),tw,'Apke edition',GAPS/'tw1wc.mid',
            dict(title='Prelude from BWV 1006a',composer='Johann Sebastian Bach',born='1685',died='1750',arranger='Stefan Apke (IMSLP #554880, CC BY-SA 4.0)',
                 gaps_id='281_tw1wc',youtube='foQ9dHbwLGo',performer='Mateusz Kowalski',video_title='Johann Sebastian Bach\'s "Prelude from BWV 1006a" played by Mateusz Kowalski on a 2007 Fritz Ober'),
            json.loads((DOC/'guitar-room-fit-bach-full-ring.json').read_text())['best'],
            next((r['id'] for r in c.get('bodyChoice',{}).get('ranking',[]) if r['id'].startswith('g')),'g27')))   # best measured body
    for f in sorted((OUT/'pieces').glob('*.clip.json')):
        slug=f.name[:-len('.clip.json')];c=json.loads(f.read_text());d=GAPS/slug;meta=json.loads((d/'meta.json').read_text())
        out.append((slug,json.loads((OUT/f'guitar-piece-{slug}-events.json').read_text()),d/f"{meta['scorehash']}.xml",'GAPS score',
            d/f"{meta['scorehash']}-fine-aligned.mid",meta,c['dynamics']['room'],c['bodyRanking'][0]['id']))
    return out


def clean_xml(xml):
    root=ET.parse(xml).getroot();parts=root.findall('part')
    for sp in root.find('part-list').findall('score-part'):
        for tag in ('part-name','part-abbreviation'):
            x=sp.find(tag)
            if x is not None:x.set('print-object','no')
    for clef in parts[0].iter('clef'):      # guitar is written an octave above where it sounds: treble-8 clef
        if clef.findtext('sign')=='G' and clef.find('clef-octave-change') is None:ET.SubElement(clef,'clef-octave-change').text='-1'
    for k,x in enumerate(parts[0].iter('note')):x.set('id',f'n{k}')
    if len(parts)>1:
        for k,x in enumerate(parts[1].iter('note')):x.set('id',f't{k}')
    for part in parts:
        for m in part.findall('measure'):
            # Exports repeat a marking once per voice (the tempo mark 2-4 times in bar 1): drop a
            # direction that says the same thing at the same moment (voice/staff attributes aside).
            seen=set();cursor=0;start=0
            for x in list(m):
                if x.tag=='backup':cursor-=int(x.findtext('duration') or 0)
                elif x.tag=='forward':cursor+=int(x.findtext('duration') or 0)
                elif x.tag=='note' and x.find('chord') is None:cursor+=int(x.findtext('duration') or 0)
                elif x.tag=='direction':
                    key=(cursor,tuple((y.tag,' '.join(''.join(y.itertext()).split())) for t in x.findall('direction-type') for y in t))
                    if key[1] and key in seen:m.remove(x);continue
                    seen.add(key)
            for d in list(m.findall('direction')):
                for t in list(d.findall('direction-type')):
                    if t.find('wedge') is not None:d.remove(t)
                if d.find('direction-type') is None:m.remove(d)
            if len({n.findtext('voice') for n in m.findall('note')})>=3:
                for n in m.findall('note'):
                    if n.find('rest') is not None:n.set('print-object','no')
    pluck={}        # notation note id -> right-hand finger (Verovio does not draw <pluck>; the page does)
    # Right-hand fingers written as loose text ("p", "pa", "im" above the staff) become
    # <pluck> marks on the notes struck at that moment, so they sit on their notes: letters
    # go to those notes from the lowest up ("pa": p on the bass, a on the melody); a single
    # letter goes to the highest note, or the lowest if it is p.
    for m in parts[0].findall('measure'):
        cursor=0;start=0;onsets=[];texts=[]
        for x in list(m):
            if x.tag=='backup':cursor-=int(x.findtext('duration') or 0)
            elif x.tag=='forward':cursor+=int(x.findtext('duration') or 0)
            elif x.tag=='direction':
                w=' '.join(t.text or '' for t in x.iter('words')).strip()
                if w and set(w)<=set('pimac') and len(x.findall('direction-type'))==1:texts.append((cursor,w,x))
            elif x.tag=='note':
                dur=int(x.findtext('duration') or 0);chord=x.find('chord') is not None
                onset=start if chord else cursor
                if not chord:start=cursor;cursor+=dur
                pe=x.find('pitch')
                if pe is not None and x.find('grace') is None:
                    midi=12*int(pe.findtext('octave'))+dict(C=0,D=2,E=4,F=5,G=7,A=9,B=11)[pe.findtext('step')]+int(pe.findtext('alter') or 0)
                    onsets.append((onset,midi,x))
        for at,w,d in texts:
            notes=sorted((n for n in onsets if n[0]==at),key=lambda n:n[1])
            if not notes:continue
            letters=list(w)
            if len(letters)==1:targets=[notes[0] if letters[0]=='p' else notes[-1]]
            else:targets=[notes[round(j*(len(notes)-1)/(len(letters)-1))] for j in range(len(letters))]
            if len({id(t[2]) for t in targets})<len(targets):continue          # fewer notes than letters
            for letter,(_,_,note) in zip(letters,targets):pluck[note.get('id')]=letter
            m.remove(d)
    # Beams belong to a chord's first note only; the GAPS export also puts them on chord
    # members, which makes Verovio open beams it never closes and drop the rest of the bar.
    for part in parts:
        for n in part.iter('note'):
            if n.find('chord') is not None:
                for bm in n.findall('beam'):n.remove(bm)
    # Notation: a note shared by two voices keeps both stems, but its fingering once.
    for m in parts[0].findall('measure'):
        cursor=0;start=0;seen=set()
        for x in list(m):
            if x.tag=='backup':cursor-=int(x.findtext('duration') or 0)
            elif x.tag=='forward':cursor+=int(x.findtext('duration') or 0)
            elif x.tag=='note':
                dur=int(x.findtext('duration') or 0);chord=x.find('chord') is not None
                onset=start if chord else cursor
                if not chord:start=cursor;cursor+=dur
                pe=x.find('pitch')
                if pe is None or x.find('grace') is not None:continue
                key=(onset,pe.findtext('step'),pe.findtext('alter'),pe.findtext('octave'))
                if key not in seen:seen.add(key);continue
                for tech in x.iter('technical'):
                    for f in tech.findall('fingering'):tech.remove(f)
    if len(parts)>1:                       # tab: numbers on lines only
        for m in parts[1].findall('measure'):
            for d in list(m.findall('direction')):m.remove(d)
            # A note shared by two voices (one notehead, two stems) is written once per voice:
            # in tab that prints its fret twice ("33"). Keep the first; a later copy becomes a
            # silent <forward> in its voice (or disappears if it was a chord member).
            cursor=0;start=0;seen=set();children=list(m)
            for x in children:
                if x.tag=='backup':cursor-=int(x.findtext('duration') or 0)
                elif x.tag=='forward':cursor+=int(x.findtext('duration') or 0)
                elif x.tag=='note':
                    dur=int(x.findtext('duration') or 0);chord=x.find('chord') is not None
                    onset=start if chord else cursor
                    if not chord:start=cursor;cursor+=dur
                    if x.find('rest') is not None or x.find('grace') is not None:continue
                    key=(onset,x.findtext('.//string'),x.findtext('.//fret'))
                    if key not in seen:seen.add(key);continue
                    i=list(m).index(x);m.remove(x)
                    if not chord:
                        f=ET.Element('forward');ET.SubElement(f,'duration').text=str(dur)
                        if x.find('voice') is not None:ET.SubElement(f,'voice').text=x.findtext('voice')
                        m.insert(i,f)
            for n in m.findall('note'):
                if n.find('rest') is not None:n.set('print-object','no');continue
                for tag in ('stem','beam'):     # keep type/dot/time-modification: Verovio spaces both staves by them
                    for x in n.findall(tag):n.remove(x)
                st=ET.SubElement(n,'stem');st.text='none'
                notations=n.find('notations')
                if notations is not None:
                    for tag in ('slur','tied','tuplet','arpeggiate','fermata','ornaments','articulations','dynamics'):
                        for x in notations.findall(tag):notations.remove(x)
    return gzip.compress(ET.tostring(root,encoding='utf-8',xml_declaration=True),9),pluck


def export(slug,events,xml,edition,mid,meta,room,body):
    meta=tidy(meta,slug)
    notes,_,_=read_notes(mid,1e9);apply_edition(notes,xml,edition);tuning=edition_tuning(xml)
    assert len(notes)==len(events),(slug,len(notes),len(events))
    out=[]
    for n,e in zip(notes,events):
        assert e['pitch'] in (n['pitch'],) or e.get('touch'),(slug,e['start'],e['pitch'],n['pitch'])
        art=0;param=0.
        if e.get('transition')=='legato':art=ART['hammer' if e.get('articulation','').startswith('hammer') else 'pull'];param=e['legato_amount']
        if e.get('touch'):art=4;param=e.get('touched_fret',12)
        out.append(dict(start=round(e['start'],5),end=round(e['end'],5),pitch=e.get('sounding',e['pitch']),velocity=round(e['velocity'],1),
            string=e['string'],fret=e.get('touched_fret',e['fret']) if e.get('touch') else e['fret'],finger=e['finger'] if isinstance(e.get('finger'),int) else -1,
            articulation=art,art_param=param,measure=n['score_measure'],ids=[f"n{n['score_xml_index']}",f"t{n['score_tab_xml_index']}"]))
    d=WEB/'pieces'/slug;d.mkdir(parents=True,exist_ok=True)
    perf=dict(format='pfsynth score 1',instrument='guitar',tuning=tuning,duration=max(e['end'] for e in events)+.5,notes=out,
        title=meta['title'],composer=meta['composer'],dates=f"{meta['born']}–{meta['died']}",arranger=meta.get('arranger'),
        performance=dict(performer=meta.get('performer'),video_title=meta.get('video_title'),gaps_id=meta['gaps_id'],youtube=meta['youtube'],timing=GAPS_CREDIT,
            dynamics='velocities fitted by pfsynth to the recording with its room modelled, clipped at a 3 mm pluck'),
        room=dict(rt_low=room['rt_low'],rt_high=room['rt_high'],ratio=room['ratio']),body=body,license='CC BY-NC-SA 4.0 (derived from GAPS)')
    xmlgz,pluck=clean_xml(xml)
    for n in out:
        if n['ids'][0] in pluck:n['pluck']=pluck[n['ids'][0]]          # right-hand finger p/i/m/a
    (d/'score.json').write_text(json.dumps(perf,separators=(',',':'),ensure_ascii=False))
    (d/'score.musicxml.gz').write_bytes(xmlgz)
    return dict(slug=slug,title=meta['title'],composer=meta['composer'],dates=perf['dates'],born=int(meta['born'] or 0),performer=meta.get('performer'),duration=round(perf['duration'],1),notes=len(out),body=body)


def bodies():
    g=json.loads((ROOT/'research/strings/body/guitars.json').read_text());d=WEB/'bodies';d.mkdir(parents=True,exist_ok=True);out=[]
    for x in g['guitars']:
        src=OUT/'bodies'/f"{x['id']}.wav"
        if not src.exists():continue
        shutil.copyfile(src,d/src.name)
        out.append(dict(id=x['id'],maker=x['maker'],year=x.get('year',''),place=x.get('place',''),category=x.get('category',''),wood=x.get('wood','')))
    (WEB/'bodies.json').write_text(json.dumps(dict(credit='Guitar body responses: Robert Mores, measured guitars (Zenodo 4604577), CC BY 4.0. Maker names as spelled in the source list.',bodies=out),ensure_ascii=False,indent=1))
    return len(out)


def main():
    index=sorted((export(*p) for p in pieces()),key=lambda x:(x['born'],x['composer'],x['title']))
    (WEB/'pieces.json').write_text(json.dumps(dict(pieces=index),ensure_ascii=False,indent=1))
    print(len(index),'pieces;',bodies(),'bodies',flush=True)
    for x in index:print(' ',x['slug'],x['notes'],'notes,',x['duration'],'s, body',x['body'])


if __name__=='__main__':main()
