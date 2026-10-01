"""Import GOAT tablature / performed violin contours and append local auditions.

Run with build/body-venv/bin/python. Keeps source files and earlier audio intact.
"""
import bisect
import ctypes as ct
import hashlib
import json
from pathlib import Path
import guitarpro
import mido
import numpy as np
from stringlab_audition import ROOT, OUT, SR, P, ptr, library, checks, write_clip

DOC = ROOT / 'experiments/string-gestures'
GUITAR = ROOT / 'research/strings/midi/guitar/goat/audio-examples/example1/example1.gp5'
VIOLIN = ROOT / 'research/strings/midi/violin/Wohlfahrt/Wohlfahrt_Op45-08_BernardChevalier_b_OfyqFc_kI-0000-0080.mid'


def setup(lib):
    lib.pf_lab_string_size.restype = ct.c_size_t
    lib.pf_lab_string_material.argtypes = [ct.c_void_p,ct.c_double,ct.c_double,ct.c_int,ct.c_double,ct.c_int]
    lib.pf_lab_string_loading.argtypes = [ct.c_void_p,ct.POINTER(ct.c_double)]
    lib.pf_lab_string_init.argtypes = [ct.c_void_p,ct.c_double,ct.c_double,ct.c_int,ct.c_double]
    lib.pf_lab_string_pitch.argtypes = [ct.c_void_p,ct.c_double,ct.c_int,ct.c_double]
    lib.pf_lab_string_release.argtypes = [ct.c_void_p]
    lib.pf_lab_string_legato.argtypes = [ct.c_void_p,ct.c_double,ct.c_int,ct.c_double,ct.c_double]
    lib.pf_lab_string_touch.argtypes = [ct.c_void_p,ct.c_double,ct.c_double]
    lib.pf_lab_string_touch_width.argtypes = [ct.c_void_p,ct.c_double,ct.c_double,ct.c_double]
    # Void C functions: without this ctypes reads a garbage int as their result.
    for name in ('pf_lab_string_legato','pf_lab_string_touch','pf_lab_string_touch_width','pf_lab_string_release','pf_lab_string_process','pf_lab_string_pitch'):getattr(lib,name).restype = None
    lib.pf_lab_string_process.argtypes = [ct.c_void_p,P,ct.c_int]
    lib.pf_lab_string_hammer.argtypes = [ct.c_void_p,ct.c_double,ct.c_int,ct.c_double]
    lib.pf_lab_bow_controls.argtypes = [ct.c_void_p,ct.c_int,ct.c_int,ct.c_double,ct.c_double,ct.c_double,ct.c_double]
    lib.pf_lab_bow_pitch.argtypes = [ct.c_void_p,ct.c_double]


def goat():
    song = guitarpro.parse(str(GUITAR)); track = song.tracks[0]
    notes = []; previous = {}
    # This example has no tempo changes or repeat markers. Beat starts are absolute.
    assert not any(m.header.isRepeatOpen or m.header.repeatClose > 0 for m in track.measures)
    for measure in track.measures:
        for voice in measure.voices:
            for beat in voice.beats:
                assert beat.effect.mixTableChange is None, 'Tempo changes need an explicit adapter'
                start = (beat.start - 960) / 960 * 60 / song.tempo
                duration = beat.duration.time / 960 * 60 / song.tempo
                for n in beat.notes:
                    if n.type == guitarpro.NoteType.tie:
                        assert n.string in previous
                        previous[n.string]['end'] = start + duration
                        continue
                    assert n.type == guitarpro.NoteType.normal
                    string = track.strings[n.string - 1]
                    effect = n.effect
                    row = dict(start=start,end=start+duration,pitch=string.value+n.value,
                               velocity=n.velocity,string=n.string,fret=n.value,
                               hammer_to=effect.hammer,slides=[s.name for s in effect.slides],
                               bend=[(p.position / guitarpro.BendEffect.maxPosition,p.value / 2)
                                     for p in effect.bend.points] if effect.bend else [],
                               mute=effect.palmMute)
                    notes.append(row); previous[n.string] = row
    notes.sort(key=lambda n:(n['start'],n['string']))
    origin = notes[0]['start']
    for n in notes: n['start'] -= origin; n['end'] -= origin
    # Retain exact string/fret identity and link hammer/legato-slide destinations.
    for string in range(1,7):
        sequence = [n for n in notes if n['string'] == string]
        for a,b in zip(sequence,sequence[1:]):
            connected = abs(a['end'] - b['start']) < .002
            if connected and (a['hammer_to'] or 'legatoSlideTo' in a['slides']):
                b['transition'] = 'hammer' if a['hammer_to'] else 'slide'
                b['from_pitch'] = a['pitch']
            if connected and a['slides']:
                a['slide_to'] = b['pitch']
    return notes, song.tempo


