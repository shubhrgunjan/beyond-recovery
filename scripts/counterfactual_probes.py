"""Restore identical physics/controller states, then probe physically bounded pushes."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
os.environ.setdefault('MUJOCO_GL','egl')
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from datetime import datetime,timezone
import hashlib,json,multiprocessing,time
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def atomic(path,data):
    path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(path)


def prepare(root,seeds):
    import mujoco,numpy as np
    from beyond_recovery.live import LiveEngine
    checkpoints=[];parity=[]
    for seed in seeds:
        task=dict(duration=45.,waypoints=[[5.5,0]],labels=['Far station'],fixtures=[],walls=[],pushes=[])
        parent=LiveEngine(capture_video=False,autostart=False,output_root=root/'parents',task_overrides=task)
        parent._start(dict(scenario='hazard_control',label=f'Undisturbed checkpoint parent seed{seed}',
                           settings=dict(seed=seed,speed=.4,force_scale=1,controller='amp')))
        pending=[.8,1.7,2.8,3.8]
        for _ in range(1500):
            parent._step()
            if pending and parent.data.qpos[0]>=pending[0]:
                x=pending.pop(0);flags=mujoco.mjtState.mjSTATE_INTEGRATION
                state=np.zeros(mujoco.mj_stateSize(parent.model,flags));mujoco.mj_getState(parent.model,parent.data,state,flags)
                path=root/'checkpoints'/f'seed{seed}-x{x:.1f}.npz';path.parent.mkdir(exist_ok=True)
                np.savez_compressed(path,integration=state,history=np.array(parent.amp.history),
                                    amp_last=parent.amp.last,action=parent.action,qpos=parent.data.qpos.copy(),
                                    parent_time=parent.sim_time,parent_x=float(parent.data.qpos[0]))
                checkpoints.append(dict(seed=seed,x=x,path=str(path),parent_time=parent.sim_time,
                                        checkpoint_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
                if seed==seeds[0] and x==1.7:
                    checkpoint=dict(np.load(path))
                    child_task=task|dict(settle=0.)
                    child=LiveEngine(capture_video=False,autostart=False,output_root=root/'parity',
                                     task_overrides=child_task,initial_state=checkpoint)
                    child._start(dict(scenario='hazard_control',label='Unperturbed restore parity',
                                      settings=dict(seed=seed,speed=.4,force_scale=1,controller='amp')))
                    errors=[]
                    for _ in range(10):
                        parent._step();child._step()
                        errors.append(float(np.max(np.abs(parent.data.qpos-child.data.qpos))))
                    child._finish('parity_check')
                    parity.append(dict(seed=seed,x=x,steps=10,max_abs_qpos_error=max(errors)))
                    assert max(errors)<1e-8,parity
            if not pending:break
        assert not pending,(seed,pending)
        parent._finish('checkpoint_collection')
        print('CHECKPOINTS',seed,flush=True)
    atomic(root/'checkpoints.json',checkpoints);atomic(root/'restore-parity.json',parity)
    return checkpoints


def worker(job):
    import numpy as np
    from beyond_recovery.live import LiveEngine
    from beyond_recovery.scenarios import box
    width=job['width']
    fixtures=[] if width is None else [box(2.3,side*(width/2+.15),.55,1.,.15,.55,
                                         label='Recovery-space barrier') for side in (-1,1)]
    task=dict(duration=30.,settle=0.,waypoints=[[5.5,0]],labels=['Far station'],fixtures=fixtures,walls=[],
              pushes=[dict(time=.2,duration=.18,force=[0,job['sign']*job['strength'],0],label='Counterfactual lateral probe')])
    task['navigation_activate_at']=.4
    engine=LiveEngine(capture_video=False,autostart=False,output_root=Path(job['root'])/'trials',
                      task_overrides=task,initial_state=dict(np.load(job['checkpoint']['path'])))
    engine._start(dict(scenario='hazard_control',label=job['key'],
                       settings=dict(seed=job['checkpoint']['seed'],speed=.4,force_scale=1,controller='amp',navigation=job.get('navigation','direct'),amp_yaw_gain=job.get('amp_yaw_gain',1.))))
    overlap=False
    for ci in range(engine.data.ncon):
        c=engine.data.contact[ci]
        if c.dist<-.001 and (int(c.geom[0]) in engine.obstacle_geoms or int(c.geom[1]) in engine.obstacle_geoms):overlap=True
    manifest_path=engine.recorder/'manifest.json';manifest=json.loads(manifest_path.read_text())
    manifest.update(counterfactual_probe=job,initial_barrier_overlap=overlap)
    atomic(manifest_path,manifest)
    for _ in range(3000):
        if engine.state!='running':break
        engine._step()
    if engine.recorder:engine._finish('hard_horizon')
    summary=json.loads((Path(engine.last_run)/'summary.json').read_text())
    row={k:job[k] for k in ('key','width','strength','sign')}
    row.update(navigation=job.get('navigation','direct'),seed=job['checkpoint']['seed'],x=job['checkpoint']['x'],path=engine.last_run,
               run_id=summary['id'],task_success=summary['result']=='success',result=summary['result'],
               fell=bool(summary['fall_events']),
               stood=bool(summary['fall_events']) and all(f.get('recovered_at') is not None for f in summary['fall_events']),
               task_resumed=any(f.get('task_resumed_at') is not None for f in summary['fall_events']),
               time=summary['simulated_seconds'],initial_barrier_overlap=overlap,
               fall_events=summary['fall_events'],barrier_contacts=len(engine.hazard_contacts))
    atomic(Path(engine.last_run)/'probe_metrics.json',row)
    return row


def report(rows,total,root):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    xs=[.8,1.7,2.8,3.8];widths=[None,.75,.9,1.2]
    cells=[]
    for x in xs:
        for w in widths:
            g=[r for r in rows if r['x']==x and r['width']==w and not r['initial_barrier_overlap']]
            if g:cells.append(dict(x=x,width=w,n=len(g),success=sum(r['task_success'] for r in g),
                                   falls=sum(r['fell'] for r in g),stood=sum(r['stood'] for r in g)))
    atomic(root/'results.json',rows);atomic(root/'aggregate.json',dict(cells=cells,completed=len(rows),total=total))
    figures=ROOT/'reports/figures';figures.mkdir(exist_ok=True)
    fig,ax=plt.subplots(figsize=(9,4))
    for w in widths:
        points=[c for c in cells if c['width']==w]
        if points:ax.plot([c['x'] for c in points],[c['success']/c['n'] for c in points],'-o',label='Open' if w is None else f'{w:.2f} m')
    ax.axvspan(1.3,3.3,color='grey',alpha=.12,label='Corridor extent')
    ax.set(xlabel='Checkpoint x along original task (m)',ylabel='Task completion fraction under probes',
           ylim=(-.03,1.03),title='Counterfactual task-resuming recoverability probes')
    ax.legend(fontsize=8,ncol=3);ax.grid(alpha=.2);fig.tight_layout();fig.savefig(figures/'counterfactual_profiles.png',dpi=160);plt.close(fig)
    block='\n\n## Further stage: state-matched counterfactual probes\n\n'
    block+=f'Progress: {len(rows)}/{total} branches saved. Each branch restores the same physics integration state and four-frame controller history, then applies a 0.18 s lateral force pulse after 0.20 s. Forces are 80, 140 or 200 N in either lateral direction. Corridor width is changed without changing the robot/controller. There is no trip box in this experiment.\n\n'
    block+='Checkpoints are before, within and beyond the constrained region. This controls the gait/pose differences that otherwise confound comparing different routes. Restoration is an offline experiment initialization, never an execution-time recovery action. Initial barrier penetrations beyond 1 mm are flagged and excluded from the displayed estimates.\n\n'
    block+='| Checkpoint x | Clear width | Completion | Balance-loss trials | All loss episodes recovered |\n|---|---|---|---|---|\n'
    for c in cells:
        block+=f'| {c["x"]:.1f} m | {"Open" if c["width"] is None else str(c["width"])+" m"} | {c["success"]}/{c["n"]} | {c["falls"]}/{c["n"]} | {c["stood"]}/{c["falls"]} |\n'
    block+='\n![Counterfactual profiles](figures/counterfactual_profiles.png)\n\nThe six force conditions for one seed share a parent state. They are not independent seed replications. These are empirical estimates for one fixed controller over a finite force grid, not a viability guarantee or a calibrated lower bound for unseen dynamics.\n'
    path=ROOT/'reports/WAKE_UP_REPORT.md';text=path.read_text().split('\n\n## Further stage: state-matched counterfactual probes')[0]
    path.write_text(text+block)


def main():
    p=argparse.ArgumentParser();p.add_argument('--seeds',type=int,default=8);p.add_argument('--workers',type=int,default=3);args=p.parse_args()
    root=ROOT/'artifacts/research'/datetime.now().strftime('probes-%Y%m%d-%H%M%S');root.mkdir(parents=True)
    checkpoints=prepare(root,list(range(args.seeds)))
    jobs=[]
    for cp in checkpoints:
        for strength in (80,140,200):
            for sign in (-1,1):
                for width in (None,.75,.9,1.2):
                    jobs.append(dict(key=f'seed{cp["seed"]}-x{cp["x"]}-w{width}-f{sign*strength}',
                                     checkpoint=cp,width=width,strength=strength,sign=sign,root=str(root)))
    atomic(root/'experiment.json',dict(started=datetime.now(timezone.utc).isoformat(),jobs=jobs,workers=args.workers))
    with zipfile.ZipFile(root/'source_snapshot.zip','w',zipfile.ZIP_DEFLATED) as z:
        for folder in ('src','configs','scripts'):
            for f in (ROOT/folder).rglob('*'):
                if f.is_file() and '__pycache__' not in f.parts:z.write(f,str(f.relative_to(ROOT)))
    rows=[]
    with ProcessPoolExecutor(max_workers=args.workers,mp_context=multiprocessing.get_context('spawn')) as pool:
        futures={pool.submit(worker,job):job for job in jobs}
        for future in as_completed(futures):
            job=futures[future]
            try:
                row=future.result();rows.append(row)
                with (root/'results.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
                print(json.dumps(dict(completed=len(rows),total=len(jobs),key=row['key'],
                                      success=row['task_success'],fell=row['fell'],overlap=row['initial_barrier_overlap'])),flush=True)
            except Exception as e:
                with (root/'errors.jsonl').open('a') as f:f.write(json.dumps(dict(job=job,error=repr(e)))+'\n')
                print('ERROR',job['key'],repr(e),flush=True)
            if len(rows)%12==0:report(rows,len(jobs),root)
    report(rows,len(jobs),root)
    print('RESULTS',root,flush=True)

if __name__=='__main__':main()
