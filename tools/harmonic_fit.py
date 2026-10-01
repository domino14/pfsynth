"""Fit the natural-harmonic model to the harmonic-versus-ordinary contrasts measured on real
guitars (harmonic_measure.py).

The model is measured exactly like the recordings: each harmonic (open string, finger
touching the node, lifted) against an ordinary note at the same sounding pitch, same
string where the fretboard allows (12th-fret harmonic vs fret 12; 7th vs fret 19), with
the same body. The contrast cancels the body and our general tone and leaves the technique.

    build/body-venv/bin/python tools/harmonic_fit.py [report]
"""
import itertools,json,sys
import numpy as np
from stringlab_audition import ROOT,SR,library
from string_gesture_audition import setup
from guitar_dynamics_fit import Model
from guitar_harmonics import STANDARD,touch_at,hz
from harmonic_measure import features,contrast

DOC=ROOT/'experiments/string-gestures'
START=.05
HAND=.19            # right hand, fraction of the open string from the bridge (AG-PT fit)


def physical_pluck(fret,hand=HAND):
    """The hand stays put while the vibrating length shrinks (fitted on AG-PT ordinary notes)."""
    return min(.45,hand*2**(fret/12))


def pairs():
    """(string, touched fret, partial n, ordinary string, ordinary fret)."""
    out=[]
    for s in range(1,7):
        out.append((s,12,2,s,12))
        out.append((s,7,3,s,19))
    return out


_ordinary={}


def model_rows(model,touch,velocity=90):
    """touch: dict(rho, lift, offset (m), pluck, width (fraction of string, optional)).
    Ordinary notes are plucked at the hand's fixed physical point (cached across calls)."""
    from harmonic_measure import refine_f0
    rows=[]
    for s,fret,n,os_,of in pairs():
        op=STANDARD[s-1];sounding=op+round(12*np.log2(n))
        t=dict(position=touch_at(s,op,fret,touch['offset']),rho=touch['rho'],lift=touch['lift'])
        if touch.get('width'):t['width']=touch['width']
        h=dict(start=START,end=START+2,pitch=op,velocity=velocity,string=s,fret=0,bend=[],mute=False,pluck_position=touch['pluck'],touch=t)
        o=dict(start=START,end=START+2,pitch=STANDARD[os_-1]+of,velocity=velocity,string=os_,fret=of,bend=[],mute=False,pluck_position=physical_pluck(of))
        row=dict(source='model',string=s,fret=fret,partial=n,pitch=sounding);on=round(START*SR)
        x=model.render([h],1.8);f0=refine_f0(x,SR,on,hz(op)*n);row['harmonic']=features(x,SR,on,f0,f0/n)
        k=(os_,of,velocity,id(model))
        if k not in _ordinary:
            y=model.render([o],1.8);g=refine_f0(y,SR,on,hz(o['pitch']));_ordinary[k]=features(y,SR,on,g,g/n)
        row['normal']=_ordinary[k]
        rows.append(row)
    return rows


def distance(model_c,real_c):
    """Mean absolute differences of the contrasts: partial balance 2-9 (dB), decay of
    partials 1-8 (dB/s, halved), high-band attack relative to partial 1 (dB) and the
    touched string's leftover modes (dB, halved). The attack is taken relative to partial
    1, not to the sustained high band, which on quiet notes is recording noise."""
    a=np.array(model_c['balance_db'][:8]);b=np.array(real_c['balance_db'][:8])
    da=np.array(model_c['decay_db_s'][:8]);db=np.array(real_c['decay_db_s'][:8])
    parts=dict(balance=float(np.nanmean(np.abs(a-b))),decay=float(np.nanmean(np.abs(da-db)))/2,attack=abs(model_c['attack_vs_body_db']-real_c['attack_vs_body_db']))
    rm,rr=model_c['residue_db'].get('harmonic'),real_c['residue_db'].get('harmonic')
    parts['residue']=abs(rm-rr)/2 if rm is not None and rr is not None and np.isfinite(rm) and np.isfinite(rr) else 0.
    parts['total']=sum(parts.values());return {k:round(v,2) for k,v in parts.items()}


GRID=dict(width=[.02,.03,.04,.05],rho=[200,424,800],lift=[.04,.06,.08],offset=[1e-3,2e-3,3e-3])


def main():
    """Grid over the finger (width, damping, lift time, placement), plucked at the hand's
    point; scored on the steel-string AG-PT pairs plus the nylon Philharmonia pairs. A
    coarser grid (width 0.01-0.03, rho to 6000/s, lift to 0.15 s, offset 0/2 mm) put
    the optimum here first."""
    lib,_=library();setup(lib);model=Model(lib,'nylon / Gil de Avalle body + loading',5,True)
    import harmonic_measure as hm
    agpt=json.loads((DOC/'harmonic-agpt-pairs.json').read_text());real=dict(agpt=contrast(agpt),philharmonia=json.loads((DOC/'harmonic-measure-report.json').read_text())['philharmonia']['contrast'])
    cal=json.loads((DOC/'guitar-harmonics-report.json').read_text())['calibration']
    old=dict(rho=cal['rho_per_s'],lift=cal['lift_s'],offset=cal['offset_mm']*1e-3,pluck=.12)
    def evaluate(touch):
        c=contrast(model_rows(model,touch));d={k:distance(c,v) for k,v in real.items()}
        return dict(touch=touch,contrast=c,distance=d,total=round(d['agpt']['total']+d['philharmonia']['total'],2))
    before=evaluate(old);print('point finger (before):',before['distance'],flush=True)
    rows=[]
    for w,rho,lift,off in itertools.product(*GRID.values()):
        rows.append(evaluate(dict(rho=rho,lift=lift,offset=off,pluck=HAND,width=w)))
        print(rows[-1]['touch'],rows[-1]['total'],flush=True)
    best=min(rows,key=lambda r:r['total'])
    print('best',best['touch'],best['distance'],flush=True)
    clean=lambda v:None if isinstance(v,float) and not np.isfinite(v) else v
    report=dict(method=__doc__.strip().splitlines()[0],hand=HAND,real=real,before=before,best=best,
        finger=dict(width_fraction=best['touch']['width'],width_mm_on_650=round(best['touch']['width']*650,1),rho_per_s=best['touch']['rho'],lift_s=best['touch']['lift'],offset_mm=best['touch']['offset']*1e3,pluck=best['touch']['pluck']),
        grid=[dict(touch=r['touch'],total=r['total'],agpt=r['distance']['agpt']['total'],philharmonia=r['distance']['philharmonia']['total']) for r in rows])
    (DOC/'harmonic-fit-report.json').write_text(json.dumps(report,indent=1,default=lambda v:clean(float(v)))+'\n')


if __name__=='__main__':main()
