"""Qualify the experimental AMP adapter on standing and physically settled falls."""
import json,math
from pathlib import Path
import mujoco,numpy as np
from beyond_recovery.reference import build_robot
from beyond_recovery.recovery import AMPController
from beyond_recovery.scenarios import get_scenario

results=[]
for name,quat in [('upright',[1,0,0,0]),('back',[0,0,1,0]),('side',[.70710678,.70710678,0,0]),('front',[.70710678,0,.70710678,0])]:
    m,d,*_=build_robot(get_scenario('open_floor'),0)
    controller=AMPController(m,d)
    if name!='upright':
        d.qpos[2]=.45;d.qpos[3:7]=quat;mujoco.mj_forward(m,d)
        for _ in range(1000):
            d.ctrl[:]=d.qpos[7:36]
            mujoco.mj_step(m,d)
        mujoco.mj_forward(m,d)
    stable=0;best=0;rise=None
    for k in range(1000):
        action,target=controller.step(d,np.array([.3,0,0]) if name=='upright' else np.zeros(3))
        d.ctrl[:]=target
        for _ in range(10):mujoco.mj_step(m,d)
        mujoco.mj_forward(m,d)
        up=d.xmat[m.body('pelvis').id].reshape(3,3)[2,2]
        stable=stable+1 if d.qpos[2]>.65 and up>math.cos(math.radians(25)) else 0
        best=max(best,stable)
        if stable>=50 and rise is None:rise=(k+1)*.02
        if name!='upright' and rise is not None:break
    row={'pose':name,'stood_for_1s':rise is not None,'time':rise,'final_height':float(d.qpos[2]),'best_stable_steps':best}
    results.append(row);print(row,flush=True)
Path('artifacts/recovery-qualification.json').write_text(json.dumps(results,indent=2)+'\n')
