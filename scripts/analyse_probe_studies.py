"""Summarize state-matched experiments, accounting for reused parent seeds."""
import csv,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
FIG=ROOT/'reports/figures';FIG.mkdir(exist_ok=True)
DATA=ROOT/'reports/data';DATA.mkdir(exist_ok=True)

def load(prefix):
    roots=sorted((ROOT/'artifacts/research').glob(prefix+'-*'))
    if not roots:return None,[]
    root=roots[-1];return root,json.loads((root/'results.json').read_text())

def export(name,rows):
    if not rows:return
    fields=['seed','x','width','strength','sign','navigation','task_success','fell','stood','task_resumed','initial_barrier_overlap','result','time','run_id','path']
    with (DATA/(name+'.csv')).open('w') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)

def key(r):return tuple(r[k] for k in ('seed','x','width','strength','sign'))

def cluster_interval(values):
    values=np.array(values,dtype=float);rng=np.random.default_rng(731)
    samples=rng.choice(values,(10000,len(values)),replace=True).mean(axis=1)
    return np.quantile(samples,[.025,.975])

def main():
    root,rows=load('probes');aroot,astar=load('replanning');iroot,impact=load('impact')
    export('push_probes',rows);export('map_replanning',astar);export('higher_impulse_probes',impact)
    valid=[r for r in rows if not r['initial_barrier_overlap']]
    text=f'''# State-matched follow-up analysis

Initial push grid: {len(rows)}/768 branches saved; {sum(r['initial_barrier_overlap'] for r in rows)} initial penetrations flagged. The 80/140/200 N pulses last 0.18 s (14.4/25.2/36 Ns). **{sum(r['fell'] for r in valid)} balance losses occurred.** Consequently, failures here do not demonstrate failure to regain upright balance. Eight parent seeds are reused across all six force cases and corridor widths.

The restore qualification reproduced ten unperturbed policy steps with exactly zero qpos difference. This checks the implemented checkpoint mechanism at one checkpoint, not a proof for arbitrary dynamics or every state. Different checkpoint positions also have different remaining task distances and gait phases, so their raw success fractions do not isolate a causal effect of progress. Within-checkpoint width comparisons are the cleaner contrast.

## A conventional navigation control

The A* baseline has a perfect static map, 0.10 m grid, 0.23 m planar inflation and replans every 0.4 simulated seconds. It activates at 0.4 s, after the 0.20–0.38 s pulse. The low-level AMP controller, target, speed limit, parent state, pulse and 30 s branch horizon remain fixed. It may go around the end of the barrier. It has no learned reserve model, contact planner or guarantees.

'''
    pairs=[];lookup={key(r):r for r in valid};parity=[]
    for a in astar:
        d=lookup.get(key(a))
        if d is None:continue
        pairs.append((d,a))
        aa=np.load(Path(a['path'])/'trace.npz');dd=np.load(Path(d['path'])/'trace.npz')
        n=min(sum(aa['time']<=.4+1e-9),sum(dd['time']<=.4+1e-9))
        parity.append(float(np.max(np.abs(aa['qpos'][:n]-dd['qpos'][:n]))))
    if pairs:
        text+=f'{len(pairs)}/144 planned matched planner comparisons saved. Largest pre-intervention qpos difference through t=0.40 s: **{max(parity):.3g}** (mixed metres/radians).\n\n'
        text+='| Width | Direct completion | A* completion | Seed-mean difference | Seed bootstrap 95% interval |\n|---|---|---|---|---|\n'
        fig,ax=plt.subplots(figsize=(8,4));means=[];intervals=[]
        for w in (None,.75,.9):
            g=[p for p in pairs if p[0]['width']==w];seeds=sorted({d['seed'] for d,a in g})
            delta=[np.mean([int(a['task_success'])-int(d['task_success']) for d,a in g if d['seed']==s]) for s in seeds]
            ci=cluster_interval(delta);m=np.mean(delta);means.append(m);intervals.append(ci)
            text+=f'| {"Open" if w is None else str(w)+" m"} | {sum(d["task_success"] for d,a in g)}/{len(g)} | {sum(a["task_success"] for d,a in g)}/{len(g)} | {m:+.1%} | [{ci[0]:+.1%}, {ci[1]:+.1%}] |\n'
        intervals=np.array(intervals);means=np.array(means)
        ax.bar(range(3),means,color=['#9eada3','#658f81','#d2a16c']);ax.errorbar(range(3),means,yerr=[means-intervals[:,0],intervals[:,1]-means],fmt='none',color='#20332a',capsize=5)
        ax.axhline(0,color='grey',lw=1);ax.set(xticks=range(3),xticklabels=['Open','0.75 m','0.90 m'],ylabel='A* minus direct task-completion fraction',title='Conventional replanning control at the pre-entry checkpoint')
        ax.grid(axis='y',alpha=.2);fig.tight_layout();fig.savefig(FIG/'replanning_control.png',dpi=180);plt.close(fig)
        text+='\n![Replanning control](figures/replanning_control.png)\n\nIntervals resample the eight parent seeds, retaining their six paired force cases together (10,000 deterministic bootstrap draws). They describe sensitivity to the small seeded initial jitter in this simulator; they are not calibrated deployment bounds. With only eight parents and an exploratory control, do not treat branch counts as independent replications.\n\n'
        totals=(sum(d['task_success'] for d,a in pairs),sum(a['task_success'] for d,a in pairs))
        text+=f'Across the matched rows, completion changes from {totals[0]}/{len(pairs)} to {totals[1]}/{len(pairs)}. '
        if totals[1]>totals[0]:text+='This supports a contribution from route-following limitations. Any residual failures remain controller-dependent; they do not establish physical impossibility.\n'
        else:text+='This particular basic planner did not improve aggregate completion. That does not eliminate navigation as a mechanism: a planar, forward-only steering controller can still stall near contacts. We cannot classify the remaining failures as physical unrecoverability.\n'
    if impact:
        text+=f'''\n## Stronger-impulse physical recovery probes

{len(impact)}/288 planned branches saved. This follow-up was selected **after** the first grid produced no falls. Pulses are 300/450/600 N for 0.18 s (54/81/108 Ns), at x=1.7 or 2.8 m. These are exploratory simulated impacts; no claim is made about their real-world frequency. Widths are open/0.90/1.20 m, with the same eight parent seeds and fixed direct follower. Initial penetrations are excluded.

| Checkpoint | Width | Task completion | Balance loss | All loss episodes regained standing | Standing without completing task* |
|---|---|---|---|---|---|
'''
        validi=[r for r in impact if not r['initial_barrier_overlap']]
        for x in (1.7,2.8):
            for w in (None,.9,1.2):
                g=[r for r in validi if r['x']==x and r['width']==w];f=[r for r in g if r['fell']];s=[r for r in f if r['stood']]
                text+=f'| {x} m | {"Open" if w is None else str(w)+" m"} | {sum(r["task_success"] for r in g)}/{len(g)} | {len(f)}/{len(g)} | {len(s)}/{len(f)} | {sum(not r["task_success"] for r in s)}/{len(s)} |\n'
        text+='\n*Denominator is trials in which every detected loss episode regained standing. Physical stabilization, task continuation and simulator contact force are separate observations. A wall can supply support as well as restrict movement; geometric free space need not have a monotonic relationship with controller-specific recovery.\n'
        fig,axes=plt.subplots(1,2,figsize=(11,4),sharey=True)
        for ax,x in zip(axes,(1.7,2.8)):
            for w,c in zip((None,.9,1.2),('#517f70','#d19560','#778ba7')):
                fs=[];ts=[]
                for force in (300,450,600):
                    g=[r for r in validi if r['x']==x and r['width']==w and r['strength']==force]
                    fs.append(np.mean([not r['fell'] or r['stood'] for r in g]) if g else np.nan)
                    ts.append(np.mean([r['task_success'] for r in g]) if g else np.nan)
                label='Open' if w is None else f'{w:.2f} m'
                ax.plot([300,450,600],fs,'o--',color=c,alpha=.65,label=label+' upright')
                ax.plot([300,450,600],ts,'s-',color=c,label=label+' task')
            ax.set(title=f'Checkpoint x={x} m',xlabel='0.18 s pulse force (N)',ylim=(-.04,1.04));ax.grid(alpha=.2)
        axes[0].set_ylabel('Fraction within the tested force/seed grid');axes[1].legend(fontsize=7,ncol=2)
        fig.suptitle('Higher-impulse probes: upright survival and task continuation');fig.tight_layout();fig.savefig(FIG/'impact_recovery.png',dpi=180);plt.close(fig)
        text+='\n![Higher-impulse recovery](figures/impact_recovery.png)\n\nDashed “upright” means either no balance loss or all detected loss episodes recovered. It does not require task completion. Each force/width/position cell contains 16 branches from eight parents and two directions; those two directions are not independent seeds.\n'
    text+='\n## Download the trial-level tables\n\n[Initial push probes CSV](data/push_probes.csv) · [Map-replanning CSV](data/map_replanning.csv) · [Higher-impulse CSV](data/higher_impulse_probes.csv). Raw run paths are on Thor; each includes inputs, state trace, telemetry, event log, plots and interpretation.\n'
    (ROOT/'reports/PROBE_STUDY_ANALYSIS.md').write_text(text)
    report=ROOT/'reports/WAKE_UP_REPORT.md';current=report.read_text().split('\n\n## Deeper probe interpretation')[0]
    report.write_text(current+'\n\n## Deeper probe interpretation\n\n'+text.replace('# State-matched follow-up analysis','',1))
    print('Analysed',len(rows),len(astar),len(impact),flush=True)
if __name__=='__main__':main()
