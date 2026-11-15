"""Measure command tracking before attributing task failure to recovery limits."""
import os
os.environ.setdefault('MUJOCO_GL','egl')
import argparse,json,time
from pathlib import Path
import numpy as np
from beyond_recovery.live import LiveEngine
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--extended',action='store_true');args=parser.parse_args()
root=ROOT/('artifacts/research/command-qualification-extended' if args.extended else 'artifacts/research/command-qualification');root.mkdir(exist_ok=True,parents=True)
rows=[]
for seed in (0,1):
    for command in (([0,0,1.],[0,0,1.5],[0,0,2.],[.4,0,.5],[.4,0,1.]) if args.extended else ([0,0,.5],[.08,0,.5],[.15,0,.5],[.25,0,.5],[0,.2,.5])):
        e=LiveEngine(capture_video=False,autostart=False,output_root=root/'trials',task_overrides={'duration':14.,'fixtures':[],'walls':[],'pushes':[]})
        e._start(dict(scenario='open_floor',label=f'Command qualification {command}',settings={'controller':'amp','speed':.4,'seed':seed}))
        for _ in range(100):e._step()
        e.manual=True;e.intervened=True;e.drive=np.array(command);e.drive_until=time.monotonic()+10000
        yaw=[]
        for _ in range(500):
            if e.state!='running':break
            e._step();r=e.data.xmat[e.pelvis].reshape(3,3);yaw.append(np.arctan2(r[1,0],r[0,0]))
        e._finish('qualification_complete')
        row=dict(seed=seed,command=command,yaw_change=float(np.unwrap(yaw)[-1]-np.unwrap(yaw)[0]),falls=len(e.fall_events),run=e.last_run)
        rows.append(row);(root/'results.json').write_text(json.dumps(rows,indent=2));print(row,flush=True)
