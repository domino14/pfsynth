"""Conservative left-hand fingering constraints for inferred listening-room tabs.

Designed hand limits, not biometric measurements or a guarantee for every player.
Search never truncates MIDI durations to make a fingering pass.
"""
import itertools
import math


def finger_options(active,violin=False,fixed=None,reach_limits=None):
    fixed=fixed or {};scale=328 if violin else 650;spacing=5.5 if violin else 8
    limits={(1,2):24 if violin else 45,(1,3):42 if violin else 75,
            (1,4):62 if violin else 105,(2,3):24 if violin else 35,
            (2,4):44 if violin else 65,(3,4):25 if violin else 40}
    if reach_limits: limits.update(reach_limits)
    stopped=[(i,s,f) for i,s,f in active if f]
    if len({s for _,s,_ in active})!=len(active):return None
    if len(stopped)>4 and violin:return None
    for digits in itertools.product(range(1,5),repeat=len(stopped)):
        assignment=dict(zip((i for i,_,_ in stopped),digits))
        if any(assignment.get(i)!=d for i,d in fixed.items() if i in assignment):continue
        valid=True
        # One digit may hold a barre only at the same position. Guitar barre
        # is index-only; a violin finger may stop adjacent strings together.
        for d in set(digits):
            contacts=[(s,f) for (_,s,f),digit in zip(stopped,digits) if digit==d]
            if len(contacts)>1:
                strings=[s for s,_ in contacts];frets={f for _,f in contacts}
                if len(frets)>1 or (not violin and d!=1) or (violin and max(strings)-min(strings)>1):valid=False;break
                fret=contacts[0][1]
                if any(min(strings)<=s<=max(strings) and f<fret for _,s,f in active):valid=False;break
        if not valid:continue
        for a,b in itertools.combinations(range(len(stopped)),2):
            _,sa,fa=stopped[a];_,sb,fb=stopped[b];da,db=digits[a],digits[b]
            if da==db:continue
            if (da-db)*(fa-fb)<0:valid=False;break
            dx=scale*abs(2**(-fa/12)-2**(-fb/12));dy=spacing*abs(sa-sb)
            if math.hypot(dx,dy)>limits[tuple(sorted((da,db)))]:valid=False;break
        if valid:
            assignment.update({i:0 for i,_,f in active if not f});yield assignment
    return None


def geometry(active,violin=False,fixed=None):
    return next(finger_options(active,violin,fixed),None)


def guitar_fingers(notes,beam_width=64):
    """Choose fingers over a phrase, retaining the existing string/fret path.

    Position is the fret under the index. One-fret-per-finger is preferred;
    a one-fret extension is allowed with a cost and pairwise reach checks.
    Held contacts keep both their digit and fret throughout their duration.
    """
    groups=[]
    for i in sorted(range(len(notes)),key=lambda i:notes[i]['start']):
        if not groups or abs(notes[groups[-1][0]]['start']-notes[i]['start'])>.000001:groups.append([])
        groups[-1].append(i)
    states=[(0,{},None,None,{})]
    for group in groups:
        t=notes[group[0]]['start'];candidates=[]
        for cost,assigned,anchor,last,positions in states:
            held=[i for i in assigned if notes[i]['end']>t+.000001]
            contacts=[(i,notes[i]['string']-1,notes[i]['fret']) for i in held+group]
            fixed={i:assigned[i] for i in held}
            for digits in finger_options(contacts,fixed=fixed):
                stopped=[(i,f) for i,_,f in contacts if f]
                possible=range(1,20) if stopped else [anchor or 1]
                for position in possible:
                    errors=[abs(f-(position+digits[i]-1)) for i,f in stopped]
                    if any(e>1 for e in errors):continue
                    shift=0 if anchor is None else 650*abs(2**(-position/12)-2**(-anchor/12))
                    if last is not None and shift>900*max(t-last,.001)+15:continue
                    # Strong preference for a stable position and relaxed finger
                    # placement, rather than repeatedly sliding the index.
                    score=cost+.08*shift+2*sum(errors)+(.001*position if anchor is None else 0)
                    new=dict(assigned);new.update({i:digits[i] for i in group})
                    ps=dict(positions);ps.update({i:position for i in group})
                    candidates.append((score,new,position,t,ps))
        if not candidates:raise ValueError(f'No phrase-feasible fingers for fixed strings/frets at {t:.3f}s; durations retained')
        unique={}
        for state in sorted(candidates,key=lambda s:s[0]):
            key=(state[2],tuple((i,state[1][i]) for i in held_indices(notes,state[1],t)))
            if key not in unique:unique[key]=state
            if len(unique)>=beam_width:break
        states=list(unique.values())
    if states:
        _,digits,_,_,positions=min(states,key=lambda s:s[0])
        for i,n in enumerate(notes):n['finger']=digits[i];n['hand_position']=positions[i]
    return notes


def held_indices(notes,assigned,t):
    return [i for i in assigned if notes[i]['end']>t+.000001]


