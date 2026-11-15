"""Keep controller qualification and post-calibration results prominent in the report."""
import csv,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'reports/data';DATA.mkdir(exist_ok=True)
allend=[]
for root in sorted((ROOT/'artifacts/research').glob('endurance-*')):
    if (root/'results.json').exists():allend+=json.loads((root/'results.json').read_text())
calroot=sorted((ROOT/'artifacts/research').glob('calibrated-*'))[-1]
rows=json.loads((calroot/'results.json').read_text())
legacyroot=sorted((ROOT/'artifacts/research').glob('matched-*'))[-1]
legacy=json.loads((legacyroot/'results.json').read_text())
text='''# Baseline qualification and calibration

The early studies used the **legacy task protocol**: AMP yaw gain 1 and stop immediately on entering the 0.25 m arrival zone. Subsequent checks found two baseline confounds. Do not interpret their task-completion rates as intrinsic physical recoverability.

In two command-check seeds, commanding a pure 0.5 rad/s yaw for ten seconds changed heading by only about 0.26 rad (rather than the requested 5 rad). A 2.0 network yaw command produced about 6.86 rad without a fall. This motivated an empirical 4× AMP yaw-command mapping, capped at ±2; it is not a policy retraining result or a claim of accurate yaw tracking across all states. Twenty command-qualification trials retain full traces.

At some waypoint arrivals, stopping at the outer boundary allowed drift to repeatedly break continuous dwell. The optional **centered** arrival mode continues toward an inner radius of 0.10 m while still requiring continuous dwell inside the original 0.25 m acceptance radius. It keeps a 0.20 m/s minimum approach command before heading attenuation. It does not enlarge the acceptance zone, shorten dwell, reset state or skip subgoals.

## Nominal 12-goal endurance, no disturbances

Same 180 s horizon, 0.4 m/s limit, three route rounds and eight seeded initial conditions. These seeds were reused during calibration, so this is development qualification, not independent validation. The original walking controller has a different actuator profile; its result establishes a usable nominal route, not an isolated robustness advantage.

| Controller / protocol | Trials saved | Complete all 12 goals | Falls | Completion time range |
|---|---|---|---|---|
'''
for c,g,mode in [('reference',1,'legacy'),('amp',1,'legacy'),('amp',4,'legacy'),('amp',4,'centered')]:
    group=[r for r in allend if r['controller']==c and r['gain']==g and r.get('arrival_mode','legacy')==mode]
    successful=[r for r in group if r['result']=='success']
    duration=(f'{min(r["time"] for r in successful):.2f}–{max(r["time"] for r in successful):.2f} s') if successful else '—'
    text+=f'| {c}, yaw ×{g}, {mode} arrival | {len(group)}/8 | {len(successful)}/{len(group)} | {sum(r["falls"]>0 for r in group)}/{len(group)} | {duration} |\n'
text+='\n## Repeat of the trip design after yaw calibration\n\n'
trip=[r for r in rows if r['kind']=='trip'];probe=[r for r in rows if r['kind']=='probe']
text+=f'{len(trip)}/144 trip runs and {len(probe)}/288 paired pre-entry probe runs saved. These repeats use yaw ×4 and **legacy arrival**, to isolate yaw mapping from the separate arrival fix. Same seeds/geometry/controller weights/actuator profile/horizons as the original design. Calibration was selected using observed data; these repeats are exploratory, not fresh held-out confirmation. All original results remain saved.\n\n'
text+='| 13 cm trip contrast | Legacy yaw ×1 | Yaw ×4 |\n|---|---|---|\n'
for split,label in [('matrix','Seeds 0–7'),('holdout','Additional seeds 8–19')]:
    for width in (None,.9):
        old=[r for r in legacy if r['split']==split and r['height']==.13 and r['width']==width]
        new=[r for r in trip if r['split']==split and r['height']==.13 and r['width']==width]
        text+=f'| {label}, {"open" if width is None else "0.90 m"} | {sum(r["task_success"] for r in old)}/{len(old)} | {sum(r["task_success"] for r in new)}/{len(new)} |\n'
for label,rs in [('Legacy yaw ×1',legacy),('Yaw ×4',trip)]:
    stood=[r for r in rs if r['stood']]
    text+=f'\n{label}: {sum(not r["task_success"] for r in stood)}/{len(stood)} trials that regained standing after every detected loss still failed task completion. This changes with the task-control protocol; it is not a controller-independent property of the state.\n'
