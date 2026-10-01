"""Bach, Prelude from the Lute Suite BWV 1006a (arr. Stefan Apke): the whole of Mateusz
Kowalski's performance (GAPS tw1wc), for the listening room and the video.

GAPS's fine-aligned MIDI (its transcription model's onsets; the 11 notes it does not
confirm are inner voices, not misplaced chords) with the Apke edition's strings, frets
and fingers (apply_edition, standard tuning), velocities fitted to Kowalski's recording
with his fitted room, window by window (as the Sonatina). Apke's six slurs on the first
page are played as hammer-ons and pull-offs with their calibrated strength
(guitar_legato_audition.py); the later pages' slurs have not been extracted, so every
other note is plucked. A plays every note at velocity 100; B the fitted performance.
GAPS: noncommercial research, no redistribution; the recording is kept local.

    build/body-venv/bin/python tools/guitar_bach_full.py
"""
import hashlib,json
import numpy as np
import mido
from scipy.io import wavfile
from stringlab_audition import ROOT,OUT,SR,library,write_clip
from string_gesture_audition import setup,export_midi
from classical_string_audition import read_notes,score
from guitar_edition_fingering import apply_edition
from paired_string_audition import audio
from guitar_dynamics_fit import Model,fit_room_dynamics_long,physical_cap
from score_engrave import engrave
from guitar_sustain import let_ring

DOC=ROOT/'experiments/string-gestures';SRC=ROOT/'research/strings/midi/gaps';NAME='tw1wc';CID='guitar-bach-full'