def performed_violin():
    clock = 0.; notes = []; active = {}; bends = {c:[] for c in range(16)}
    for msg in mido.MidiFile(VIOLIN):
        clock += msg.time
        if msg.type == 'pitchwheel': bends[msg.channel].append((clock,msg.pitch / 4096))
        elif msg.type == 'note_on' and msg.velocity:
            key = (msg.channel,msg.note); assert key not in active
            active[key] = dict(start=clock,pitch=msg.note,velocity=msg.velocity,channel=msg.channel)
        elif msg.type == 'note_off' or msg.type == 'note_on' and not msg.velocity:
            row = active.pop((msg.channel,msg.note),None)
            if row: row['end'] = clock; notes.append(row)
    assert not active
    notes.sort(key=lambda n:n['start']); origin = notes[0]['start']
    for n in notes:
        series = bends[n['channel']]; times = [v[0] for v in series]
        lo = max(0,bisect.bisect_right(times,n['start'])-1)
        hi = bisect.bisect_right(times,n['end'])
        n['curve'] = [(max(t,n['start'])-n['start'],v) for t,v in series[lo:hi]]
        assert n['curve']; n['start'] -= origin; n['end'] -= origin
    from string_hand_geometry import infer, audit
    infer(notes, True)
    assert audit(notes, True)['passed']
    return notes


def guitar_pitch(n,t,gestures):
    pitch = float(n['pitch'])
    if not gestures: return pitch
    length = n['end'] - n['start']; phase = min(1,max(0,(t-n['start'])/length))
    if n['bend']:
        pitch += np.interp(phase,*zip(*n['bend']))
    if 'slide_to' in n and phase > .72:
        # Fretted slide traverses successive contacts on a 128-frame control
        # grid. Timing is an explicit interpretation of GP.
        amount = (phase-.72)/.28; delta = n['slide_to']-n['pitch']
        pitch = n['pitch']+np.sign(delta)*min(abs(delta),np.floor(abs(delta)*amount+.5))
    return pitch