text+='\n## Does map replanning help once yaw response is improved?\n\n'
oldprobes=json.loads((sorted((ROOT/'artifacts/research').glob('probes-*'))[-1]/'results.json').read_text())
oldastar=json.loads((sorted((ROOT/'artifacts/research').glob('replanning-*'))[-1]/'results.json').read_text())
text+='| Width, x=0.8 m | Legacy direct | Legacy A* | Yaw ×4 direct | Yaw ×4 A* |\n|---|---|---|---|---|\n'
fig,ax=plt.subplots(figsize=(10,4));barwidth=.18
for wi,width in enumerate((None,.75,.9)):
    groups=[[r for r in oldprobes if r['x']==.8 and r['width']==width],
            [r for r in oldastar if r['width']==width],
            [r for r in probe if r['width']==width and r['navigation']=='direct'],
            [r for r in probe if r['width']==width and r['navigation']=='astar']]
    text+=f'| {"Open" if width is None else str(width)+" m"} | '+' | '.join(f'{sum(r["task_success"] for r in rs)}/{len(rs)}' for rs in groups)+' |\n'
    for gi,(group,label,color) in enumerate(zip(groups,('Legacy direct','Legacy A*','Yaw ×4 direct','Yaw ×4 A*'),('#a7b8aa','#78958a','#d6ad86','#ae784f'))):
        ax.bar(wi+(gi-1.5)*barwidth,np.mean([r['task_success'] for r in group]) if group else np.nan,barwidth,color=color,label=label if wi==0 else None)
ax.set(xticks=range(3),xticklabels=['Open','0.75 m','0.90 m'],ylim=(0,1.1),ylabel='Task-completion fraction',title='Task-controller qualification can change the recovery story')
ax.grid(axis='y',alpha=.2);ax.legend(fontsize=8,ncol=2);fig.tight_layout();fig.savefig(ROOT/'reports/figures/calibrated_navigation.png',dpi=180);plt.close(fig)
text+='\nWithin yaw ×4, paired A* minus direct completion (95% parent-seed bootstrap intervals):\n\n'
for width in (.75,.9):
    g=[r for r in probe if r['width']==width]
    deltas=[]
    for seed in range(8):
        direct=[r for r in g if r['seed']==seed and r['navigation']=='direct']
        planned=[r for r in g if r['seed']==seed and r['navigation']=='astar']
        if len(direct)==len(planned)==6:deltas.append((sum(r['task_success'] for r in planned)-sum(r['task_success'] for r in direct))/6)
    if deltas:
        rng=np.random.default_rng(731);ci=np.quantile(rng.choice(deltas,(10000,len(deltas)),replace=True).mean(axis=1),[.025,.975])
        text+=f'- {width:.2f} m: {np.mean(deltas):+.1%}, interval [{ci[0]:+.1%}, {ci[1]:+.1%}]; {len(deltas)} complete parent-seed clusters.\n'
if len(probe)==288:
    lookup={(r['seed'],r['width'],r['strength'],r['sign'],r['navigation']):r for r in probe};errors=[]
    for row in probe:
        if row['navigation']!='direct':continue
        other=lookup[(row['seed'],row['width'],row['strength'],row['sign'],'astar')]
        a=np.load(Path(row['path'])/'trace.npz');b=np.load(Path(other['path'])/'trace.npz')
        n=min(sum(a['time']<=.4+1e-9),sum(b['time']<=.4+1e-9));errors.append(float(np.max(np.abs(a['qpos'][:n]-b['qpos'][:n]))))
    text+=f'\nLargest direct/A* qpos difference through the 0.40 s intervention boundary: **{max(errors):.3g}** across {len(errors)} matched pairs. {sum(r["fell"] for r in probe)}/{len(probe)} calibrated pre-entry branches crossed balance-loss thresholds.\n'
text+='\n![Calibrated navigation comparison](figures/calibrated_navigation.png)\n\nEach complete cell has 48 branches, but only eight parent seeds, each tested under six force cases. Treat the counts as descriptive. A* uses a known map and can detour around the finite barriers. The yaw mapping is active from branch initialization; A* activates after the force pulse at 0.4 s. State-matched direct/A* comparisons within the new mapping should be interpreted separately from cross-mapping comparisons.\n'
for name,rs in [('calibrated_trip',trip),('calibrated_probes',probe),('nominal_endurance',allend)]:
    if rs:
        keys=sorted(set().union(*(r.keys() for r in rs)))
        keys=[k for k in keys if k not in ('fall_events',)]
        with (DATA/(name+'.csv')).open('w') as f:
            writer=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');writer.writeheader();writer.writerows(rs)
text+='\n[Calibrated trip CSV](data/calibrated_trip.csv) · [Calibrated probes CSV](data/calibrated_probes.csv) · [Nominal endurance CSV](data/nominal_endurance.csv).\n'
(ROOT/'reports/CALIBRATION_ANALYSIS.md').write_text(text)
report=ROOT/'reports/WAKE_UP_REPORT.md';current=report.read_text().split('\n\n## Baseline calibration interpretation')[0]
report.write_text(current+'\n\n## Baseline calibration interpretation\n\n'+text.replace('# Baseline qualification and calibration','',1))
print('Calibration report',len(trip),len(probe),len(allend),flush=True)
