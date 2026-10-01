"""Attach Apke's printed score to the GAPS excerpt, note by note, a whole system at a time.

Noteheads come from the PDF's own vectors (tools/score_geometry.py), matched to
the MusicXML staff part measure by measure: onsets in tick order take noteheads in
x order and every staff position must agree. Each excerpt note then carries the
pixel position of its printed head; the page shows whole systems unstretched.
"""
import json,hashlib,copy,struct,subprocess,zlib
import numpy as np
from scipy import ndimage
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from guitar_edition_fingering import part_notes,SOURCE as MUSICXML
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/stringlab'
SOURCE='https://imslp.org/wiki/Suite_in_E_major,_BWV_1006a_(Bach,_Johann_Sebastian)'
GEOMETRY=ROOT/'research/strings/scores/apke-bwv1006a-page7-geometry.json'
CLEFSCAN=ROOT/'research/strings/scores/apke-bwv1006a-page7-clefscan.json'
E4=4*7+2   # written treble-clef bottom line, as a diatonic index
SHARED={"guitar-bach-material","guitar-bach-body","guitar-bach-carbon","guitar-bach-body-choice","guitar-bach-loading","guitar-bach-dynamics","guitar-bach-character","guitar-bach-hammer","guitar-bach-slurs"}


def clefscan_heads(g):
    """ClefScan noteheads per system, with staff steps from its own staff lines.
    ClefScan reads a guitar treble-8 clef as plain treble; pitch identity comes from
    the MusicXML, so only head positions and staff steps are used."""
    r=json.loads(CLEFSCAN.read_text());staves={s['id']:s for s in r['staves']}
    out=[[] for _ in g['systems']]
    for o in r['objects']:
        if o['kind']!='head':continue
        s=staves[o['staff']];ys=[sum(p[1] for p in line)/len(line) for line in s['lines']]
        x0,y0,x1,y1=o['bbox'];y=(y0+y1)/2
        i=min(range(len(g['systems'])),key=lambda k:abs(g['systems'][k]['lines'][0]-ys[0]))
        out[i].append(dict(x=x0,y=y,w=x1-x0,step=round((ys[4]-y)/(s['space']/2))))
    for heads in out:heads.sort(key=lambda h:(h['x'],-h['y']))
    return out


def engraved_heads(source='clefscan'):
    """Map (score tick, sounding pitch) -> printed notehead; report what was checked."""
    g=json.loads(GEOMETRY.read_text());space=g['space_px']
    staff=part_notes(ET.parse(MUSICXML).getroot().findall('part')[0],-12)
    found=clefscan_heads(g) if source=='clefscan' else [s['heads'] for s in g['systems']]
    measures=[]
    for i,s in enumerate(g['systems']):
        edges=[s['left']]+s['barlines'];measures+=[(i,a,b) for a,b in zip(edges,edges[1:])]
    heads={};report=dict(source=source,matched_measures=[],unmatched_measures=[],fingers_checked=0,fingers_agree=0,finger_mismatches=[])
    for number,(i,a,b) in enumerate(measures,1):
        system=g['systems'][i]
        ink=[h for h in found[i] if a<h['x']+h['w']/2<b]
        notes=sorted((n for n in staff if int(n['measure'])==number),key=lambda n:(n['tick'],n['diatonic']))
        if len(ink)!=len(notes):report['unmatched_measures'].append(dict(measure=number,printed=len(ink),musicxml=len(notes)));continue
        groups=defaultdict(list)
        for n in notes:groups[n['tick']].append(n)
        cursor=0;pairs=[]
        for tick in sorted(groups):
            chunk=sorted(ink[cursor:cursor+len(groups[tick])],key=lambda h:h['step']);cursor+=len(groups[tick])
            group=sorted(groups[tick],key=lambda n:n['diatonic'])
            if [h['step'] for h in chunk]!=[n['diatonic']-E4 for n in group]:break
            pairs+=zip(group,chunk)
        else:
            report['matched_measures'].append(number)
            for n,h in pairs:
                # Edition fingers are printed just left of the head; cross-check MusicXML.
                near=[d for d in system['digits'] if -2<h['x']-d['x1']<1.3*space and abs(d['y']-h['y'])<1.1*space]
                printed=min(near,key=lambda d:h['x']-d['x1'])['digit'] if near else None
                if n['finger'] is not None:
                    report['fingers_checked']+=1
                    if printed==int(n['finger']):report['fingers_agree']+=1
                    else:report['finger_mismatches'].append(dict(measure=number,tick=n['tick'],pitch=n['pitch'],musicxml=int(n['finger']),printed=printed))
                heads[(n['tick'],n['pitch'])]=dict(system=i,x=round(h['x']+h['w']/2,2),y=h['y'],w=h['w'],measure=number,printed_finger=printed)
            continue
        report['unmatched_measures'].append(dict(measure=number,reason='staff positions disagree'))
    return g,heads,report


