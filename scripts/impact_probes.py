"""Exploratory higher-impulse follow-up after the initial probe grid produced no falls."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
os.environ.setdefault('MUJOCO_GL','egl')
from concurrent.futures import ProcessPoolExecutor,as_completed
from datetime import datetime
import json,multiprocessing,zipfile
from pathlib import Path
from counterfactual_probes import worker,atomic
ROOT=Path(__file__).resolve().parents[1]

def main():
    parent=sorted((ROOT/'artifacts/research').glob('probes-*'))[-1]
    checkpoints=json.loads((parent/'checkpoints.json').read_text())
    root=ROOT/'artifacts/research'/datetime.now().strftime('impact-%Y%m%d-%H%M%S');root.mkdir(parents=True)
    jobs=[]
    for cp in checkpoints:
        if cp['x'] not in (1.7,2.8):continue
        for strength in (300,450,600):
            for sign in (-1,1):
                for width in (None,.9,1.2):
                    jobs.append(dict(key=f'impact-seed{cp["seed"]}-x{cp["x"]}-w{width}-f{strength*sign}',checkpoint=cp,
                                     width=width,strength=strength,sign=sign,root=str(root),navigation='direct'))
    atomic(root/'experiment.json',dict(parent_experiment=str(parent),jobs=jobs,
        motivation='Exploratory follow-up: zero balance losses in the completed 80/140/200 N grid. Increase pulse impulses to 54/81/108 Ns to probe physical recovery; no real-world frequency claim.',
        planned_summary='Separate balance loss, upright recovery and task completion; paired states; no claim that arbitrary forces represent operational likelihood'))
    with zipfile.ZipFile(root/'source_snapshot.zip','w',zipfile.ZIP_DEFLATED) as z:
        for folder in ('src','configs','scripts'):
            for f in (ROOT/folder).rglob('*'):
                if f.is_file() and '__pycache__' not in f.parts:z.write(f,str(f.relative_to(ROOT)))
    rows=[]
    with ProcessPoolExecutor(max_workers=3,mp_context=multiprocessing.get_context('spawn')) as pool:
        futures={pool.submit(worker,j):j for j in jobs}
        for f in as_completed(futures):
            job=futures[f]
            try:
                row=f.result();rows.append(row)
                with (root/'results.jsonl').open('a') as out:out.write(json.dumps(row)+'\n')
                atomic(root/'results.json',rows)
                print(json.dumps(dict(completed=len(rows),total=len(jobs),key=row['key'],success=row['task_success'],fell=row['fell'],stood=row['stood'])),flush=True)
            except Exception as e:
                with (root/'errors.jsonl').open('a') as out:out.write(json.dumps(dict(job=job,error=repr(e)))+'\n')
                print('ERROR',job['key'],repr(e),flush=True)
    print('RESULTS',root,flush=True)
if __name__=='__main__':main()
