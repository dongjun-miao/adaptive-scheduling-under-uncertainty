"""One extraction path for every public number and figure; raw final runs only."""
import json,hashlib,sys
from pathlib import Path
from fractions import Fraction
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
ROOT=Path(__file__).resolve().parents[1]
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
colors={'B1':'#555555','B2':'#0072B2','B3':'#D55E00','B4':'#009E73'}
def build():
 rows=[];sources=[]
 for p in sorted((ROOT/'phase2c-final-pilot').glob('*-B*.json')):
  r=json.loads(p.read_text());sources.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
  if r['status']!='OK':raise ValueError('Incomplete run must be reported: '+p.name)
  callbacks=r['callbacks'];fallback=sum(len(c['decision']['starts']) for c in callbacks if c['fallback']);starts=sum(len(c['decision']['starts']) for c in callbacks)
  episodes=sum(c['fallback'] and (i==0 or not callbacks[i-1]['fallback']) for i,c in enumerate(callbacks))
  rows.append(dict(instance=r['instance'],regime=r['regime'],seed=r['seed'],policy=r['policy'],makespan=r['makespan'],fallback_starts=fallback,starts=starts,fallback_episodes=episodes,fallback_callbacks=sum(c['fallback'] for c in callbacks),budget_exhaustion_callbacks=sum(c['failure']=='TOTAL_BUDGET_EXHAUSTED' for c in callbacks),calls=sum(c['called'] for c in callbacks),wall=sum(c['solver_seconds'] for c in callbacks),effort=r['deterministic_effort'],start_metric=r['metrics']['start_time'],decision_metric=r['metrics']['decision_time']))
 totals={k:{field:sum(r[field] for r in rows if r['policy']==k) for field in ('starts','fallback_starts','fallback_callbacks','fallback_episodes','budget_exhaustion_callbacks','calls','wall','effort')} for k in colors}
 data=dict(description='Final Phase2C only; two instances, four regimes, two seeds, one optimizer repetition. Deterministic seed duplicates are not independent.',rows=rows,totals=totals,sources=sources)
 (ROOT/'figures/figure_data_manifest.json').write_text(json.dumps(data,indent=2))
 def save(fig,name):
  fig.savefig(ROOT/f'figures/{name}.png',dpi=220,bbox_inches='tight');fig.savefig(ROOT/f'figures/{name}.pdf',bbox_inches='tight',metadata={'CreationDate':None});plt.close(fig)
 fig,ax=plt.subplots(figsize=(8.2,3.6));ax.set(xlim=(0,10),ylim=(0,5));ax.axis('off')
 def box(x,y,w,text,color):
  ax.add_patch(FancyBboxPatch((x,y),w,.65,boxstyle='round,pad=.08',facecolor=color,edgecolor='#455A64'));ax.text(x+w/2,y+.325,text,ha='center',va='center',fontsize=9)
 box(.2,3.9,2,'Private scenario\nrealizations + arrivals','#FBE9E7');box(3.1,3.9,2.3,'Execution simulator\nphysical authority','#FBE9E7');box(6.4,3.9,3.1,'Public observation\ncompleted history + busy state','#E3F2FD')
 box(6.4,2.25,3.1,'Fixed / machine EMA\npublic forecasts only','#E3F2FD');box(3.1,2.25,2.3,'Residual CP-SAT\nbudgeted advisory plan','#E3F2FD');box(.2,2.25,2,'Validate, commit\nand safe dispatch','#E3F2FD');box(3.1,.45,2.3,'Realized evaluation\nindependent validation','#EEEEEE')
 for a,b in [((2.3,4.22),(3,4.22)),((5.5,4.22),(6.3,4.22)),((8,3.85),(8,2.98)),((6.3,2.57),(5.5,2.57)),((3,2.57),(2.3,2.57)),((1.2,2.98),(3.65,3.85)),((4.25,2.1),(4.25,1.2))]:ax.annotate('',xy=b,xytext=a,arrowprops=dict(arrowstyle='->',color='#37474F'))
 ax.text(5.85,3.35,'Public API boundary',ha='center',fontsize=9,color='#0072B2');ax.text(5,.05,'Illustrative architecture; no hidden future durations enter the planner.',ha='center',fontsize=9)
 save(fig,'01_system_architecture')
 regimes=['deterministic','stationary','slowdown','stochastic_slowdown'];labels=['Control 11','Control 29*','Stationary 11','Stationary 29','Slowdown 11','Slowdown 29*','Stoch.+slow 11','Stoch.+slow 29']
 selected={(r['regime'],r['seed'],r['policy']):r for r in rows if r['instance']=='abz5'}
 fig,ax=plt.subplots(figsize=(8.2,4.0))
 for index,k in enumerate(colors):
  vals=[selected[(reg,seed,k)]['makespan']-selected[(reg,seed,'B2')]['makespan'] for reg in regimes for seed in (11,29)]
  ax.scatter(vals,[i+(index-1.5)*.13 for i in range(8)],label=k,color=colors[k],marker=['s','o','^','D'][index],s=36)
 ax.axvline(0,color='#888',lw=.8);ax.set_yticks(range(8),labels);ax.invert_yaxis();ax.set_xlabel('Realized makespan minus B2 (time units; lower is better)');ax.legend(ncol=4,loc='lower right');ax.grid(axis='x',alpha=.2);fig.subplots_adjust(bottom=.25);fig.text(.12,.01,'abz5 only; one optimizer run per cell. *Same deterministic physical realization as seed 11.',fontsize=8)
 save(fig,'02_paired_makespan')
 fig,axes=plt.subplots(1,2,figsize=(8.2,3.4))
 for k in colors:
  rs=[r for r in rows if r['instance']=='abz5' and r['policy']==k]
  axes[0].scatter([r['calls'] for r in rs],[r['makespan'] for r in rs],label=k,color=colors[k],marker={'B1':'s','B2':'o','B3':'^','B4':'D'}[k],s=30,alpha=.8)
 axes[0].set(xlabel='Actual CP-SAT calls per run',ylabel='Realized makespan (time units)');axes[0].legend(ncol=2,fontsize=8)
 frac=[100*totals[k]['fallback_starts']/totals[k]['starts'] for k in colors];axes[1].bar(list(colors),frac,color=list(colors.values()));axes[1].set(ylim=(0,100),ylabel='Starts under fallback (%)',xlabel='All final pilot runs (840 starts / policy)')
 for i,v in enumerate(frac):axes[1].text(i,v+2,f'{v:.1f}%',ha='center',fontsize=9)
 fig.tight_layout();save(fig,'03_budget_tradeoff')
 print(json.dumps(totals,indent=2))
if __name__=='__main__':build()

