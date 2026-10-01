"""Performance video: the score, tab and a fretboard, driven by the fitted performance.

Light theme to match the engraved score. Each Verovio system is shown whole, staff at a
fixed height; notes light up as they sound, their hue set by pluck strength (the
velocities fitted to the recording; harmonics as played); each repeat pass dims the bars
it does not play; slurs get H/P arcs. Below, a fretboard: every string's vibrating
length drawn from its own simulated motion (piece_video_audio.py), the finger at its
fret, the touch at the node for harmonics, a tap for hammer-ons and pull-offs. Pieces,
bodies, rooms and credits: video_pieces.py.

    build/body-venv/bin/python tools/piece_video_audio.py bach
    build/video-venv/bin/python tools/piece_video.py --piece bach [--preview SECONDS] [--start SECONDS] [--stills T,...]
"""
import bisect,colorsys,json,math,subprocess,sys
from pathlib import Path
import numpy as np
import skia
from video_pieces import PIECES,SUBTITLE,BODY_CREDIT,GAPS,body_text

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/stringlab';V=ROOT/'build/video';FONTS=V/'fonts'
W,H=1920,1080
PAPER=(0xF6,0xF3,0xEC);CARD=(0xFF,0xFF,0xFF);INK=(0x1E,0x22,0x28);MUTED=(0x6B,0x72,0x7C);HAIR=(0xDD,0xD6,0xCA)
CARD_X,CARD_Y,CARD_W,CARD_H=40,140,1840,560
SCALE=(CARD_W-60)/2500                                   # system: left 50 .. right 2550 SVG units
NUT,BRIDGE,BOARD_Y=170.,1760.,860.


def rgb(c,a=1.):return skia.Color4f(c[0]/255,c[1]/255,c[2]/255,a)


def oklch(L,C,h):
    a,b=C*math.cos(math.radians(h)),C*math.sin(math.radians(h))
    l_,m_,s_=L+.3963377774*a+.2158037573*b,L-.1055613458*a-.0638541728*b,L-.0894841775*a-1.2914855480*b
    l,m,s=l_**3,m_**3,s_**3
    lin=(4.0767416621*l-3.3077115913*m+.2309699292*s,-1.2684380046*l+2.6097574011*m-.3413193965*s,-.0041960863*l-.7034186147*m+1.7076147010*s)
    g=lambda x:12.92*x if x<=.0031308 else 1.055*x**(1/2.4)-.055
    return tuple(int(round(255*min(1,max(0,g(v))))) for v in lin)


def hue_for(velocity):
    """Pluck strength (dB re the median note, as the listening room's level lane) -> hue,
    blue (soft) through green and amber to red (loud), at even perceptual lightness."""
    db=25*math.log10(max(velocity,1)/100);u=min(1,max(0,(db+12)/24))
    return oklch(.62,.15,262-u*234)


class Fonts:
    def __init__(self):
        tf=lambda n:skia.Typeface.MakeFromFile(str(FONTS/n))
        self.serif=tf('SourceSerif4Display-Regular.ttf');self.serif_it=tf('SourceSerif4-It.ttf');self.serif_sb=tf('SourceSerif4-Semibold.ttf')
        self.sans=tf('SourceSans3-Regular.ttf');self.sans_sb=tf('SourceSans3-Semibold.ttf');self.sans_b=tf('SourceSans3-Bold.ttf');self.sans_it=tf('SourceSans3-It.ttf')


def text(canvas,s,x,y,typeface,size,color,align='left',alpha=1.,spacing=0.):
    font=skia.Font(typeface,size);font.setSubpixel(True);font.setEdging(skia.Font.Edging.kSubpixelAntiAlias)
    paint=skia.Paint(Color4f=rgb(color,alpha),AntiAlias=True)
    width=font.measureText(s)+spacing*max(0,len(s)-1)
    x0=x-width if align=='right' else x-width/2 if align=='center' else x
    if spacing:
        for ch in s:canvas.drawString(ch,x0,y,font,paint);x0+=font.measureText(ch)+spacing
    else:canvas.drawString(s,x0,y,font,paint)
    return width


