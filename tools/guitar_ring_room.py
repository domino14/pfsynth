"""Was the fitted rooms' long bass reverberation standing in for strings that stopped
too soon? For each full performance, the room is fitted on its first 24 s twice, on the
same grid: with the aligned MIDI's durations (strings stopped at note-off) and with the
strings left to ring (guitar_sustain.let_ring). The ringing fits are the rooms used from
now on (guitar-room-fit-<piece>-ring.json).

    build/body-venv/bin/python tools/guitar_ring_room.py
"""
import copy,json
import numpy as np
from scipy.io import wavfile
from stringlab_audition import ROOT,OUT,SR,library
from string_gesture_audition import setup
from guitar_dynamics_fit import Model
from guitar_room_fit import fit_room
from guitar_sustain import let_ring

DOC=ROOT/'experiments/string-gestures';SECONDS=24.
PIECES={'bach-full':('guitar-bach-full','Kowalski'),'sonatina':('guitar-sonatina-harmonics','Međugorac')}


def main():
    lib,_=library();setup(lib);model=Model(lib,'nylon / Gil de Avalle body + loading',5,True)
    for key,(cid,who) in PIECES.items():
        ev=json.loads((OUT/f'{cid}-events.json').read_text())
        for n in ev:n['end']=n.get('end_written',n['end'])                       # MIDI durations
        ref=wavfile.read(OUT/f'audio/{cid}-ref.wav')[1].astype(float)/32768
        stopped=[dict(n,velocity=100) for n in ev if n['start']<SECONDS-.5];ringing=copy.deepcopy(stopped)
        let_ring(ringing,SECONDS)
        print(key,len(stopped),'notes; median duration %.2f -> %.2f s'%(np.median([n['end']-n['start'] for n in stopped]),np.median([n['end']-n['start'] for n in ringing])),flush=True)
        a=fit_room(model,stopped,ref,SECONDS,lambda s:print('  stopped at note-off:',s,flush=True))
        b=fit_room(model,ringing,ref,SECONDS,lambda s:print('  strings ring:       ',s,flush=True))
        (DOC/f'guitar-room-fit-{key}-ring.json').write_text(json.dumps(dict(method=__doc__.strip().splitlines()[0],clip=cid,seconds=SECONDS,performer=who,
            best=b['best'],dry=b['dry'],stopped=dict(best=a['best'],dry=a['dry']),rows=b['rows']),indent=1)+'\n')


if __name__=='__main__':main()
