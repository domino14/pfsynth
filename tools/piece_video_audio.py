"""Audio and string motion for a performance video (tools/piece_video.py).

The fitted performance as the listening room plays it, with the piece's body (Sonatina:
g54, Josef Pages, Cadiz 1806, the user's choice; Bach: the closest-ranked body) and the
room fitted to the recording (video_pieces.py): each
string is rendered on its own (the strings are independent in the renderer, so their
sum is the usual render), summed, through the body's measured response, then through
the fitted room - a stereo version, two decorrelated tails (different noise seeds)
sharing the direct sound. Writes the WAV, and each string's envelope at the video frame
rate for the fretboard.

    build/body-venv/bin/python tools/piece_video_audio.py [sonatina|bach]
"""
import json,sys
import numpy as np
from scipy.io import wavfile
from scipy.signal import fftconvolve
from stringlab_audition import ROOT,OUT,SR,library
from string_gesture_audition import setup,render_guitar
from guitar_room_fit import room_impulse
from video_pieces import PIECES

VIDEO=ROOT/'build/video';FPS=30;LEAD=1.5;TAIL=5.0


def main(piece='sonatina'):
    cfg=PIECES[piece];VIDEO.mkdir(parents=True,exist_ok=True)
    lib,_=library();setup(lib)
    data=json.loads((OUT/'stringlab.json').read_text());clip=next(c for c in data['clips'] if c['id']==cfg['clip'])
    BODY=clip['bodyChoice']['default'] if cfg['body']=='auto' else cfg['body'];ROOM=cfg['room']
    notes=json.loads((OUT/f"{cfg['clip']}-events.json").read_text());duration=clip['duration']
    print(piece,'body',BODY,'room',ROOM,flush=True)
    strings={}
    for s in range(1,7):
        mine=[n for n in notes if n['string']==s]
        strings[s]=render_guitar(lib,mine,duration,True,0,body=False,material=1,loading=None,velocity_cap=4).astype(float) if mine else np.zeros(round(duration*SR))
        print('string',s,len(mine),'notes',flush=True)
    whole=render_guitar(lib,notes,duration,True,0,body=False,material=1,loading=None,velocity_cap=4).astype(float)
    force=sum(strings.values());err=np.abs(force-whole).max()/np.abs(whole).max()
    print('per-string sum vs whole render: max difference %.2e of peak'%err,flush=True);assert err<1e-4
    sr,ir=wavfile.read(OUT/f'bodies/{BODY}.wav');assert sr==SR;ir=ir.astype(float)
    body=fftconvolve(force,ir)[:len(force)]
    room=json.loads((ROOT/'experiments/string-gestures'/ROOM).read_text())['best']
    pad=np.zeros(round(TAIL*SR));y=np.concatenate([body,pad]);out=[]
    for seed in (1,2):
        r=room_impulse(room['rt_low'],room['rt_high'],room['ratio'],seed=seed);out.append(fftconvolve(y,r)[:len(y)])
    st=np.stack(out,1);st=np.concatenate([np.zeros((round(LEAD*SR),2)),st])
    fade=round(1.5*SR);st[-fade:]*=np.linspace(1,0,fade)[:,None]**2
    st*=10**(-1/20)/np.abs(st).max()                                   # peak -1 dBFS
    wavfile.write(VIDEO/f"{cfg['out']}-audio.wav",SR,np.round(st*32767).astype(np.int16))
    # String envelopes at the frame rate (RMS over 50 ms around each frame time).
    total=len(st)/SR;frames=int(total*FPS);env=np.zeros((6,frames));w=round(.05*SR)
    for s in range(1,7):
        x=np.concatenate([np.zeros(round(LEAD*SR)),strings[s],np.zeros(round(TAIL*SR))])
        c=np.cumsum(np.concatenate([[0],x*x]))
        for k in range(frames):
            a=max(0,round(k/FPS*SR)-w//2);b=min(len(x),a+w);env[s-1,k]=np.sqrt((c[b]-c[a])/max(1,b-a))
    np.savez_compressed(VIDEO/f"{cfg['out']}-strings.npz",env=env,fps=FPS,lead=LEAD,tail=TAIL,duration=duration,body=BODY)
    rms=20*np.log10(np.sqrt(np.mean(st**2)))
    print(f'{total:.1f} s, peak -1 dBFS, RMS {rms:.1f} dBFS; room RT60 {room["rt_low"]}/{room["rt_high"]} s, ratio {room["ratio"]}',flush=True)


if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else 'sonatina')
