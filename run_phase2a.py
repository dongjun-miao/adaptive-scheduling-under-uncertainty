"""Preregistered paired pilot; every attempt persisted, no successful-run filtering."""
import json,csv,random,hashlib,statistics,sys
from pathlib import Path
from dataclasses import asdict,is_dataclass
from engine import *
from policies import *

def tiny():
    return Instance((Machine(0),Machine(1)),(Operation('a','A',0,Q(2)),Operation('b','A',1,Q(1),('a',)),Operation('c','B',1,Q(2)),Operation('d','B',0,Q(1),('c',)),Operation('e','C',0,Q(1))))
def public():
    lines=Path('fixtures/abz5').read_text().splitlines(); n,m=map(int,lines[0].split()); ops=[]
    for j,line in enumerate(lines[1:n+1]):
        vals=list(map(int,line.split()))
        for k in range(m):
            oid=f'j{j:02}o{k:02}'; ops.append(Operation(oid,f'j{j:02}',vals[2*k],Q(vals[2*k+1]),(f'j{j:02}o{k-1:02}',) if k else ()))
    return Instance(tuple(Machine(k) for k in range(m)),tuple(ops))
def scenario(i,regime,seed,at):
    arrivals=tuple((j,Q(0)) for j in sorted({o.job for o in i.operations}))
    durations=tuple((o.id,o.nominal*(random.Random(seed_for(seed,'duration',o.id)).choice([1,2]) if regime=='stationary' else 1)) for o in i.operations)
    return Scenario(i,arrivals,durations,(('duration',seed),),((0,Q(at),Q(2)),) if regime=='slowdown' else ())
def encode(x):
    if isinstance(x,Q): return {'numerator':x.numerator,'denominator':x.denominator}
    if is_dataclass(x): return asdict(x)
    raise TypeError(type(x).__name__)
def main(out='pilot'):
    folder=Path(out); folder.mkdir(exist_ok=False); records=[]; details=[]
    for name,i,period in [('tiny',tiny(),3),('abz5',public(),200)]:
        for regime in ('deterministic','stationary','slowdown'):
            for seed in (11,29):
                s=scenario(i,regime,seed,period); sh=hashlib.sha256(repr(s).encode()).hexdigest()
                for label in ('B0','B1'):
                    policy=B0() if label=='B0' else B1(PolicyConfig(Q(period)))
                    row=dict(instance=name,regime=regime,seed=seed,policy=label,scenario_hash=sh,status='FAILED',error=None,makespan=None,replay=False,utilization=None)
                    ledger=None
                    try:
                        ledger=execute(s,policy,0); end=validate_run(s,ledger); replay(s,ledger)
                        # Separate arithmetic reconstruction from raw events, not makespan property.
                        starts={e.operation:e.time for e in ledger.events if e.kind=='start'}; ends={e.operation:e.time for e in ledger.events if e.kind=='complete'}
                        assert len(starts)==len(i.operations)==len(ends); assert max(ends.values(),default=Q(0))==end
                        busy=sum(ends[k]-starts[k] for k in ends)
                        row.update(status='OK',makespan=int(end),replay=True,utilization=float(busy/(len(i.machines)*end)))
                    except Exception as exc: row['error']=repr(exc)
                    row.update(policy.accounting()); row['infeasible']=sum(r.get('result') is not None and r['result'].status=='INFEASIBLE' for r in policy.records); row['fallback_rate']=row['fallbacks']/max(1,row['callbacks'])
                    records.append(row); details.append(dict(run=row,scenario=s,ledger=ledger,callbacks=policy.records,lifecycle=getattr(policy,'lifecycle',[])))
                    (folder/'runs.json').write_text(json.dumps(records,indent=2)); (folder/'details.json').write_text(json.dumps(details,default=encode,indent=2))
                    print(name,regime,seed,label,row['status'],row['makespan'],flush=True)
    with (folder/'runs.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0])); w.writeheader(); w.writerows(records)
    pairs=[]
    for a,b in zip(records[::2],records[1::2]):
        assert a['scenario_hash']==b['scenario_hash']
        pairs.append(dict(instance=a['instance'],regime=a['regime'],seed=a['seed'],B0=a['makespan'],B1=b['makespan'],difference=b['makespan']-a['makespan'] if a['status']==b['status']=='OK' else None))
    (folder/'pairs.json').write_text(json.dumps(pairs,indent=2))
    print(json.dumps(pairs,indent=2))
if __name__=='__main__': main(sys.argv[1] if len(sys.argv)>1 else 'pilot')
