"""Small baseline check, no benchmark download or experiment output directory."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import *
from policies import B1,PolicyConfig
from run_phase2a import tiny,scenario
s=scenario(tiny(),'deterministic',11,3);p=B1(PolicyConfig(Q(3),.02,.20,0,'deterministic'));l=execute(s,p);assert validate_run(s,l)==4;replay(s,l);print('tiny baseline valid; makespan=4')
