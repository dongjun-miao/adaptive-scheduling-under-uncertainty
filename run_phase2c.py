import json,sys,hashlib,csv
from pathlib import Path
from dataclasses import asdict
from engine import *
from policies import *
from triggers import *
from forecasting import *
from prediction_metrics import evaluate
from run_phase2a import tiny,public,encode
from run_phase2b import generate

def main(output='phase2c-pilot'):
 out=Path(output);out.mkdir(exist_ok=False);rows=[];pairs=[]
 for name,i,period in [('tiny',tiny(),3),('abz5',public(),200)]:
  for regime in ('deterministic','stationary','slowdown','stochastic_slowdown'):
   for seed in (11,29):
    s=generate(i,regime,seed,period);sh=hashlib.sha256(repr(s).encode()).hexdigest();group={}
    for label in ('B1','B2','B3','B4'):
     cfg=PolicyConfig(Q(period),.02,.20,0,'deterministic',10.)
     p=B1(cfg,forecaster=Nominal() if label=='B1' else MachineEMA()) if label in ('B1','B2') else (B3(cfg) if label=='B3' else B4(cfg))
     r=dict(instance=name,regime=regime,seed=seed,optimizer_repetition=0,policy=label,scenario_hash=sh,config=asdict(cfg),status='FAILED',error=None,makespan=None,ledger=None)
     try:
      l=execute(s,p,0);end=validate_run(s,l);replay(s,l);metrics=evaluate(l,p.records);r.update(status='OK',ledger=l,makespan=int(end),metrics=metrics)
     except Exception as exc:r['error']=repr(exc)
     r.update(scenario=s,callbacks=p.records,lifecycle=p.lifecycle,updates=p.forecaster.updates,accounting=p.accounting(),deterministic_effort=sum(c['result'].deterministic_seconds or 0 for c in p.records if c.get('result')))
     (out/f'{name}-{regime}-{seed}-{label}.json').write_text(json.dumps(r,default=encode,indent=2));brief={k:v for k,v in r.items() if k not in ('scenario','callbacks','lifecycle','updates','ledger','metrics')}
     if 'metrics' in r:brief['metrics']={k:v for k,v in r['metrics'].items() if k!='attributions'}
     rows.append(brief);group[label]=r;print(name,regime,seed,label,r['status'],r['makespan'],flush=True)
     (out/'runs.json').write_text(json.dumps(rows,default=encode,indent=2))
    for a,b in [('B2','B1'),('B3','B2'),('B4','B2'),('B4','B3')]:pairs.append(dict(instance=name,regime=regime,seed=seed,comparison=a+'-'+b,difference=group[a]['makespan']-group[b]['makespan'] if group[a]['status']==group[b]['status']=='OK' else None))
    (out/'pairs.json').write_text(json.dumps(pairs,indent=2))
 with (out/'pairs.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(pairs[0]));w.writeheader();w.writerows(pairs)
if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else 'phase2c-pilot')
