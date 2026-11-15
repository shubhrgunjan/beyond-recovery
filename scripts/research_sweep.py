"""Matched, accelerated physical trials; continuously checkpoint the wake-up report."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
os.environ.setdefault('MUJOCO_GL','egl')

import argparse
from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
from datetime import datetime,timezone
import hashlib,json,math,multiprocessing
from pathlib import Path
import time,zipfile

ROOT=Path(__file__).resolve().parents[1]


def atomic(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp');temporary.write_text(value);temporary.replace(path)


def worker(job):
    from beyond_recovery.live import LiveEngine
    from beyond_recovery.scenarios import box
    start=time.monotonic()
    width,height,seed=job['width'],job['height'],job['seed']
    fixtures=[]
    if height:
        fixtures.append(box(2.1,0,height/2,.22,.28,height/2,(.65,.39,.19,1),label='Matched trip box'))
    if width is not None:
        fixtures.extend([box(2.3,side*(width/2+.15),.55,1.,.15,.55,(.38,.44,.48,1),label='Recovery-space barrier') for side in (-1,1)])
    overrides=dict(name='matched_trip_study',title='Matched trip and clearance study',
                   question='Does clearance change task resumption while the controller and trip hazard are fixed?',
                   duration=45.,waypoints=[[5.5,0]],labels=['Reach the far side of the hazard'],
                   fixtures=fixtures,walls=[],pushes=[],
                   reset_jitter={'position':.015,'yaw':.015})
    engine=LiveEngine(capture_video=False,autostart=False,
                      output_root=job['root']+'/trials',task_overrides=overrides)
    engine._start(dict(scenario='hazard_control',label=job['key'],
                       settings=dict(seed=seed,speed=.4,force_scale=1,controller='amp',amp_yaw_gain=job.get('amp_yaw_gain',1.))))
    manifest_path=engine.recorder/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    manifest['research_condition']=job
    atomic(manifest_path,json.dumps(manifest,indent=2)+'\n')
    for _ in range(4000):
        if engine.state!='running':break
        engine._step()
    if engine.recorder:engine._finish('hard_horizon')
    summary=json.loads((Path(engine.last_run)/'summary.json').read_text())
    falls=summary['fall_events']
    box_contact=next((c['time'] for c in engine.hazard_contacts if c['label']=='Matched trip box'),None)
    first=falls[0] if falls else None
    row={k:job[k] for k in ('key','width','height','seed','split')}
    row.update(run_id=summary['id'],path=engine.last_run,result=summary['result'],
               task_success=summary['result']=='success',time=summary['simulated_seconds'],
               fell=bool(falls),stood=bool(falls) and all(f.get('recovered_at') is not None for f in falls),
               task_resumed=any(f.get('task_resumed_at') is not None for f in falls),
               first_fall=first['start'] if first else None,
               recovery_latency=first.get('recovered_at')-first['start'] if first and first.get('recovered_at') is not None else None,
               first_box_contact=box_contact,hazard_contacts=len(engine.hazard_contacts),
               head_peak_n=engine.analysis['head_contact_peak_n'],wall_seconds=time.monotonic()-start)
    atomic(Path(engine.last_run)/'research_metrics.json',json.dumps(row,indent=2)+'\n')
    return row


def wilson(k,n):
    if not n:return (None,None)
    z=1.96;p=k/n;d=1+z*z/n
    c=(p+z*z/(2*n))/d
    r=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return max(0,c-r),min(1,c+r)


def report(rows,total,started,root,done=False):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    utc=datetime.now(timezone.utc).isoformat(timespec='seconds')
    widths=[None,.75,.9,1.2,1.5];heights=[0.,.06,.13]
    cells=[]
    for h in heights:
        for w in widths:
            group=[r for r in rows if r['width']==w and r['height']==h and r['split']=='matrix']
            if not group:continue
            n=len(group);success=sum(r['task_success'] for r in group);falls=sum(r['fell'] for r in group)
            stood=sum(r['stood'] for r in group);resumed=sum(r['task_resumed'] for r in group)
            lo,hi=wilson(success,n)
            cells.append(dict(width=w,height=h,n=n,success=success,falls=falls,stood=stood,resumed=resumed,ci=[lo,hi]))
    figures=ROOT/'reports/figures';figures.mkdir(parents=True,exist_ok=True)
    values=np.full((len(heights),len(widths)),np.nan)
    for c in cells:values[heights.index(c['height']),widths.index(c['width'])]=c['success']/c['n']
    fig,ax=plt.subplots(figsize=(9,4))
    image=ax.imshow(np.ma.masked_invalid(values),vmin=0,vmax=1,cmap='RdYlGn',aspect='auto')
    ax.set(xticks=range(len(widths)),xticklabels=['Open' if w is None else f'{w:.2f} m' for w in widths],
           yticks=range(len(heights)),yticklabels=[f'{100*h:.0f} cm box' for h in heights],
           xlabel='Clear recovery width',ylabel='Obstacle condition',
           title='Task completion within the fixed observation window — pilot simulation')
    for c in cells:
        ax.text(widths.index(c['width']),heights.index(c['height']),f'{c["success"]}/{c["n"]}',
                ha='center',va='center',color='black',fontweight='bold')
    fig.colorbar(image,ax=ax,label='Task completion fraction')
    fig.tight_layout();fig.savefig(figures/'task_completion_map.png',dpi=160);plt.close(fig)
    contrasts=[]
    for split in ('matrix','holdout'):
        a={r['seed']:r for r in rows if r['width'] is None and r['height']==.13 and r['split']==split}
        b={r['seed']:r for r in rows if r['width']==.9 and r['height']==.13 and r['split']==split}
        seeds=sorted(set(a)&set(b))
        if not seeds:continue
        open_only=sum(a[s]['task_success'] and not b[s]['task_success'] for s in seeds)
        narrow_only=sum(b[s]['task_success'] and not a[s]['task_success'] for s in seeds)
        discordant=open_only+narrow_only
        p=min(1.,2*sum(math.comb(discordant,k) for k in range(min(open_only,narrow_only)+1))/2**discordant) if discordant else 1.
        contrasts.append(dict(split=split,n=len(seeds),open_success=sum(a[s]['task_success'] for s in seeds),
                              narrow_success=sum(b[s]['task_success'] for s in seeds),
                              open_only=open_only,narrow_only=narrow_only,paired_exact_p=p))
    elapsed=time.monotonic()-started
    text=f'''# Beyond Recovery — wake-up report

Updated: {utc} (UTC). Status: **{'completed' if done else 'experiments running; checkpoint saved'}**.

## Executive summary

The upgraded live console is at http://localhost:8080. Refresh the page. It has a much larger viewport, fullscreen/expand, controls over the scene, physical rough-floor/trip/head-strike scenarios, a learned get-up controller, and written trial analysis. Existing recordings remain saved.

The experimental G1 AMP controller physically recovered from settled back, side and front falls in our model. A real-time trip trial lost balance at 9.46 s, sustained upright recovery at 11.90 s and advanced its original task at 22.70 s, without a pose reset. The original walking-only policy is still selectable.

**Current study progress: {len(rows)}/{total} matched trials saved; {elapsed/60:.1f} minutes elapsed.** The report is checkpointed during execution so a session interruption does not erase the findings.

## What is being tested

One fixed AMP controller and actuator profile; speed 0.4 m/s; identical target at x=5.5 m; identical 45 s nominal task horizon. A trip box is at x=2.1 m. Only box height, surrounding clear width and seeded initial x/y/yaw offsets change. Initial variation is ±1.5 cm and ±0.015 rad. There are no injected pushes, no retraining, no operator input and no state resets during a trial. Post-fall observation can extend the horizon by up to 20 s so impact and recovery are not cut off.

The matrix uses 0, 6 and 13 cm obstacles, open/0.75/0.90/1.20/1.50 m widths and seeds 0–7. Box-free corridor controls test nominal feasibility. Additional seeds 8–19 compare open and 0.90 m width at 13 cm height. The latter seeds were not in the pilot. The contrast itself was chosen after the pilot, so the study remains exploratory.

## Results so far

| Box | Clear width | Task success (95% Wilson interval) | Balance loss | Upright recovered* | Task resumed after loss* |
|---|---|---|---|---|---|
'''
    for c in cells:
        label='Open' if c['width'] is None else f'{c["width"]:.2f} m'
        text+=f'| {100*c["height"]:.0f} cm | {label} | {c["success"]}/{c["n"]} ({c["ci"][0]:.0%}–{c["ci"][1]:.0%}) | {c["falls"]}/{c["n"]} | {c["stood"]}/{c["falls"]} | {c["resumed"]}/{c["falls"]} |\n'
    text+='\n*Recovery columns use balance-loss trials as their denominator. Upright recovery requires height >0.65 m, tilt <25° and bounded angular speed for one continuous second. It is separate from subsequent task advancement.\n\n'
    text+='![Task completion map](figures/task_completion_map.png)\n\n## Matched primary contrast: 13 cm box, open vs 0.90 m\n\n'
    for c in contrasts:
        text+=f'- {c["split"]}: {c["n"]} paired seeds; open succeeds {c["open_success"]}/{c["n"]}, constrained {c["narrow_success"]}/{c["n"]}. Discordant pairs: {c["open_only"]} favor open, {c["narrow_only"]} favor constrained. Exploratory exact paired p={c["paired_exact_p"]:.4g}.\n'
    text+='''
## Why this could matter — and what it does not establish

The pilot showed that both open and constrained cases could stand up, while only the open case advanced the original task within 35 s. This motivates **task-resuming recoverability**, rather than standing up as the sole recovery metric.

A width effect is relevant to the proposed problem only after checking that the corresponding box-free corridor is feasible. A failure can also arise from the walking controller's obstacle-passage or local route-following limitations. It does not prove that every possible recovery action was physically unavailable. Multiple strategies, calibrated uncertainty, preservation learning and physical validation remain future work.

The paired p-values concern these particular simulation initial conditions. Small samples, an exploratory contrast, many inspected cells and the limited disturbance domain prevent broad claims of significance, safety or novelty. Later sections will add trajectory-mechanism checks and selected recordings when available.

## Other physically observed tests

- Uneven paving: 15 measured hazard contacts, one subgoal advanced, no balance loss in a 35 s qualification.
- Overhead beam: a measured head contact-force proxy of about 178.7 N; no task subgoal advanced in 35 s. This primarily exposes clearance/ducking/avoidance competence, not a demonstrated loss of all recovery options. Contact force is not an injury estimate.
- Live control checks: actual state changes, frozen pause time, an exact 20 ms step, physical pushes, manual driving, WebSockets and automatic saves passed. An immediate 0.00 s stop still saves a video, figures and traces. Twelve targeted tests pass.

## Artifacts and reproduction

'''
    text+=f'- Experiment root on Thor: `{root}`. Every trial saves state/action/force telemetry, contacts/events, figures, analysis, configuration and metrics. Matrix trials use accelerated native physics without live pacing; videos for selected contrasts will be rendered from saved states and labeled accordingly. The interactive live console continues recording videos automatically.\n'
    text+='- `results.jsonl` is append-only progress; `results.json` is the current complete result set; `experiment.json` records the plan; `source_snapshot.zip` preserves the code/configuration used at launch.\n'
    text+='- The baseline and AMP profiles have different published actuator settings. This study compares widths within AMP, not controller-to-controller robustness.\n'
    text+='- The live app exposes current-state visualization, not these accelerated recordings.\n'
    atomic(ROOT/'reports/WAKE_UP_REPORT.md',text)
    atomic(Path(root)/'results.json',json.dumps(rows,indent=2)+'\n')
    atomic(Path(root)/'aggregate.json',json.dumps(dict(cells=cells,contrasts=contrasts,completed=len(rows),total=total,done=done),indent=2)+'\n')


def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=3);p.add_argument('--max-minutes',type=float,default=40)
    args=p.parse_args();root=ROOT/'artifacts/research'/datetime.now().strftime('matched-%Y%m%d-%H%M%S');root.mkdir(parents=True)
    plan=[]
    # Interleave widths per seed/height so intermediate reports contain matched comparisons.
    for seed in range(8):
        for h in (.13,0.,.06):
            for w in (None,.9,.75,1.2,1.5):
                key=f'matrix-h{h:.2f}-w{w}-seed{seed}'
                plan.append(dict(key=key,width=w,height=h,seed=seed,split='matrix',root=str(root)))
    # Schedule held-out contrast early enough to finish before the deadline.
    holdout=[dict(key=f'holdout-h0.13-w{w}-seed{seed}',width=w,height=.13,seed=seed,split='holdout',root=str(root))
             for seed in range(8,20) for w in (None,.9)]
    plan=plan[:45]+holdout+plan[45:]
    atomic(root/'experiment.json',json.dumps(dict(plan=plan,workers=args.workers,max_minutes=args.max_minutes,
                                               started=datetime.now(timezone.utc).isoformat()),indent=2)+'\n')
    with zipfile.ZipFile(root/'source_snapshot.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for base in ('src','configs','scripts'):
            for f in (ROOT/base).rglob('*'):
                if f.is_file() and '__pycache__' not in f.parts:archive.write(f,str(f.relative_to(ROOT)))
        archive.write(ROOT/'requirements-thor.lock','requirements-thor.lock')
    rows=[];started=time.monotonic();index=0;pending={}
    report(rows,len(plan),started,root)
    with ProcessPoolExecutor(max_workers=args.workers,mp_context=multiprocessing.get_context('spawn')) as pool:
        while index<len(plan) or pending:
            while len(pending)<args.workers and index<len(plan) and time.monotonic()-started<args.max_minutes*60:
                job=plan[index];pending[pool.submit(worker,job)]=job;index+=1
            if not pending:break
            finished,_=wait(pending,timeout=10,return_when=FIRST_COMPLETED)
            for future in finished:
                job=pending.pop(future)
                try:
                    row=future.result();rows.append(row)
                    with (root/'results.jsonl').open('a') as log:log.write(json.dumps(row)+'\n')
                    print(json.dumps(dict(completed=len(rows),total=len(plan),condition=row['key'],
                                          success=row['task_success'],fell=row['fell'],stood=row['stood'],
                                          seconds=round(row['wall_seconds'],2))),flush=True)
                except Exception as error:
                    with (root/'errors.jsonl').open('a') as log:log.write(json.dumps(dict(job=job,error=repr(error)))+'\n')
                    print('ERROR',job['key'],repr(error),flush=True)
            if finished:report(rows,len(plan),started,root)
            if time.monotonic()-started>=args.max_minutes*60 and not pending:break
    report(rows,len(plan),started,root,done=True)
    print('RESULTS',root,flush=True)

if __name__=='__main__':main()
