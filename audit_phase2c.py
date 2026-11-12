import json,math
from pathlib import Path
from engine import *
from residual import Problem,Task,Row,Result,validate_plan
import sys
root=Path(sys.argv[1] if len(sys.argv)>1 else 'phase2c-final-pilot')
def q(v):return Q(v['numerator'],v['denominator']) if isinstance(v,dict) and 'numerator' in v else v
summary=[];effects=[];duration_maps={};failures=[]
for file in root.glob('*-B*.json'):
 r=json.loads(file.read_text())
 if r['status']!='OK':failures.append((file.name,r['error']));continue
 s=r['scenario'];i=s['instance'];instance=Instance(tuple(Machine(m['id']) for m in i['machines']),tuple(Operation(o['id'],o['job'],o['machine'],q(o['nominal']),tuple(o['predecessors'])) for o in i['operations']))
 scenario=Scenario(instance,tuple((j,q(t)) for j,t in s['arrivals']),tuple((k,q(d)) for k,d in s['durations']),tuple(tuple(x) for x in s['seeds']),tuple((m,q(t),q(f)) for m,t,f in s['slowdowns']))
 l=r['ledger'];ledger=ExecutionLedger(tuple(ExecutionEvent(q(e['time']),e['kind'],e['operation'],e['machine']) for e in l['events']),tuple((q(t),Decision(tuple(tuple(x) for x in d['starts']),tuple(q(w) for w in d['wakeups']))) for t,d in l['decisions']),l['policy_seed'])
 assert validate_run(scenario,ledger)==r['makespan'];replay(scenario,ledger)
 sources={};calls=0
 for c in r['callbacks']:
  if c['called']:
   calls+=1;assert c['trigger_permitted'];p=c['problem'];p=Problem(p['now'],tuple(Task(x['id'],x['machine'],x['duration'],tuple(x['predecessors']),x['frozen_start']) for x in p['tasks']),tuple(tuple(x) for x in p['completed']),p['horizon'],p['observation_hash'],p['instance_hash'],p['forecast_version'])
   result=c['result']
   if result and result['status'] in ('OPTIMAL','FEASIBLE'):
    v=dict(result);v['rows']=tuple(Row(**row) for row in v['rows']);validate_plan(p,Result(**v))
  if c.get('committed_source'):sources[c['committed_source']['version']]=c['committed_source']
  for oid,m in c['decision']['starts']:
   a=c['authorizations'][oid]
   if a:
    src=sources[a['plan_version']];assert src['call_id']==a['call_id'];assert dict(src['forecast']['estimates'])[oid]==a['duration'];assert a['plan_version']==c['plan_version']
   else:assert c['fallback']
 assert calls==r['accounting']['solver_calls'];assert r['accounting']['allocated_budget']<=.200000001
 at=r['metrics']['attributions'];planned=[x for x in at if x['authorized']];mismatch=sum(x['plan_prediction']!=x['start_prediction'] for x in planned)
 for key,metric in [('start_prediction','start_time'),('plan_prediction','decision_time')]:
  err=[float(q(x[key])-q(x['actual'])) for x in at if x[key] is not None];assert len(err)==r['metrics'][metric]['coverage']
  if err:assert abs(sum(abs(x) for x in err)/len(err)-r['metrics'][metric]['MAE'])<1e-10
 row=dict(instance=r['instance'],regime=r['regime'],seed=r['seed'],policy=r['policy'],makespan=r['makespan'],planned=len(planned),mismatch=mismatch,coverage=r['metrics']['decision_time']['coverage'],start_MAE=r['metrics']['start_time']['MAE'],plan_MAE=r['metrics']['decision_time']['MAE'],calls=calls,effort=r['deterministic_effort'],fallback_operations=sum(len(c['decision']['starts']) for c in r['callbacks'] if c['fallback']))
 summary.append(row);duration_maps[(r['instance'],r['regime'],r['seed'],r['policy'])]={x['operation']:q(x['actual']) for x in at}
for key,durations in duration_maps.items():
 if key[-1]=='B1' and 'slowdown' in key[1]:
  for label in ('B2','B3','B4'):effects.append(dict(key=key[:-1],policy=label,different_durations=sum(v!=duration_maps[key[:-1]+(label,)][oid] for oid,v in durations.items())))
(root/'independent-audit.json').write_text(json.dumps(dict(valid=len(summary),failures=failures,runs=summary,calendar_exposure=effects),indent=2));print('validated',len(summary),'failures',failures);print('calendar changed',effects)
