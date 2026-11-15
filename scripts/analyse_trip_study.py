"""Mechanism checks and evidence-bounded interpretation of the completed trip matrix."""
import json,math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
root=sorted((ROOT/'artifacts/research').glob('matched-*'))[-1]
rows=json.loads((root/'results.json').read_text())
figures=ROOT/'reports/figures';figures.mkdir(exist_ok=True)
fallrows=[r for r in rows if r['stood']]
false_reassurance=sum(not r['task_success'] for r in fallrows)
parity=[]
for seed in range(8):
    a=next(r for r in rows if r['split']=='matrix' and r['height']==.13 and r['width'] is None and r['seed']==seed)
    b=next(r for r in rows if r['split']=='matrix' and r['height']==.13 and r['width']==.9 and r['seed']==seed)
    if a['first_box_contact'] is None or b['first_box_contact'] is None:continue
    aa=np.load(Path(a['path'])/'trace.npz');bb=np.load(Path(b['path'])/'trace.npz')
    cutoff=min(a['first_box_contact'],b['first_box_contact'])-.02
    n=min(sum(aa['time']<cutoff),sum(bb['time']<cutoff))
    if not n:continue
    delta=np.abs(aa['qpos'][:n]-bb['qpos'][:n])
    contacts=json.loads((Path(b['path'])/'analysis.json').read_text())['hazard_contacts']
    barrier=next((c['time'] for c in contacts if c['label']=='Recovery-space barrier'),None)
    parity.append(dict(seed=seed,cutoff=float(cutoff),max_abs_qpos_difference=float(delta.max()),
                       root_position_difference=float(delta[:,:3].max()),first_barrier_contact=barrier,
                       open_box_contact=a['first_box_contact'],narrow_box_contact=b['first_box_contact']))
(root/'precontact-parity.json').write_text(json.dumps(parity,indent=2)+'\n')

widths=[None,.75,.9,1.2,1.5]
fig,axes=plt.subplots(1,2,figsize=(12,4.3))
for panel,split in zip(axes,['matrix','holdout']):
    selected=widths if split=='matrix' else [None,.9]
    standing=[];resume=[];labels=[]
    for w in selected:
        g=[r for r in rows if r['height']==.13 and r['width']==w and r['split']==split and r['fell']]
        labels.append(('Open' if w is None else f'{w:.2f}m')+f'\n{len(g)} loss trials')
        standing.append(sum(r['stood'] for r in g)/len(g) if g else np.nan)
        resume.append(sum(r['task_resumed'] for r in g)/len(g) if g else np.nan)
    x=np.arange(len(labels));panel.bar(x-.17,standing,.34,label='All balance-loss episodes regained standing',color='#6b9e84')
    panel.bar(x+.17,resume,.34,label='Original task subsequently advanced',color='#d49664')
    panel.set(xticks=x,xticklabels=labels,ylim=(0,1.1),ylabel='Fraction of balance-loss trials',
              title='Exploratory matrix seeds 0–7' if split=='matrix' else 'Additional seeds 8–19')
    panel.grid(axis='y',alpha=.2)
axes[0].legend(fontsize=7,loc='lower left');fig.suptitle('Standing up and resuming the task are different outcomes — 13 cm box')
fig.tight_layout();fig.savefig(figures/'standing_vs_resumption.png',dpi=180);fig.savefig(figures/'standing_vs_resumption.svg');plt.close(fig)

fig,axes=plt.subplots(2,2,figsize=(11,8))
selected=[]
for seed,split in [(0,'matrix'),(17,'holdout')]:
    for width in (None,.9):
        selected.append(next(r for r in rows if r['seed']==seed and r['split']==split and r['width']==width and r['height']==.13))
for ax,row in zip(axes.flat,selected):
    t=np.load(Path(row['path'])/'trace.npz');q=t['qpos'];times=t['time']
    color=ax.scatter(q[:,0],q[:,1],c=times,s=3,cmap='viridis',vmin=0,vmax=45)
    ax.add_patch(plt.Rectangle((1.88,-.28),.44,.56,facecolor='#b48252',alpha=.7))
    if row['width']:
        w=row['width'];ax.add_patch(plt.Rectangle((1.3,w/2),2,.3,color='#88959d',alpha=.6));ax.add_patch(plt.Rectangle((1.3,-w/2-.3),2,.3,color='#88959d',alpha=.6))
    summary=json.loads((Path(row['path'])/'summary.json').read_text())
    for f in summary['fall_events']:
        for key,marker in [('start','x'),('recovered_at','s'),('task_resumed_at','*')]:
            if f.get(key) is not None:
                i=min(np.searchsorted(times,f[key]),len(times)-1);ax.plot(q[i,0],q[i,1],marker,markersize=8,color='#bd453f')
    ax.set(xlim=(-.5,6),ylim=(-2,2),xlabel='x (m)',ylabel='y (m)',aspect='equal',
           title=f'Seed {row["seed"]}, {"open" if row["width"] is None else "0.90 m"}: {row["result"]}')
