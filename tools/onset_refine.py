"""Per-note onsets inside chords and strums, measured from the recording.

Note-aligned MIDI (GAPS) can bucket a chord's notes onto one onset even where the player
strums or rolls it (Sonatina III's final, arpeggiated chord has five identical onsets).
For every note that shares its onset with another note (within 30 ms), or carries an
arpeggio mark, this finds the note's own attack in the recording: its partials, minus
any frequency shared with the other chord notes or with strings still ringing, are
tracked on a fine STFT, and the onset is where their log-magnitude rises fastest (the
frame centre at the steepest rise marks the attack). Low notes use a longer window so
their partials separate. A note without a clear attack of its own keeps its MIDI onset.
Isolated notes keep the alignment's timing.
"""
import numpy as np
from scipy.signal import stft

OPEN_WINDOW=(-.08,.12)        # s around the MIDI onset for chord notes (a strum spans < 120 ms)
ARPEGGIO_WINDOW=(-.08,.60)    # for notes under an arpeggio mark


def hz(m):return 440*2**((m-69)/12)


BIAS=.0058      # s; per-note estimator runs 5.8 ms early on isolated notes (median)


def refine(notes,audio,sr,origin,tolerance=.03):
    """Returns per-note changes; updates notes in place (start_midi keeps the old onset).

    Strums and rolls cross the strings in order: when a chord window holds one clear
    attack per note spread over more than 40 ms (or the chord has an arpeggio mark), the
    attacks are assigned in string order, in the direction that best agrees with each
    note's own partial evidence (upward by default under an arpeggio mark). Otherwise
    (a pinch) each note keeps its own estimate if within 40 ms, else its MIDI onset."""
    order=sorted(range(len(notes)),key=lambda i:notes[i]['start'])
    groups=[];cur=[order[0]]
    for i in order[1:]:
        if notes[i]['start']-notes[cur[0]]['start']<=tolerance:cur.append(i)
        else:groups.append(cur);cur=[i]
    groups.append(cur)
    cache={};changes=[]
    def spectrogram(n_fft):
        if n_fft not in cache:
            f,t,Z=stft(audio,sr,nperseg=n_fft,noverlap=n_fft-96,boundary=None,padded=False);cache[n_fft]=(f,t+0.,np.log(np.abs(Z)+1e-9))
        return cache[n_fft]
    def own(n,t0,lo,hi,ringing):
        f0=hz(n['pitch']);n_fft=8192 if f0<120 else 4096 if f0<250 else 2048
        f,t,L=spectrogram(n_fft)
        # A re-plucked string cuts its previous note, so same-string notes are not "others".
        others=[hz(m['pitch'])*k for m in ringing if m is not n and m['string']!=n['string'] for k in range(1,16)]
        partials=[k*f0 for k in range(1,12) if k*f0<5000 and all(abs(k*f0-o)>max(.025*k*f0,2*f[1]) for o in others)]
        if not partials:return None,0.
        frames=np.flatnonzero((t>=origin+t0+lo-.05)&(t<=origin+t0+hi+.05))
        env=sum(L[np.argmin(abs(f-p))-1:np.argmin(abs(f-p))+2][:,frames].max(0) for p in partials)/len(partials)
        slope=np.convolve(np.diff(env),np.ones(5)/5,'same');ts=t[frames][1:];inside=(ts>=origin+t0+lo)&(ts<=origin+t0+hi)
        k=np.flatnonzero(inside)[np.argmax(slope[inside])]
        return float(ts[k]-origin+BIAS),float(slope[k]/(np.median(np.abs(slope))+1e-9))
    def attacks(t0,lo,hi,group):
        # The chord's fundamentals are distinct even in an octave stack: watch that band.
        f0s=[hz(notes[k]['pitch']) for k in group];f,t,L=spectrogram(1024);band=(f>=.8*min(f0s))&(f<=1.2*max(f0s))
        # Threshold against the 1.5 s before the chord as well as the chord itself: inside a
        # chord window most frames are attacks, and what follows may be applause.
        frames=np.flatnonzero((t>=origin+t0-1.5)&(t<=origin+t0+hi+.03))
        flux=np.convolve(np.maximum(np.diff(L[band][:,frames],axis=1),0).sum(0),np.ones(3)/3,'same');ts=t[frames][1:]
        # Attacks of other notes (not in this chord) are not chord notes.
        foreign=[n['start'] for k,n in enumerate(notes) if k not in group and t0+lo-.03<=n['start']<=t0+hi+.03]
        peaks=[i for i in range(1,len(flux)-1) if flux[i]>flux[i-1] and flux[i]>=flux[i+1] and flux[i]>1.5*np.median(flux) and origin+t0+lo<=ts[i]<=origin+t0+hi
               and all(abs(ts[i]-origin-u)>.025 for u in foreign)]
        # Non-maximum suppression: one attack's ripple must not count as several attacks.
        kept=[]
        for i in sorted(peaks,key=lambda i:-flux[i]):
            if all(abs(ts[i]-ts[j])>=.025 for j in kept):kept.append(i)
        return sorted((float(ts[i]-origin),float(flux[i])) for i in kept)
    for g in groups:
        arp=any(notes[i].get('score_arpeggiate') for i in g)
        if len(g)<2 and not arp:continue
        lo,hi=ARPEGGIO_WINDOW if arp else OPEN_WINDOW;t0=notes[g[0]]['start']
        ringing=[n for n in notes if n['start']<t0+hi and n['end']>t0+lo]
        est={i:own(notes[i],t0,lo,hi,ringing) for i in g}
        peaks=attacks(t0,lo,hi,set(g))
        if len(peaks)>=len(g):
            top=sorted(sorted(peaks,key=lambda p:-p[1])[:len(g)]);times=[p[0] for p in top]
        else:times=[]
        if times and (arp or times[-1]-times[0]>.04):
            up=sorted(g,key=lambda i:-notes[i]['string'])          # string 6 first: upward roll
            def disagreement(seq):return sum(abs(est[i][0]-tm) for i,tm in zip(seq,times) if est[i][0] is not None and est[i][1]>=4)
            seq=up if (arp and disagreement(up)<=disagreement(up[::-1])) or (not arp and disagreement(up)<=disagreement(up[::-1])) else up[::-1]
            for i,tm in zip(seq,times):changes.append(dict(index=i,pitch=notes[i]['pitch'],string=notes[i]['string'],midi=notes[i]['start'],refined=round(tm,4),method='strum in string order',direction='up' if seq is up else 'down',arpeggio=arp))
            continue
        for i in g:
            new,strength=est[i]
            if new is not None and strength>=4 and abs(new-t0)<=.04:changes.append(dict(index=i,pitch=notes[i]['pitch'],string=notes[i]['string'],midi=notes[i]['start'],refined=round(new,4),method='own partials (pinch)'))
            else:changes.append(dict(index=i,pitch=notes[i]['pitch'],string=notes[i]['string'],midi=notes[i]['start'],refined=None,reason='kept MIDI onset'))
    for c in changes:
        c['shift_ms']=None if c.get('refined') is None else round((c['refined']-c['midi'])*1000,1)
        if c.get('refined') is not None:
            n=notes[c['index']];n['start_midi']=n['start'];n['start']=c['refined'];n['end']=max(n['end'],n['start']+.05);n['onset_source']=c['method']
    return changes
