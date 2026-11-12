import unittest,tempfile
from pathlib import Path
from engine import *
from policies import *
from residual import *
from test_closed_loop import chain
class ReproTests(unittest.TestCase):
 def test_fixed_cutoff(self):
  p=B1(PolicyConfig(Q(2))); l=execute(chain(),p); replay(chain(),l)
  for r in p.records:
   if r['called']: self.assertEqual(r['forecast'].through,0); self.assertEqual(r['observation_cutoff'],r['time']); self.assertIsNotNone(r['result'])
 def test_deterministic_api(self):
  p=B1(PolicyConfig(Q(2),.001,.01,0,'deterministic')); l=execute(chain(),p);validate_run(chain(),l)
  self.assertTrue(all(r['result'].deterministic_seconds>=0 for r in p.records if r['called']))
 def test_exclusive_output(self):
  from run_phase2a import main
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(FileExistsError): main(d)
 def test_mode_rejected(self):
  with self.assertRaises(ValueError): PolicyConfig(mode='bad')
