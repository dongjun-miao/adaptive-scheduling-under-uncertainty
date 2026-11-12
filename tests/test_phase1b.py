import unittest,random,time,json
from dataclasses import replace,asdict
from unittest.mock import Mock
from engine import *
from residual import *
from test_engine import case

def snapshots(s):
    seen=[]
    def policy(o,r): seen.append(o); return fifo(o,r)
    execute(s,policy); return seen

def forecast(o):
    done={k for k,_ in o.completed_durations}
    return Forecast(1,o.time,tuple((x.id,x.nominal) for x in o.operations if x.id not in done))

def randomized(o,r):
    operations=list(o.operations); r.shuffle(operations)
    # Select a single random eligible action, preserving deterministic RNG consumption.
    ready=[]; done={e.operation for e in o.history if e.kind=='complete'}; started={e.operation for e in o.history if e.kind=='start'}; busy={m for _,m,_ in o.running}
    for x in operations:
        if x.id not in started and set(x.predecessors)<=done and x.machine not in busy: ready.append((x.id,x.machine))
    return Decision(tuple(ready[:1]))

class IntegrityTests(unittest.TestCase):
    def setUp(self): self.s=case(); self.l=execute(self.s)
    def reject(self,l):
        with self.assertRaises(ValueError): validate_decision_event_consistency(l)
    def test_positive_terminal_empty(self): validate_run(self.s,self.l); self.assertEqual(self.l.decisions[-1][1],Decision(()))
    def test_missing(self): self.reject(replace(self.l,decisions=self.l.decisions[1:]))
    def test_extra(self): self.reject(replace(self.l,decisions=self.l.decisions+((Q(9),Decision(())),)))
    def test_duplicate(self): self.reject(replace(self.l,decisions=self.l.decisions+self.l.decisions[:1]))
    def test_wrong_machine(self): self.reject(replace(self.l,decisions=((Q(0),Decision((('a',9),('c',1)))),)+self.l.decisions[1:]))
    def test_wrong_time(self): self.reject(replace(self.l,decisions=((Q(1),self.l.decisions[0][1]),)+self.l.decisions[1:]))
    def test_reordered(self): self.reject(replace(self.l,decisions=tuple(reversed(self.l.decisions))))
    def test_missing_start(self): self.reject(replace(self.l,events=tuple(e for e in self.l.events if not(e.kind=='start' and e.operation=='a'))))
    def test_extra_start(self): self.reject(replace(self.l,events=self.l.events+(ExecutionEvent(Q(4),'start','z',0),)))
    def test_truncated_replay(self):
        with self.assertRaises(ValueError): replay(self.s,replace(self.l,decisions=()))
    def test_malformed(self): self.reject(replace(self.l,decisions=(None,)))
    def test_missing_seed(self): self.reject(replace(self.l,policy_seed=None))
    def test_random_seed_replay(self):
        i=Instance((Machine(0),),(Operation('a','A',0,Q(1)),Operation('b','B',0,Q(1)),Operation('c','C',0,Q(1))))
        s=stochastic(i,9); ledgers=[execute(s,randomized,k) for k in range(8)]
        self.assertGreater(len({l.decisions for l in ledgers}),1)
        for k,l in enumerate(ledgers):
            self.assertEqual(l.policy_seed,k); self.assertEqual(execute(s,randomized,k),l); replay(s,l); replay_policy(s,l,randomized,k)
        with self.assertRaisesRegex(ValueError,'seed'): replay_policy(s,ledgers[0],randomized,99)
        self.assertNotIn('policy',dict(s.seeds))

