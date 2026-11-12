"""Phase 2A policies: persistent advisory plans and periodic-only optimization."""
from dataclasses import dataclass,asdict
from fractions import Fraction as Q
import time,math
from engine import Decision,Forecast
from residual import prepare,solve,validate_plan,digest
from closed_loop import safe_dispatch
from forecasting import Nominal

@dataclass(frozen=True)
class PolicyConfig:
    period:Q=Q(3)
    per_call:float=0.02
    total:float=0.20
    seed:int=0
    mode:str="wall"
    safety_wall:float=10.0
    def __post_init__(self):
        if self.mode not in ('wall','deterministic') or not math.isfinite(self.safety_wall) or self.safety_wall<=0: raise ValueError('budget mode')
        if not isinstance(self.period,Q) or self.period<=0 or self.period.denominator!=1: raise ValueError('positive integer period')
        if any(not math.isfinite(x) or x<0 for x in (self.per_call,self.total)): raise ValueError('budget')

def fifo_public(obs):
    releases={e.operation:e.time for e in obs.history if e.kind=='arrival'}
    started={e.operation for e in obs.history if e.kind=='start'}; done={k for k,_ in obs.completed_durations}
    busy={m for _,m,_ in obs.running}; choices=[]
    for o in sorted(obs.operations,key=lambda o:(releases[o.job],o.job,o.id)):
        if o.id not in started and set(o.predecessors)<=done and o.machine not in busy:
            choices.append((o.id,o.machine)); busy.add(o.machine)
    return Decision(tuple(choices))

class B0:
    def __init__(self): self.records=[]
    def __call__(self,obs,rng):
        t=time.perf_counter(); d=fifo_public(obs)
        self.records.append(dict(time=obs.time,decision=d,called=False,overhead=time.perf_counter()-t,forecast_version=1))
        return d
    def accounting(self): return dict(callbacks=len(self.records),solver_calls=0,solver_seconds=0,overhead=sum(r['overhead'] for r in self.records),validation_seconds=0,fallbacks=0,invalid=0,blocked=0,delayed=0,forecast_updates=0,allocated_budget=0)