def load(cfg):
    data=json.loads((OUT/'stringlab.json').read_text());clip=next(c for c in data['clips'] if c['id']==cfg['clip'])
    events=json.loads((OUT/f"{cfg['clip']}-events.json").read_text())
    played={(round(e['start'],3),e['string']):e for e in events}
    notes=[]
    for n in clip['score']['notes']:
        e=played.get((round(n['start'],3),n['string']))
        if e is None:continue
        notes.append(dict(n,velocity=e['velocity'],pluck=e.get('pluck_position',.19),touch=e.get('touch'),transition=e.get('transition'),articulation=e.get('articulation','')))
    notes.sort(key=lambda n:n['start'])
    strings=np.load(V/f"{cfg['out']}-strings.npz")
    return clip,notes,strings


def raster_systems(clip):
    out={}
    for f in clip['score']['engraving']['systems']:
        if f['index'] in out:continue
        svg=OUT/f['image'];png=V/'systems'/(Path(f['image']).stem+'.png');png.parent.mkdir(parents=True,exist_ok=True)
        width=round(f['crop'][2]*SCALE)
        subprocess.run(['rsvg-convert','-w',str(width),'-o',str(png),str(svg)],check=True)
        out[f['index']]=skia.Image.open(str(png))
    return out


def fret_x(f):return NUT+(BRIDGE-NUT)*(1-2**(-f/12))


def string_y(s,x):
    """Strings fan out from the nut (17 px apart) to the bridge (25 px); string 1 on top like the tab."""
    u=(x-NUT)/(BRIDGE-NUT);gap=17+8*u
    return BOARD_Y+(s-3.5)*gap


