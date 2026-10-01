"""Engrave a MusicXML staff part with Verovio, one system per SVG, and place tab under it.

For scores without a printed edition (e.g. GAPS transcriptions): the staff part is
engraved by ClefScan's pinned Verovio build, notehead positions are read from the SVG
(Verovio tags each note with its written pitch and each measure with its number), and
the excerpt's notes are matched measure by measure (onset order + written pitch, as for
the IMSLP Bach). Output plugs into the listening room's whole-system view.
"""
import hashlib
import copy,glob,json,re,subprocess
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from guitar_edition_fingering import part_notes,measure_order

ROOT=Path(__file__).resolve().parents[1]
VEROVIO=sorted(Path.home().glob('sources/sep23-omr/.runtime/verovio/*/bin/verovio'))
SVG='{http://www.w3.org/2000/svg}'


def staff_excerpt(source,last_measure,out):
    """Staff part only, measures up to last_measure, guitar treble-8 clef, no tempo glyphs."""
    tree=ET.parse(source);root=tree.getroot();parts=root.findall('part')
    for p in parts[1:]:root.remove(p)
    for sp in root.find('part-list').findall('score-part')[1:]:root.find('part-list').remove(sp)
    name=root.find('part-list/score-part/part-name');name.set('print-object','no')
    staff=parts[0]
    for m in list(staff.findall('measure')):
        if int(m.get('number'))>last_measure:staff.remove(m)
    for m in staff.findall('measure'):
        for d in list(m.findall('direction')):
            if d.find('.//metronome') is not None:m.remove(d)   # SMuFL text font is unavailable in an <img>-style SVG
            # Hairpins engrave badly under the staff (user request): drop them, keep other directions.
            for t in list(d.findall('direction-type')):
                if t.find('wedge') is not None:d.remove(t)
            if d in list(m) and d.find('direction-type') is None:m.remove(d)
        # Three-voice bars (an inner voice doubling the arpeggio's notes) carry filler rests
        # that land on the bass and belong to no visible line: keep them, unprinted.
        if len({n.findtext('voice') for n in m.findall('note')})>=3:
            for n in m.findall('note'):
                if n.find('rest') is not None:n.set('print-object','no')
    clef=staff.find('measure/attributes/clef')
    if clef.find('clef-octave-change') is None:ET.SubElement(clef,'clef-octave-change').text='-1'
    for tag in ('work','movement-title','identification','credit'):
        for e in root.findall(tag):root.remove(e)
    tree.write(out,encoding='utf-8',xml_declaration=True)


def render(xml,outdir,width=2600):
    v=VEROVIO[-1];resources=v.parent.parent/'share/verovio'
    for f in Path(outdir).glob('system_*.svg'):f.unlink()
    subprocess.run([str(v),'-r',str(resources),'-f','xml','-a','--breaks','auto','--page-width',str(width),'--page-height','100','--adjust-page-height',
        '--header','none','--footer','none','--svg-view-box','--svg-remove-xlink','-x','1',
        '--svg-additional-attribute','note@pname','--svg-additional-attribute','note@oct','--svg-additional-attribute','measure@n',
        '-o',str(Path(outdir)/'system.svg'),str(xml)],check=True,capture_output=True)
    return sorted(Path(outdir).glob('system_*.svg'))


def geometry(svg):
    """Notehead centres, staff lines and barlines in the SVG's outer units."""
    root=ET.parse(svg).getroot();w,h=map(float,root.get('viewBox').split()[2:])
    inner=next(e for e in root.iter(f'{SVG}svg') if e.get('class')=='definition-scale');iw=float(inner.get('viewBox').split()[2]);k=w/iw
    margin=next(e for e in inner.iter(f'{SVG}g') if e.get('class')=='page-margin');tx,ty=map(float,re.findall(r'[-\d.]+',margin.get('transform') or 'translate(0,0)')[:2])
    X=lambda x:(float(x)+tx)*k;Y=lambda y:(float(y)+ty)*k
    lines=[];bars=[];heads=[];extent={}
    for m in root.iter(f'{SVG}g'):
        if 'measure' not in (m.get('class') or '').split():continue
        n=int(m.get('data-n'))
        for staff in m.iter(f'{SVG}g'):
            if staff.get('class')=='staff':
                for p in staff.findall(f'{SVG}path'):
                    x1,y1,x2,y2=map(float,re.findall(r'[-\d.]+',p.get('d'))[:4]);lines.append((Y(y1),X(x1),X(x2)))
                    a,b=extent.get(n,(X(x1),X(x2)));extent[n]=(min(a,X(x1)),max(b,X(x2)))   # the measure's staff lines
        for b in m.iter(f'{SVG}g'):
            if b.get('class')=='barLine':
                for p in b.findall(f'{SVG}path'):bars.append(X(re.findall(r'[-\d.]+',p.get('d'))[0]))
        for note in m.iter(f'{SVG}g'):
            if note.get('class')!='note':continue
            use=next(note.iter(f'{SVG}use'))
            # Verovio 6 positions glyphs with transform="translate(x, y) scale(..)".
            ux,uy=(use.get('x'),use.get('y')) if use.get('x') else re.findall(r'translate\(([-\d.]+),\s*([-\d.]+)\)',use.get('transform'))[0]
            heads.append(dict(measure=n,x=X(ux),y=Y(uy),diatonic=7*int(note.get('data-oct'))+'cdefgab'.index(note.get('data-pname'))))
    ys=sorted({round(l[0],2) for l in lines});space=(ys[4]-ys[0])/4
    for hd in heads:hd['x']+=.59*space   # Bravura noteheadBlack is ~1.18 staff spaces wide
    return dict(width=w,height=h,space=space,lines=ys[:5],left=min(l[1] for l in lines),right=max(l[2] for l in lines),barlines=sorted(set(round(b,2) for b in bars)),heads=heads,measures=extent)


