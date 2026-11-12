import unittest,copy
from validator import validate
class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.spec={0:(0,{0:2},[]),1:(0,{1:3},[0]),2:(1,{0:2},[])}
        self.rows=[dict(id=0,job=0,machine=0,start=0,duration=2),dict(id=1,job=0,machine=1,start=2,duration=3),dict(id=2,job=1,machine=0,start=2,duration=2)]
    def test_positive(self): self.assertEqual(validate(self.spec,self.rows,5),5)
    def reject(self,reason):
        with self.assertRaisesRegex(ValueError,reason): validate(self.spec,self.rows,5)
    def test_precedence(self): self.rows[1]['start']=1; self.reject('precedence')
    def test_collision(self): self.rows[2]['start']=1; self.reject('collision')
    def test_duration(self): self.rows[0]['duration']=1; self.reject('duration')
    def test_missing(self): self.rows.pop(); self.reject('coverage')
    def test_duplicate(self): self.rows.append(copy.deepcopy(self.rows[0])); self.reject('coverage')
    def test_machine(self): self.rows[0]['machine']=8; self.reject('eligibility')
    def test_identity(self): self.rows[0]['job']=8; self.reject('identity')
    def test_negative(self): self.rows[0]['start']=-1; self.reject('time')
    def test_objective(self):
        with self.assertRaisesRegex(ValueError,'makespan'): validate(self.spec,self.rows,6)

class StrictValidationTests(unittest.TestCase):
    def test_isolated_precedence(self):
        spec={0:(0,{0:2},[]),1:(0,{1:2},[0]),2:(1,{2:10},[])}
        rows=[dict(id=0,job=0,machine=0,start=0,duration=2),dict(id=1,job=0,machine=1,start=1,duration=2),dict(id=2,job=1,machine=2,start=0,duration=10)]
        with self.assertRaisesRegex(ValueError,'^precedence$'): validate(spec,rows,10)
    def test_isolated_collision(self):
        spec={0:(0,{0:2},[]),1:(1,{0:2},[])}
        rows=[dict(id=0,job=0,machine=0,start=0,duration=2),dict(id=1,job=1,machine=0,start=1,duration=2)]
        with self.assertRaisesRegex(ValueError,'^collision$'): validate(spec,rows,3)
    def test_unknown_id(self):
        with self.assertRaisesRegex(ValueError,'coverage'): validate({},[dict(id=7,job=0,machine=0,start=0,duration=1)],1)
    def test_nonfinite(self):
        with self.assertRaisesRegex(ValueError,'time'): validate({0:(0,{0:1},[])},[dict(id=0,job=0,machine=0,start=float('nan'),duration=1)],1)
