"""Independent prediction attribution from committed source snapshots, not model state."""
from fractions import Fraction as Q
import math

def evaluate(ledger,callbacks):
 starts={e.operation:e.time for e in ledger.events if e.kind=='start'};ends={e.operation:e.time for e in ledger.events if e.kind=='complete'}
 sources={};rows=[]
 for c in callbacks:
  if 'committed_source' in c:
   src=c['committed_source'];sources[src['version']]=src
  for oid,m in c['decision'].starts:
   auth=c['authorizations'][oid]; actual=ends[oid]-starts[oid];start_prediction=dict(c['forecast'].estimates)[oid]
   row=dict(operation=oid,start=starts[oid],actual=actual,start_prediction=start_prediction,plan_prediction=None,plan_version=None,call_id=None,forecast_version=None,fallback=c['fallback'],authorized=False)
   if auth is not None:
    if c['fallback']:raise ValueError('fallback assigned plan')
    src=sources.get(auth['plan_version'])
    if not src or src['call_id']!=auth['call_id'] or src['forecast'].version!=auth['forecast_version'] or dict(src['forecast'].estimates).get(oid)!=auth['duration']:raise ValueError('incorrect forecast attribution')
    if auth['plan_version']!=c['plan_version']:raise ValueError('stale authorization')
    row.update(plan_prediction=auth['duration'],plan_version=auth['plan_version'],call_id=auth['call_id'],forecast_version=auth['forecast_version'],authorized=True)
   elif not c['fallback']:raise ValueError('missing plan authorization')
   if c['time']!=starts[oid]:raise ValueError('prediction time')
   rows.append(row)
 if len(rows)!=len(starts) or len({r['operation'] for r in rows})!=len(rows):raise ValueError('prediction coverage')
 def metric(key):
  errors=[float(r[key]-r['actual']) for r in rows if r[key] is not None]
  return dict(coverage=len(errors),MAE=sum(abs(x) for x in errors)/len(errors) if errors else None,RMSE=math.sqrt(sum(x*x for x in errors)/len(errors)) if errors else None)
 return dict(start_time=metric('start_prediction'),decision_time=metric('plan_prediction'),attributions=rows)
