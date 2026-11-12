import unittest
from engine import *
from policies import B0,B1,PolicyConfig
from test_closed_loop import chain
class PolicyTests(unittest.TestCase):
    def test_periodic_not_callback(self):
        p=B1(PolicyConfig(Q(4))); l=execute(chain(5,2),p); validate_run(chain(5,2),l)
        self.assertEqual([r['time'] for r in p.records if r['called']],[0,4]); self.assertGreater(len(p.records),2)
        self.assertEqual({r['forecast_version'] for r in p.records},{1})
    def test_b0_no_solver(self):
        p=B0(); l=execute(chain(),p); self.assertEqual(p.accounting()['solver_calls'],0); validate_run(chain(),l)
    def test_slowdown_at_start(self):
        s=Scenario(Instance((Machine(0),),(Operation('a','A',0,Q(2)),)),(('A',Q(3)),),(('a',Q(2)),),slowdowns=((0,Q(3),Q(2)),))
        l=execute(s,B0()); self.assertEqual(validate_run(s,l),7); replay(s,l)

class AdversarialPolicyTests(unittest.TestCase):
    def test_completion_no_replan_early(self):
        p=B1(PolicyConfig(Q(10))); l=execute(chain(1,5),p); self.assertEqual([r['time'] for r in p.records if r['called']],[0]); self.assertEqual([(e.operation,e.time) for e in l.events if e.kind=='start'],[('a',0),('b',5)]); replay(chain(1,5),l)
    def test_arrival_waits_period(self):
        i=Instance((Machine(0),),(Operation('a','A',0,Q(1)),Operation('b','B',0,Q(1))))
        s=Scenario(i,(('A',Q(0)),('B',Q(2))),(('a',Q(1)),('b',Q(1))))
        p=B1(PolicyConfig(Q(4))); l=execute(s,p); self.assertEqual([r['time'] for r in p.records if r['called']],[0,4]); self.assertEqual([e.time for e in l.events if e.kind=='start'],[0,4]); validate_run(s,l)
    def test_budget_failure(self):
        p=B1(PolicyConfig(Q(1),0.01,0.01)); l=execute(chain(),p); self.assertEqual(p.accounting()['solver_calls'],1); self.assertTrue(any(r['failure']=='TOTAL_BUDGET_EXHAUSTED' for r in p.records)); validate_run(chain(),l)
    def test_unknown_and_invalid(self):
        from dataclasses import replace
        from residual import solve
        for field,value in [('status','UNKNOWN'),('observation_hash','wrong')]:
            def fake(p,**kw): return replace(solve(p,**kw),**{field:value})
            p=B1(PolicyConfig(Q(4)),fake); l=execute(chain(),p); self.assertTrue(any(r['fallback'] for r in p.records)); validate_run(chain(),l)
    def test_noninterference(self):
        from dataclasses import replace
        from test_engine import case
        a=replace(case(),durations=(('a',Q(2)),('b',Q(1)),('c',Q(6)),('d',Q(1)),('e',Q(1))),arrivals=(('A',Q(0)),('B',Q(0)),('C',Q(9))))
        b=replace(a,durations=(('a',Q(2)),('b',Q(7)),('c',Q(8)),('d',Q(3)),('e',Q(2))),arrivals=(('A',Q(0)),('B',Q(0)),('C',Q(10))))
        ps=[]
        for s in (a,b):
            p=B1(PolicyConfig(Q(2))); execute(s,p); ps.append(next(r for r in p.records if r['time']==2))
        for key in ('problem','decision','observation_hash','plan_version'): self.assertEqual(ps[0][key],ps[1][key])
    def test_interval_trigger_and_versions(self):
        for period in (Q(2),Q(4)):
            p=B1(PolicyConfig(period)); execute(chain(7,2),p)
            self.assertTrue(all(r['time']==0 or r['time']%period==0 for r in p.records if r['called']))
            self.assertEqual(len({r['observation_version'] for r in p.records}),len(p.records)); self.assertEqual({r['forecast_version'] for r in p.records},{1})
    def test_obsolete_timers_current_plan_only(self):
        p=B1(PolicyConfig(Q(2))); l=execute(chain(7,5),p); validate_run(chain(7,5),l)
        self.assertEqual(len([e for e in l.events if e.kind=='start']),2)
        self.assertTrue(all(not r['called'] for r in p.records if r['time']==5))
    def test_fifo_release_not_id(self):
        i=Instance((Machine(0),),(Operation('z','old',0,Q(1)),Operation('a','new',0,Q(1))))
        obs=Observation(Q(2),i.operations,(ExecutionEvent(Q(0),'arrival','old'),ExecutionEvent(Q(1),'arrival','new')),(),())
        self.assertEqual(B0()(obs,None).starts,(('z',0),))
