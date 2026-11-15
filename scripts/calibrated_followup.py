"""Repeat primary experiments after empirical yaw-command calibration."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
os.environ.setdefault('MUJOCO_GL','egl')
from concurrent.futures import ProcessPoolExecutor,as_completed
from datetime import datetime
import json,multiprocessing,zipfile
from pathlib import Path
from counterfactual_probes import worker as probe_worker,atomic
from research_sweep import worker as trip_worker
ROOT=Path(__file__).resolve().parents[1]

def dispatch(job):return (probe_worker if job['kind']=='probe' else trip_worker)(job)

def main():
    oldtrip=sorted((ROOT/'artifacts/research').glob('matched-*'))[-1]
    oldprobe=sorted((ROOT/'artifacts/research').glob('probes-*'))[-1]
    root=ROOT/'artifacts/research'/datetime.now().strftime('calibrated-%Y%m%d-%H%M%S');root.mkdir(parents=True)
    jobs=[]
    for j in json.loads((oldtrip/'experiment.json').read_text())['plan']:
        jobs.append(j|dict(root=str(root/'trip'),amp_yaw_gain=4.,kind='trip'))
    for cp in json.loads((oldprobe/'checkpoints.json').read_text()):
        if cp['x']!=.8:continue
        for strength in (80,140,200):
            for sign in (-1,1):
                for width in (None,.75,.9):
                    for navigation in ('direct','astar'):
                        jobs.append(dict(key=f'gain4-{navigation}-seed{cp["seed"]}-w{width}-f{strength*sign}',
                            kind='probe',checkpoint=cp,width=width,strength=strength,sign=sign,root=str(root/'probe'),
                            amp_yaw_gain=4.,navigation=navigation))
    atomic(root/'experiment.json',dict(jobs=jobs,parents=[str(oldtrip),str(oldprobe)],
        motivation='Yaw calibration chosen from command tests and nominal endurance results. Rerun the full trip design plus paired pre-entry direct/A* probes, not just favorable cases.',
        intervention='AMP yaw command multiplied by 4, from trial start; all other controller weights/actuator profile unchanged. Direct/A* pairs share this mapping and are identical until A* activation at .4 s.',
        caveat='Exploratory method development on the existing seeds, not a fresh held-out confirmation. Original legacy-mapping results remain preserved.'))
    with zipfile.ZipFile(root/'source_snapshot.zip','w',zipfile.ZIP_DEFLATED) as z:
        for folder in ('src','configs','scripts'):
            for f in (ROOT/folder).rglob('*'):
                if f.is_file() and '__pycache__' not in f.parts:z.write(f,str(f.relative_to(ROOT)))
    rows=[]
    with ProcessPoolExecutor(max_workers=3,mp_context=multiprocessing.get_context('spawn')) as pool:
        futures={pool.submit(dispatch,j):j for j in jobs}
        for f in as_completed(futures):
            job=futures[f]
            try:
                row=f.result()|dict(kind=job['kind'],amp_yaw_gain=4.);rows.append(row)
                with (root/'results.jsonl').open('a') as out:out.write(json.dumps(row)+'\n')
                atomic(root/'results.json',rows)
                print(json.dumps(dict(completed=len(rows),total=len(jobs),kind=job['kind'],key=row['key'],success=row['task_success'])),flush=True)
            except Exception as e:
                with (root/'errors.jsonl').open('a') as out:out.write(json.dumps(dict(job=job,error=repr(e)))+'\n')
                print('ERROR',job['key'],repr(e),flush=True)
    print('RESULTS',root,flush=True)
if __name__=='__main__':main()
