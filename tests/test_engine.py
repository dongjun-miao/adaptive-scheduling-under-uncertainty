import unittest,random
from dataclasses import replace,FrozenInstanceError
from engine import *

def case():
    i=Instance((Machine(0),Machine(1)),(Operation('a','A',0,Q(2)),Operation('b','A',1,Q(1),('a',)),Operation('c','B',1,Q(2)),Operation('d','B',0,Q(1),('c',)),Operation('e','C',0,Q(1))))
    return Scenario(i,(('A',Q(0)),('B',Q(0)),('C',Q(2))),(('a',Q(2)),('b',Q(1)),('c',Q(2)),('d',Q(1)),('e',Q(1))))
class EngineTests(unittest.TestCase):
    def test_expected_timeline(self):
        s=case(); l=execute(s)
        expected=[(0,'arrival','A'),(0,'arrival','B'),(0,'start','a'),(0,'start','c'),(2,'complete','a'),(2,'complete','c'),(2,'arrival','C'),(2,'start','b'),(2,'start','d'),(3,'complete','b'),(3,'complete','d'),(3,'start','e'),(4,'complete','e')]
        self.assertEqual([(e.time,e.kind,e.operation) for e in l.events],expected)
        self.assertEqual(validate_ledger(s,l),4)
    def test_replay(self):
        s=case(); l=execute(s); self.assertEqual(replay(s,l),l)
    def test_stochastic_determinism(self):
        a=stochastic(case().instance,42); b=stochastic(case().instance,42)
        self.assertEqual(a,b); self.assertEqual(execute(a),execute(b)); validate_ledger(a,execute(a))
        self.assertEqual(len(set(v for _,v in a.seeds)),4)
    def test_fractional_exactness(self):
        s=replace(case(),durations=tuple((k,Q(1,3)) for k,_ in case().durations))
        l=execute(s); self.assertEqual(next(e.time for e in l.events if e.kind=='complete'),Q(1,3)); validate_ledger(s,l)
    def test_future_noninterference(self):
        a=case(); b=replace(a,arrivals=(('A',Q(0)),('B',Q(0)),('C',Q(7))),durations=(('a',Q(2)),('b',Q(9)),('c',Q(2)),('d',Q(8)),('e',Q(5))))
        seen=[]
        for s in (a,b):
            records=[]
            def policy(obs,rng):
                d=fifo(obs,rng)
                if obs.time==0: records.append((obs,d,rng.getstate()))
                return d
            execute(s,policy,81); seen.append(records)
        self.assertEqual(seen[0],seen[1])
    def test_visibility_and_immutability(self):
        s=case(); seen=[]
        def policy(obs,rng): seen.append(obs); return fifo(obs,rng)
        execute(s,policy)
        self.assertEqual(seen[0].completed_durations,()); self.assertNotIn('C',{o.job for o in seen[0].operations})
        self.assertEqual(dict(seen[1].completed_durations),{'a':Q(2),'c':Q(2)})
        self.assertFalse(hasattr(seen[0],'scenario')); self.assertFalse(hasattr(seen[0],'durations'))
        with self.assertRaises(FrozenInstanceError): seen[0].operations[0].nominal=Q(999)
        self.assertEqual(dict(s.durations)['a'],2)
    def reject(self,starts,reason):
        with self.assertRaisesRegex(ValueError,reason): execute(case(),lambda o,r:Decision(starts))
    def test_precedence(self): self.reject((('b',1),),'precedence')
    def test_precedence_checked_before_collision(self): self.reject((('b',1),('c',1)),'precedence') # separate eligible collision below
    def test_eligible_collision(self):
        s=case(); i=replace(s.instance,operations=s.instance.operations+(Operation('f','A',0,Q(1)),)); s=replace(s,instance=i,durations=s.durations+(('f',Q(1)),))
        with self.assertRaisesRegex(ValueError,'collision'): execute(s,lambda o,r:Decision((('a',0),('f',0))))
    def test_duplicate(self): self.reject((('a',0),('a',0)),'duplicate')
    def test_migration(self): self.reject((('a',1),),'migration')
    def test_future_arrival(self): self.reject((('e',0),),'unreleased')
    def test_restart_running(self):
        s=replace(case(),arrivals=(('A',Q(0)),('B',Q(0)),('C',Q(1))))
        def policy(o,r): return fifo(o,r) if o.time==0 else Decision((('a',0),))
        with self.assertRaisesRegex(ValueError,'restart'): execute(s,policy)
    def test_corrupt_completion(self):
        s=case(); l=execute(s); events=list(l.events); events[4]=replace(events[4],time=Q(1))
        with self.assertRaisesRegex(ValueError,'completion'): validate_ledger(s,replace(l,events=tuple(events)))
    def test_missing_completion(self):
        s=case(); l=execute(s)
        with self.assertRaisesRegex(ValueError,'incomplete'): validate_ledger(s,replace(l,events=l.events[:-1]))
    def test_cycle(self):
        s=case(); i=replace(s.instance,operations=(replace(s.instance.operations[0],predecessors=('b',)),)+s.instance.operations[1:])
        with self.assertRaisesRegex(ValueError,'cycle'): execute(replace(s,instance=i))
    def test_zero_duration(self):
        with self.assertRaises(ValueError): execute(replace(case(),durations=(('a',Q(0)),)+case().durations[1:]))
    def test_deadlock(self):
        with self.assertRaisesRegex(ValueError,'deadlock'): execute(case(),lambda o,r:Decision(()))

