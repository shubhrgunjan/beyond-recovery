"""Compare yaw command mappings on the same nominal long-horizon route."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
os.environ.setdefault('MUJOCO_GL','egl')
import argparse,json,multiprocessing
from concurrent.futures import ProcessPoolExecutor,as_completed
from datetime import datetime
from pathlib import Path
from counterfactual_probes import atomic
ROOT=Path(__file__).resolve().parents[1]

def worker(job):
    from beyond_recovery.live import LiveEngine
    e=LiveEngine(capture_video=False,autostart=False,output_root=Path(job['root'])/'trials')
    e._start(dict(scenario='endurance',label=f'Nominal endurance {job["controller"]} gain{job["gain"]} seed{job["seed"]}',
                  settings=dict(controller=job['controller'],seed=job['seed'],speed=.4,force_scale=1,amp_yaw_gain=job['gain'],arrival_mode=job.get('arrival_mode','legacy'))))
    for _ in range(11000):
        if e.state!='running':break
        e._step()
    if e.recorder:e._finish('hard_horizon')
    s=json.loads((Path(e.last_run)/'summary.json').read_text())
    return dict(seed=job['seed'],controller=job['controller'],gain=job['gain'],arrival_mode=job.get('arrival_mode','legacy'),path=e.last_run,result=s['result'],goals=s['completed_subgoals'],falls=len(s['fall_events']),time=s['simulated_seconds'])

def main():
    p=argparse.ArgumentParser();p.add_argument('--seeds',type=int,default=8);p.add_argument('--centered',action='store_true');a=p.parse_args()
    root=ROOT/'artifacts/research'/datetime.now().strftime('endurance-%Y%m%d-%H%M%S');root.mkdir(parents=True)
    jobs=[dict(seed=s,controller=c,gain=g,root=str(root)) for s in range(a.seeds) for c,g in ([('amp',4)] if a.centered else [('amp',1),('amp',4),('reference',1)])]
    if a.centered:
        for j in jobs:j['arrival_mode']='centered'
    atomic(root/'experiment.json',dict(jobs=jobs,motivation='Qualify nominal turning and 12-goal completion before attributing task failures to recovery. Gain 4 chosen after command-tracking measurements; exploratory calibration, not held-out evidence.'))
    rows=[]
    with ProcessPoolExecutor(max_workers=3,mp_context=multiprocessing.get_context('spawn')) as pool:
        for f in as_completed([pool.submit(worker,j) for j in jobs]):
            row=f.result();rows.append(row);atomic(root/'results.json',rows);print(row,flush=True)
    print('RESULTS',root,flush=True)
if __name__=='__main__':main()
