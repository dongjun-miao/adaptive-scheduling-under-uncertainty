"""Immutable contracts and small exact-time, nonpreemptive JSP execution engine."""
from dataclasses import dataclass
from fractions import Fraction as Q
import hashlib, random
from math import prod as math_product
from typing import Callable

@dataclass(frozen=True)
class Machine:
    id: int
@dataclass(frozen=True)
class Operation:
    id: str
    job: str
    machine: int
    nominal: Q
    predecessors: tuple[str,...] = ()
@dataclass(frozen=True)
class Instance:
    machines: tuple[Machine,...]
    operations: tuple[Operation,...]
@dataclass(frozen=True)
class Scenario:
    instance: Instance
    arrivals: tuple[tuple[str,Q],...]
    durations: tuple[tuple[str,Q],...]
    seeds: tuple[tuple[str,int],...] = ()
    slowdowns: tuple[tuple[int,Q,Q],...] = ()
@dataclass(frozen=True)
class ExecutionEvent:
    time: Q
    kind: str
    operation: str
    machine: int = -1
@dataclass(frozen=True)
class Observation:
    time: Q
    operations: tuple[Operation,...]
    history: tuple[ExecutionEvent,...]
    completed_durations: tuple[tuple[str,Q],...]
    running: tuple[tuple[str,int,Q],...]
@dataclass(frozen=True)
class Forecast:
    version: int
    through: Q
    estimates: tuple[tuple[str,Q],...]
@dataclass(frozen=True)
class Decision:
    starts: tuple[tuple[str,int],...]
    wakeups: tuple[Q,...] = ()
@dataclass(frozen=True)
class SchedulePlan:
    decisions: tuple[tuple[Q,Decision],...]
@dataclass(frozen=True)
class ExecutionLedger:
    events: tuple[ExecutionEvent,...]
    decisions: tuple[tuple[Q,Decision],...]
    policy_seed: int | None = None

def seed_for(seed:int, stream:str, key:str='')->int:
    return int.from_bytes(hashlib.sha256(f'{seed}:{stream}:{key}'.encode()).digest()[:8],'big')

def stochastic(instance:Instance, seed:int)->Scenario:
    # Independent operation-keyed draws; constant duration frozen at start (no within-run drift).
    jobs=sorted({o.job for o in instance.operations})
    return Scenario(instance,tuple((j,Q(0)) for j in jobs),
        tuple((o.id,o.nominal*Q(random.Random(seed_for(seed,'duration',o.id)).randint(1,3),2)) for o in instance.operations),
        tuple((k,seed_for(seed,k)) for k in ('duration','arrival','disturbance','measurement')))

def check_scenario(s:Scenario):
    if any(type(v) is not tuple for v in (s.instance.operations,s.instance.machines,s.arrivals,s.durations,s.seeds)) or any(type(o.predecessors) is not tuple for o in s.instance.operations): raise ValueError('immutable tuple schema required')
    ops={o.id:o for o in s.instance.operations}; machines={m.id for m in s.instance.machines}
    if len(ops)!=len(s.instance.operations) or len(machines)!=len(s.instance.machines): raise ValueError('duplicate IDs')
    if type(s.slowdowns) is not tuple or any(m not in machines or not isinstance(t,Q) or t<0 or not isinstance(f,Q) or f<1 for m,t,f in s.slowdowns): raise ValueError("slowdown schema")
    arrivals=dict(s.arrivals); durations=dict(s.durations)
    if len(arrivals)!=len(s.arrivals) or set(arrivals)!={o.job for o in ops.values()}: raise ValueError('arrivals')
    if len(durations)!=len(s.durations) or set(durations)!=set(ops): raise ValueError('durations')
    if any(not isinstance(t,Q) or t<0 for t in arrivals.values()) or any(not isinstance(d,Q) or d<=0 for d in durations.values()): raise ValueError('exact positive durations / nonnegative arrivals required')
    for o in ops.values():
        if o.machine not in machines or not isinstance(o.nominal,Q) or o.nominal<=0 or any(p not in ops or ops[p].job!=o.job for p in o.predecessors): raise ValueError('operation schema')
    pending=set(ops); done=set()
    while pending:
        ready={k for k in pending if set(ops[k].predecessors)<=done}
        if not ready: raise ValueError('precedence cycle')
        done |= ready; pending -= ready

