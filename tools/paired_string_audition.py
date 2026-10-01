"""Local real-performance comparisons with published note alignments.

GAPS research-only demo and Bach Violin CC BY-NC-ND recording: do not publish.
"""
import csv,json,hashlib,subprocess,shutil
from fractions import Fraction
from scipy.io import wavfile
from scipy.signal import resample_poly
import numpy as np
import mido
from stringlab_audition import ROOT,OUT,SR,library,write_clip
from string_gesture_audition import setup,render_guitar,render_violin,export_midi
from classical_string_audition import read_notes,fingering,score,DOC


def audio(path,start,duration):
    sr,x=wavfile.read(path)
    x=x[round(start*sr):round((start+duration)*sr)].astype(float)
    if x.ndim==2:x=x.mean(axis=1)
    ratio=Fraction(SR,sr);x=resample_poly(x,ratio.numerator,ratio.denominator)
    return x[:round(duration*SR)]


def main():
    lib,_=library();setup(lib)
    gp=ROOT/'research/strings/midi/gaps';vp=ROOT/'research/strings/midi/bach-performance'
    # read_notes subtracts the first onset; retain that source offset for audio.
    t=0;origin=None
    for msg in mido.MidiFile(gp/'tw1wc.mid'):
        t+=msg.time
        if msg.type=='note_on' and msg.velocity:origin=t;break
    duration=18
    gn,_,_=read_notes(gp/'tw1wc.mid',duration);fingering(gn)
    from guitar_edition_fingering import apply_edition
    apply_edition(gn)
    gr=audio(gp/'tw1wc.wav',origin,duration)
    rows=list(csv.DictReader(open(vp/'notes/isabella-stewart-gardner/karen-gomyo_bwv1006_mov1.csv')))
    times=list(csv.DictReader(open(vp/'alignments/isabella-stewart-gardner/karen-gomyo_bwv1006_mov1.csv')))
    assert len(rows)==len(times)
    vn=[];vo=float(times[0]['start']);vd=28
    for n,a in zip(rows,times):
        start=float(a['start'])-vo;end=float(a['end'])-vo
        if 0<=start<vd:vn.append(dict(start=start,end=min(end,vd),pitch=int(n['pitch']),velocity=int(n['velocity']),channel=0))
    vn.sort(key=lambda n:(n['start'],n['pitch']));fingering(vn,True)
    decoded=OUT/'gomyo-source.wav'
    subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-y','-i',str(vp/'audio/isabella-stewart-gardner/karen-gomyo_bwv1006.mp3'),'-t',str(vo+vd+1),'-ar',str(SR),str(decoded)],check=True)
    vr=audio(decoded,vo,vd);decoded.unlink()
    clips=[]
    for kind,ns,d,ref,source,offset,performer in [('guitar',gn,duration,gr,'https://aim-qmul.github.io/GAPS/',origin,'Mateusz Kowalski'),('violin',vn,vd,vr,'https://hermandong.com/bach-violin-dataset/',vo,'Karen Gomyo')]:
        name=kind+'-bach-performance';print(name,len(ns),'notes',flush=True)
        if kind=='guitar':a=render_guitar(lib,ns,d,True);b=render_guitar(lib,ns,d,True,1)
        else:a=render_violin(lib,ns,d,False);b=render_violin(lib,ns,d,False,1)
        assert len(ref)==len(a) and np.isfinite(ref).all()
        description=f'Bach Prelude, BWV 1006a on guitar / BWV 1006 on violin. Real recording: {performer}. The synth follows published aligned note timing; B varies attack and tone. No recorded vibrato, slides or bow controls are inferred from note-only alignments. Guitar uses Apke edition strings, frets and marked fingers; violin choices are inferred. Unmarked guitar fingers remain unspecified. Local research audition; recording rights remain with its source.'
        c=write_clip(name,f'{kind.title()} · Bach, real performance',f'{performer} · aligned recording',dict(current=a,fitted=b,ref=ref),dict(current='Aligned timing, fixed character',fitted='Aligned timing, varying character',ref=f'Real performance · {performer}'),description,'Real recording','Which synth is closer to the real performance?')
        c['score']=score(ns,kind,'Bach · Prelude, BWV 1006'+('a' if kind=='guitar' else ''),None,None,source)
        if kind=='guitar':
            c['score']['inferred']=False
            c['score']['fingering_source']='Apke edition; unmarked stopped fingers left blank'
            boundaries=[0]+[float(point[1])-offset for point in json.loads((gp/'tw1wc-syncpoints.json').read_text()) if 0<float(point[1])-offset<d]+[d]
            c['score']['measures']=boundaries
        mid=OUT/(name+'.mid');export_midi(ns,mid,kind=='violin')
        events=OUT/(name+'-events.json');events.write_text(json.dumps(ns,indent=2)+'\n')
        c['downloads']=[dict(label='Aligned excerpt MIDI',url=mid.name),dict(label='String / finger assignments',url=events.name)]
        if kind=='guitar':
            shutil.copyfile(gp/'tw1wc.xml',OUT/'gaps-bach-source-tab.musicxml')
            c['downloads'].append(dict(label='Source tablature (MusicXML)',url='gaps-bach-source-tab.musicxml'))
        c['alignment']=dict(source_audio_offset_seconds=offset,method='Published fine-aligned MIDI' if kind=='guitar' else 'MIDI derived from published estimated note alignments',source=source,recording_performer=performer,source_sha256=hashlib.sha256((gp/'tw1wc.mid' if kind=='guitar' else vp/'alignments/isabella-stewart-gardner/karen-gomyo_bwv1006_mov1.csv').read_bytes()).hexdigest())
        clips.append(c)
    data=json.loads((OUT/'stringlab.json').read_text());ids={c['id'] for c in clips}
    data['clips']=[c for c in data['clips'] if c['id'] not in ids]+clips
    data['attribution']+=' Real Bach performances: Mateusz Kowalski / GAPS (local noncommercial research only); Karen Gomyo / Isabella Stewart Gardner Museum / Bach Violin Dataset (CC BY-NC-ND 4.0).'
    from string_score_alignment import attach
    if (OUT/'scores/imslp-apke-prelude-page7.png').exists():data,_=attach(data)
    temp=OUT/'stringlab.tmp';temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(OUT/'stringlab.json')
    (DOC/'paired-performance-report.json').write_text(json.dumps(clips,indent=2)+'\n')
    print('Real-performance pairs ready',flush=True)

if __name__=='__main__':main()
