"""Public-only advisory residual JSP adapter. No execution or scenario references."""
from dataclasses import dataclass,asdict,replace
from fractions import Fraction
from collections import Counter
import hashlib,json,time,math
import ortools
from ortools.sat.python import cp_model
from engine import Observation,Forecast

def integer(x):
    if type(x) is int: return x
    if isinstance(x,Fraction) and x.denominator==1: return x.numerator
    raise ValueError('integer time required')

def digest(x): return hashlib.sha256(repr(x).encode()).hexdigest()
@dataclass(frozen=True)
class Task:
    id:str
    machine:int
    duration:int
    predecessors:tuple[str,...]
    frozen_start:int|None=None
@dataclass(frozen=True)
class Problem:
    now:int
    tasks:tuple[Task,...]
    completed:tuple[tuple[str,int],...]
    horizon:int
    observation_hash:str
    instance_hash:str
    forecast_version:int
@dataclass(frozen=True)
class Row:
    id:str
    machine:int
    start:int
    end:int
    running:bool=False
@dataclass(frozen=True)
class Result:
    status:str
    rows:tuple[Row,...]
    objective:int|None
    bound:float|None
    solver_seconds:float
    elapsed_seconds:float
    time_limit:float
    workers:int
    seed:int
    ortools_version:str
    observation_hash:str
    instance_hash:str
    forecast_version:int
    deterministic_limit:float|None=None
    deterministic_seconds:float|None=None
    response_proto:str|None=None
    parameters:str|None=None

def prepare(obs:Observation,forecast:Forecast,convention='total_minus_elapsed')->Problem:
    try:
        return _prepare(obs,forecast,convention)
    except (KeyError,TypeError,AttributeError) as exc:
        raise ValueError('malformed public observation or forecast') from exc

def _prepare(obs:Observation,forecast:Forecast,convention)->Problem:
    if convention not in ('total_minus_elapsed','remaining'): raise ValueError('forecast convention')
    t=integer(obs.time)
    if t<0 or integer(forecast.through)>t: raise ValueError('forecast timing')
    ops={o.id:o for o in obs.operations}
    if len(ops)!=len(obs.operations): raise ValueError('duplicate operation')
    completed={}; starts={}; released=set(); occupied={}; prev=(-1,-1)
    ranks={'complete':0,'arrival':1,'timer':2,'start':4}
    for e in obs.history:
        et=integer(e.time)
        if et<0 or et>t or e.kind not in ranks or (et,ranks[e.kind])<prev: raise ValueError('history time/order')
        prev=(et,ranks[e.kind])
        if e.kind=='timer':
            if e.operation!='wakeup' or e.machine!=-1: raise ValueError('timer identity')
            continue
        if e.kind=='arrival':
            if e.operation in released: raise ValueError('duplicate arrival')
            released.add(e.operation); continue
        if e.operation not in ops or e.machine!=ops[e.operation].machine: raise ValueError('history identity/machine')
        o=ops[e.operation]
        if e.kind=='start':
            if o.id in starts or o.job not in released or e.machine in occupied or not set(o.predecessors)<=set(completed): raise ValueError('invalid history start')
            starts[o.id]=et; occupied[e.machine]=o.id
        else:
            if o.id not in starts or o.id in completed or occupied.get(e.machine)!=o.id or et<=starts[o.id]: raise ValueError('invalid history completion')
            completed[o.id]=et; del occupied[e.machine]
    if any(o.job not in released for o in ops.values()): raise ValueError('unreleased operation')
    running={k:(integer(m),integer(st)) for k,m,st in obs.running}
    if len(running)!=len(obs.running) or running!={k:(ops[k].machine,st) for k,st in starts.items() if k not in completed}: raise ValueError('running history mismatch')
    if dict(obs.completed_durations)!={k:completed[k]-starts[k] for k in completed} or len(obs.completed_durations)!=len(completed): raise ValueError('completed duration mismatch')
    estimates=dict(forecast.estimates); unfinished=set(ops)-set(completed)
    if len(estimates)!=len(forecast.estimates) or set(estimates)!=unfinished: raise ValueError('forecast IDs')
    tasks=[]
    for k in sorted(unfinished):
        o=ops[k]; d=integer(estimates[k])
        if type(o.machine) is not int or o.machine<0: raise ValueError('machine key')
        if d<=0: raise ValueError('positive forecast required')
        if any(p not in ops for p in o.predecessors): raise ValueError('predecessor identity')
        st=running[k][1] if k in running else None
        if st is not None and convention=='total_minus_elapsed': d=max(1,d-(t-st))
        tasks.append(Task(k,o.machine,d,o.predecessors,st))
    # Validate acyclic public topology independently of solver feasibility.
    pending={x.id for x in tasks}; done=set(completed)
    while pending:
        ready={x.id for x in tasks if x.id in pending and set(x.predecessors)<=done}
        if not ready: raise ValueError('precedence cycle')
        pending-=ready; done|=ready
    horizon=t+sum(x.duration for x in tasks)
    if horizon>=2**60: raise ValueError('integer horizon overflow guard')
    return Problem(t,tuple(tasks),tuple(sorted(completed.items())),horizon,digest(obs),digest(obs.operations),forecast.version)