def render_guitar(lib,notes,duration,gestures,variation=0,seed=7201,block=128,body=True,material=0,loading=None,velocity_cap=1):
    # velocity_cap > 1 is opt-in for fitted dynamics louder than MIDI 127; default unchanged.
    output = np.zeros(round(duration*SR),np.float32)
    states = {s:ct.create_string_buffer(lib.pf_lab_string_size()) for s in range(1,7)}
    owners = {}; rng = np.random.default_rng(seed); params = {}
    events = []
    for i,n in enumerate(notes):
        events += [(round(n['start']*SR),1,i),(round(n['end']*SR),0,i)]
        params[i] = (.19+variation*rng.uniform(-.012,.012),1+variation*rng.uniform(-.035,.035))
        # Opt-in natural harmonic: a finger touch from the onset, lifted after `lift` s.
        if n.get('touch'): events.append((round((n['start']+n['touch']['lift'])*SR),2,i))
    events.sort(); cursor = 0
    for at in range(0,len(output),block):
        end = min(at+block,len(output)); boundaries = [at,end]
        while cursor < len(events) and events[cursor][0] < end:
            boundaries.append(max(at,events[cursor][0])); cursor += 1
        # Event indexing below is independent of rendering block size.
        for a,b in zip(sorted(set(boundaries)),sorted(set(boundaries))[1:]):
            for _,kind,i in [e for e in events if e[0] == a]:
                n = notes[i]; s = n['string']
                if kind == 2:
                    if owners.get(s) == i: lib.pf_lab_string_touch(states[s],0,0)
                elif kind:
                    connected = gestures and n.get('transition') in ('slide','hammer','legato') and s in owners
                    pos,gain = params[i]
                    pos = n.get('pluck_position',pos)
                    if not connected:
                        if material:
                            lib.pf_lab_string_material(states[s],n['pitch'],min(velocity_cap,n['velocity']/127*gain),s,pos,material)
                            if loading is not None:
                                losses=np.ascontiguousarray(loading(n),dtype=np.float64)
                                lib.pf_lab_string_loading(states[s],losses.ctypes.data_as(ct.POINTER(ct.c_double)))
                        else:lib.pf_lab_string_init(states[s],n['pitch'],min(velocity_cap,n['velocity']/127*gain),s,pos)
                        if n.get('touch'):
                            t = n['touch']
                            # Opt-in finger width; without it the point touch is unchanged.
                            if t.get('width'): lib.pf_lab_string_touch_width(states[s],t['position'],t['rho'],t['width'])
                            else: lib.pf_lab_string_touch(states[s],t['position'],t['rho'])
                    elif n['transition'] == 'hammer':
                        lib.pf_lab_string_hammer(states[s],n['pitch'],s,n['velocity']/127)
                    elif n['transition'] == 'legato':
                        # Opt-in physical hammer-on / pull-off (pf_pluck_legato).
                        lib.pf_lab_string_legato(states[s],n['pitch'],s,n['legato_amount'],n.get('legato_contact',5e-4))
                    owners[s] = i
                elif owners.get(s) == i:
                    # Connected successor arrives at exactly this frame; do not
                    # damp the ringing string before hammer/slide continuation.
                    successor = next((j for frame,k,j in events if frame==a and k==1 and notes[j]['string']==s),None)
                    # A slurred successor keeps the string fretted: aligned MIDI may end the
                    # first note a few ms before the slur, which must not drop the damper.
                    slurred = gestures and any(m.get('transition')=='legato' and m['string']==s and 0<=m['start']-n['end']<.15 for m in notes[i+1:])
                    if not (gestures and successor is not None and notes[successor].get('transition')) and not slurred:
                        lib.pf_lab_string_release(states[s])
            for s,i in owners.items():
                n = notes[i]; pitch = guitar_pitch(n,a/SR,gestures)
                lib.pf_lab_string_pitch(states[s],pitch,s,25 if n['mute'] else 0)
                lib.pf_lab_string_process(states[s],ptr(output[a:b]),b-a)
    if body:lib.pf_lab_body(ptr(output),len(output),0)
    assert np.isfinite(output).all() and np.abs(output).max() < 10
    return output


def render_violin(lib,notes,duration,contours=True,variation=0,seed=7201,block=128):
    output = np.zeros(round(duration*SR),np.float32)
    states = {s:ct.create_string_buffer(lib.pf_lab_bow_size()) for s in range(4)}
    for s in states: lib.pf_lab_bow_init(states[s],69,.6,0);lib.pf_lab_bow_release(states[s])
    owners = {}; rng = np.random.default_rng(seed); params = {}; events = []
    for i,n in enumerate(notes):
        params[i] = dict(contact=.12+variation*rng.uniform(-.009,.009),pressure=3+variation*rng.uniform(-.16,.16),attack=.055+variation*rng.uniform(-.015,.015),speed=1+variation*rng.uniform(-.045,.045),phase=rng.uniform(0,6.28))
        events += [(round(n['start']*SR),1,i),(round(n['end']*SR),0,i)]
    events.sort(); by_frame = {}
    for frame,k,i in events: by_frame.setdefault(frame,[]).append((k,i))
    # Keep imported channel contours attached to each note before mapping strings.
    times = {i:np.array([v[0] for v in n['curve']]) for i,n in enumerate(notes)}
    values = {i:np.array([v[1] for v in n['curve']]) for i,n in enumerate(notes)}
    boundaries = sorted(set([0,len(output),*range(0,len(output),block),*[f for f in by_frame if 0<=f<len(output)]]))
    for a,b in zip(boundaries,boundaries[1:]):
        for kind,i in by_frame.get(a,[]):
            n = notes[i]; s = n['string']
            if kind:
                owners[s] = i;lib.pf_lab_bow_note(states[s],n['pitch'],n['velocity']/127)
            elif owners.get(s) == i: lib.pf_lab_bow_release(states[s])
        for s,i in owners.items():
            n = notes[i]; p = params[i]; t = a/SR-n['start']
            pitch = n['pitch'] + (np.interp(t,times[i],values[i]) if contours else 0)
            lib.pf_lab_bow_pitch(states[s],pitch)
            drift = 1+variation*.018*np.sin(2*np.pi*.8*t+p['phase'])
            lib.pf_lab_bow_controls(states[s],s,int(n['stopped']),p['contact'],p['pressure'],p['attack'],(.06+.22*n['velocity']/127)*p['speed']*drift)
            lib.pf_lab_bow_process(states[s],ptr(output[a:b]),b-a)
    lib.pf_lab_body(ptr(output),len(output),1)
    assert np.isfinite(output).all() and np.abs(output).max() < 3
    return output


