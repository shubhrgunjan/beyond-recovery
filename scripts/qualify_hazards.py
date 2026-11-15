"""Accelerated execution of the live physics owner; saves all qualification trials."""
import json
import os
os.environ.setdefault('MUJOCO_GL','egl')
from pathlib import Path
from beyond_recovery.live import LiveEngine

engine=LiveEngine();engine.closing=True;engine.thread.join()
results=[]
for scenario in ['rough_pavement','trip_box_open','trip_box_constrained','overhead_strike']:
    engine._start(dict(scenario=scenario,label='Accelerated hazard qualification',
                       settings=dict(seed=0,speed=.4,force_scale=1,controller='amp')))
    manifest_path=engine.recorder/'manifest.json'
    manifest=json.loads(manifest_path.read_text());manifest['live']=False;manifest['execution_mode']='Accelerated qualification using the same physics owner; no wall-clock pacing'
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    for _ in range(1750):
        if engine.state!='running':break
        engine._step()
    if engine.recorder:engine._finish('qualification_window')
    summary=json.loads((Path(engine.last_run)/'summary.json').read_text())
    row={k:summary[k] for k in ['id','scenario','result','simulated_seconds','completed_subgoals','fall_events']}
    row['hazard_contacts']=len(engine.hazard_contacts)
    row['head_peak_n']=engine.analysis['head_contact_peak_n']
    results.append(row);print(json.dumps(row),flush=True)
Path('artifacts/hazard-qualification.json').write_text(json.dumps(results,indent=2)+'\n')
