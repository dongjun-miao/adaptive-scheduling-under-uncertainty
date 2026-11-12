"""Safe public-only coordinator. The engine alone owns private execution state."""
from dataclasses import dataclass
from fractions import Fraction as Q
import time,math
from engine import Decision,Forecast,fifo
from residual import prepare,solve,validate_plan

@dataclass(frozen=True)
class Config:
    period: Q = Q(2)
    time_limit: float = 1.0
    solver_seed: int = 0
    def __post_init__(self):
        if not isinstance(self.period,Q) or self.period<=0: raise ValueError('positive Fraction period required')
        if not math.isfinite(self.time_limit) or self.time_limit<0: raise ValueError('finite solver budget required')
        if type(self.solver_seed) is not int or not 0<=self.solver_seed<2**31: raise ValueError('solver seed')

@dataclass(frozen=True)
class DispatchNote:
    operation:str
    planned:Q
    observed:Q
    reason:str

@dataclass(frozen=True)
class PlanningRecord:
    observation:object
    forecast:Forecast
    problem:object
    result:object
    decision:Decision
    failure:str|None
    fallback:bool
    invalid:bool
    solver_called:bool
    solver_seconds:float|None
    validation_seconds:float
    overhead_seconds:float
    notes:tuple[DispatchNote,...]
    invalidated:tuple[str,...]

def safe_dispatch(obs,rows):
    """Stable plan order; blocked head prevents overtaking on its machine."""
    ops={o.id:o for o in obs.operations}
    started={e.operation for e in obs.history if e.kind=='start'}
    done={e.operation for e in obs.history if e.kind=='complete'}
    busy={m for _,m,_ in obs.running}; held=set(); accepted=[]; notes=[]
    for row in sorted(rows,key=lambda r:(r.start,r.machine,r.id)):
        if row.running or row.id in started: continue
        reason=None
        if row.id not in ops: reason='unreleased'
        elif row.machine!=ops[row.id].machine: reason='wrong machine'
        elif row.start>obs.time: reason='not due'
        elif row.machine in held: reason='prior plan entry blocked'
        elif not set(ops[row.id].predecessors)<=done: reason='predecessor incomplete'
        elif row.machine in busy: reason='machine busy'
        if reason:
            held.add(row.machine)
            if row.start<=obs.time: notes.append(DispatchNote(row.id,Q(row.start),obs.time,reason))
            continue
        accepted.append((row.id,row.machine)); busy.add(row.machine)
        if row.start<obs.time: notes.append(DispatchNote(row.id,Q(row.start),obs.time,'delayed start'))
    return Decision(tuple(accepted)),tuple(notes)

class Coordinator:
    def __init__(self,config=Config(),solver=solve):
        self.config=config; self.solver=solver; self.records=[]; self.previous=()
    def __call__(self,obs,rng):
        begin=time.perf_counter(); failure=None; fallback=False; invalid=False; called=False; result=None; problem=None; validation=0.; solver_seconds=None
        done={k for k,_ in obs.completed_durations}
        forecast=Forecast(len(self.records)+1,obs.time,tuple((o.id,o.nominal) for o in obs.operations if o.id not in done))
        # Assess old due entries before explicit replacement, preserving an audit of delays.
        _,notes=safe_dispatch(obs,self.previous)
        started={e.operation for e in obs.history if e.kind=='start'}
        invalidated=tuple(r.id for r in self.previous if not r.running and r.id not in started)
        try:
            problem=prepare(obs,forecast,'total_minus_elapsed')
            called=True; result=self.solver(problem,time_limit=self.config.time_limit,seed=self.config.solver_seed)
            solver_seconds=result.solver_seconds
            if result.status not in ('OPTIMAL','FEASIBLE'): raise RuntimeError('solver status '+result.status)
            check=time.perf_counter()
            try: validate_plan(problem,result)
            except Exception:
                invalid=True; raise
            finally: validation=time.perf_counter()-check
            action,newnotes=safe_dispatch(obs,result.rows); notes+=newnotes; self.previous=result.rows
        except Exception as exc:
            failure=type(exc).__name__+': '+str(exc); fallback=True; self.previous=()
            action=fifo(obs,rng)
        # Timers depend only on public clock/plan; engine coalesces duplicates across requests.
        next_period=(obs.time//self.config.period+1)*self.config.period
        wakeups={next_period}
        wakeups.update(Q(r.start) for r in self.previous if not r.running and r.start>obs.time)
        action=Decision(action.starts,tuple(sorted(wakeups)))
        record=PlanningRecord(obs,forecast,problem,result,action,failure,fallback,invalid,called,solver_seconds,validation,time.perf_counter()-begin,notes,invalidated)
        self.records.append(record)
        return action
    def accounting(self):
        return dict(solver_calls=sum(r.solver_called for r in self.records),solver_seconds=sum(r.solver_seconds or 0 for r in self.records),unknown_solver_times=sum(r.solver_called and r.solver_seconds is None for r in self.records),validation_seconds=sum(r.validation_seconds for r in self.records),planning_overhead_seconds=sum(r.overhead_seconds for r in self.records),fallback_count=sum(r.fallback for r in self.records),invalid_plan_count=sum(r.invalid for r in self.records),blocked_delayed_count=sum(len(r.notes) for r in self.records))
