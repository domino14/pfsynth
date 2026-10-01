"""Room menu: the rooms fitted to each recording (guitar_room_fit.py), applied in the browser.

Each fitted room becomes an impulse response (direct sound plus octave-band noise
decaying with the fitted RT60s, tail energy = the fitted reverberant/direct ratio) that
the listening room convolves after the body, on the synth versions only. Per clip and
room, gains keep the synth versions level with the recording; a headroom factor keeps
every room below full scale (applied to the recording too).

    build/body-venv/bin/python tools/guitar_room_choice.py
"""
import json,re
import numpy as np
from scipy.io import wavfile
from scipy.signal import fftconvolve
from stringlab_audition import ROOT,OUT,SR
from guitar_room_fit import room_impulse

DOC=ROOT/'experiments/string-gestures'
ROOMS=[('kowalski','guitar-room-fit-refined.json','Fitted to Kowalski’s recording (GSI showroom)'),
       ('medugorac','guitar-room-fit-sonatina.json','Fitted to Međugorac’s recording'),
       ('kowalski-ring','guitar-room-fit-bach-full-ring.json','Fitted to Kowalski’s recording, strings ringing (full Prelude)'),
       ('medugorac-ring','guitar-room-fit-sonatina-ring.json','Fitted to Međugorac’s recording, strings ringing')]


def main():
    (OUT/'rooms').mkdir(exist_ok=True);rooms=[];irs={}
    for rid,report,label in ROOMS:
        path=DOC/report
        if not path.exists():continue
        r=json.loads(path.read_text());b=r['best'];irs[rid]=room_impulse(b['rt_low'],b['rt_high'],b['ratio'])
        wavfile.write(OUT/f'rooms/{rid}.wav',SR,irs[rid].astype(np.float32))
        rooms.append(dict(id=rid,label=label,ir=f'rooms/{rid}.wav',rt60_200hz=b['rt_low'],rt60_4khz=b['rt_high'],reverb_to_direct=b['ratio'],
            note=f"Reverberation time {b['rt_low']:.1f} s at 200 Hz, {b['rt_high']:.1f} s at 4 kHz; reverberant energy {b['ratio']:.1f}× the direct sound. "
                 f"Fitted jointly with note velocities to {r.get('clip','guitar-bach-dynamics')} ({r.get('seconds',18):.0f} s); a statistical room, not a measured impulse response."))
    data=json.loads((OUT/'stringlab.json').read_text());summary={}
    for c in data['clips']:
        c.pop('roomChoice',None)
        if not (c['id'].startswith('guitar') and re.match('Real performance',c['labels']['ref'])):continue
        x={k:wavfile.read(OUT/f"audio/{c['id']}-{k}.wav")[1].astype(float)/32768 for k in ('current','fitted')}
        gains={};headroom={}
        for rid,ir in irs.items():
            gains[rid]={};peak=0
            for k,y in x.items():
                z=fftconvolve(y,ir)[:len(y)];g=np.sqrt(np.mean(y**2)/np.mean(z**2));gains[rid][k]=round(float(g),6);peak=max(peak,g*np.abs(z).max())
            headroom[rid]=round(min(1.,.95/peak),4)
        c['roomChoice']=dict(gains=gains,headroom=headroom);summary[c['id']]=headroom
    data['rooms']=rooms
    tmp=OUT/'stringlab.tmp';tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(OUT/'stringlab.json')
    print(len(rooms),'rooms;',len(summary),'clips',summary)


if __name__=='__main__':main()
