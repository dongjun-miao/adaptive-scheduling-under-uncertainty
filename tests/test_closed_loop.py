import unittest,random
from dataclasses import replace
from engine import *
from residual import solve,Row
from closed_loop import Coordinator,Config,safe_dispatch
from test_engine import case

def chain(actual=5,nominal=2):
    i=Instance((Machine(0),),(Operation('a','A',0,Q(nominal)),Operation('b','A',0,Q(1),('a',))))
    return Scenario(i,(('A',Q(0)),),(('a',Q(actual)),('b',Q(1))))

def run(s,config=Config(),solver=solve):
    c=Coordinator(config,solver); l=execute(s,c,17); validate_run(s,l); replay(s,l); return c,l

class ClosedLoopTests(unittest.TestCase):
    def test_hand_trace_late(self):
        c,l=run(chain(),Config(Q(1)))
        physical=[(e.time,e.kind,e.operation) for e in l.events if e.kind!='timer']
        self.assertEqual(physical,[(0,'arrival','A'),(0,'start','a'),(5,'complete','a'),(5,'start','b'),(6,'complete','b')])
        self.assertEqual(validate_run(chain(),l),6)
        self.assertTrue(any(n.reason=='predecessor incomplete' for r in c.records for n in r.notes))
        self.assertTrue(any(r.observation.running for r in c.records))
        self.assertEqual(dict(c.records[2].forecast.estimates)['a'],2)
    def test_early_completion(self):
        c,l=run(chain(1,5)); self.assertEqual([(e.operation,e.time) for e in l.events if e.kind=='start'],[('a',0),('b',1)])
        self.assertEqual(validate_run(chain(1,5),l),2)
    def test_normal_simultaneous(self):
        c,l=run(case(),Config(Q(2)))
        self.assertEqual(validate_run(case(),l),4)
        at2=[e.kind for e in l.events if e.time==2]
        self.assertEqual(at2,['complete','complete','arrival','timer','start','start'])
        self.assertEqual(sum(t==2 for t,d in l.decisions),1)
    def test_timer_only(self):
        c,l=run(chain(5,5),Config(Q(2)))
        self.assertEqual([e.kind for e in l.events if e.time==2],['timer'])
        self.assertIn(Q(2),[t for t,d in l.decisions])
    def test_competing(self):
        i=Instance((Machine(0),),(Operation('a','A',0,Q(2)),Operation('b','B',0,Q(1))))
        s=Scenario(i,(('A',Q(0)),('B',Q(0))),(('a',Q(2)),('b',Q(1))))
        _,l=run(s); self.assertEqual(validate_run(s,l),3); self.assertEqual(len([e for e in l.events if e.kind=='start']),2)
    def test_blocked_machine_guard(self):
        o=Observation(Q(2),(Operation('a','A',0,Q(2)),Operation('b','B',0,Q(1))),(ExecutionEvent(Q(0),'start','a',0),),(),(('a',0,Q(0)),))
        d,notes=safe_dispatch(o,(Row('b',0,2,3),)); self.assertEqual(d.starts,()); self.assertEqual(notes[0].reason,'machine busy')
    def test_no_overtaking(self):
        o=Observation(Q(2),(Operation('a','A',0,Q(1),('p',)),Operation('b','B',0,Q(1))),(),(),())
        d,n=safe_dispatch(o,(Row('a',0,1,2),Row('b',0,2,3))); self.assertEqual(d.starts,()); self.assertEqual(n[1].reason,'prior plan entry blocked')
    def test_unknown_real(self):
        c,l=run(chain(),Config(Q(2),0)); self.assertTrue(all(r.result.status=='UNKNOWN' for r in c.records)); self.assertEqual(c.accounting()['fallback_count'],len(c.records)); self.assertEqual(validate_run(chain(),l),6)
    def test_status_fallbacks(self):
        for status in ('INFEASIBLE','MODEL_INVALID','UNKNOWN','FEASIBLE'):
            def stub(p,**kw): return replace(solve(p,**kw),status=status)
            c,l=run(chain(),solver=stub)
            self.assertEqual(any(r.fallback for r in c.records),status!='FEASIBLE')
            validate_run(chain(),l)
    def test_invalid_plan(self):
        def bad(p,**kw): return replace(solve(p,**kw),observation_hash='wrong')
        c,l=run(chain(),solver=bad); self.assertTrue(all(r.invalid and r.fallback for r in c.records)); validate_run(chain(),l)
    def test_solver_exception(self):
        def bad(*a,**kw): raise RuntimeError('injected failure')
        c,l=run(chain(),solver=bad); self.assertIn('injected failure',c.records[0].failure); self.assertEqual(c.accounting()['unknown_solver_times'],len(c.records))
    def test_midrun_noninterference(self):
        a=replace(case(),durations=(('a',Q(2)),('b',Q(1)),('c',Q(6)),('d',Q(1)),('e',Q(1))),arrivals=(('A',Q(0)),('B',Q(0)),('C',Q(9))))
        b=replace(a,durations=(('a',Q(2)),('b',Q(7)),('c',Q(8)),('d',Q(3)),('e',Q(2))),arrivals=(('A',Q(0)),('B',Q(0)),('C',Q(10))))
        ca,la=run(a); cb,lb=run(b)
        ra=next(r for r in ca.records if r.observation.time==2); rb=next(r for r in cb.records if r.observation.time==2)
        self.assertTrue(ra.observation.running); self.assertTrue(ra.observation.completed_durations)
        for attr in ('observation','forecast','problem','decision'): self.assertEqual(getattr(ra,attr),getattr(rb,attr))
        self.assertEqual(ra.result.rows,rb.result.rows)
    def test_fractional_timer(self):
        c,l=run(chain(),Config(Q(1,2))); self.assertIn(Q(1,2),[t for t,d in l.decisions]); validate_run(chain(),l)
        self.assertTrue(any(r.failure and 'integer' in r.failure for r in c.records))
    def test_zero_time_rejected(self):
        with self.assertRaisesRegex(ValueError,'strictly future'): execute(chain(),lambda o,r:Decision((),(o.time,)))
        with self.assertRaises(ValueError): Config(Q(0))
    def test_bounded_timer_deadlock(self):
        with self.assertRaisesRegex(ValueError,'event budget'): execute(chain(),lambda o,r:Decision((),(o.time+1,)),max_events=3)
    def test_no_timer_deadlock(self):
        with self.assertRaisesRegex(ValueError,'deadlock'): execute(chain(),lambda o,r:Decision(()))
    def test_duplicate_wakeup_rejected(self):
        with self.assertRaisesRegex(ValueError,'unique'): execute(chain(),lambda o,r:Decision((),(Q(1),Q(1))))
    def test_corrupt_timer(self):
        c,l=run(chain())
        with self.assertRaises(ValueError): validate_run(chain(),replace(l,events=tuple(e for e in l.events if not(e.kind=='timer' and e.time==2))))
    def test_empty_and_terminal(self):
        s=Scenario(Instance((),()),(),()); c,l=run(s); self.assertEqual(l.events,()); self.assertEqual(c.records,[]); self.assertEqual(validate_run(s,l),0)
        c,l=run(chain()); self.assertEqual(l.decisions[-1][1].starts,()); self.assertEqual(max(e.time for e in l.events),6)
    def test_repeat_accounting(self):
        c,l=run(chain()); c2,l2=run(chain()); self.assertEqual(l,l2)
        a=c.accounting(); self.assertEqual(a['solver_calls'],len(c.records)); self.assertEqual(a['solver_seconds'],sum(r.solver_seconds for r in c.records)); self.assertGreaterEqual(a['planning_overhead_seconds'],a['validation_seconds'])
