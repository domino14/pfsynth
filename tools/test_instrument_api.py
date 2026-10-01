"""The C instrument API (src/host/pfi.c, pf_guitar.c) against the offline renderers.

Guitar: pf_instrument_guitar must render exactly what tools/string_gesture_audition.py
render_guitar renders (material strings, no loading, velocity headroom 4) on the same
notes - the Bach (hammer-ons and pull-offs) and the Sonatina (harmonics) - with the
inputs rounded to the score format's float32 fields on both sides.
Piano: build/apitest checks the pf_player adapter (src/host/apitest.c).

    build/body-venv/bin/python tools/test_instrument_api.py
"""
import ctypes as ct,json,subprocess,unittest
import numpy as np
from stringlab_audition import ROOT,OUT,SR,library
from string_gesture_audition import setup,render_guitar

SOURCES=['src/host/pfi.c','src/host/pf_instrument.c','src/host/pf_piano_instrument.c','src/host/pf_guitar.c','src/host/pf_score_io.c',
         'src/host/pfplayer.c','src/host/midi.c','src/core/pf_partial.c','src/core/pf_attack.c','src/core/pf_resonance.c','src/core/pf_pluck.c']
ART={'normal':0,'hammer-on':1,'pull-off':2,'slide':3,'harmonic':4,'muted':5,'tie':6}


class Note(ct.Structure):
    _fields_=[('start',ct.c_double),('end',ct.c_double),('pitch',ct.c_float),('velocity',ct.c_float),('art_param',ct.c_float),('slide_to',ct.c_float),
              ('bend_first',ct.c_int),('bend_count',ct.c_int),('string',ct.c_byte),('fret',ct.c_byte),('finger',ct.c_byte),('articulation',ct.c_ubyte),('reserved',ct.c_int)]


class Score(ct.Structure):
    _fields_=[('notes',ct.POINTER(Note)),('n_notes',ct.c_int),('controls',ct.c_void_p),('n_controls',ct.c_int),('bends',ct.c_void_p),('n_bends',ct.c_int),
              ('tuning',ct.POINTER(ct.c_byte)),('n_strings',ct.c_int),('duration',ct.c_double)]


def api():
    subprocess.run(['cc','-O2','-std=c99','-Wall','-Wextra','-dynamiclib',*SOURCES,'-o','build/pfinstrument.dylib'],cwd=ROOT,check=True)
    lib=ct.CDLL(str(ROOT/'build/pfinstrument.dylib'))
    lib.pfi_size.restype=ct.c_ulong;lib.pfi_size.argtypes=[ct.c_char_p]
    lib.pfi_init.argtypes=[ct.c_void_p,ct.c_char_p,ct.c_double]
    lib.pfi_param_find.argtypes=[ct.c_void_p,ct.c_char_p]
    lib.pfi_set.argtypes=[ct.c_void_p,ct.c_int,ct.c_double]
    lib.pfi_load.argtypes=[ct.c_void_p,ct.POINTER(Score)]
    lib.pfi_render.argtypes=[ct.c_void_p,ct.POINTER(ct.c_float),ct.POINTER(ct.c_float),ct.c_int]
    lib.pfi_param_count.argtypes=[ct.c_void_p];lib.pfi_param_name.argtypes=[ct.c_void_p,ct.c_int];lib.pfi_param_name.restype=ct.c_char_p
    return lib


def f32(x):return float(np.float32(x))


def to_score(events,seconds,tuning):
    """Offline events (string_gesture_audition format) -> score notes; float32 fields rounded
    the same way for the Python reference."""
    keep=[dict(e) for e in events if e['start']<seconds];arr=(Note*len(keep))()
    for e,n in zip(keep,arr):
        e['velocity']=f32(e['velocity'])
        art='normal';param=0.
        if e.get('transition')=='legato':art='hammer-on' if e.get('articulation','').startswith('hammer') else 'pull-off';e['legato_amount']=f32(e['legato_amount']);param=e['legato_amount']
        if e.get('touch'):art='harmonic';param=12
        n.start,n.end=e['start'],e['end'];n.pitch=e.get('sounding',e['pitch']) if art=='harmonic' else e['pitch'];n.velocity=e['velocity']
        n.art_param=param;n.string=e['string'];n.fret=12 if art=='harmonic' else e['fret'];n.finger=e['finger'] if isinstance(e.get('finger'),int) else -1
        n.articulation=ART[art];n.bend_first=n.bend_count=0
    tun=(ct.c_byte*6)(*tuning)
    return keep,arr,Score(arr,len(keep),None,0,None,0,tun,6,seconds),tun


class GuitarMatchesOfflineRenderer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api=api();cls.lab,_=library();setup(cls.lab)

    def render_c(self,score,params):
        lib=self.api;mem=ct.create_string_buffer(lib.pfi_size(b'guitar')+16);lib.pfi_init(mem,b'guitar',SR)
        for k,v in params.items():
            i=lib.pfi_param_find(mem,k.encode());self.assertGreaterEqual(i,0,k);lib.pfi_set(mem,i,v)
        self.assertEqual(lib.pfi_load(mem,ct.byref(score)),0)
        n=round(score.duration*SR);left=np.zeros(n,np.float32);right=np.zeros(n,np.float32)
        for a in range(0,n,128):
            b=min(n,a+128);lib.pfi_render(mem,left[a:].ctypes.data_as(ct.POINTER(ct.c_float)),right[a:].ctypes.data_as(ct.POINTER(ct.c_float)),b-a)
        self.assertTrue(np.array_equal(left,right))
        return left

    def compare(self,clip,tuning,seconds=90.):
        events=json.loads((OUT/f'{clip}-events.json').read_text());keep,arr,score,tun=to_score(events,seconds,tuning)
        fit=json.loads((ROOT/'experiments/string-gestures/harmonic-fit-report.json').read_text())['exaggerated']
        params={'Let strings ring':0,'Velocity headroom':4,'Harmonic touch width':fit['width_fraction']*650,'Harmonic touch damping':fit['rho_per_s'],
                'Harmonic touch time':fit['lift_s']*1000,'Harmonic touch offset':fit['offset_mm'],'Harmonic pluck position':fit['pluck']}
        c=self.render_c(score,params)
        py=render_guitar(self.lab,keep,seconds,True,0,body=False,material=1,loading=None,velocity_cap=4)
        slurs=sum(1 for n in arr if n.articulation in (1,2));harmonics=sum(1 for n in arr if n.articulation==4)
        diff=int((c!=py).sum());print(f'{clip}: {len(keep)} notes ({slurs} slurs, {harmonics} harmonics), {len(c)} samples, {diff} differ, max |d| {np.abs(c-py).max():.3g}',flush=True)
        self.assertEqual(diff,0)

    def test_bach_slurs(self):self.compare('guitar-bach-full',[64,59,55,50,45,40])
    def test_sonatina_harmonics(self):self.compare('guitar-sonatina-harmonics',[64,59,55,50,45,38])

    def test_strings_inferred_when_missing(self):
        """A score without strings (plain MIDI) still plays: every note gets a string and a
        fret in range, simultaneous notes on different strings."""
        events=json.loads((OUT/'guitar-bach-full-events.json').read_text())[:200]
        keep,arr,score,tun=to_score(events,20.,[64,59,55,50,45,40])
        for n in arr:n.string=-1;n.fret=-1;n.finger=-1;n.articulation=0
        x=self.render_c(score,{'Let strings ring':1})
        self.assertTrue(np.isfinite(x).all() and np.abs(x).max()>0)


if __name__=='__main__':unittest.main(verbosity=2)
