"""Public-history-only fixed and machine EMA duration forecasts."""
from fractions import Fraction as Q
from engine import Forecast

def positive_ceiling(x):
    if not isinstance(x,Q) or x<=0: raise ValueError('positive rational forecast')
    return max(1,-(-x.numerator//x.denominator))

class Nominal:
    def __init__(self): self.version=1; self.cutoff=Q(0); self.updates=[]; self.last=None
    def snapshot(self,obs):
        done={k for k,_ in obs.completed_durations}
        return Forecast(self.version,self.cutoff,tuple((o.id,Q(positive_ceiling(o.nominal))) for o in obs.operations if o.id not in done))

class MachineEMA(Nominal):
    def __init__(self,alpha=Q(1,4)):
        super().__init__()
        if not isinstance(alpha,Q) or not 0<alpha<=1: raise ValueError('alpha')
        self.alpha=alpha; self.multipliers={}; self.processed=set()
    def snapshot(self,obs):
        ops={o.id:o for o in obs.operations}; durations=dict(obs.completed_durations)
        for event in sorted((e for e in obs.history if e.kind=='complete'),key=lambda e:(e.time,e.operation)):
            if event.operation in self.processed: continue
            if event.time>obs.time or event.operation not in durations: raise ValueError('unpublished completion')
            o=ops[event.operation]; ratio=durations[o.id]/o.nominal
            if ratio<=0: raise ValueError('observed duration')
            old=self.multipliers.get(o.machine,Q(1)); new=self.alpha*ratio+(1-self.alpha)*old
            self.multipliers[o.machine]=new; self.processed.add(o.id); self.version+=1; self.cutoff=event.time; self.last=(event.time,o.id)
            self.updates.append(dict(operation=o.id,machine=o.machine,time=event.time,ratio=ratio,old=old,new=new,version=self.version))
        done=set(durations)
        return Forecast(self.version,self.cutoff,tuple((o.id,Q(positive_ceiling(o.nominal*self.multipliers.get(o.machine,Q(1))))) for o in obs.operations if o.id not in done))
