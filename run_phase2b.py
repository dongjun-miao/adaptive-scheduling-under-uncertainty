"""Frozen B1/B2 forecast-treatment pilot. Existing outputs are never overwritten."""
import json,sys,hashlib,math,platform
from pathlib import Path
from dataclasses import asdict,replace
from engine import *
from policies import *
from forecasting import *
from run_phase2a import tiny,public,scenario,encode

def generate(i,regime,seed,period):
    base=scenario(i,'stationary' if regime=='stochastic_slowdown' else regime,seed,period)
    return replace(base,slowdowns=((0,Q(period),Q(2)),)) if regime=='stochastic_slowdown' else base

def main(output='phase2b-pilot'):
 out=Path(output);out.mkdir(exist_ok=False); rows=[];pairs=[]
 for name,i,period in [('tiny',tiny(),3),('abz5',public(),200)]:
  for regime in ('deterministic','stationary','slowdown','stochastic_slowdown'):
   for seed in (11,29):
    s=generate(i,regime,seed,period);scenario_hash=hashlib.sha256(repr(s).encode()).hexdigest()
    for repetition in (0,1):
     pair=[]
     for label in ('B1','B2'):
      config=PolicyConfig(Q(period),.02,.20,0,'deterministic',10.)
      model=Nominal() if label=='B1' else MachineEMA(Q(1,4));p=B1(config,forecaster=model)
      record=dict(instance=name,regime=regime,seed=seed,repetition=repetition,policy=label,scenario_hash=scenario_hash,config=asdict(config),alpha=Q(1,4) if label=='B2' else None,status='FAILED',error=None,makespan=None,ledger=None)
      try:
       l=execute(s,p,0);end=validate_run(s,l);replay(s,l)
       starts={e.operation:e.time for e in l.events if e.kind=='start'};ends={e.operation:e.time for e in l.events if e.kind=='complete'}; predictions={}
       for callback in p.records:
        estimate=dict(callback['forecast'].estimates)
        for oid,m in callback['decision'].starts:
         assert oid not in predictions and oid in estimate and callback['time']==starts[oid]
         predictions[oid]=dict(at=callback['time'],forecast_version=callback['forecast_version'],prediction=estimate[oid],actual=ends[oid]-starts[oid])
       assert set(predictions)==set(starts)
       errors=[float(v['prediction']-v['actual']) for v in predictions.values()]
       episodes=sum(r['fallback'] and (k==0 or not p.records[k-1]['fallback']) for k,r in enumerate(p.records))
       record.update(status='OK',makespan=int(end),ledger=l,predictions=predictions,MAE=sum(abs(e) for e in errors)/len(errors),RMSE=math.sqrt(sum(e*e for e in errors)/len(errors)),fallback_episodes=episodes)
      except Exception as exc:record['error']=repr(exc)
      record.update(callbacks=p.records,lifecycle=p.lifecycle,updates=model.updates,scenario=s,accounting=p.accounting(),deterministic_effort=sum(r['result'].deterministic_seconds or 0 for r in p.records if r.get('result')))
      filename=f'{name}-{regime}-{seed}-{repetition}-{label}.json';(out/filename).write_text(json.dumps(record,default=encode,indent=2))
      brief={k:v for k,v in record.items() if k not in ('callbacks','lifecycle','updates','scenario','ledger','predictions')};rows.append(brief);pair.append(record)
      print(name,regime,seed,repetition,label,record['status'],record['makespan'],flush=True)
     a,b=pair;assert a['scenario_hash']==b['scenario_hash'] and a['config']==b['config']
     pairs.append(dict(instance=name,regime=regime,seed=seed,repetition=repetition,B1=a['makespan'],B2=b['makespan'],difference=b['makespan']-a['makespan'] if a['status']==b['status']=='OK' else None,MAE_B1=a.get('MAE'),MAE_B2=b.get('MAE'),RMSE_B1=a.get('RMSE'),RMSE_B2=b.get('RMSE')))
     (out/'runs.json').write_text(json.dumps(rows,default=encode,indent=2));(out/'pairs.json').write_text(json.dumps(pairs,indent=2))
 (out/'environment.json').write_text(json.dumps(dict(python=platform.python_version(),platform=platform.platform(),ortools=__import__('ortools').__version__),indent=2))
if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else 'phase2b-pilot')
