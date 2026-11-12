import unittest
from dataclasses import replace
from engine import Observation,Operation,ExecutionEvent,Forecast,Q
from residual import prepare,solve,validate_plan,Row

class IntegrityPatchTests(unittest.TestCase):
    def setUp(self):
        self.obs=Observation(Q(0),(Operation('a','A',0,Q(1)),),(ExecutionEvent(Q(0),'arrival','A'),),(),())
        self.f=Forecast(1,Q(0),(('a',Q(1)),)); self.p=prepare(self.obs,self.f); self.r=solve(self.p)
    def reject(self,r,reason):
        with self.assertRaisesRegex(ValueError,reason): validate_plan(self.p,r)
    def test_start_after_horizon(self): self.reject(replace(self.r,rows=(Row('a',0,100,101),),objective=101),'horizon')
    def test_end_after_horizon(self): self.reject(replace(self.r,rows=(Row('a',0,1,2),),objective=2),'horizon')
    def test_observation_hash(self): self.reject(replace(self.r,observation_hash='unrelated'),'observation_hash')
    def test_instance_hash(self): self.reject(replace(self.r,instance_hash='unrelated'),'instance_hash')
    def test_forecast_version(self): self.reject(replace(self.r,forecast_version=999),'forecast_version')
    def test_negative_time(self): self.reject(replace(self.r,rows=(Row('a',0,-1,0),)),'time')
    def test_malformed_times(self):
        for value in (None,'0',0.0,Q(1,2),float('nan'),float('inf'),True):
            with self.subTest(value=value): self.reject(replace(self.r,rows=(Row('a',0,value,1),)),'integer')
    def test_objective(self): self.reject(replace(self.r,objective=0),'objective')
    def test_status(self):
        for status in ('UNKNOWN','INFEASIBLE','MODEL_INVALID','bogus'):
            with self.subTest(status=status): self.reject(replace(self.r,status=status),'status')
    def test_missing_solution(self): self.reject(replace(self.r,rows=()),'coverage')
    def test_missing_objective(self): self.reject(replace(self.r,objective=None),'integer')
    def test_horizon_equality(self): self.assertEqual(validate_plan(self.p,self.r),self.p.horizon)
    def test_running_boundary(self):
        obs=Observation(Q(2),self.obs.operations,(ExecutionEvent(Q(0),'arrival','A'),ExecutionEvent(Q(0),'start','a',0)),(),(('a',0,Q(0)),))
        p=prepare(obs,replace(self.f,through=Q(2))); r=solve(p)
        self.assertEqual((r.rows[0].start,r.rows[0].end),(0,3)); self.assertEqual(validate_plan(p,r),p.horizon)
        with self.assertRaisesRegex(ValueError,'horizon'): validate_plan(p,replace(r,rows=(replace(r.rows[0],end=4),),objective=4))
        with self.assertRaisesRegex(ValueError,'restart'): validate_plan(p,replace(r,rows=(replace(r.rows[0],start=1),)))
    def test_cross_observation(self):
        obs=replace(self.obs,operations=(replace(self.obs.operations[0],nominal=Q(2)),))
        p=prepare(obs,self.f); self.assertEqual(p.tasks,self.p.tasks)
        with self.assertRaisesRegex(ValueError,'observation_hash'): validate_plan(p,self.r)
    def test_cross_forecast(self):
        p=prepare(self.obs,replace(self.f,version=2)); self.assertEqual(p.tasks,self.p.tasks)
        with self.assertRaisesRegex(ValueError,'forecast_version'): validate_plan(p,self.r)
    def test_malformed_observation(self):
        for obs in (replace(self.obs,operations=None),replace(self.obs,running=(([],0,Q(0)),)),replace(self.obs,history=(None,))):
            with self.subTest(obs=obs),self.assertRaisesRegex(ValueError,'malformed public'): prepare(obs,self.f)