class B1:
    def __init__(self,config=PolicyConfig(),solver=solve,forecaster=None):
        self.forecaster=forecaster if forecaster is not None else Nominal()
        self.config=config; self.solver=solver; self.records=[]; self.plan=None; self.plan_version=0; self.call_id=0; self.allocated=0.; self.lifecycle=[]; self.fallback=False
    def permission(self,obs,f,triggers):
        return any(x in triggers for x in ('INITIAL_PLAN','PERIODIC_REPLAN')),{}
    def __call__(self,obs,rng):
        begin=time.perf_counter(); done={k for k,_ in obs.completed_durations}; started={e.operation for e in obs.history if e.kind=='start'}
        f=self.forecaster.snapshot(obs)
        unfinished=any(o.id not in done for o in obs.operations)
        triggers=[]
        if obs.time==0: triggers.append('INITIAL_PLAN')
        if obs.time>0 and obs.time%self.config.period==0: triggers.append('PERIODIC_REPLAN')
        for kind,label in [('complete','COMPLETION'),('arrival','ARRIVAL')]:
            if any(e.time==obs.time and e.kind==kind for e in obs.history): triggers.append(label)
        if self.plan and any(Q(row.start)==obs.time and not row.running for row in self.plan['result'].rows): triggers.append('PLANNED_START')
        if not triggers: triggers.append('OBSOLETE_WAKEUP')
        permitted,trigger_info=self.permission(obs,f,triggers)
        record=dict(trigger_permitted=permitted,trigger_info=trigger_info,time=obs.time,triggers=tuple(triggers),observation_version=len(self.records)+1,observation_hash=digest(obs),forecast_version=f.version,forecast=f,training_cutoff=f.through,observation_cutoff=obs.time,planning_time=obs.time,last_completion=self.forecaster.last,called=False,failure=None,result=None,problem=None,validation_seconds=0.,invalid=False,solver_seconds=0.,fallback=False,budget=0.)
        if self.plan and all(row.id in done for row in self.plan['result'].rows):
            self.lifecycle.append((self.plan_version,obs.time,'COMPLETED')); self.plan=None
        if permitted and unfinished:
            remaining=max(0.,self.config.total-self.allocated)
            limit=min(self.config.per_call,remaining)
            if limit<=1e-12:
                record['failure']='TOTAL_BUDGET_EXHAUSTED'; self.fallback=True
                if self.plan: self.lifecycle.append((self.plan_version,obs.time,'INVALIDATED')); self.plan=None
            else:
                self.call_id+=1; self.allocated+=limit; record.update(call_id=self.call_id,budget=limit)
                if self.plan: self.lifecycle.append((self.plan_version,obs.time,'INVALIDATED')); self.plan=None
                try:
                    p=prepare(obs,f); record['problem']=p; record['forecast']=f; record['training_cutoff']=f.through; record['observation_cutoff']=obs.time; record['planning_time']=obs.time
                    record['called']=True
                    kwargs=dict(time_limit=limit,seed=self.config.seed) if self.config.mode=='wall' else dict(time_limit=self.config.safety_wall,seed=self.config.seed,deterministic_limit=limit)
                    r=self.solver(p,**kwargs); record['result']=r; record['solver_seconds']=r.solver_seconds
                    if r.status not in ('OPTIMAL','FEASIBLE'): raise ValueError('solver status '+r.status)
                    tick=time.perf_counter()
                    try: validate_plan(p,r)
                    except Exception: record['invalid']=True; raise
                    finally: record['validation_seconds']=time.perf_counter()-tick
                    self.plan_version+=1
                    self.lifecycle.extend((self.plan_version,obs.time,s) for s in ('CREATED','VALIDATED','COMMITTED'))
                    self.plan=dict(version=self.plan_version,result=r,observation_hash=p.observation_hash,instance_hash=p.instance_hash,forecast_version=f.version,forecast=f,call_id=self.call_id,created=obs.time,committed=obs.time,config=asdict(self.config),validated=True)
                    self.fallback=False
                except Exception as exc: record['failure']=type(exc).__name__+': '+str(exc); self.fallback=True
        notes=()
        if self.fallback:
            d=fifo_public(obs); record['fallback']=bool(unfinished)
        elif self.plan:
            d,notes=safe_dispatch(obs,self.plan['result'].rows)
            if d.starts: self.lifecycle.append((self.plan_version,obs.time,'PARTIALLY_EXECUTED'))
        else: d=Decision(())
        wakeups={(obs.time//self.config.period+1)*self.config.period}
        if self.plan: wakeups.update(Q(row.start) for row in self.plan['result'].rows if not row.running and row.id not in started and row.start>obs.time)
        d=Decision(d.starts,tuple(sorted(wakeups)))
        record['authorizations']={oid:dict(plan_version=self.plan['version'],call_id=self.plan['call_id'],forecast_version=self.plan['forecast_version'],duration=dict(self.plan['forecast'].estimates)[oid]) if self.plan and not self.fallback else None for oid,m in d.starts}
        if self.plan and record['called'] and not record['failure']: record['committed_source']=dict(version=self.plan['version'],call_id=self.plan['call_id'],forecast=self.plan['forecast'])
        record.update(decision=d,notes=notes,plan_version=self.plan['version'] if self.plan else None,overhead=time.perf_counter()-begin)
        self.records.append(record); return d
    def accounting(self):
        return dict(callbacks=len(self.records),solver_calls=sum(r['called'] for r in self.records),solver_seconds=sum(r['solver_seconds'] for r in self.records),overhead=sum(r['overhead'] for r in self.records),validation_seconds=sum(r['validation_seconds'] for r in self.records),fallbacks=sum(r['fallback'] for r in self.records),invalid=sum(r['invalid'] for r in self.records),blocked=sum(n.reason!='delayed start' for r in self.records for n in r['notes']),delayed=sum(n.reason=='delayed start' for r in self.records for n in r['notes']),forecast_updates=len(self.forecaster.updates),allocated_budget=self.allocated)
