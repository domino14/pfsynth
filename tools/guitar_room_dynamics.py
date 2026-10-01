"""Re-render the Bach dynamics clips with velocities fitted with Kowalski's room.

guitar_room_fit.py showed the room is load-bearing: fitted without it, velocities came out
too contrasted (squashed afterwards with an exponent of 0.5) and soft notes after loud ones
too soft. Here the velocities are refitted with the room fitted to Kowalski's recording
(fit_room_dynamics), the contrast exponent is re-checked with that room applied, and the
B versions of "dynamics from the recording" and "fitted versus random variation" are
re-rendered. The audio stays dry: the Room menu adds the fitted room in the browser.
Run guitar_legato_audition.py, guitar_body_choice.py, guitar_room_choice.py and
stringlab_page.py afterwards.

    build/body-venv/bin/python tools/guitar_room_dynamics.py
"""
import copy,json
import numpy as np
from scipy.io import wavfile
from stringlab_audition import ROOT,OUT,SR,library,write_clip
from string_gesture_audition import setup,export_midi
from guitar_dynamics_fit import Model,fit_room_dynamics,room_calibration,V0,EXP

DOC=ROOT/'experiments/string-gestures'


def main():
    lib,_=library();setup(lib)
    data=json.loads((OUT/'stringlab.json').read_text());old={c['id']:c for c in data['clips']}
    dyn=old['guitar-bach-dynamics'];duration=dyn['duration']
    notes=[dict(n,velocity=100) for n in json.loads((OUT/'guitar-bach-performance-events.json').read_text())]
    ref=wavfile.read(OUT/'audio/guitar-bach-performance-ref.wav')[1].astype(float)/32768
    room=json.loads((DOC/'guitar-room-fit-refined.json').read_text())['best']
    model=Model(lib,dyn['dynamics']['model'],5,True)
    r=fit_room_dynamics(model,notes,ref,duration,room)
    velocity,info=room_calibration(model,notes,ref,duration,r['velocity'],room)
    print('contrast exponent with the room %.2f; loudness-envelope error (room applied) constant %.2f dB, fitted %.2f dB'%(info['gamma'],info['constant_error_db'],info['fitted_error_db']),flush=True)
    fitted=[dict(n,velocity=float(round(v,1)),velocity_source='fitted to Kowalski recording with its room (model estimate)') for n,v in zip(notes,velocity)]
    fixed=model.render(notes,duration);dynamic=model.render(fitted,duration);variation=model.render(notes,duration,1)
    for x in (fixed,dynamic,variation):assert np.isfinite(x).all() and len(x)==len(ref)
    top=max(n['velocity'] for n in fitted)
    export_midi([dict(n,velocity=max(1,int(round(n['velocity']*127/top)))) for n in fitted],OUT/'guitar-bach-dynamics.mid')
    (OUT/'guitar-bach-dynamics-events.json').write_text(json.dumps(fitted,indent=2)+'\n')
    shared=(f'Same Kowalski timing, Apke strings/frets and model ({model.name}, no random variation) throughout. Each note was rendered alone and its velocity fitted so the notes, '
        f'passed through a room fitted to Kowalski’s recording (reverberation {room["rt_low"]:.1f} s low, {room["rt_high"]:.1f} s high, reverberant energy equal to the direct sound), '
        'match the recording’s intensity across frequency, with a separate timbre correction so tone mismatch is not read as dynamics. With the room modelled the contrast no longer needs '
        f'squashing (exponent {info["gamma"]:.2f}). The audio is dry: set Room to “Fitted to Kowalski’s recording” to hear it as fitted. Louder notes pluck harder, so the string’s tension '
        'nonlinearity follows the dynamics. Estimates under this model, not measured finger force; weakly audible notes lean on their neighbours.')
    labels=dict(fitted='Velocities fitted to Kowalski (with his room)',ref='Real performance · Mateusz Kowalski')
    clips=[write_clip('guitar-bach-dynamics',dyn['note'],dyn['dynamic'],dict(current=fixed,fitted=dynamic,ref=ref),dict(labels,current=dyn['labels']['current']),
               shared+' A keeps the source MIDI’s constant velocity.','Real recording',dyn['question']),
           write_clip('guitar-bach-character',old['guitar-bach-character']['note'],old['guitar-bach-character']['dynamic'],dict(current=variation,fitted=dynamic,ref=ref),
               dict(labels,current=old['guitar-bach-character']['labels']['current']),shared+' A instead adds the earlier bounded random variation around velocity 100.','Real recording',old['guitar-bach-character']['question'])]
    for c in clips:
        c.update({k:old[c['id']][k] for k in ('score','downloads') if k in old[c['id']]})
        c['dynamics']=dict(model=model.name,range_exponent=info['gamma'],room=room,envelope_error_db=dict(constant_with_room=info['constant_error_db'],fitted_with_room=info['fitted_error_db']),method='room-aware band-power fit')
        for n,f in zip(c['score']['notes'],fitted):n['velocity']=f['velocity']
    data['clips']=[clips[[x['id'] for x in clips].index(c['id'])] if c['id'] in {x['id'] for x in clips} else c for c in data['clips']]
    tmp=OUT/'stringlab.tmp';tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(OUT/'stringlab.json')
    db=lambda v:20*EXP*np.log10(np.asarray(v)/V0);m=np.array([n['score_measure'] for n in notes])
    report=dict(room=room,calibration=info,share=r['share'].tolist(),measure_median_db={int(k):round(float(np.median(db(velocity)[m==k])),1) for k in sorted(set(m))},
        velocity=dict(p5=float(np.percentile(velocity,5)),median=float(np.median(velocity)),p95=float(np.percentile(velocity,95))))
    (DOC/'guitar-room-dynamics-report.json').write_text(json.dumps(report,indent=2,default=float)+'\n')
    print('measure medians dB',report['measure_median_db'],flush=True)


if __name__=='__main__':main()