def main():
    lib,_=library();setup(lib)
    t=0;origin=None
    for msg in mido.MidiFile(SRC/f'{NAME}.mid'):
        t+=msg.time
        if msg.type=='note_on' and msg.velocity:origin=t;break
    sr,raw=wavfile.read(SRC/f'{NAME}.wav',mmap=True);length=raw.shape[0]/sr
    notes,_,_=read_notes(SRC/f'{NAME}.mid',1e9)
    duration=round(min(length-origin,max(n['end'] for n in notes)+3),2)
    apply_edition(notes,SRC/f'{NAME}.xml','Apke edition')
    for n in notes:n.update(bend=[],slides=[],hammer_to=False,mute=False)
    ring=let_ring(notes,duration)                      # strings ring until a hand would stop them
    print('strings ring:',ring,flush=True)
    ref=audio(SRC/f'{NAME}.wav',origin,duration)
    model=Model(lib,'nylon / Gil de Avalle body + loading',5,True)
    room=json.loads((DOC/'guitar-room-fit-bach-full-ring.json').read_text())['best']   # Kowalski's room, refitted with ringing strings
    print(f'{len(notes)} notes, {duration} s; fitting dynamics with the room, window by window',flush=True)
    velocity,info=fit_room_dynamics_long(model,notes,ref,duration,room)
    velocity,clipped=physical_cap(velocity);print('plucks clipped at 3 mm:',clipped,flush=True)
    fitted=[dict(n,velocity=float(round(v,1))) for n,v in zip(notes,velocity)]
    leg=json.loads((DOC/'guitar-legato-report.json').read_text());slurs=[]
    for kind,key,marks in (('hammer-on','clearance_mm',leg['hammer_notes']),('pull-off','pull_mm',leg['pull_notes'])):
        for s in marks:
            n=next(n for n in fitted if abs(n['start']-s['start'])<1e-3 and n['pitch']==s['pitch'] and n['string']==s['string'])
            n.update(transition='legato',legato_amount=s[key]/1e3,legato_contact=leg['contact_s'],articulation=f'{kind} (Apke slur, assumed)');slurs.append(n)
    assert len(slurs)==6
    plain=[dict(n,velocity=100.) for n in notes]
    a=model.render(plain,duration);b=model.render(fitted,duration)
    for x in (a,b):assert np.isfinite(x).all() and len(x)==len(ref)
    print('contrast exponent %.1f; envelope error constant %.2f dB, fitted %.2f dB'%(info['gamma'],info['constant_error_db'],info['fitted_error_db']),flush=True)
    desc=('Bach, Prelude from BWV 1006a in Stefan Apke’s arrangement, the whole of Mateusz Kowalski’s performance, from GAPS’s fine-aligned MIDI with the Apke edition’s strings, frets and fingers. '
        f'B uses velocities fitted to this recording with its room modelled (reverberation {room["rt_low"]:.1f} s low, {room["rt_high"]:.1f} s high), window by window, and plays Apke’s six slurs on the first page as hammer-ons and pull-offs; '
        'the later pages’ slurs are not yet extracted, so every other note is plucked. Strings ring until a hand would stop them (the same string played again, the fretting finger needed elsewhere or out of reach, or a clashing note after the written length), not at the MIDI note-off; the room was refitted for that. A plays every note at the same velocity. Measured Gil de Avalle body as rendered; the Body menu applies the closest body; set Room to “Fitted to Kowalski’s recording, strings ringing (full Prelude)” to hear it as fitted. '
        'Local research audition: GAPS is noncommercial research only, and the recording is kept local.')
    c=write_clip(CID,'Guitar · Bach Prelude, full performance','BWV 1006a · Apke arr. · Mateusz Kowalski',dict(current=a,fitted=b,ref=ref),
        dict(current='Constant velocity, all plucked',fitted='Fitted dynamics, Apke’s slurs',ref='Real performance · Mateusz Kowalski'),desc,'Real recording','Which is closer to the recording?')
    c['score']=score(fitted,'guitar','Bach · Prelude BWV 1006a',None,None,'https://aim-qmul.github.io/GAPS/')
    points=json.loads((SRC/f'{NAME}-syncpoints.json').read_text())
    c['score']['measures']=[0]+[float(p[1])-origin for p in points if 0<float(p[1])-origin<duration]+[duration]
    c['score']['audit']=dict(passed=None,note='Strings, frets and fingers from the Apke edition via the GAPS score.');c['score']['inferred']=False
    c['score']['fingering_source']='Apke edition; unmarked stopped fingers left blank'
    for n,src in zip(c['score']['notes'],fitted):
        n['velocity']=src['velocity']
        if src.get('transition')=='legato':n['legato']='HO' if src['articulation'].startswith('hammer') else 'PO'
    engraving,engraved=engrave(SRC/f'{NAME}.xml',c['score']['notes'],duration,OUT/'scores/bach-full','scores/bach-full')
    print('engraved',engraved['notes_placed'],'of',engraved['notes'],'notes; unmatched measures',engraved['unmatched'][:5],flush=True)
    c['score']['engraving']=dict(engraving,edition='Engraved from the GAPS score (Apke arrangement) with Verovio',license='GAPS CC BY-NC-SA 4.0, research use',source='https://aim-qmul.github.io/GAPS/',
        caption='The whole GAPS score of Apke’s arrangement, engraved with Verovio one system at a time. Each tab number sits under its engraved note; HO/PO arcs mark the six slurs from the printed edition’s first page.',
        check=dict(measures_matched=engraved['matched'],unmatched=engraved['unmatched']))
    top=max(n['velocity'] for n in fitted);mid=OUT/f'{CID}.mid'
    export_midi([dict(n,velocity=max(1,int(round(n['velocity']*127/top)))) for n in fitted],mid)
    (OUT/f'{CID}-events.json').write_text(json.dumps(fitted,indent=2,default=float)+'\n')
    (OUT/f'{CID}-plain-events.json').write_text(json.dumps(plain,indent=2,default=float)+'\n')
    c['downloads']=[dict(label='Performance MIDI (fitted velocities, loudest = 127)',url=mid.name),dict(label='Notes, strings, slurs',url=f'{CID}-events.json')]
    c['sustain']=dict(method='guitar_sustain.let_ring',stops=ring)
    c['dynamics']=dict(model=model.name,range_exponent=info['gamma'],room=room,method='room-aware band-power fit',envelope_error_db=dict(constant_with_room=info['constant_error_db'],fitted_with_room=info['fitted_error_db']))
    c['alignment']=dict(source_audio_offset_seconds=origin,method='Published GAPS fine-aligned MIDI (= the GAPS transcription model’s onsets)',source='https://aim-qmul.github.io/GAPS/',recording_performer='Mateusz Kowalski',youtube='foQ9dHbwLGo',
        source_sha256=hashlib.sha256((SRC/f'{NAME}.mid').read_bytes()).hexdigest())
    data=json.loads((OUT/'stringlab.json').read_text())
    data['clips']=[x for x in data['clips'] if x['id']!=CID]+[c]
    tmp=OUT/'stringlab.tmp';tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(OUT/'stringlab.json')
    print('wrote',CID,flush=True)


if __name__=='__main__':main()