def export_midi(notes,path,violin=False):
    midi = mido.MidiFile(ticks_per_beat=960); track = mido.MidiTrack(); midi.tracks.append(track)
    events = [(0,mido.MetaMessage('set_tempo',tempo=500000))]
    channels = sorted({n['channel'] if violin else n['string']-1 for n in notes})
    for channel in channels:
        events.append((0,mido.Message('program_change',channel=channel,program=40 if violin else 24)))
        for cc,value in [(101,0),(100,0),(6,12),(38,0),(101,127),(100,127)]:
            events.append((0,mido.Message('control_change',channel=channel,control=cc,value=value)))
    for n in notes:
        channel = n['channel'] if violin else n['string']-1
        events.append((n['start'],mido.Message('note_on',channel=channel,note=n['pitch'],velocity=n['velocity'])))
        events.append((n['end'],mido.Message('note_off',channel=channel,note=n['pitch'],velocity=0)))
        for t in np.arange(n['start'],n['end'],1/200):
            offset = np.interp(t-n['start'],*zip(*n['curve'])) if violin else guitar_pitch(n,t,True)-n['pitch']
            value = int(np.clip(round(offset/12*8192),-8192,8191))
            events.append((float(t),mido.Message('pitchwheel',channel=channel,pitch=value)))
    last = 0
    for t,msg in sorted(events,key=lambda e:(e[0],0 if e[1].type=='note_off' else 1)):
        tick = round(t*1920);track.append(msg.copy(time=tick-last));last=tick
    midi.save(path)