def fifo(obs:Observation, rng:random.Random)->Decision:
    done={e.operation for e in obs.history if e.kind=='complete'}
    started={e.operation for e in obs.history if e.kind=='start'}
    busy={m for _,m,_ in obs.running}; choices=[]
    for o in sorted(obs.operations,key=lambda x:x.id):
        if o.id not in started and set(o.predecessors)<=done and o.machine not in busy:
            choices.append((o.id,o.machine)); busy.add(o.machine)
    return Decision(tuple(choices))

def execute(s:Scenario, policy:Callable[[Observation,random.Random],Decision]=fifo, policy_seed:int=0, *, max_events:int=10000)->ExecutionLedger:
    check_scenario(s)
    if type(policy_seed) is not int: raise ValueError('policy seed required')
    ops={o.id:o for o in s.instance.operations}; arrivals=dict(s.arrivals); durations=dict(s.durations)
    history=[]; decisions=[]; released=set(); started=set(); done=set(); running={}; starts={}; rng=random.Random(policy_seed)
    if type(max_events) is not int or max_events<1: raise ValueError("positive event budget required")
    timers=set(); batches=0
    t=Q(0)
    while len(done)<len(ops):
        batches+=1
        if batches>max_events: raise ValueError("event budget exhausted / possible deadlock")
        for oid in sorted(k for k,(end,_) in running.items() if end==t):
            _,m=running.pop(oid); done.add(oid); history.append(ExecutionEvent(t,'complete',oid,m))
        for job in sorted(j for j,a in arrivals.items() if a==t and j not in released):
            released.add(job); history.append(ExecutionEvent(t,'arrival',job))
        public=tuple(o for o in s.instance.operations if o.job in released)
        obs=Observation(t,public,tuple(history),tuple((k,t0-starts[k]) for k,t0 in sorted((e.operation,e.time) for e in history if e.kind=='complete')),
            tuple((k,m,starts[k]) for k,(_,m) in sorted(running.items())))
        if t in timers:
            timers.remove(t); history.append(ExecutionEvent(t,"timer","wakeup"))
        decision=policy(obs,rng)
        if not isinstance(decision,Decision): raise ValueError('decision type')
        if type(decision.wakeups) is not tuple or len(set(decision.wakeups))!=len(decision.wakeups) or any(not isinstance(w,Q) or w<=t for w in decision.wakeups): raise ValueError('wakeups must be unique strictly future Fractions')
        timers.update(decision.wakeups)
        decisions.append((t,decision)); busy={m for _,m in running.values()}; selected=set()
        for oid,m in decision.starts:
            if oid not in ops or ops[oid].job not in released: raise ValueError('unreleased/unknown operation')
            o=ops[oid]
            if oid in started or oid in selected: raise ValueError('restart/duplicate')
            if m!=o.machine: raise ValueError('migration')
            if not set(o.predecessors)<=done: raise ValueError('precedence')
            if m in busy: raise ValueError('collision')
            selected.add(oid); busy.add(m)
        for oid,m in decision.starts:
            started.add(oid); starts[oid]=t; running[oid]=(t+durations[oid]*math_product(f for machine,at,f in s.slowdowns if machine==m and t>=at),m); history.append(ExecutionEvent(t,'start',oid,m))
        if len(done)==len(ops): break
        future=[end for end,_ in running.values()]+[a for j,a in arrivals.items() if j not in released and a>t]+list(timers)
        if not future:
            if len(done)!=len(ops): raise ValueError('deadlock / policy declined ready work')
            break
        t=min(future)
    return ExecutionLedger(tuple(history),tuple(decisions),policy_seed)

def replay(s:Scenario, ledger:ExecutionLedger)->ExecutionLedger:
    validate_run(s,ledger)
    it=iter(ledger.decisions)
    def policy(obs,rng):
        try: t,d=next(it)
        except StopIteration as exc: raise ValueError('truncated replay decisions') from exc
        if obs.time!=t: raise ValueError('replay clock')
        return d
    actual=execute(s,policy,ledger.policy_seed)
    if actual!=ledger: raise ValueError('replay mismatch')
    return actual

