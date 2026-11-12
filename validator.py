import math
from collections import Counter

def validate(spec, rows, makespan):
    # spec maps globally unique operation id to (job, eligible durations, predecessors).
    errors=[]
    counts=Counter(r['id'] for r in rows)
    if counts != Counter({k:1 for k in spec}): errors.append('coverage')
    indexed={r['id']:r for r in rows}
    for r in rows:
        if r['id'] not in spec: continue
        job,options,preds=spec[r['id']]
        if r['job']!=job: errors.append('identity')
        if r['machine'] not in options: errors.append('eligibility')
        elif r['duration']!=options[r['machine']]: errors.append('duration')
        if not all(math.isfinite(r[k]) for k in ('start','duration')) or r['start']<0 or r['duration']<=0: errors.append('time')
        for p in preds:
            if p in indexed and indexed[p]['start']+indexed[p]['duration']>r['start']+1e-9: errors.append('precedence')
    for i,a in enumerate(rows):
        for b in rows[i+1:]:
            if a['machine']==b['machine'] and max(a['start'],b['start'])<min(a['start']+a['duration'],b['start']+b['duration'])-1e-9: errors.append('collision')
    actual=max((r['start']+r['duration'] for r in rows),default=0)
    if not math.isfinite(makespan) or abs(actual-makespan)>1e-9: errors.append('makespan')
    if errors: raise ValueError(','.join(sorted(set(errors))))
    return actual