fig.colorbar(color,ax=axes.ravel().tolist(),label='Simulated time (s)',shrink=.6)
fig.suptitle('Illustrative paired trajectories: pilot difference and a held-out counterexample\nX = balance loss; square = standing recovered; star = task advanced',fontsize=11)
fig.subplots_adjust(top=.86,hspace=.4,right=.85)
fig.savefig(figures/'paired_trajectories.png',dpi=180);fig.savefig(figures/'paired_trajectories.svg');plt.close(fig)

text=f'''# Interpretation of the completed 144-trial trip study

## Three results worth keeping

1. **Nominal feasibility was established:** all 40 box-free corridor executions succeeded, using eight initial-condition seeds reused across five widths. These are not 40 independent seeds.
2. **Standing is an incomplete success metric:** {false_reassurance}/{len(fallrows)} trials in which all detected balance-loss episodes regained standing still failed to complete the task segment. This is descriptive across related conditions, not a population-wide failure probability.
3. **The simple clearance hypothesis did not hold reliably:** the pilot/matrix advantage at 0.90 m did not repeat in the additional seeds. Matrix seeds: open 6/8 versus corridor 3/8, exploratory exact paired p=0.25. Additional seeds: open 6/12 versus corridor 7/12, paired p=1.0. This is not evidence of equivalence, but it is insufficient evidence for a reliable wider-is-better claim.

![Standing versus resumption](figures/standing_vs_resumption.png)

## Why it matters

The research objective should explicitly require task resumption, not just standing after a fall. However, preserving empty space or counting nominal recovery behaviors is too crude: contacts, landing orientation, obstacle passage and controller quirks can change the outcome in either direction. A support surface may help recovery while a barrier may trap the task controller.

This strengthens the motivation for measuring **task-conditioned recovery capability**, but it does not establish a new algorithm or demonstrate preservation learning. The present controller has one unified recovery policy, not an independently selectable portfolio of recovery strategies.

## Mechanism and initial-state check

'''
text+='| Seed | Max pre-box-contact qpos difference (mixed m/rad) | First barrier contact |\n|---|---|---|\n'
for r in parity:text+=f'| {r["seed"]} | {r["max_abs_qpos_difference"]:.3g} | {r["first_barrier_contact"]} s |\n'
text+='\nThe check compares open and 0.90 m trajectories before the earliest measured trip-box contact. Differences can reveal earlier barrier interactions or numerical/contact sensitivity; they must not be ignored when attributing the outcome to post-fall space alone. The next counterfactual study restores an identical physics/controller checkpoint to remove approach-trajectory differences.\n\n'
text+='![Illustrative trajectories](figures/paired_trajectories.png)\n\nThe selected seeds are illustrations, not representative success estimates. Seed 17 is deliberately shown as a counterexample to the pilot story. Aggregate counts above take precedence over videos.\n'
(ROOT/'reports/TRIP_STUDY_ANALYSIS.md').write_text(text)
# Place the interpretation before the independently checkpointed probe section.
path=ROOT/'reports/WAKE_UP_REPORT.md';current=path.read_text()
marker='\n\n## Completed trip-study interpretation'
if marker in current:
    left,rest=current.split(marker,1)
    suffix='\n\n## Further stage: state-matched counterfactual probes'+rest.split('\n\n## Further stage: state-matched counterfactual probes',1)[1] if '\n\n## Further stage: state-matched counterfactual probes' in rest else ''
else:
    parts=current.split('\n\n## Further stage: state-matched counterfactual probes',1);left=parts[0]
    suffix='\n\n## Further stage: state-matched counterfactual probes'+parts[1] if len(parts)>1 else ''
updated=left+marker+'\n\n'+text.replace('# Interpretation of the completed 144-trial trip study','',1)+suffix
path.write_text(updated)
print('Standing but task failed',false_reassurance,'/',len(fallrows),flush=True)
print('Precontact parity',parity,flush=True)