def validate_ledger(s:Scenario, ledger:ExecutionLedger):
    """Independent event scan: does not call execute or replay."""
    check_scenario(s); ops={o.id:o for o in s.instance.operations}; durations=dict(s.durations); arrivals=dict(s.arrivals)
    starts={}; ends={}; released=set(); busy={}; previous=(Q(-1),-1); rank={'complete':0,'arrival':1,'timer':2,'start':4}
    for e in ledger.events:
        if e.kind not in rank or (e.time,rank[e.kind])<previous: raise ValueError('event order')
        previous=(e.time,rank[e.kind])
        if e.kind=='timer':
            if e.operation!='wakeup' or e.machine!=-1: raise ValueError('timer identity')
            continue
        if e.kind=='arrival':
            if e.operation in released or arrivals.get(e.operation)!=e.time: raise ValueError('arrival')
            released.add(e.operation); continue
        if e.operation not in ops: raise ValueError('identity')
        o=ops[e.operation]
        if e.machine!=o.machine: raise ValueError('machine')
        if e.kind=='start':
            if o.id in starts or o.job not in released or not set(o.predecessors)<=set(ends) or o.machine in busy: raise ValueError('invalid start')
            starts[o.id]=e.time; busy[o.machine]=o.id
        else:
            if o.id not in starts or o.id in ends or busy.get(o.machine)!=o.id or e.time-starts[o.id]!=durations[o.id]*math_product(f for machine,at,f in s.slowdowns if machine==o.machine and starts[o.id]>=at): raise ValueError('invalid completion')
            ends[o.id]=e.time; del busy[o.machine]
    if set(ends)!=set(ops) or busy: raise ValueError('incomplete ledger')
    return max(ends.values(),default=Q(0))

def validate_decision_event_consistency(ledger:ExecutionLedger):
    """Independent logging check, not physical validation or replay."""
    from collections import Counter
    if type(ledger.policy_seed) is not int: raise ValueError('missing policy seed')
    try:
        expected=sorted({Q(0)} | {e.time for e in ledger.events if e.kind in ('arrival','complete','timer')}) if ledger.events else []
        times=[t for t,d in ledger.decisions]
        if times!=expected: raise ValueError('decision timestamps missing, extra, duplicated or reordered')
        requested=set(); fired=set()
        for t,d in ledger.decisions:
            due=[e for e in ledger.events if e.kind=="timer" and e.time==t]
            if len(due)>1 or (due and t not in requested) or (t in requested and not due): raise ValueError("timer request/event mismatch")
            if due: fired.add(t)
            if type(d.wakeups) is not tuple or len(set(d.wakeups))!=len(d.wakeups) or any(not isinstance(w,Q) or w<=t for w in d.wakeups): raise ValueError("invalid wakeup")
            requested.update(d.wakeups)
        if times and any(w<=times[-1] and w not in fired for w in requested): raise ValueError("missing timer event")
        authorized=[]
        for t,d in ledger.decisions:
            if not isinstance(t,Q) or not isinstance(d,Decision) or not isinstance(d.starts,tuple): raise ValueError('malformed decision')
            for oid,m in d.starts:
                if type(oid) is not str or type(m) is not int: raise ValueError('malformed start')
                authorized.append((t,oid,m))
        actual=[(e.time,e.operation,e.machine) for e in ledger.events if e.kind=='start']
        if len({x[1] for x in authorized})!=len(authorized) or len({x[1] for x in actual})!=len(actual): raise ValueError('duplicate start')
        if Counter(authorized)!=Counter(actual): raise ValueError('decision/start mismatch')
    except (TypeError,AttributeError,IndexError) as exc: raise ValueError('malformed decision history') from exc

def validate_run(s:Scenario,ledger:ExecutionLedger):
    validate_decision_event_consistency(ledger)
    return validate_ledger(s,ledger)

def replay_policy(s:Scenario,ledger:ExecutionLedger,policy,expected_seed:int):
    validate_run(s,ledger)
    if ledger.policy_seed!=expected_seed: raise ValueError('inconsistent policy seed')
    actual=execute(s,policy,ledger.policy_seed)
    if actual!=ledger: raise ValueError('policy replay mismatch')
    return actual
