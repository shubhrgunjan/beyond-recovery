"""Experimental public G1 AMP controller; fixed profile for an entire trial.

Provenance: ccrpRepo/wbc_fsm 4b9afa27ad4eeab8e95584c67c91275b9831fc4d,
State_MJAmp.h/.cpp and mathTypes.h. Profile differences prevent matched actuator
comparisons with the reference controller. This is simulation-only qualification.
"""
from collections import deque
from pathlib import Path
import math

import mujoco
import numpy as np
import onnxruntime as ort


class AMPController:
    def __init__(self, model, data):
        root=Path(__file__).resolve().parents[2]
        options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
        self.session=ort.InferenceSession(str(root/'third_party/g1_amp/policy.onnx'),options,
                                          providers=['CPUExecutionProvider'])
        assert self.session.get_inputs()[0].shape[-1]==384
        self.input=self.session.get_inputs()[0].name
        self.default=np.array([-.312,0,0,.669,-.363,0]*2+[0,0,0]+
                               [.2,.2,0,.6,0,0,0]+[.2,-.2,0,.6,0,0,0])
        armature=np.array([.025101925,.025101925,.010177520,.025101925,.00721945,.00721945]*2+
                          [.010177520,.00721945,.00721945]+
                          [.003609725]*5+[.0021812]*2+[.003609725]*5+[.0021812]*2)
        limits=np.array([139,139,88,139,50,50]*2+[88,50,50]+[25]*5+[10]*2+[25]*5+[10]*2)
        kp=armature*(20*math.pi)**2;kd=4*armature*20*math.pi
        self.scale=.25*limits/kp
        model.actuator_gainprm[:,0]=kp
        model.actuator_biasprm[:,1]=-kp;model.actuator_biasprm[:,2]=-kd
        model.actuator_forcerange[:]=np.column_stack([-limits,limits])
        model.dof_armature[6:35]=armature
        data.qpos[2]=.78;data.qpos[7:36]=self.default;data.ctrl[:]=self.default
        mujoco.mj_forward(model,data)
        self.pelvis=model.body('pelvis').id
        self.history=deque(maxlen=4);self.last=np.zeros(29)

    def step(self,data,command):
        rotation=data.xmat[self.pelvis].reshape(3,3)
        obs=np.concatenate([data.sensor('imu_ang_vel').data,
                            rotation.T@[0,0,-1],command,
                            data.qpos[7:36]-self.default,data.qvel[6:35],self.last])
        if not self.history:self.history.extend([obs.copy() for _ in range(4)])
        else:self.history.append(obs.copy())
        x=np.clip(np.concatenate(self.history),-100,100).astype(np.float32)[None]
        self.last=np.clip(self.session.run(None,{self.input:x})[0].reshape(-1),-100,100)
        return self.last, self.default+self.scale*self.last