class Video:
    def __init__(self,piece='sonatina'):
        self.cfg=cfg=PIECES[piece];self.tuning=cfg['tuning'];self.out=cfg['out']
        self.clip,self.notes,strings=load(cfg);self.fonts=Fonts()
        body=str(strings['body']) if 'body' in strings.files else cfg['body']
        guitars={g['id']:g for g in json.loads((ROOT/'research/strings/body/guitars.json').read_text())['guitars']}
        self.maker,self.where=body_text(guitars[body]);self.body=body
        self.env=strings['env'];self.fps=int(strings['fps']);self.lead=float(strings['lead']);self.duration=float(strings['duration'])
        e=self.clip['score']['engraving'];self.frames=e['systems'];self.space=e['space'];self.systems=raster_systems(self.clip)
        self.top=max(f['lines'][0] for f in self.frames)                         # SVG units above the staff, worst case
        self.staff_y=CARD_Y+28+self.top*SCALE
        self.ts=1.8*self.space*SCALE*1.08;self.tab_y=CARD_Y+CARD_H-34-5*self.ts
        self.by_string={s:[n for n in self.notes if n['string']==s] for s in range(1,7)}
        self.starts={s:[n['start'] for n in v] for s,v in self.by_string.items()}
        ref=np.percentile(self.env[self.env>0],99.7);self.env_db=20*np.log10(self.env/ref+1e-9)
        self.total=self.env.shape[1]/self.fps;self.end_card=self.total-5.0
        self.last=max(n['end'] for n in self.notes)
        self.static=self.background()

    # ---------- static layers ----------
    def background(self):
        surface=skia.Surface(W,H);c=surface.getCanvas();c.clear(rgb(PAPER))
        F=self.fonts
        text(c,self.cfg['label'],62,62,F.sans_sb,17,MUTED,spacing=2.4)
        w=text(c,self.cfg['title'],58,112,F.serif,50,INK)
        text(c,SUBTITLE,58+w+46,112,F.serif_it,22,MUTED)
        # pluck-strength legend
        x0,y0,w=1300,74,240
        for k in range(w):
            col=oklch(.62,.15,262-(k/(w-1))*234);c.drawRect(skia.Rect.MakeXYWH(x0+k,y0,1.2,8),skia.Paint(Color4f=rgb(col)))
        text(c,'soft',x0,y0+27,F.sans,15,MUTED);text(c,'loud',x0+w,y0+27,F.sans,15,MUTED,'right')
        text(c,'pluck strength, fitted to the recording',x0+w/2,y0-10,F.sans,15,MUTED,'center')
        # score card
        shadow=skia.Paint(Color4f=rgb((0,0,0),.10),AntiAlias=True,MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle,10))
        r=skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(CARD_X,CARD_Y+4,CARD_W,CARD_H),10,10);c.drawRRect(r,shadow)
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(CARD_X,CARD_Y,CARD_W,CARD_H),10,10),skia.Paint(Color4f=rgb(CARD),AntiAlias=True))
        self.draw_guitar(c)
        foot=f"Physically modelled nylon strings · measured body of a {self.maker} guitar{self.where} (R. Mores) · room, timing and dynamics fitted to {self.cfg['performer']}’s recording (GAPS)"
        text(c,foot,W/2,1052,F.sans,16,MUTED,'center')
        return surface.makeImageSnapshot()

    def draw_guitar(self,c):
        aa=lambda col,a=1.:skia.Paint(Color4f=rgb(col,a),AntiAlias=True)
        top=lambda x:string_y(1,x)-14;bot=lambda x:string_y(6,x)+14
        # body: upper bout from the 12th fret, soundhole, bridge
        body=skia.Path();x12=fret_x(12)
        body.moveTo(x12-10,BOARD_Y-96);body.cubicTo(x12+260,BOARD_Y-122,1650,BOARD_Y-140,1905,BOARD_Y-112)
        body.lineTo(1905,BOARD_Y+112);body.cubicTo(1650,BOARD_Y+140,x12+260,BOARD_Y+122,x12-10,BOARD_Y+96);body.close()
        c.drawPath(body,aa((0xF0,0xE6,0xD3)));c.drawPath(body,skia.Paint(Color4f=rgb((0xDC,0xCC,0xB0)),AntiAlias=True,Style=skia.Paint.kStroke_Style,StrokeWidth=1.5))
        hole=NUT+.745*(BRIDGE-NUT)
        for r,col,w in ((96,(0xC9,0xB2,0x8E),5),(88,(0xB0,0x93,0x6A),1.6)):
            c.drawCircle(hole,BOARD_Y,r,skia.Paint(Color4f=rgb(col),AntiAlias=True,Style=skia.Paint.kStroke_Style,StrokeWidth=w))
        c.drawCircle(hole,BOARD_Y,80,aa((0x4A,0x40,0x36),.88))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(BRIDGE-6,BOARD_Y-78,BRIDGE+60,BOARD_Y+78),8,8),aa((0xB5,0x96,0x6E)))
        c.drawRect(skia.Rect.MakeLTRB(BRIDGE-4,BOARD_Y-72,BRIDGE+3,BOARD_Y+72),aa((0xF4,0xEE,0xE2)))
        # fingerboard to the 19th fret, slightly tapering
        end=fret_x(19.4);board=skia.Path();board.moveTo(NUT,top(NUT)-4);board.lineTo(end,top(end)-6);board.lineTo(end,bot(end)+6);board.lineTo(NUT,bot(NUT)+4);board.close()
        c.drawPath(board,aa((0xE4,0xD5,0xBC)));c.drawPath(board,skia.Paint(Color4f=rgb((0xCF,0xBC,0x9C)),AntiAlias=True,Style=skia.Paint.kStroke_Style,StrokeWidth=1.2))
        for f in range(1,20):
            x=fret_x(f);c.drawLine(x,top(x)-3,x,bot(x)+3,skia.Paint(Color4f=rgb((0xA9,0x9C,0x8A)),AntiAlias=True,StrokeWidth=2.4))
        c.drawRect(skia.Rect.MakeLTRB(NUT-9,top(NUT)-6,NUT,bot(NUT)+6),aa((0xF2,0xEC,0xDF)))
        c.drawRect(skia.Rect.MakeLTRB(NUT-9,top(NUT)-6,NUT,bot(NUT)+6),skia.Paint(Color4f=rgb((0xC8,0xBA,0xA2)),AntiAlias=True,Style=skia.Paint.kStroke_Style,StrokeWidth=1))
        for f in (3,5,7,9,12,15,17,19):
            x=(fret_x(f-1)+fret_x(f))/2;text(c,str(f),x,bot(x)+30,self.fonts.sans,15,MUTED,'center')
        for s in range(1,7):text(c,self.tuning[s-1],NUT-24,string_y(s,NUT)+5,self.fonts.sans_sb,15,MUTED,'center')

    # ---------- per frame ----------
    def frame_at(self,t):
        i=bisect.bisect_right([f['start'] for f in self.frames],t)-1;return max(0,i)

    def x_of(self,f,t):
        p=np.array(f['points']);return float(np.interp(t,p[:,0],p[:,1]))

    def draw_system(self,c,f,t,alpha=1.,dy=0.):
        img=self.systems[f['index']];X=lambda x:CARD_X+30+(x-50)*SCALE;y0=self.staff_y-f['lines'][0]*SCALE+dy
        Y=lambda y:y0+y*SCALE;cut=skia.Rect.MakeLTRB(CARD_X+4,CARD_Y+4,CARD_X+CARD_W-4,CARD_Y+CARD_H-4)
        c.save();c.clipRect(cut)
        layer=alpha<.999
        if layer:c.saveLayerAlpha(cut,int(255*alpha))
        c.drawImage(img,CARD_X+30-50*SCALE,y0)
        # notehead colour, multiplied into the ink (black heads stay black on a coloured halo)
        active=[];F=self.fonts
        for n in self.notes:
            if n['ink']['system']!=f['index'] or not (f['start']-1e-6<=n['start']<f['end']-1e-6):continue
            on=t-n['start']
            if on<-.02 or t>n['end']+.35:continue
            a=max(.28,math.exp(-max(0,on)/.45)) if t<=n['end'] else .28*max(0,1-(t-n['end'])/.35)
            active.append((n,a))
        for n,a in active:
            col=hue_for(n['velocity']);x,y=X(n['ink']['x']),Y(n['ink']['y'])
            glow=skia.Paint(Color4f=rgb(col,.55*a),AntiAlias=True,MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle,7))
            c.drawCircle(x,y,13,glow)
            mul=skia.Paint(Color4f=rgb(tuple(255-(255-v)*min(1,a*1.25) for v in col)),AntiAlias=True,BlendMode=skia.BlendMode.kMultiply)
            c.drawCircle(x,y,.82*self.space*SCALE*1.35,mul)
        # tab
        left,right=X(f['left']),X(f['barline']);ts=self.ts;ty=self.tab_y+dy
        hair=skia.Paint(Color4f=rgb((0xC3,0xBC,0xB0)),AntiAlias=True,StrokeWidth=1.1)
        for s in range(6):
            c.drawLine(left,ty+s*ts,right,ty+s*ts,hair);text(c,self.tuning[s],left-14,ty+s*ts+5,F.sans_sb,14,MUTED,'right')
        for b in [f['left']]+f['barlines']:c.drawLine(X(b),ty,X(b),ty+5*ts,skia.Paint(Color4f=rgb((0xA8,0xA0,0x93)),AntiAlias=True,StrokeWidth=1.6))
        visit=[n for n in self.notes if n['ink']['system']==f['index'] and f['start']-1e-6<=n['start']<f['end']-1e-6]
        live={id(n):a for n,a in active}
        for n in visit:                                                       # sustain lines
            x=X(n['ink']['x']);y=ty+(n['string']-1)*ts;x2=max(x+8,min(right,X(self.x_of(f,n['end']))))
            a=live.get(id(n),0);col=hue_for(n['velocity'])
            c.drawLine(x+9,y,x2,y,skia.Paint(Color4f=rgb(col,.18+.55*a),AntiAlias=True,StrokeWidth=3.2,StrokeCap=skia.Paint.kRound_Cap))
        for n in visit:
            if n.get('legato') not in ('HO','PO'):continue
            prev=[m for m in self.by_string[n['string']] if m['start']<n['start']];prev=prev[-1] if prev else None
            if prev is None or prev['ink']['system']!=f['index']:continue
            x0,x1=X(prev['ink']['x']),X(n['ink']['x']);y=ty+(n['string']-1)*ts-12;a=live.get(id(n),0);col=hue_for(n['velocity'])
            arc=skia.Path();arc.moveTo(x0,y);arc.quadTo((x0+x1)/2,y-16,x1,y)
            c.drawPath(arc,skia.Paint(Color4f=rgb(col if a>0 else MUTED,.5+.5*a),AntiAlias=True,Style=skia.Paint.kStroke_Style,StrokeWidth=1.8))
            text(c,n['legato'][0],(x0+x1)/2,y-12,F.sans_b,12,col if a>0 else MUTED,'center')
        for n in visit:
            x=X(n['ink']['x']);y=ty+(n['string']-1)*ts;a=live.get(id(n),0);col=hue_for(n['velocity'])
            label=str(n.get('tab',n['fret']));font=skia.Font(F.sans_b,15.5);w=font.measureText(label)+9
            rr=skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x-w/2,y-9.5,w,19),6,6)
            c.drawRRect(rr,skia.Paint(Color4f=rgb(CARD),AntiAlias=True))
            if a>0:c.drawRRect(rr,skia.Paint(Color4f=rgb(col,min(1,.25+a)),AntiAlias=True))
            text(c,label,x,y+5.5,F.sans_b,15.5,(255,255,255) if a>.45 else INK,'center')
        # bars this repeat pass does not play
        for a_,b_ in f.get('dim',[]):
            c.drawRect(skia.Rect.MakeLTRB(X(a_),CARD_Y+4,X(b_),CARD_Y+CARD_H-4),skia.Paint(Color4f=rgb(CARD,.82)))
        if layer:c.restore()
        c.restore()
        return X,ty

    def draw(self,c,T):
        t=T-self.lead;c.drawImage(self.static,0,0)
        i=self.frame_at(t);f=self.frames[i];fade=.32
        if i>0 and t-f['start']<fade:
            a=(t-f['start'])/fade;a=a*a*(3-2*a)
            self.draw_system(c,self.frames[i-1],t,1-a,-10*a);X,ty=self.draw_system(c,f,t,a,10*(1-a))
        else:X,ty=self.draw_system(c,f,t)
        if -0.2<t<self.last+.5:                                               # playhead
            x=X(self.x_of(f,t));g=skia.Paint(Color4f=rgb((0x2B,0x5C,0xA8),.10),AntiAlias=True)
            c.drawRect(skia.Rect.MakeLTRB(x-7,CARD_Y+20,x+7,ty+5*self.ts+16),g)
            c.drawLine(x,CARD_Y+20,x,ty+5*self.ts+16,skia.Paint(Color4f=rgb((0x2B,0x5C,0xA8),.55),AntiAlias=True,StrokeWidth=1.6))
        self.draw_strings(c,T,t)
        F=self.fonts;past=[n for n in self.notes if n['start']<=max(t,0)]
        bar=past[-1]['score_measure'] if past else 1
        text(c,f'Bar {bar}',1860,100,F.serif,32,INK,'right')
        mm=lambda s:f'{int(s//60)}:{int(s%60):02d}'
        text(c,f'{mm(min(max(t,0),self.duration))} / {mm(self.duration)}',1860,124,F.sans,15,MUTED,'right')
        self.overlays(c,T,t)

    def draw_strings(self,c,T,t):
        k=min(self.env.shape[1]-1,int(round(T*self.fps)))
        for s in range(1,7):
            notes=self.by_string[s];j=bisect.bisect_right(self.starts[s],t)-1
            db=self.env_db[s-1,k];amp=17*min(1,max(0,(db+46)/46))**1.15
            base=skia.Paint(Color4f=rgb((0x8C,0x7A,0x62) if s>=4 else (0x9A,0x9E,0xA4)),AntiAlias=True,StrokeWidth=1.2+.45*s)
            n=notes[j] if j>=0 else None
            harmonic=bool(n and n.get('touch'))
            fret=0 if (n is None or harmonic) else n['fret']
            xa=fret_x(fret) if fret else NUT;xb=BRIDGE
            # the dead part of the string behind the finger
            if xa>NUT:c.drawLine(NUT,string_y(s,NUT),xa,string_y(s,xa),base)
            col=hue_for(n['velocity']) if n else (0x99,0x99,0x99)
            if amp<.25:
                c.drawLine(xa,string_y(s,xa),xb,string_y(s,xb),base)
            else:
                pts=np.linspace(0,1,90);xs=xa+(xb-xa)*pts;ys=np.array([string_y(s,x) for x in xs])
                shape=np.sin(2*np.pi*pts) if harmonic else np.sin(np.pi*pts)
                lens=skia.Path();lens.moveTo(xs[0],ys[0])
                for x,y,v in zip(xs,ys,shape):lens.lineTo(x,y-amp*abs(v))
                for x,y,v in zip(xs[::-1],ys[::-1],shape[::-1]):lens.lineTo(x,y+amp*abs(v))
                lens.close();c.drawPath(lens,skia.Paint(Color4f=rgb(col,.20),AntiAlias=True))
                phase=T*2*np.pi*3.7+s*1.3
                for g,al in ((0,.85),(.9,.35),(1.8,.15)):
                    p=skia.Path();cp=math.cos(phase-g)
                    for q,(x,y,v) in enumerate(zip(xs,ys,shape)):(p.moveTo if q==0 else p.lineTo)(x,y+amp*v*cp)
                    c.drawPath(p,skia.Paint(Color4f=rgb(col,al),AntiAlias=True,Style=skia.Paint.kStroke_Style,StrokeWidth=1.2+.45*s))
            if n and fret and t<=n['end']:                                   # fretting finger
                x=fret_x(fret-1)+.72*(fret_x(fret)-fret_x(fret-1));y=string_y(s,x)
                c.drawCircle(x,y,9.5,skia.Paint(Color4f=rgb(col,.92),AntiAlias=True));c.drawCircle(x,y,9.5,skia.Paint(Color4f=rgb((255,255,255),.9),AntiAlias=True,Style=skia.Paint.kStroke_Style,StrokeWidth=1.5))
            if harmonic and t<=n['start']+max(.6,n['touch']['lift']):          # touch at the node
                x=NUT+(BRIDGE-NUT)*.5;y=string_y(s,x);a=1 if t<=n['start']+n['touch']['lift'] else max(0,1-(t-n['start']-n['touch']['lift'])/.5)
                c.drawCircle(x,y,11,skia.Paint(Color4f=rgb(col,.9*a),AntiAlias=True,Style=skia.Paint.kStroke_Style,StrokeWidth=2.4))
                text(c,'harmonic · XII',x,string_y(1,x)-30,self.fonts.serif_it,22,col,'center',alpha=a)
            if n and n.get('transition')=='legato' and 0<=t-n['start']<.7:  # left-hand slur, no pluck
                u=(t-n['start'])/.7;kind='hammer-on' if n['articulation'].startswith('hammer') else 'pull-off'
                x=fret_x(fret-1)+.72*(fret_x(fret)-fret_x(fret-1)) if fret else NUT+6;y=string_y(s,x)
                c.drawCircle(x,y,10+18*min(1,u*2.5),skia.Paint(Color4f=rgb(col,.7*(1-min(1,u*2.5))),AntiAlias=True,Style=skia.Paint.kStroke_Style,StrokeWidth=2.2))
                text(c,kind,x,string_y(1,x)-30,self.fonts.serif_it,22,col,'center',alpha=1-u)
            elif n and 0<=t-n['start']<.3:                                   # pluck flash
                u=(t-n['start'])/.3;x=xb-n['pluck']*(xb-xa);y=string_y(s,x)
                c.drawCircle(x,y,6+16*u,skia.Paint(Color4f=rgb(col,.55*(1-u)),AntiAlias=True,Style=skia.Paint.kStroke_Style,StrokeWidth=2))

    def overlays(self,c,T,t):
        F=self.fonts
        if T<3.4:                                                             # title card over the score
            a=1 if T<2.3 else max(0,1-(T-2.3)/1.1)
            c.drawRect(skia.Rect.MakeXYWH(CARD_X,CARD_Y,CARD_W,CARD_H),skia.Paint(Color4f=rgb(CARD,.94*a)))
            who,what,line=self.cfg['card']
            text(c,who,W/2,CARD_Y+215,F.serif_it,34,MUTED,'center',a)
            text(c,what,W/2,CARD_Y+300,F.serif,86,INK,'center',a)
            text(c,line,W/2,CARD_Y+360,F.serif_it,26 if len(line)<90 else 22,MUTED,'center',a)
        if T>self.end_card:
            a=min(1,(T-self.end_card)/1.0);c.drawRect(skia.Rect.MakeXYWH(0,0,W,H),skia.Paint(Color4f=rgb(PAPER,.97*a)))
            y=300
            title,sub=self.cfg['credits_title']
            text(c,title,W/2,y,F.serif,64,INK,'center',a);text(c,sub,W/2,y+48,F.serif_it,28,MUTED,'center',a)
            lines=[('Sound',self.cfg['sound']),
                   ('Guitar body',BODY_CREDIT.format(maker=self.maker,where=self.where)),
                   ('Performance',f"timing and dynamics fitted to {self.cfg['performer']}’s recording, {GAPS}"),
                   ('Room','fitted to the same recording'),
                   ('Score',self.cfg['score']),
                   ('Synth','pfsynth')]
            for k,(h,s) in enumerate(lines):
                yy=y+150+k*46;text(c,h.upper(),560,yy,F.sans_sb,15,MUTED,'right',a,spacing=1.6);text(c,s,590,yy,F.sans,21,INK,'left',a)


