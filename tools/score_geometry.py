"""Exact engraved geometry of Apke's BWV 1006a Prelude page from the PDF's vectors.

The IMSLP PDF is MuseScore output: every notehead is a font glyph and every staff
line / barline a vector line, so positions are read, not recognized. Needs
pdfminer.six (Homebrew's python3.14 has it; the body-venv does not):

    /opt/homebrew/opt/python@3.14/bin/python3.14 tools/score_geometry.py

Writes research/strings/scores/apke-bwv1006a-page7-geometry.json in the pixel
space of build/stringlab/scores/imslp-apke-prelude-page7.png (1556 x 2200).
Matching to MusicXML notes happens in string_score_alignment.py.
"""
import json,hashlib
from pathlib import Path
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTChar,LTLine,LTRect,LTCurve,LTContainer

ROOT=Path(__file__).resolve().parents[1]
PDF=ROOT/'research/strings/scores/bach-bwv1006a-apke-imslp.pdf'
OUT=ROOT/'research/strings/scores/apke-bwv1006a-page7-geometry.json'
PAGE=7;W,H=1556,2200
NOTEHEAD=''   # MuseScore 1.x "MScore" font: black notehead


def walk(node):
    for child in node:
        yield child
        if isinstance(child,LTContainer)and not isinstance(child,LTChar):yield from walk(child)


def main():
    page=list(extract_pages(PDF,page_numbers=[PAGE-1]))[0]
    sx,sy=W/page.width,H/page.height
    px=lambda x:round(x*sx,2);py=lambda y:round((page.height-y)*sy,2)
    chars=[];lines=[];shapes=[]
    for o in walk(page):
        if isinstance(o,LTChar):chars.append(o)
        elif isinstance(o,LTLine):lines.append(o)
        elif isinstance(o,(LTRect,LTCurve)):shapes.append(o)
    # Staff lines are drawn per measure (0.4 pt). Cluster their heights.
    staff_y=sorted({round(l.y0,2) for l in lines if abs(l.y1-l.y0)<.01 and abs(l.linewidth-.4)<.05 and l.x1-l.x0>60})
    staves=[]
    for y in sorted(staff_y,reverse=True):
        if staves and len(staves[-1])<5 and abs(staves[-1][-1]-y)<6:staves[-1].append(y)
        else:staves.append([y])
    assert all(len(s)==5 for s in staves),staves
    space=(staves[0][0]-staves[0][4])/4
    def staff_of(y):return min(range(len(staves)),key=lambda i:abs((staves[i][0]+staves[i][4])/2-y))
    result=dict(source=str(PDF.relative_to(ROOT)),pdf_sha256=hashlib.sha256(PDF.read_bytes()).hexdigest(),pdf_page=PAGE,
        image=dict(width=W,height=H),space_px=round(space*sy,3),systems=[])
    for i,s in enumerate(staves):
        segs=[l for l in lines if abs(l.y1-l.y0)<.01 and abs(l.y0-s[0])<.01 and abs(l.linewidth-.4)<.05]
        bars=sorted({round(l.x0,2) for l in lines if abs(l.x1-l.x0)<.01 and abs(l.linewidth-.8)<.05 and abs(l.y1-s[0])<.3 and abs(l.y0-s[4])<.3})
        result['systems'].append(dict(lines=[py(y) for y in s],left=px(min(l.x0 for l in segs)),right=px(max(l.x1 for l in segs)),barlines=[px(x) for x in bars],heads=[],digits=[],ink=None))
    # Glyph origin (matrix e,f) is the notehead's vertical centre for SMuFL-style fonts.
    for c in chars:
        x0,y0=c.matrix[4],c.matrix[5];i=staff_of(y0);sysd=result['systems'][i];s=staves[i]
        if c.get_text()==NOTEHEAD and 'MScore' in c.fontname and 'BC' not in c.fontname and 'Text' not in c.fontname:
            # Diatonic steps above the bottom staff line (written E4 in a treble clef).
            step=(y0-s[4])/(space/2)
            assert abs(step-round(step))<.08,(c,step)
            sysd['heads'].append(dict(x=px(x0),y=py(y0),w=round((c.x1-c.x0)*sx,2),step=round(step)))
        elif 'MScoreBC' in c.fontname and c.get_text().isdigit():
            sysd['digits'].append(dict(x=px((c.x0+c.x1)/2),y=py((c.y0+c.y1)/2),x1=px(c.x1),digit=int(c.get_text())))
    # Ink extent per system, clipped halfway to its neighbours, for natural-size crops.
    for o in chars+lines+shapes:
        yc=(o.y0+o.y1)/2;i=staff_of(yc);d=result['systems'][i]
        if 'FreeSerif' in getattr(o,'fontname','') and o.size>13:continue   # titles
        box=[px(o.x0),py(o.y1),px(o.x1),py(o.y0)]
        d['ink']=box if d['ink'] is None else [min(d['ink'][0],box[0]),min(d['ink'][1],box[1]),max(d['ink'][2],box[2]),max(d['ink'][3],box[3])]
    for d in result['systems']:d['heads'].sort(key=lambda h:(h['x'],-h['y']))
    # Placement hints for marks between staves: barre numerals (VII) belong to the
    # staff below, dynamics (MuseScore text font) to the staff above. Boxes hug the
    # glyph's baseline rather than pdfminer's full font box.
    result['hints']=[]
    for c in chars:
        t=c.get_text();em=c.size*sy;base=py(c.matrix[5]);w=c.x1-c.x0
        barre='FreeSerif' in c.fontname and round(c.size)==12 and t in ('V','I','X') and base>result['systems'][0]['lines'][0]-8*result['space_px']
        if barre or 'MScoreText' in c.fontname:
            result['hints'].append(dict(box=[px(c.x0+.2*w),round(base-.6*em,2),px(c.x1-.2*w),round(base-.05*em,2)],belongs='below' if barre else 'above'))
    # Slurs: filled Bezier shapes, much wider than tall (string-number circles are round).
    for c in shapes:
        if isinstance(c,LTCurve) and any(seg[0]=='c' for seg in (c.original_path or [])) and c.x1-c.x0>2.5*(c.y1-c.y0):
            yc=(c.y0+c.y1)/2;result['systems'][staff_of(yc)].setdefault('slurs',[]).append(dict(x0=px(c.x0),x1=px(c.x1),y=py(yc)))
    # Dashed lines in this edition are barre extensions (with their end hooks).
    for l in lines:
        if getattr(l,'dashing_style',None) and l.dashing_style[0]:
            result['hints'].append(dict(box=[px(l.x0)-1,py(l.y1)-1,px(l.x1)+1,py(l.y0)+1],belongs='below'))
    OUT.write_text(json.dumps(result,indent=1)+'\n')
    print(OUT,'systems',len(staves),'heads',sum(len(d['heads']) for d in result['systems']),'digits',sum(len(d['digits']) for d in result['systems']))

if __name__=='__main__':main()
