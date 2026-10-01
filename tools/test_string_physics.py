"""Regression checks for the opt-in left-hand physics: legato and harmonic touch."""
import ctypes as ct
import unittest
import numpy as np
from stringlab_audition import library,SR,ptr
from string_gesture_audition import setup

LIB,_=library();setup(LIB)

def render(steps,seconds,string=2,midi=64,pos=.19):
    """steps: {frame: callable(state) -> new MIDI pitch or None} before that frame."""
    st=ct.create_string_buffer(LIB.pf_lab_string_size());LIB.pf_lab_string_material(st,midi,.7,string,pos,1)
    out=np.zeros(round(seconds*SR),np.float32);cur=midi
    for a in range(0,len(out),64):
        for frame,step in steps.items():
            if a<=frame<a+64:
                new=step(st)
                if new is not None:cur=new
        LIB.pf_lab_string_pitch(st,cur,string,0);LIB.pf_lab_string_process(st,ptr(out[a:a+64]),min(64,len(out)-a))
    return out.astype(float)

def partial(x,f):
    X=np.abs(np.fft.rfft(x*np.hanning(len(x)),1<<16));fr=np.fft.rfftfreq(1<<16,1/SR)
    return 20*np.log10(X[(fr>f*.97)&(fr<f*1.03)].max()+1e-12)

class LegatoTests(unittest.TestCase):
    def test_same_pitch_reexpansion_is_transparent(self):
        ref=render({},1.)
        same=render({13230:lambda s:LIB.pf_lab_string_legato(s,64,2,0.,0.)},1.)
        self.assertLess(np.linalg.norm(same[13230:]-ref[13230:])/np.linalg.norm(ref[13230:]),1e-3)

    def test_hammer_and_pull_land_on_pitch_and_decay(self):
        for midi,amount in ((66,7e-4),(63,6e-4)):
            x=render({17640:lambda s,m=midi,a=amount:(LIB.pf_lab_string_legato(s,m,2,a,5e-4),m)[1]},1.5)
            self.assertTrue(np.isfinite(x).all())
            seg=x[round(.45*SR):round(.75*SR)];f=440*2**((midi-69)/12)
            self.assertGreater(partial(seg,f),partial(seg,440*2**((64-69)/12))+10)
            self.assertLess(np.abs(x[-4410:]).max(),np.abs(x[17640:22050]).max())

class TouchTests(unittest.TestCase):
    def test_touch_off_is_bit_identical(self):
        self.assertTrue(np.array_equal(render({},.5),render({0:lambda s:LIB.pf_lab_string_touch(s,.5,0.)},.5)))

    def test_twelfth_fret_touch_keeps_even_partials(self):
        f0=440*2**((64-69)/12)
        open_=render({},1.2,string=1,pos=.12)[13230:]
        harm=render({0:lambda s:LIB.pf_lab_string_touch(s,.5,424.),2205:lambda s:LIB.pf_lab_string_touch(s,0,0)},1.2,string=1,pos=.12)[13230:]
        self.assertLess(partial(harm,f0)-partial(open_,f0),-40)        # fundamental drained
        self.assertGreater(partial(harm,2*f0)-partial(open_,2*f0),-1)  # octave untouched

if __name__=='__main__':unittest.main()
