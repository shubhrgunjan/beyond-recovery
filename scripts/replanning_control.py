"""Test whether a standard map planner explains apparent task-recovery failures."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
os.environ.setdefault('MUJOCO_GL','egl')
from concurrent.futures import ProcessPoolExecutor,as_completed
from datetime import datetime
import json,multiprocessing
from pathlib import Path
from counterfactual_probes import worker,atomic

ROOT=Path(__file__).resolve().parents[1]


def main():
    parent=sorted((ROOT/'artifacts/research').glob('probes-*'))[-1]
    checkpoints=json.loads((parent/'checkpoints.json').read_text())
    root=ROOT/'artifacts/research'/datetime.now().strftime('replanning-%Y%m%d-%H%M%S');root.mkdir(parents=True)
    jobs=[]
    for cp in checkpoints:
        if cp['x']!=.8:continue
        for strength in (80,140,200):
            for sign in (-1,1):
                for width in (None,.75,.9):
                    jobs.append(dict(key=f'astar-seed{cp["seed"]}-x0.8-w{width}-f{strength*sign}',
                        checkpoint=cp,width=width,strength=strength,sign=sign,root=str(root),navigation='astar'))
    atomic(root/'experiment.json',dict(parent_experiment=str(parent),jobs=jobs,
        intervention='Perfect-map A* activated only after .4 s, following the .2–.38 s force pulse; low-level controller/physics unchanged'))
    rows=[]
    with ProcessPoolExecutor(max_workers=3,mp_context=multiprocessing.get_context('spawn')) as pool:
        futures={pool.submit(worker,j):j for j in jobs}
        for f in as_completed(futures):
            job=futures[f]
            try:
                row=f.result();rows.append(row)
                with (root/'results.jsonl').open('a') as out:out.write(json.dumps(row)+'\n')
                atomic(root/'results.json',rows)
                print(json.dumps(dict(completed=len(rows),total=len(jobs),key=row['key'],success=row['task_success'])),flush=True)
            except Exception as e:
                with (root/'errors.jsonl').open('a') as out:out.write(json.dumps(dict(job=job,error=repr(e)))+'\n')
                print('ERROR',job['key'],repr(e),flush=True)
    print('RESULTS',root,flush=True)

if __name__=='__main__':main()
