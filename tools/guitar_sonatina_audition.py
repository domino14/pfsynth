"""Natural harmonics against a real performance: Morel, Sonatina III (GAPS -D1wc), whole piece.

Inon Međugorac's recording (YouTube M066__FzA6k, fetched locally at the user's request)
with GAPS's fine-aligned MIDI (alignment f-measure 0.97) and its MusicXML strings/frets.
Bars 11, 35, 142 and 166 end on a 12th-fret harmonic on the D string ("Harm XII"); the
GAPS TAB writes it as fret 12, which for this harmonic is also the sounding pitch (D4).
Both synth versions use velocities fitted to the recording and the measured body; they
differ only in that note: fretted at 12 versus the open string touched at its midpoint
with the finger fitted to real harmonics (harmonic_fit.py). The final chord (arpeggio
mark) is moved to the upward strum the GAPS transcription model finds in the recording:
GAPS's score alignment had placed it 0.65 s late, where nothing is played. GAPS:
noncommercial research, no redistribution; keep local.

    build/body-venv/bin/python tools/guitar_sonatina_audition.py
"""
import copy,hashlib,json,re
import numpy as np
from stringlab_audition import ROOT,OUT,SR,library,write_clip
from string_gesture_audition import setup,export_midi
from classical_string_audition import read_notes,score
from guitar_edition_fingering import apply_edition,edition_tuning
from string_hand_geometry import audit
from paired_string_audition import audio
from guitar_dynamics_fit import Model,fit_room_dynamics_long,EXP,V0,physical_cap
from guitar_harmonics import touch_at,PLUCK
from guitar_sustain import let_ring

DOC=ROOT/'experiments/string-gestures'
SRC=ROOT/'research/strings/midi/gaps/sonatina3'
NAME='morel-sonatina3-D1wc'
OPEN=edition_tuning(SRC/f'{NAME}.xml')   # drop D: the 6th string is tuned to D2


def transcribed(path):
    import mido
    t=0;out=[]
    for m in mido.MidiFile(path):
        t+=m.time
        if m.type=='note_on' and m.velocity:out.append((t,m.note))
    return out


def strum_from_transcription(notes,amt,origin,sweep=.02):
    """Arpeggio-marked chords: each note gets the onset the GAPS transcription model
    (build/amt-venv; research/strings/midi/gaps/sonatina3/*-amt.mid) finds for its pitch
    in the densest cluster near the aligned chord (most chord pitches within 250 ms).
    Pitches the model misses go before or after their string neighbours in the roll's
    order (upward: low strings first), `sweep` s per string. Applied only when the
    cluster holds at least three of the chord's pitches."""
    groups={}
    for n in notes:
        if n.get('score_arpeggiate'):groups.setdefault(round(n['start'],3),[]).append(n)
    log=[]
    for t0,chord in groups.items():
        pitches={n['pitch'] for n in chord}
        cand=[(u-origin,q) for u,q in amt if q in pitches and t0-1.0<=u-origin<=t0+.3]
        best=max(((sum(1 for p in pitches if any(c<=u<=c+.25 and q==p for u,q in cand)),-c,c) for c,_ in cand),default=(0,0,None))
        if best[0]<3:log.append(dict(time=t0,applied=False,found=best[0]));continue
        c=best[2];found={p:min(u for u,q in cand if q==p and c<=u<=c+.25) for p in pitches if any(q==p and c<=u<=c+.25 for u,q in cand)}
        order=sorted(chord,key=lambda n:-n['string'])            # upward: string 6 first
        times=[found.get(n['pitch']) for n in order]
        for k in range(len(order)):                                # fill misses from string neighbours
            if times[k] is None:
                after=next((times[j]-sweep*(j-k) for j in range(k+1,len(order)) if times[j] is not None),None)
                before=next((times[j]+sweep*(k-j) for j in range(k-1,-1,-1) if times[j] is not None),None)
                times[k]=after if after is not None else before
        for n,t in zip(order,times):
            n['start_gaps']=n['start'];n['start']=round(float(t),4);n['onset_source']='upward strum from the GAPS transcription model' if n['pitch'] in found else f'upward strum, {round(sweep*1000)} ms before the next string (not detected)'
        log.append(dict(time=t0,applied=True,onsets={f"{n['pitch']}@s{n['string']}":round((n['start']-t0)*1000) for n in order}))
    return log