def edition_slurs(g,notes):
    """Printed slurs -> (source, destination) excerpt notes. Each slur end takes the
    nearest printed head; both notes must be consecutive on one string (ligado)."""
    sp=g['space_px'];found=[]
    for i,system in enumerate(g['systems']):
        for slur in system.get('slurs',[]):
            near=[n for n in notes if n['ink']['system']==i and abs(n['ink']['y']-slur['y'])<2.5*sp and slur['x0']-1.2*sp<n['ink']['x']<slur['x1']+1.2*sp]
            if len(near)<2:continue
            a=min(near,key=lambda n:abs(n['ink']['x']-slur['x0']));b=min(near,key=lambda n:abs(n['ink']['x']-slur['x1']))
            same=[n for n in notes if n['string']==a['string'] and n['start']>a['start']]
            if a is not b and same and same[0] is b:found.append((a,b,'hammer-on' if b['pitch']>a['pitch'] else 'pull-off'))
    return found


def page_raster(g,scale):
    """Grayscale page at `scale` x the 1556-px coordinate space (Poppler PGM)."""
    raw=subprocess.run(['pdftoppm','-gray','-f',str(g['pdf_page']),'-l',str(g['pdf_page']),'-scale-to-x',str(g['image']['width']*scale),'-scale-to-y',str(g['image']['height']*scale),str(ROOT/g['source'])],capture_output=True,check=True).stdout
    head=raw.split(b'\n',3);w,h=map(int,head[1].split());return np.frombuffer(head[3],np.uint8)[:w*h].reshape(h,w)


def write_png(path,a):
    raw=b''.join(b'\0'+row.tobytes() for row in a)
    chunk=lambda t,d:struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',a.shape[1],a.shape[0],8,0,0,0,0))+chunk(b'IDAT',zlib.compress(raw,9))+chunk(b'IEND',b''))


def ink_owners(g,img,scale):
    """Assign every connected ink component to a system. Components touching a staff
    seed it; floating marks (dynamics below a staff, fingerings and barre text above
    the next) join whichever system's ink is nearest, closest pairs first."""
    labels,n=ndimage.label(img<200,structure=np.ones((3,3)))
    boxes=np.array([[b[0].start,b[0].stop,b[1].start,b[1].stop] for b in ndimage.find_objects(labels)],float)
    owner=np.full(n,-1);sp=g['space_px']*scale
    # Edition semantics first: barre numerals seed the staff below, dynamics the one above.
    for h in g.get('hints',[]):
        x0,y0,x1,y1=(round(v*scale) for v in h['box'])
        ids=np.unique(labels[y0:y1,x0:x1]);ids=ids[ids>0]-1
        if h['belongs']=='below':i=next(k for k,st in enumerate(g['systems']) if st['lines'][0]*scale>y1)
        else:i=max(k for k,st in enumerate(g['systems']) if st['lines'][4]*scale<y0)
        owner[ids]=i
    # Seeds: ink on the staff, then ink reaching into the ledger-line zone (bass notes
    # far below a staff, whose stems may point at the next one); nearest staff wins.
    for reach in (.3,4.2):
        claim={}
        for i,s in enumerate(g['systems']):
            band=labels[int(s['lines'][0]*scale-reach*sp):int(s['lines'][4]*scale+reach*sp),int(s['left']*scale):int(s['right']*scale)]
            centre=(s['lines'][0]+s['lines'][4])/2*scale
            for k in np.unique(band)[1:]-1:
                if owner[k]<0:
                    d=abs((boxes[k,0]+boxes[k,1])/2-centre)
                    if k not in claim or d<claim[k][0]:claim[k]=(d,i)
        for k,(d,i) in claim.items():owner[k]=i
    gy=np.maximum(0,np.maximum(boxes[:,None,0]-boxes[None,:,1],boxes[None,:,0]-boxes[:,None,1]))
    gx=np.maximum(0,np.maximum(boxes[:,None,2]-boxes[None,:,3],boxes[None,:,2]-boxes[:,None,3]))
    D=np.hypot(gx,gy);done=owner>=0
    best=D[:,done].min(1);near=owner[done][D[:,done].argmin(1)]
    while not done.all():
        j=np.flatnonzero(~done)[np.argmin(best[~done])];owner[j]=near[j];done[j]=True
        closer=D[j]<best;best[closer]=D[j][closer];near[closer]=owner[j]
    return labels,owner,boxes