def status_name(status):
    names={cp_model.OPTIMAL:'OPTIMAL',cp_model.FEASIBLE:'FEASIBLE',cp_model.INFEASIBLE:'INFEASIBLE',cp_model.UNKNOWN:'UNKNOWN',cp_model.MODEL_INVALID:'MODEL_INVALID'}
    if status not in names: raise ValueError('unrecognized solver status')
    return names[status]

def solve(p:Problem,time_limit=2.0,seed=0,deterministic_limit=None)->Result:
    if not math.isfinite(time_limit) or time_limit<0 or type(seed) is not int or not 0<=seed<2**31: raise ValueError('solver configuration')
    begin=time.perf_counter(); model=cp_model.CpModel(); variables={}; machines={}; completed=dict(p.completed)
    for task in p.tasks:
        st=model.NewIntVar(p.now,p.now if task.frozen_start is not None else p.horizon,'s_'+task.id)
        en=model.NewIntVar(p.now,p.horizon,'e_'+task.id)
        iv=model.NewIntervalVar(st,task.duration,en,'i_'+task.id)
        variables[task.id]=(st,en); machines.setdefault(task.machine,[]).append(iv)
    for intervals in machines.values(): model.AddNoOverlap(intervals)
    for task in p.tasks:
        for pred in task.predecessors:
            model.Add(variables[task.id][0]>=variables[pred][1] if pred in variables else variables[task.id][0]>=completed[pred])
    makespan=model.NewIntVar(p.now,p.horizon,'makespan')
    model.AddMaxEquality(makespan,[v[1] for v in variables.values()] or [p.now]); model.Minimize(makespan)
    solver=cp_model.CpSolver(); solver.parameters.max_time_in_seconds=time_limit; solver.parameters.num_search_workers=1; solver.parameters.random_seed=seed
    if deterministic_limit is not None:
        if not math.isfinite(deterministic_limit) or deterministic_limit<0: raise ValueError("deterministic budget")
        solver.parameters.max_deterministic_time=deterministic_limit
    status=solver.Solve(model)
    result=extract(p,solver,status,variables,makespan,time_limit,seed,begin)
    result=replace(result,deterministic_limit=deterministic_limit,deterministic_seconds=solver.ResponseProto().deterministic_time,response_proto=str(solver.ResponseProto()),parameters=str(solver.parameters))
    if result.status in ('OPTIMAL','FEASIBLE'): validate_plan(p,result)
    return result

def extract(p,solver,status,variables,makespan,time_limit,seed,begin):
    name=status_name(status); rows=(); objective=None; bound=None
    if name in ('OPTIMAL','FEASIBLE'):
        rows=tuple(Row(x.id,x.machine,x.frozen_start if x.frozen_start is not None else solver.Value(variables[x.id][0]),solver.Value(variables[x.id][1]),x.frozen_start is not None) for x in p.tasks)
        objective=solver.Value(makespan); bound=solver.BestObjectiveBound()
    return Result(name,rows,objective,bound,solver.WallTime(),time.perf_counter()-begin,time_limit,1,seed,ortools.__version__,p.observation_hash,p.instance_hash,p.forecast_version)

def validate_plan(p:Problem,r:Result):
    """Plain interval scan; no CP constraints or solver access."""
    if r.status not in ('OPTIMAL','FEASIBLE'): raise ValueError('nonfeasible status')
    for field in ('observation_hash','instance_hash','forecast_version'):
        if type(getattr(r,field)) is not type(getattr(p,field)) or getattr(r,field)!=getattr(p,field):
            raise ValueError('result provenance mismatch: '+field)
    tasks={x.id:x for x in p.tasks}; rows={x.id:x for x in r.rows}
    if Counter(x.id for x in r.rows)!=Counter({k:1 for k in tasks}): raise ValueError('coverage')
    for k,row in rows.items():
        task=tasks[k]; st=integer(row.start); en=integer(row.end)
        if st<0 or en<0: raise ValueError('negative interval time')
        # Historical running start may precede now; residual occupancy is [now,end).
        if st>p.horizon or en>p.horizon: raise ValueError('planning horizon')
        if row.machine!=task.machine: raise ValueError('machine')
        if task.frozen_start is not None:
            if st!=task.frozen_start or not row.running: raise ValueError('running restart')
            if en!=p.now+task.duration: raise ValueError('running forecast duration')
        elif row.running or st<p.now: raise ValueError('start time')
        elif en-st!=task.duration: raise ValueError('duration')
        for pred in task.predecessors:
            end=rows[pred].end if pred in rows else dict(p.completed)[pred]
            if max(st,p.now)<end: raise ValueError('precedence')
    items=list(rows.values())
    for i,a in enumerate(items):
        for b in items[i+1:]:
            if a.machine==b.machine and max(a.start,b.start,p.now)<min(a.end,b.end): raise ValueError('collision')
    if integer(r.objective)!=max([p.now]+[x.end for x in items]): raise ValueError('objective')
    return r.objective