class ResidualTests(unittest.TestCase):
    def setUp(self): self.obs=snapshots(case()); self.p=prepare(self.obs[0],forecast(self.obs[0])); self.r=solve(self.p)
    def test_idle_oracle(self): self.assertEqual(self.r.objective,3); validate_plan(self.p,self.r)
    def test_completed_simultaneous(self):
        p=prepare(self.obs[1],forecast(self.obs[1])); self.assertEqual(set(dict(p.completed)),{'a','c'}); self.assertEqual(solve(p).objective,4)
    def test_empty(self):
        p=prepare(self.obs[-1],forecast(self.obs[-1])); self.assertEqual(p.tasks,()); self.assertEqual(solve(p).objective,4)
    def test_determinism(self):
        r=solve(self.p); self.assertEqual(r.rows,self.r.rows); self.assertEqual(r.objective,self.r.objective)
    def test_future_absent(self): self.assertNotIn('e',{x.id for x in self.p.tasks})
    def test_forecast_invalid(self):
        for estimates in ((),(('a',Q(-1)),),tuple((k,float('nan')) for k,_ in forecast(self.obs[0]).estimates),tuple((k,float('inf')) for k,_ in forecast(self.obs[0]).estimates),tuple((k,Q(1,2)) for k,_ in forecast(self.obs[0]).estimates),(('alien',Q(1)),)):
            with self.subTest(estimates=estimates),self.assertRaises(ValueError): prepare(self.obs[0],Forecast(1,Q(0),estimates))
    def test_fractional_clock(self):
        with self.assertRaisesRegex(ValueError,'integer'): prepare(replace(self.obs[0],time=Q(1,2)),forecast(self.obs[0]))
    def test_wrong_machine_key(self):
        o=replace(self.obs[0],operations=(replace(self.obs[0].operations[0],machine=-1),)+self.obs[0].operations[1:])
        with self.assertRaisesRegex(ValueError,'machine'): prepare(o,forecast(o))
    def test_long_horizon(self):
        f=Forecast(1,Q(0),tuple((k,Q(1000000)) for k,_ in forecast(self.obs[0]).estimates)); p=prepare(self.obs[0],f)
        self.assertEqual(p.horizon,4000000); self.assertEqual(solve(p).objective,2000000)
    def test_mutations(self):
        for rows,reason in [(self.r.rows[:-1],'coverage'),(self.r.rows+(self.r.rows[0],),'coverage'),(self.r.rows+(Row('future',0,0,1),),'coverage'),((replace(self.r.rows[0],machine=9),)+self.r.rows[1:],'machine')]:
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason): validate_plan(self.p,replace(self.r,rows=rows))
    def test_precedence_mutation(self):
        rows=tuple(replace(x,start=0,end=1) if x.id=='b' else x for x in self.r.rows)
        with self.assertRaisesRegex(ValueError,'precedence'): validate_plan(self.p,replace(self.r,rows=rows))
    def test_collision_mutation(self):
        # d has completed predecessor c at 2; shift a to collide with d, keeping b after a.
        rows=(Row('a',0,2,4),Row('b',1,4,5),Row('c',1,0,2),Row('d',0,2,3))
        with self.assertRaisesRegex(ValueError,'collision'): validate_plan(self.p,replace(self.r,rows=rows,objective=5))
    def test_status_controlled(self):
        for status in (cp_model.OPTIMAL,cp_model.FEASIBLE,cp_model.INFEASIBLE,cp_model.UNKNOWN,cp_model.MODEL_INVALID):
            solver=Mock(); solver.WallTime.return_value=0.; solver.Value.return_value=0; solver.BestObjectiveBound.return_value=0
            p=replace(self.p,tasks=(),horizon=0); r=extract(p,solver,status,{},0,1,0,time.perf_counter())
            if status in (cp_model.OPTIMAL,cp_model.FEASIBLE): self.assertEqual(r.objective,0)
            else: solver.Value.assert_not_called(); self.assertIsNone(r.objective); self.assertEqual(r.rows,())
    def test_real_timeout(self):
        r=solve(self.p,time_limit=0); self.assertEqual(r.status,'UNKNOWN'); self.assertEqual(r.rows,()); self.assertIsNone(r.objective)
    def test_invalid_history(self):
        with self.assertRaises(ValueError): prepare(replace(self.obs[1],history=self.obs[1].history[1:]),forecast(self.obs[1]))
    def test_midrun_isolation_and_running(self):
        a=replace(case(),durations=(('a',Q(2)),('b',Q(1)),('c',Q(6)),('d',Q(1)),('e',Q(1))),arrivals=(('A',Q(0)),('B',Q(0)),('C',Q(9))))
        b=replace(a,durations=(('a',Q(2)),('b',Q(7)),('c',Q(8)),('d',Q(4)),('e',Q(2))),arrivals=(('A',Q(0)),('B',Q(0)),('C',Q(10))))
        oa=snapshots(a)[1]; ob=snapshots(b)[1]; self.assertEqual(oa.time,2); self.assertEqual(oa,ob); self.assertTrue(oa.running); self.assertTrue(oa.completed_durations)
        fa,fb=forecast(oa),forecast(ob); self.assertEqual(fa,fb)
        pa,pb=prepare(oa,fa),prepare(ob,fb); self.assertEqual(pa,pb)
        ra,rb=solve(pa),solve(pb); self.assertEqual(ra.rows,rb.rows); self.assertEqual(fifo(oa,random.Random(7)),fifo(ob,random.Random(7)))
        c=next(x for x in ra.rows if x.id=='c'); self.assertEqual((c.start,c.end,c.running),(0,3,True))
        self.assertEqual(next(x for x in pa.tasks if x.id=='c').duration,1)
        with self.assertRaisesRegex(ValueError,'restart'): validate_plan(pa,replace(ra,rows=tuple(replace(x,start=2) if x.id=='c' else x for x in ra.rows)))
        with self.assertRaisesRegex(ValueError,'coverage'): validate_plan(pa,replace(ra,rows=ra.rows+(Row('a',0,0,2),)))
        # Forecast releases M1 at 3, but actual c completes at 6. Arrival at 3 triggers attempted b.
        physical=replace(a,arrivals=(('A',Q(0)),('B',Q(0)),('C',Q(3))))
        def unsafe(o,r): return Decision((('b',1),)) if o.time==3 else fifo(o,r)
        with self.assertRaisesRegex(ValueError,'collision'): execute(physical,unsafe)