def systems_for(notes,duration,g,heads):
    """Whole-system frames with a shared crop height, each its own cleaned image,
    plus a time->x playhead map."""
    space=g['space_px'];used=sorted({heads[(n['score_tick'],n['pitch'])]['system'] for n in notes})
    tops=[s['lines'][0] for s in g['systems']];bottoms=[s['lines'][4] for s in g['systems']]
    scale=2;img=page_raster(g,scale);labels,owner,boxes=ink_owners(g,img,scale)
    def extent(i):
        mine=boxes[owner==i]/scale;mine=mine[(mine[:,1]>tops[i]-7.5*space)&(mine[:,0]<bottoms[i]+7.5*space)]
        return mine[:,0].min(),mine[:,1].max()
    above=max(tops[i]-extent(i)[0] for i in used)+.5*space;below=max(extent(i)[1]-bottoms[i] for i in used)+.5*space
    left=min(g['systems'][i]['ink'][0] for i in used)-space;right=max(g['systems'][i]['right'] for i in used)+space
    onsets=defaultdict(list)
    for n in notes:onsets[n['score_tick']].append(n)
    frames=[]
    for i in used:
        ticks=sorted(t for t in onsets if heads[(t,onsets[t][0]['pitch'])]['system']==i)
        points=[[min(n['start'] for n in onsets[t]),sum(heads[(t,n['pitch'])]['x'] for n in onsets[t])/len(onsets[t])] for t in ticks]
        bars=sorted({heads[(t,n['pitch'])]['measure'] for t in ticks for n in onsets[t]})
        y0,y1=tops[i]-above,bottoms[i]+below
        r0,r1,c0,c1=(round(v*scale) for v in (y0,y1,left,right))
        # Keep only this system's own marks, and none cut by the frame edge.
        inside=(boxes[:,0]>=r0)&(boxes[:,1]<=r1)&(boxes[:,2]>=c0)&(boxes[:,3]<=c1)
        keep=np.concatenate([[False],(owner==i)&inside])
        crop=img[r0:r1,c0:c1].copy();lab=labels[r0:r1,c0:c1]
        foreign=ndimage.binary_dilation((lab>0)&~keep[lab],iterations=2)&~keep[lab]   # with anti-aliased fringe
        crop[foreign]=255
        name=f'scores/imslp-apke-page7-system{i+1}@2x.png';write_png(OUT/name,crop)
        frames.append(dict(index=i,image=name,crop=[round(left,2),round(y0,2),round(right-left,2),round(y1-y0,2)],points=points,lines=g['systems'][i]['lines'],left=g['systems'][i]['left'],barlines=g['systems'][i]['barlines'],barline=g['systems'][i]['barlines'][-1],measures=[bars[0],bars[-1]]))
    for f,nxt in zip(frames,frames[1:]+[None]):
        f['start']=0 if f is frames[0] else f['points'][0][0]
        f['end']=nxt['points'][0][0] if nxt else duration
        if nxt:f['points'].append([f['end'],f['barline']])
        else:
            later=[h['x']+h['w']/2 for h in g['systems'][f['index']]['heads'] if h['x']>f['points'][-1][1]+1]
            f['excerpt_end_x']=round((f['points'][-1][1]+min(later))/2,2) if later else f['barline']
            f['points'].append([duration,f['excerpt_end_x']])
        # Performance timing need not follow engraved spacing; keep the map monotone.
        for a,b in zip(f['points'],f['points'][1:]):b[0]=max(a[0],b[0]);b[1]=max(a[1],b[1])
        f['points']=[[round(t,4),round(x,2)] for t,x in f['points']]
    return frames