def main():
    DOC.mkdir(parents=True,exist_ok=True);(OUT/'audio').mkdir(parents=True,exist_ok=True)
    lib,sources = library();setup(lib);verified = checks(lib)
    gn,tempo = goat();vn = performed_violin()
    # First guitar phrase spans bends, hammer transitions, and legato slides.
    gn = [n for n in gn if n['start'] < 33]
    guitar_end = min(33,max(n['end'] for n in gn))
    for n in gn: n['end'] = min(n['end'],guitar_end)
    vn = [n for n in vn if n['start'] < 27]
    violin_end = max(n['end'] for n in vn)
    gd = guitar_end+1; vd = violin_end+1
    for name,notes in [('guitar-goat',gn),('violin-wohlfahrt',vn)]:
        (DOC/(name+'-events.json')).write_text(json.dumps(notes,indent=2)+'\n')
        export_midi(notes,OUT/(name+'-gestures.mid'),name.startswith('violin'))
    print('Imported',len(gn),'guitar notes and',len(vn),'violin notes',flush=True)
    ga = render_guitar(lib,gn,gd,False);gb = render_guitar(lib,gn,gd,True);gc = render_guitar(lib,gn,gd,True,1)
    print('Guitar rendered',flush=True)
    va = render_violin(lib,vn,vd,False);vb = render_violin(lib,vn,vd,True);vc = render_violin(lib,vn,vd,True,1)
    print('Violin rendered',flush=True)
    # Tests exercise imported gestures, not only isolated notes.
    assert not np.array_equal(ga,gb) and not np.array_equal(gb,gc)
    assert not np.array_equal(va,vb) and not np.array_equal(vb,vc)
    assert np.array_equal(vc,render_violin(lib,vn,vd,True,1))
    assert np.array_equal(gc,render_guitar(lib,gn,gd,True,1))
    assert any(n['bend'] for n in gn) and any(n.get('transition')=='hammer' for n in gn)
    assert any(n.get('transition')=='slide' for n in gn)
    for name in ['guitar-goat','violin-wohlfahrt']:
        imported=list(mido.MidiFile(OUT/(name+'-gestures.mid')))
        assert sum(m.type=='note_on' and m.velocity>0 for m in imported)==len(gn if name.startswith('guitar') else vn)
        assert any(m.type=='pitchwheel' and m.pitch for m in imported)
    verified += ['Imported MIDI timing and per-channel bends retained in note curves; violin bend range verified from author code (4096 units/semitone).',
                 'GOAT tie notes merged; fret/string identities, bend points, hammer transitions and legato slides retained.',
                 'Full excerpts finite and bounded; gesture and variation outputs differ; seeded re-renders exactly reproducible.']
    clips = [
        write_clip('guitar-goat-gestures','Guitar · GOAT example 1','Bends / hammer transitions / slides',dict(current=ga,fitted=gb,ref=gc),dict(current='Notes + string identity',fitted='Tablature gestures',ref='Gestures + note variation'),'Exact GOAT string/fret assignment and Guitar Pro timing. B retains bends, ties, hammer transitions and legato slides. The third version adds small seeded pluck-position and excitation changes. Slide timing and hammer excitation are prototype interpretations, not captured gestures.','With variation','Which gesture version do you prefer?'),
        write_clip('guitar-goat-variation','Guitar · GOAT note character','Controlled repeat variation',dict(current=gb,fitted=gc,ref=render_guitar(lib,gn,gd,True,1,seed=9031)),dict(current='Gestures, fixed pluck character',fitted='Gestures, varying pluck character',ref='Another variation take'),'Same string identities, source timing and gestures. B adds bounded changes in pluck position and excitation. Third version uses a different repeatable seed; no random timing or pitch drift is added.','Another take','Which note character do you prefer?'),
        write_clip('violin-wohlfahrt-gestures','Violin · Wohlfahrt étude 8','Performed timing / pitch contours',dict(current=va,fitted=vb,ref=vc),dict(current='Performed timing, steady pitch',fitted='Performed pitch contours',ref='Contours + bow variation'),'Wohlfahrt Op.45 No.8, Bernard Chevalier performance-aligned MIDI. B retains recorded/transcribed pitch-bend curves, including vibrato and intonation. String assignment is inferred. The third version adds bounded bow attack, contact, pressure and speed variation. No automatic vibrato is added.','With variation','Which pitch interpretation do you prefer?'),
        write_clip('violin-wohlfahrt-variation','Violin · Wohlfahrt bow character','Controlled attack / tone variation',dict(current=vb,fitted=vc,ref=render_violin(lib,vn,vd,True,1,seed=9031)),dict(current='Contours, fixed bow character',fitted='Contours, varying bow character',ref='Another variation take'),'Source timing and pitch contours stay the same. B varies attack time, bow contact, friction curve and speed subtly. Third version changes the seeded take. This is a designed performance layer, not recovered bow-motion measurements.','Another take','Which bow character do you prefer?'),
        write_clip('violin-wohlfahrt-steady','Violin · steady bow variation','No vibrato / attack and tone only',dict(current=va,fitted=render_violin(lib,vn,vd,False,1),ref=render_violin(lib,vn,vd,False,1,seed=9031)),dict(current='Steady pitch, fixed bow character',fitted='Steady pitch, varying bow character',ref='Another steady take'),'Performed note timing, inferred strings and steady pitch in all three versions. B has small changes in attack and bow tone without vibrato; third version is another seeded take.','Another take','Which steady-bow version do you prefer?')]
    path = OUT/'stringlab.json';data = json.loads(path.read_text())
    ids = {c['id'] for c in clips};data['clips'] = [c for c in data['clips'] if c['id'] not in ids]+clips
    data['attribution'] += ' New guitar: GOAT public example 1, Loth et al. ISMIR 2025. New violin: Tamer et al. ISMIR 2023 Violin MIDI Dataset, Wohlfahrt Op.45 No.8 / Bernard Chevalier performance alignment. Local research auditions; string/body parameters are designed approximations.' if 'New guitar:' not in data['attribution'] else ''
    temp = path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(path)
    (DOC/'report.json').write_text(json.dumps(dict(checks=verified,guitar_tempo=tempo,source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [GUITAR,VIOLIN]},kernels={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},clips=clips),indent=2)+'\n')
    print('Added',len(clips),'listening comparisons',flush=True)


if __name__ == '__main__': main()