class ExtraCases(unittest.TestCase):
    def test_initial_empty_decision(self):
        s=replace(case(),arrivals=(('A',Q(1)),('B',Q(1)),('C',Q(2))))
        l=execute(s); self.assertEqual(l.decisions[0],(Q(0),Decision(()))); validate_run(s,l)
    def test_mutable_schema(self):
        with self.assertRaisesRegex(ValueError,'immutable'): execute(replace(case(),durations=list(case().durations)))
    def test_running_only_and_multiple(self):
        i=Instance((Machine(0),Machine(1)),(Operation('a','A',0,Q(5)),Operation('b','B',1,Q(7)),Operation('c','C',0,Q(1))))
        s=Scenario(i,(('A',Q(0)),('B',Q(0)),('C',Q(2))),(('a',Q(5)),('b',Q(7)),('c',Q(1))))
        o=snapshots(s)[1]; p=prepare(o,forecast(o)); self.assertEqual(sum(x.frozen_start is not None for x in p.tasks),2); validate_plan(p,solve(p))
        # Public prefix with only a running, obtained before a future arrival.
        i=Instance((Machine(0),),(Operation('a','A',0,Q(5)),Operation('c','C',0,Q(1))))
        s=Scenario(i,(('A',Q(0)),('C',Q(2))),(('a',Q(5)),('c',Q(1))))
        o=snapshots(s)[1]; p=prepare(o,forecast(o)); self.assertEqual(solve(p).objective,6)
    def test_empty_instance(self):
        o=Observation(Q(0),(),(),(),()); p=prepare(o,Forecast(0,Q(0),())); self.assertEqual(solve(p).objective,0)
