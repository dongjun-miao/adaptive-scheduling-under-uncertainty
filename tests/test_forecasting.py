import unittest
from dataclasses import replace
from forecasting import *
from engine import *
from policies import *
from test_closed_loop import chain
class ForecastTests(unittest.TestCase):
 def test_rounding(self):
  self.assertEqual(positive_ceiling(Q(5,4)),2);self.assertEqual(positive_ceiling(Q(1,9)),1);self.assertEqual(positive_ceiling(Q(2)),2)
 def test_public_updates_only(self):
  model=MachineEMA();ops=(Operation('a','A',0,Q(2)),Operation('b','A',0,Q(2),('a',)))
  o=Observation(Q(1),ops,(ExecutionEvent(Q(0),'start','a',0),),(),(('a',0,Q(0)),))
  self.assertEqual(model.snapshot(o).version,1);self.assertEqual(model.updates,[])
  o=replace(o,time=Q(4),history=o.history+(ExecutionEvent(Q(4),'complete','a',0),),completed_durations=(('a',Q(4)),),running=())
  f=model.snapshot(o);self.assertEqual(model.multipliers[0],Q(5,4));self.assertEqual(f.estimates,(('b',Q(3)),));self.assertEqual(f.version,2)
  self.assertEqual(model.snapshot(o),f);self.assertEqual(len(model.updates),1)
 def test_simultaneous_order(self):
  ops=(Operation('a','A',0,Q(1)),Operation('b','B',0,Q(1)))
  o=Observation(Q(4),ops,(ExecutionEvent(Q(4),'complete','b',0),ExecutionEvent(Q(4),'complete','a',0)),(('a',Q(2)),('b',Q(4))),())
  m=MachineEMA();m.snapshot(o);self.assertEqual([r['operation'] for r in m.updates],['a','b']);self.assertEqual(m.multipliers[0],Q(31,16))
 def test_shared_triggers_and_replay(self):
  for model in (Nominal(),MachineEMA()):
   p=B1(PolicyConfig(Q(4),.01,.1,0,'deterministic'),forecaster=model);l=execute(chain(),p);validate_run(chain(),l);replay(chain(),l)
   self.assertTrue(all(r['time']%4==0 for r in p.records if r['called']))
 def test_future_completion_rejected(self):
  o=Observation(Q(0),(Operation('a','A',0,Q(1)),),(ExecutionEvent(Q(2),'complete','a',0),),(('a',Q(2)),),())
  with self.assertRaises(ValueError):MachineEMA().snapshot(o)

class TreatmentTests(unittest.TestCase):
 def test_seed_specific_combination(self):
  from run_phase2b import generate
  from run_phase2a import tiny
  a=generate(tiny(),'stochastic_slowdown',11,3);b=generate(tiny(),'stochastic_slowdown',29,3)
  self.assertNotEqual(a.durations,b.durations);self.assertEqual(a.slowdowns,b.slowdowns)
 def test_no_future_leakage(self):
  from test_engine import case
  a=replace(case(),durations=(('a',Q(2)),('b',Q(1)),('c',Q(6)),('d',Q(1)),('e',Q(1))),arrivals=(('A',Q(0)),('B',Q(0)),('C',Q(9))))
  b=replace(a,durations=(('a',Q(2)),('b',Q(7)),('c',Q(8)),('d',Q(3)),('e',Q(2))),arrivals=(('A',Q(0)),('B',Q(0)),('C',Q(10))))
  records=[]
  for s in (a,b):
   p=B1(PolicyConfig(Q(2),.02,.2,0,'deterministic'),forecaster=MachineEMA());l=execute(s,p);validate_run(s,l)
   records.append(next(r for r in p.records if r['time']==2))
  for key in ('forecast','problem','decision'):self.assertEqual(records[0][key],records[1][key])
 def test_model_updates_do_not_solve(self):
  p=B1(PolicyConfig(Q(10),.02,.2,0,'deterministic'),forecaster=MachineEMA());execute(chain(1,2),p)
  self.assertEqual([r['time'] for r in p.records if r['called']],[0]);self.assertGreater(p.forecaster.version,1)
 def test_output_guard(self):
  import tempfile
  from run_phase2b import main
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(FileExistsError):main(d)