def infer(notes,violin=False,beam_width=24,tuning=None):
    # tuning: open-string MIDI pitches, string 1 first (e.g. scordatura); default standard.
    opens=[55,62,69,76] if violin else tuning or [64,59,55,50,45,40]
    groups=[]
    for i,n in enumerate(notes):
        if not groups or abs(notes[groups[-1][0]]['start']-n['start'])>.001:groups.append([])
        groups[-1].append(i)
    # cost, assignments (index -> zero-based string, offset, digit), anchor, time
    states=[(0,{},0,0)]
    for group in groups:
        t=notes[group[0]]['start'];options=[[s for s,o in enumerate(opens) if 0<=notes[i]['pitch']-o<=19] for i in group]
        next_states=[]
        for cost,assign,anchor,last in states:
            held=[i for i in assign if notes[i]['end']>t+.000001]
            occupied={assign[i][0] for i in held}
            for chosen in itertools.product(*options):
                if len(set(chosen))!=len(chosen) or occupied.intersection(chosen):continue
                contacts=[(i,*assign[i][:2]) for i in held]+[(i,s,notes[i]['pitch']-opens[s]) for i,s in zip(group,chosen)]
                digits=geometry(contacts,violin,{i:assign[i][2] for i in held})
                if digits is None:continue
                frets=[f for _,_,f in contacts if f];position=min(frets) if frets else anchor
                scale=328 if violin else 650;shift=scale*abs(2**(-position/12)-2**(-anchor/12))
                if assign and shift>(650 if violin else 900)*max(t-last,.001)+15:continue
                new=dict(assign)
                for i,s in zip(group,chosen):new[i]=(s,notes[i]['pitch']-opens[s],digits[i])
                score=cost+.015*shift+.04*sum(notes[i]['pitch']-opens[s] for i,s in zip(group,chosen))
                if violin:score+=sum(2 for i,s in zip(group,chosen) if notes[i]['pitch']==opens[s] and max([abs(v) for _,v in notes[i].get('curve',[(0,0)])])>.08)
                next_states.append((score,new,position,t))
        if not next_states:raise ValueError(f'No hand-feasible fingering at {t:.3f}s for pitches {[notes[i]["pitch"] for i in group]}; source durations retained')
        # Diverse beam keys keep plausible hand positions instead of 24 copies
        # of an equivalent history. All held finger assignments remain fixed.
        dedup={}
        for state in sorted(next_states,key=lambda v:v[0]):
            key=tuple((i,*state[1][i]) for i in state[1] if notes[i]['end']>t)
            if key not in dedup:dedup[key]=state
        states=list(dedup.values())[:beam_width]
    best=min(states,key=lambda v:v[0])[1]
    for i,n in enumerate(notes):
        s,f,d=best[i];n['string']=s if violin else s+1;n['fret']=f;n['finger']=d
        if violin:n['stopped']=bool(f)
    if not violin:guitar_fingers(notes)
    return notes


def audit(notes,violin=False,tuning=None):
    opens=[55,62,69,76] if violin else tuning or [64,59,55,50,45,40]
    failures=[];maximum=0;rolled=[];anchor=0;last=None;max_shift=0
    for n in notes:
        s=n['string'] if violin else n['string']-1
        if n['pitch']!=opens[s]+n['fret']:failures.append(dict(time=n['start'],reason='pitch/string mismatch'))
    for t in sorted({n['start'] for n in notes}):
        active=[(i,n['string'] if violin else n['string']-1,n['fret']) for i,n in enumerate(notes) if n['start']<=t+.000001 and n['end']>t+.000001]
        fixed={i:notes[i]['finger'] for i,_,_ in active if 'finger' in notes[i]}
        if geometry(active,violin,fixed) is None:failures.append(dict(time=t,reason='finger/string/stretch conflict'))
        stopped=[f for _,_,f in active if f]
        arriving=[n for n in notes if abs(n['start']-t)<.000001]
        explicit=[n['hand_position'] for n in arriving if 'hand_position' in n]
        position=explicit[0] if explicit else (min(stopped) if stopped else anchor)
        if explicit:
            if any(p!=position for p in explicit):failures.append(dict(time=t,reason='inconsistent hand positions'))
            for i,_,f in active:
                if f and abs(f-(position+notes[i]['finger']-1))>1:
                    failures.append(dict(time=t,reason='finger outside designed position/extension'))
        shift=(328 if violin else 650)*abs(2**(-position/12)-2**(-anchor/12))
        if last is not None:
            max_shift=max(max_shift,shift)
            if shift>(650 if violin else 900)*max(t-last,.001)+15:
                failures.append(dict(time=t,reason='hand-position shift exceeds designed speed limit'))
        anchor=position;last=t
        if stopped:maximum=max(maximum,(328 if violin else 650)*(2**(-min(stopped)/12)-2**(-max(stopped)/12)))
        if violin and len(active)>2:rolled.append(t)
    return dict(passed=not failures,violations=failures,max_longitudinal_span_mm=maximum,
                rolled_chord_times=rolled,scale_length_mm=328 if violin else 650,max_shift_mm=max_shift,
                assumptions='Four left-hand fingers; guitar phrase search with explicit index position and at most one-fret extensions; pairwise reach limits in mm; held fingers retained; no duration truncation. Guitar index barres cannot cross lower/open held notes. Violin adjacent-string finger stops allowed. Designed adult-hand limits, not player-specific biomechanics.')