def main():
    v=Video(sys.argv[sys.argv.index('--piece')+1] if '--piece' in sys.argv else 'sonatina');arg=lambda k,d:float(sys.argv[sys.argv.index(k)+1]) if k in sys.argv else d
    start=arg('--start',0.);length=arg('--preview',v.total-start)
    stills=[float(x) for x in sys.argv[sys.argv.index('--stills')+1].split(',')] if '--stills' in sys.argv else None
    surface=skia.Surface.MakeRaster(skia.ImageInfo.Make(W,H,skia.kRGBA_8888_ColorType,skia.kPremul_AlphaType))
    if stills:
        for T in stills:
            c=surface.getCanvas();v.draw(c,T);surface.makeImageSnapshot().save(str(V/f'still-{v.out}-{T:07.2f}.png'),skia.kPNG)
        print('stills',stills);return
    name=V/(f'{v.out}.mp4' if '--preview' not in sys.argv else f'preview-{v.out}-{start:.0f}.mp4')
    cmd=['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgba','-s',f'{W}x{H}','-r',str(v.fps),'-i','-','-ss',str(start),'-t',str(length),'-i',str(V/f'{v.out}-audio.wav'),
         '-map','0:v','-map','1:a','-c:v','libx264','-preset','slow','-crf','17','-pix_fmt','yuv420p','-profile:v','high','-tune','animation',
         '-c:a','aac_at','-b:a','256k','-movflags','+faststart','-shortest',str(name)]
    ff=subprocess.Popen(cmd,stdin=subprocess.PIPE);n=int(length*v.fps)
    for k in range(n):
        T=start+k/v.fps;c=surface.getCanvas();v.draw(c,T)
        ff.stdin.write(surface.makeImageSnapshot().tobytes())
        if k%300==0:print(f'{k}/{n} frames',flush=True)
    ff.stdin.close();ff.wait();print('wrote',name,flush=True)


if __name__=='__main__':main()