def attach(data):
    g,heads,report=engraved_heads('clefscan')
    _,vector,vreport=engraved_heads('pdf')
    # The PDF's vector glyphs are exact; use them to check every ClefScan head.
    deviation=[((heads[k]['x']-v['x'])**2+(heads[k]['y']-v['y'])**2)**.5 for k,v in vector.items() if k in heads]
    report['vector_check']=dict(measures_matched=vreport['matched_measures'],notes_compared=len(deviation),max_px=round(max(deviation),2),median_px=round(sorted(deviation)[len(deviation)//2],2))
    for c in data['clips']:
        if c['id']!='guitar-bach-performance':continue
        origin=c['alignment']['source_audio_offset_seconds']
        points=json.loads((ROOT/'research/strings/midi/gaps/tw1wc-syncpoints.json').read_text())
        # The first downbeat is 90 ms after the first aligned bass onset.
        # Treat the opening bass as part of measure 1, not an extra measure.
        starts=[0]+[float(p[1])-origin for p in points if int(p[0])>0 and float(p[1])-origin<c['duration']]+[c['duration']]
        c['score']['measures']=starts
        for n in c['score']['notes']:
            key=(n['score_tick'],n['pitch'])
            h=heads.get(key) or vector[key]
            assert h['measure']==n['score_measure'] and abs(h['x']-vector[key]['x'])<4 and abs(h['y']-vector[key]['y'])<4
            n['ink']=dict(system=h['system'],x=h['x'],y=h['y'],w=h['w'],source='ClefScan' if key in heads else 'PDF vector')
        for _,n,kind in edition_slurs(g,c['score']['notes']):n['edition_slur']=kind
        frames=systems_for(c['score']['notes'],c['duration'],g,heads)
        c['score']['engraving']=dict(image='scores/imslp-apke-prelude-page7@2x.png',imageWidth=g['image']['width'],imageHeight=g['image']['height'],space=g['space_px'],systems=frames,edition='Stefan Apke · 2018 · IMSLP #554880',source=SOURCE,pdf='scores/imslp-apke-bwv1006a.pdf',license='CC BY-SA 4.0',licenseUrl='https://creativecommons.org/licenses/by-sa/4.0/',
            alignment='Whole printed systems at natural proportions. Noteheads are recognized by ClefScan and identified against the MusicXML by measure, onset order and staff position; each tab number sits under its printed head. The edition PDF’s vector glyphs confirm every position. The playhead interpolates between performed onsets, so it moves unevenly where Kowalski’s timing departs from the engraved spacing.',
            check=dict(measures_matched=report['matched_measures'],fingers_checked=report['fingers_checked'],fingers_agree=report['fingers_agree'],vector_check=report['vector_check']))
        c['downloads']=[f for f in c['downloads'] if f['url']!='scores/imslp-apke-bwv1006a.pdf']+[dict(label='IMSLP score PDF',url='scores/imslp-apke-bwv1006a.pdf')]
    template=next(c['score'] for c in data['clips'] if c['id']=='guitar-bach-performance')
    for c in data['clips']:
        if c['id'] in SHARED:
            old=(c.get('score') or {}).get('notes') or [];c['score']=copy.deepcopy(template)
            # Keep per-clip note data (fitted velocities) when the note list is the same.
            if len(old)==len(c['score']['notes']):
                for new,before in zip(c['score']['notes'],old):
                    if (new['start'],new['pitch'])==(before['start'],before['pitch']):
                        new.update({k:before[k] for k in ('velocity','legato') if k in before})
    return data,report

if __name__=='__main__':
    p=OUT/'stringlab.json';data,check=attach(json.loads(p.read_text()));tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(p)
    report=dict(source=SOURCE,pdf_sha256=hashlib.sha256((ROOT/'research/strings/scores/bach-bwv1006a-apke-imslp.pdf').read_bytes()).hexdigest(),musicxml_sha256=hashlib.sha256(MUSICXML.read_bytes()).hexdigest(),check=check,clip=next(c['score']['engraving'] for c in data['clips'] if c['id']=='guitar-bach-performance'))
    (ROOT/'experiments/string-gestures/imslp-score-alignment.json').write_text(json.dumps(report,indent=2)+'\n')
    print('matched measures',check['matched_measures'],'unmatched',[m['measure'] for m in check['unmatched_measures']],'fingers',check['fingers_agree'],'/',check['fingers_checked'])
