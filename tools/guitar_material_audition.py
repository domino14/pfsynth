"""Measured-body / material ablations, weak-coupling string loading approximation."""
import ctypes as ct,json,hashlib,copy
import numpy as np
from scipy.io import loadmat,wavfile
from scipy.signal import fftconvolve,resample_poly
from scipy.ndimage import gaussian_filter1d
from stringlab_audition import ROOT,OUT,SR,library,write_clip,ptr
from string_gesture_audition import setup,render_guitar


def measured_body(raw,guitar):
    x=raw[guitar-1,96000:144000,:];fs=48000;N=65536
    force=x[:,0]*(10000/92.90)*4.4482
    acc=x[:,1]*(10000/10.64)*9.80665
    pressure=x[:,4]*(10000/50)
    win=.5+.5*np.cos(np.arange(fs)*np.pi/fs)
    F=np.fft.rfft(force,N);den=abs(F)**2
    regularizer=den.max()*1e-6
    H=np.fft.rfft(pressure*win,N)*F.conj()/(den+regularizer)
    A=np.fft.rfft(acc*win,N)*F.conj()/(den+regularizer)
    freq=np.fft.rfftfreq(N,1/fs)
    Y=A/np.where(freq>0,2j*np.pi*freq,1);Y[0]=0
    # Raw measured admittance is not assumed passive. Nonnegative, smoothed
    # resistive loading is an explicit weak-coupling approximation only.
    resistance=gaussian_filter1d(np.maximum(Y.real,0),3)
    impulse=np.fft.irfft(H,N)[:round(.15*fs)]
    fade=np.ones(len(impulse));fade[round(.10*fs):]=np.linspace(1,0,len(impulse)-round(.10*fs))
    impulse*=fade
    impulse=resample_poly(impulse,147,160)
    impulse/=np.sqrt(np.sum(impulse**2))
    return dict(freq=freq,resistance=resistance,impulse=impulse,guitar=guitar)


def loading(body,material):
    def loss(n):
        s=n['string'];base=440*2**(([64,59,55,50,45,40][s-1]-69)/12)
        f=440*2**((n['pitch']-69)/12);L=.65*base/f
        if s<=3:
            a=material-1;b=s-1
            mu=np.array([[.438,.588,.915],[.549,.682,.999]])[a,b]*.001
            diameter=np.array([[.718,.839,1.038],[.615,.690,.835]])[a,b]*.001
            E=np.array([[3.74,3.13,2.86],[3.08,3.04,3.]])[a,b]*1e9
            EI=E*np.pi*diameter**4/64
        else:mu=[.002206,.003843,.006129][s-4];EI=2e-5
        T=mu*(2*L*f)**2-EI*(np.pi/L)**2;k=np.arange(1,81)*np.pi/L
        hz=np.sqrt((T*k*k+EI*k**4)/mu)/(2*np.pi)
        return np.clip(T/L*np.interp(hz,body['freq'],body['resistance']),0,10)
    return loss


def main():
    lib,_=library();setup(lib)
    data=json.loads((OUT/'stringlab.json').read_text());original=next(c for c in data['clips'] if c['id']=='guitar-bach-performance')
    notes=json.loads((OUT/'guitar-bach-performance-events.json').read_text());duration=original['duration']
    raw=loadmat(ROOT/'research/strings/body/mores-qualified-selected-impulses.mat')['qualified_selected_impulses']
    bodies={i:measured_body(raw,i) for i in [5,21]}
    old=render_guitar(lib,notes,duration,True,1)
    nylon=render_guitar(lib,notes,duration,True,1,material=1)
    def render(material,guitar,with_loading=True):
        body=bodies[guitar]
        force=render_guitar(lib,notes,duration,True,1,body=False,material=material,loading=loading(body,material) if with_loading else None)
        return fftconvolve(force,body['impulse'])[:len(force)]
    measured=render(1,5);carbon=render(2,5);flamenco=render(1,21)
    unloaded=render(1,5,False)
    print('Rendered material and measured body candidates',flush=True)
    sr,ref=wavfile.read(OUT/'audio/guitar-bach-performance-ref.wav');assert sr==SR
    clips=[]
    for name,title,a,b,la,lb in [
      ('guitar-bach-material','Guitar · string material physics',old,nylon,'Earlier string / designed body','Measured nylon properties / designed body'),
      ('guitar-bach-body','Guitar · measured body resonance',nylon,measured,'Nylon / designed body','Nylon / measured Gil de Avalle body'),
      ('guitar-bach-carbon','Guitar · nylon versus fluorocarbon',measured,carbon,'Nylon trebles / wound basses','Fluorocarbon trebles / same wound basses'),
      ('guitar-bach-body-choice','Guitar · two measured bodies',measured,flamenco,'Gil de Avalle 2014 / nylon','Lester DeVoe 2018 / nylon'),
      ('guitar-bach-loading','Guitar · bridge loading',unloaded,measured,'Measured radiation only','Measured radiation + resistive loading')]:
        assert np.isfinite(a).all() and np.isfinite(b).all() and not np.array_equal(a,b)
        c=write_clip(name,title,'Bach Prelude · matched performance timing',dict(current=a,fitted=b,ref=ref.astype(float)),dict(current=la,fitted=lb,ref='Real performance · Mateusz Kowalski'),'Same Bach performance timing and fingering in both synths. Compare the string material or guitar body named on each button, then check against Kowalski’s recording. Material choices change harmonic stiffness and decay; measured bodies change resonance and string damping. Wound basses are the same in both material sets. This first version approximates bridge loading; full string/body interaction is still to come. Measured responses include some room sound and come from different guitars than Kowalski’s.','Real recording','Which synth is closer to the real performance?')
        c['score']=copy.deepcopy(original['score']);c['downloads']=original['downloads'];clips.append(c)
    ids={c['id'] for c in clips};data['clips']=[c for c in data['clips'] if c['id'] not in ids]+clips
    data['attribution']=data['attribution'].replace('Guitar and violin compositions are original; every candidate is generated by portable C kernels, without audio samples.', 'Early guitar and violin studies are original compositions; synth strings use portable C kernels. Measured-body candidates use Robert Mores impact responses (CC BY 4.0).')
    temp=OUT/'stringlab.tmp';temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(OUT/'stringlab.json')
    report=dict(material_source='https://doi.org/10.1250/ast.44.218',body_source='https://zenodo.org/records/4604577',body_sha256=hashlib.sha256((ROOT/'research/strings/body/mores-qualified-selected-impulses.mat').read_bytes()).hexdigest(),body_ir_seconds=.15,body_ir_fade_start=.10,body_loading='max(smoothed Re(Y),0) times T/L; clipped 0..10 /s. Passive diagonal damping approximation, not a full admittance feedback model.',clips=clips)
    (ROOT/'experiments/string-gestures/guitar-material-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Added',len(clips),'material/body comparisons',flush=True)

if __name__=='__main__':main()