def main():
    lib,_=library();setup(lib)
    cal=json.loads((DOC/'guitar-harmonics-report.json').read_text())['calibration']
    import mido
    t=0;origin=None
    for msg in mido.MidiFile(SRC/f'{NAME}-fine-aligned.mid'):
        t+=msg.time
        if msg.type=='note_on' and msg.velocity:origin=t;break
    from scipy.io import wavfile
    sr,_=wavfile.read(SRC/f'{NAME}.wav',mmap=True);length=_.shape[0]/sr
    notes,_,_=read_notes(SRC/f'{NAME}-fine-aligned.mid',1e9)
    DURATION=round(min(length-origin,max(n['end'] for n in notes)+2.5),2)   # the whole piece
    apply_edition(notes,SRC/f'{NAME}.xml','GAPS score')
    strum=strum_from_transcription(notes,transcribed(SRC/f'{NAME}-amt.mid'),origin)
    assert any(x['applied'] for x in strum),strum
    print('arpeggio chords',strum,flush=True)
    ring=let_ring(notes,DURATION)                      # strings ring until a hand would stop them
    print('strings ring:',ring,flush=True)
    for n in notes:n.update(bend=[],slides=[],hammer_to=False,mute=False)
    marked=[n for n in notes if re.search(r'harm',n.get('score_words',''),re.I)]
    assert [(n['score_measure'],n['fret'],n['string']) for n in marked]==[(m,12,4) for m in (11,35,142,166)],marked
    ref=audio(SRC/f'{NAME}.wav',origin,DURATION)
    harm=copy.deepcopy(notes);hs_=[harm[notes.index(m)] for m in marked]
    # 12th-fret harmonic: the open string, touched at its midpoint, sounds the fretted pitch.
    fit=json.loads((DOC/'harmonic-fit-report.json').read_text());finger=fit[fit['finger_used']] if fit.get('finger_used') else fit['finger']   # fitted to real harmonics (exaggerated on request)
    for h in hs_:
        h.update(pitch=OPEN[h['string']-1],fret=0,sounding=h['pitch'],pluck_position=finger['pluck'],
                 touch=dict(position=touch_at(h['string'],OPEN[h['string']-1],12,finger['offset_mm']*1e-3),rho=finger['rho_per_s'],lift=finger['lift_s'],width=finger['width_fraction']))
    model=Model(lib,'nylon / Gil de Avalle body + loading',5,True)
    room=json.loads((DOC/'guitar-room-fit-sonatina-ring.json').read_text())['best']   # Međugorac's room, refitted with ringing strings
    print(f'{len(notes)} notes, {DURATION} s; fitting dynamics with the room, window by window',flush=True)
    velocity,info=fit_room_dynamics_long(model,harm,ref,DURATION,room)
    velocity,clipped=physical_cap(velocity);print('plucks clipped at 3 mm:',clipped,flush=True)
    for n,v in zip(harm,velocity):n['velocity']=float(round(v,1))
    for h in hs_:h['velocity_fitted']=h['velocity'];h['velocity']=round(h['velocity']*finger.get('velocity_boost',1),1)   # show-off level (user request)
    plain=copy.deepcopy(notes)
    for n,v in zip(plain,velocity):n['velocity']=float(round(v,1))
    a=model.render(plain,DURATION);b=model.render(harm,DURATION)
    for x in (a,b):assert np.isfinite(x).all() and len(x)==len(ref)
    print('harmonics at',[(round(h['start'],2),h['score_measure'],round(h['velocity'])) for h in hs_],'contrast exponent %.1f; envelope error constant %.2f dB, fitted %.2f dB'%(info['gamma'],info['constant_error_db'],info['fitted_error_db']),flush=True)
    description=('Jorge Morel, Sonatina III, the whole piece as Inon Međugorac plays it, from GAPS’s fine-aligned MIDI and its score’s strings and frets (drop D). '
        'Bars 11, 35, 142 and 166 end on a 12th-fret natural harmonic on the D string (marked “Harm XII”). Both synths use velocities fitted to this recording with its room modelled (reverberation '+f'{room["rt_low"]:.1f} s low, {room["rt_high"]:.1f} s high'+'), window by window, and the measured Gil de Avalle body; the audio is dry, so set Room to “Fitted to Međugorac’s recording, strings ringing” to hear it as fitted; '
        'they differ only in those four notes. A frets them at the 12th fret like any note; B plucks the open string while a finger lightly touches its midpoint '
        f'(a finger of {finger["width_mm_on_650"]:.0f} mm effective width, damping, lift time and placement fitted to 145 recorded harmonics against ordinary notes on the same strings; see the “harmonics against real ones” clip). '
        'Strings ring until a hand would stop them (the same string played again, the fretting finger needed elsewhere or out of reach, or a clashing note after the written length), not at the MIDI note-off; the room was refitted for that. '
        'The final chord (arpeggio mark) is the upward strum the GAPS transcription model hears in the recording, about 150 ms from low D to high D; GAPS’s score alignment had put it 0.65 s late. '
        'Local research audition: GAPS is noncommercial research only, and the recording is kept local.')
    c=write_clip('guitar-sonatina-harmonics','Guitar · Sonatina III, full performance','Morel · Inon Međugorac · four 12th-fret harmonics',
        dict(current=a,fitted=b,ref=ref),dict(current='Harmonics played as ordinary fretted notes',fitted='Natural harmonics (finger-touch physics)',ref='Real performance · Inon Međugorac'),
        description,'Real recording','Which version of the harmonics (bars 11, 35, 142, 166) is closer to the recording?')
    c['score']=score(harm,'guitar','Morel · Sonatina III',None,None,'https://aim-qmul.github.io/GAPS/')
    import json as _j
    points=_j.loads((SRC/f'{NAME}-syncpoints.json').read_text())
    c['score']['measures']=[0]+[float(p[1])-origin for p in points if 0<float(p[1])-origin<DURATION]+[DURATION]
    # The GAPS score gives strings and frets but no left-hand fingers: no hand audit.
    c['score']['audit']=dict(passed=None,note='Not run: strings/frets from the GAPS score, left-hand fingers not given (drop-D tuning checked for every note).');c['score']['inferred']=False;c['score']['fingering_source']='from the GAPS score (drop-D tuning); fingers shown where the score marks them, otherwise blank'
    for n,src in zip(c['score']['notes'],harm):
        n['velocity']=src['velocity']
        if 'touch' in src:n.update(pitch=src['sounding'],fret=12,tab='<12>',harmonic='natural, 12th fret (Harm XII)')
    from score_engrave import engrave
    engraving,engraved=engrave(SRC/f'{NAME}.xml',c['score']['notes'],DURATION,OUT/'scores/sonatina','scores/sonatina')
    assert engraved['notes_placed']==engraved['notes'],engraved
    c['score']['engraving']=dict(engraving,edition='Engraved from the GAPS score with Verovio',license='GAPS CC BY-NC-SA 4.0, research use',source='https://aim-qmul.github.io/GAPS/',
        caption='No printed edition is available, so the whole GAPS score is engraved here with Verovio, one system at a time at natural proportions. Each tab number sits under its engraved note (matched by measure, onset order and written pitch); <12> marks the 12th-fret harmonics in bars 11, 35, 142 and 166. Large numbers are frets, small numbers left-hand fingers where the score marks them. The blue playhead follows Međugorac’s timing between notes.',
        check=dict(measures_matched=engraved['matched'],unmatched=engraved['unmatched']))
    fitted=[dict(n) for n in harm];top=max(n['velocity'] for n in fitted)
    mid=OUT/'guitar-sonatina-harmonics.mid';export_midi([dict(n,pitch=n.get('sounding',n['pitch']),velocity=max(1,int(round(n['velocity']*127/top)))) for n in fitted],mid)
    events=OUT/'guitar-sonatina-harmonics-events.json';events.write_text(json.dumps(fitted,indent=2,default=float)+'\n')
    c['downloads']=[dict(label='Performance MIDI (fitted velocities, loudest = 127)',url=mid.name),dict(label='Notes, strings, harmonic touch',url=events.name)]
    c['sustain']=dict(method='guitar_sustain.let_ring',stops=ring)
    c['dynamics']=dict(model=model.name,range_exponent=info['gamma'],room=room,method='room-aware band-power fit',envelope_error_db=dict(constant_with_room=info['constant_error_db'],fitted_with_room=info['fitted_error_db']))
    c['alignment']=dict(source_audio_offset_seconds=origin,method='Published GAPS fine-aligned MIDI (f-measure 0.97); audio lag check -10 ms; arpeggiated final chord re-timed from the GAPS transcription model',strum=strum,source='https://aim-qmul.github.io/GAPS/',recording_performer='Inon Međugorac',youtube='M066__FzA6k',
        source_sha256=hashlib.sha256((SRC/f'{NAME}-fine-aligned.mid').read_bytes()).hexdigest())
    data=json.loads((OUT/'stringlab.json').read_text())
    data['clips']=[x for x in data['clips'] if x['id']!=c['id']]+[c]
    if 'Međugorac' not in data['attribution']:data['attribution']+=' Sonatina III: Inon Međugorac / GAPS (local noncommercial research only).'
    tmp=OUT/'stringlab.tmp';tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(OUT/'stringlab.json')
    (DOC/'guitar-sonatina-report.json').write_text(json.dumps(dict(clip=c,harmonics=[dict(start=h['start'],bar=h['score_measure'],string=h['string'],velocity=h['velocity'],touch=h['touch']) for h in hs_],dynamics=info,origin=origin,duration=DURATION,engraving=c['score']['engraving']['check']),indent=2,default=float)+'\n')


if __name__=='__main__':main()
