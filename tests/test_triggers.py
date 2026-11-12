import unittest,copy
from fractions import Fraction as Q
from engine import *
from policies import *
from triggers import *
from prediction_metrics import evaluate
from test_closed_loop import chain
class TriggerTests(unittest.TestCase):
 def test_b3_authorized(self):
  p=B3(PolicyConfig(Q(2),.02,.2,0,'deterministic'));s=chain(5,2);l=execute(s,p);validate_run(s,l);replay(s,l)
  for r in p.records:
   if r['called']:self.assertTrue(set(r['triggers'])&{'INITIAL_PLAN','COMPLETION','ARRIVAL'})
  self.assertEqual(len({r['time'] for r in p.records if r['called']}),sum(r['called'] for r in p.records))
 def test_b4_cooldown(self):
  p=B4(PolicyConfig(Q(2),.02,.2,0,'deterministic'));s=chain(5,2);l=execute(s,p);validate_run(s,l);replay(s,l)
  for r in p.records:
   if r['called']:self.assertTrue(r['trigger_info']['cooldown_ready'])
 def test_wrong_attribution(self):
  p=B1(PolicyConfig(Q(4),.02,.2,0,'deterministic'));s=chain();l=execute(s,p);m=evaluate(l,p.records);self.assertEqual(m['start_time']['coverage'],2)
  records=copy.deepcopy(p.records);first=next(r for r in records if r['decision'].starts);oid=first['decision'].starts[0][0];first['authorizations'][oid]['duration']+=1
  with self.assertRaisesRegex(ValueError,'attribution'):evaluate(l,records)
 def test_fallback_coverage(self):
  p=B1(PolicyConfig(Q(2),0,0,0,'deterministic'));s=chain();l=execute(s,p);m=evaluate(l,p.records);self.assertEqual(m['decision_time']['coverage'],0);self.assertEqual(m['start_time']['coverage'],2)
 def test_new_arrival(self):
  s=Scenario(Instance((Machine(0),),(Operation('a','A',0,Q(1)),Operation('b','B',0,Q(1)))),(('A',Q(0)),('B',Q(2))),(('a',Q(1)),('b',Q(1))))
  for cls in (B3,B4):
   p=cls(PolicyConfig(Q(3),.02,.2,0,'deterministic'));l=execute(s,p);self.assertEqual(validate_run(s,l),4 if cls==B4 else 3)