def engrave(source,notes,duration,outdir,url):
    """Engrave the excerpt's measures, match notes to heads, build system frames."""
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    last=max(n['score_measure'] for n in notes)
    staff_excerpt(source,last,outdir/'excerpt.xml');pages=render(outdir/'excerpt.xml',outdir)
    staff=part_notes(ET.parse(outdir/'excerpt.xml').getroot().find('part'),-12)
    systems=[geometry(p) for p in pages];found={};report=dict(matched=[],unmatched=[])
    for i,g in enumerate(systems):
        for number in sorted({h['measure'] for h in g['heads']}):
            ink=sorted([h for h in g['heads'] if h['measure']==number],key=lambda h:(h['x'],-h['y']))
            score=sorted((n for n in staff if int(n['measure'])==number),key=lambda n:(n['tick'],n['diatonic']))
            if len(ink)!=len(score):report['unmatched'].append(dict(measure=number,engraved=len(ink),musicxml=len(score)));continue
            groups=defaultdict(list)
            for n in score:groups[n['tick']].append(n)
            cursor=0;pairs=[];ok=True
            for tick in sorted(groups):
                chunk=sorted(ink[cursor:cursor+len(groups[tick])],key=lambda h:h['diatonic']);cursor+=len(groups[tick])
                group=sorted(groups[tick],key=lambda n:n['diatonic'])
                if [h['diatonic'] for h in chunk]!=[n['diatonic'] for n in group]:ok=False;break
                pairs+=zip(group,chunk)
            if not ok:report['unmatched'].append(dict(measure=number,reason='pitches disagree'));continue
            report['matched'].append(number)
            for n,h in pairs:found.setdefault((n['tick'],n['pitch']),dict(system=i,x=round(h['x'],2),y=round(h['y'],2),w=round(1.18*g['space'],2),measure=number))
    # A repeated passage reuses its engraved system: each pass is its own "visit" (page),
    # with its own time range; notes keep their written position for the lookup.
    placed=[]
    for n in notes:
        h=found.get((n.get('score_written_tick',n['score_tick']),n['pitch']))
        if h:n['ink']=dict(system=h['system'],x=h['x'],y=h['y'],w=h['w'],source='Verovio engraving');placed.append(n)
    placed.sort(key=lambda n:n['start']);visits=[]
    for n in placed:
        if not visits or visits[-1][0]!=n['ink']['system']:visits.append((n['ink']['system'],[]))
        visits[-1][1].append(n)
    # Which measures each pass plays: the score's repeat order (first/second endings
    # unfolded), cut into runs on one system. A pass's run is matched to its visit; the
    # system's other measures (the ending not taken, music before or after the pass) are
    # dimmed in the view.
    part=ET.parse(outdir/'excerpt.xml').getroot().find('part');ms=part.findall('measure')
    on={n:i for i,g in enumerate(systems) for n in g['measures']};runs=[]
    for k in measure_order(part):
        n=int(ms[k].get('number'))
        if n not in on:continue
        if runs and runs[-1][0]==on[n]:runs[-1][1].append(n)
        else:runs.append((on[n],[n]))
    r=0;played=[]
    for i,members in visits:
        first=members[0]['score_measure']
        while r<len(runs) and not (runs[r][0]==i and first in runs[r][1]):r+=1
        played.append(set(runs[r][1]) if r<len(runs) else {n['score_measure'] for n in members});r+=1
    frames=[]
    for (i,members),plays in zip(visits,played):
        g=systems[i];onsets=defaultdict(list)
        for n in members:onsets[n['score_tick']].append(n)
        points=[[min(n['start'] for n in onsets[t]),sum(n['ink']['x'] for n in onsets[t])/len(onsets[t])] for t in sorted(onsets,key=lambda t:min(n['start'] for n in onsets[t]))]
        bars=sorted({n['score_measure'] for n in members})
        frames.append(dict(index=i,image=f'{url}/{pages[i].name}',version=hashlib.sha256(pages[i].read_bytes()).hexdigest()[:12],crop=[0,0,g['width'],g['height']],points=points,lines=g['lines'],left=round(g['left'],2),
            barlines=[b for b in g['barlines'] if b>g['left']+1],barline=round(g['right'],2),measures=[bars[0],bars[-1]]))
        dim=[]
        for n,(a,b) in sorted(g['measures'].items(),key=lambda kv:kv[1][0]):
            if n in plays:continue
            if dim and a-dim[-1][1]<1:dim[-1][1]=b
            else:dim.append([a,b])
        frames[-1]['dim']=[[round(a,2),round(b,2)] for a,b in dim]
    for f,nxt in zip(frames,frames[1:]+[None]):
        f['start']=0 if f is frames[0] else f['points'][0][0]
        f['end']=nxt['points'][0][0] if nxt else duration
        if nxt:f['points'].append([f['end'],f['barline']])
        else:
            later=[h['x'] for h in systems[f['index']]['heads'] if h['x']>f['points'][-1][1]+1]
            f['excerpt_end_x']=round((f['points'][-1][1]+min(later))/2,2) if later else f['barline']
            f['points'].append([duration,f['excerpt_end_x']])
        for a,b in zip(f['points'],f['points'][1:]):b[0]=max(a[0],b[0]);b[1]=max(a[1],b[1])
        f['points']=[[round(t,4),round(x,2)] for t,x in f['points']]
    report['notes_placed']=sum('ink' in n for n in notes);report['notes']=len(notes)
    return dict(systems=frames,space=round(sum(g['space'] for g in systems)/len(systems),3)),report
