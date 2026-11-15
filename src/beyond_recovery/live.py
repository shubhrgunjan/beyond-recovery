"""Live Thor physics service. One simulation owner; every trial is recorded."""
from __future__ import annotations

import os
os.environ.setdefault('MUJOCO_GL','egl')

import asyncio
from collections import deque
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import queue
import signal
import threading
import time
import uuid

from aiohttp import web
import imageio.v2 as imageio
import mujoco
import numpy as np
from scipy.spatial import ConvexHull, QhullError
import trimesh

from beyond_recovery.reference import build_robot
from beyond_recovery.scenarios import get_scenario, scenarios
from beyond_recovery.task import Route, average_force, wall_clearance
from beyond_recovery.interpretation import interpret, markdown
from beyond_recovery.recovery import AMPController
from beyond_recovery.navigation import GridNavigator

ROOT = Path(__file__).resolve().parents[2]


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def support_margin(points, xy):
    """Static geometric CoM margin; not a dynamic recoverability certificate."""
    if len(points) < 3:
        return None
    try:
        hull = ConvexHull(np.array(points)[:, :2])
        # scipy half-spaces use unit outward normals.
        return float(-np.max(hull.equations[:, :2] @ xy + hull.equations[:, 2]))
    except QhullError:
        return None


def export_robot(model):
    cache = ROOT / '.cache/live'
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / 'robot.glb'
    if target.exists():
        return target
    scene = trimesh.Scene()
    for body in range(1, model.nbody):
        pieces = []
        for geom in range(model.ngeom):
            if model.geom_bodyid[geom] != body or model.geom_group[geom] != 2:
                continue
            if model.geom_type[geom] != mujoco.mjtGeom.mjGEOM_MESH:
                continue
            mesh = model.geom_dataid[geom]
            va, fa = model.mesh_vertadr[mesh], model.mesh_faceadr[mesh]
            vertices = model.mesh_vert[va:va+model.mesh_vertnum[mesh]].copy()
            faces = model.mesh_face[fa:fa+model.mesh_facenum[mesh]].copy()
            part = trimesh.Trimesh(vertices, faces, process=False)
            rotation = np.zeros(9)
            mujoco.mju_quat2Mat(rotation, model.geom_quat[geom])
            transform = np.eye(4)
            transform[:3,:3] = rotation.reshape(3,3)
            transform[:3,3] = model.geom_pos[geom]
            part.apply_transform(transform)
            rgba = model.geom_rgba[geom]
            part.visual.vertex_colors = np.tile((rgba*255).astype(np.uint8), (len(vertices),1))
            pieces.append(part)
        if pieces:
            combined = trimesh.util.concatenate(pieces)
            if len(combined.faces) > 6000:
                color = combined.visual.vertex_colors.mean(axis=0).astype(np.uint8)
                combined = combined.simplify_quadric_decimation(face_count=6000)
                combined.visual.vertex_colors = color
            scene.add_geometry(combined, node_name=f'body_{body}', geom_name=f'link_{body}')
    target.write_bytes(scene.export(file_type='glb'))
    return target


class LiveEngine:
    def __init__(self, *, capture_video=True, autostart=True, output_root=None, task_overrides=None, initial_state=None):
        self.capture_video=capture_video
        self.output_root=Path(output_root) if output_root else ROOT/'artifacts/live'
        self.task_overrides=deepcopy(task_overrides or {})
        self.initial_state=initial_state
        self.commands = queue.Queue()
        self.lock = threading.Lock()
        self.history = deque(maxlen=1500)
        self.events = deque(maxlen=80)
        self.snapshot = {}
        self.closing = False
        self.state = 'ready'
        self.recorder = None
        self.renderer = None
        self.writer = None
        self.log = None
        self.frames = 0
        self.scene_version = 0
        self.sequence = 0
        self.last_error = None
        self.settings = dict(seed=0, force_scale=1., speed=.4,controller='amp',navigation='direct')
        self._load('hazard_control')
        self.mesh = export_robot(self.model)
        self.thread = None
        if autostart:
            self.thread = threading.Thread(target=self._loop, daemon=True, name='thor-physics')
            self.thread.start()

    def _event(self, text, kind='info'):
        event = dict(time=round(self.sim_time,3), text=text, kind=kind,
                     wall_time=time.time())
        self.events.append(event)
        if self.log:
            self.event_log.write(json.dumps(event)+'\n')
            self.event_log.flush()

    def _load(self, scenario):
        self.task = get_scenario(scenario)
        self.task.update(deepcopy(self.task_overrides))
        self.task['speed'] = self.settings['speed']
        self.task['arrival_mode']=self.settings.get('arrival_mode',self.task.get('arrival_mode','legacy'))
        self.navigator=GridNavigator(self.task) if self.settings.get('navigation')=='astar' else None
        for push in self.task['pushes']:
            push['force'] = (np.asarray(push['force']) * self.settings['force_scale']).tolist()
        self.model, self.data, self.deploy, self.policy, self.joint_names, _, _ = build_robot(
            self.task, int(self.settings['seed']))
        self.amp=AMPController(self.model,self.data) if self.settings.get('controller')=='amp' else None
        self.policy_name='experimental-g1-amp-walk-recovery' if self.amp else 'unitree-released-velocity-v0'
        self.input_name = self.policy.get_inputs()[0].name
        self.default = np.array(self.deploy['default_joint_pos'])
        self.offset = np.array(self.deploy['actions']['JointPositionAction']['offset'])
        self.scale = np.array(self.deploy['actions']['JointPositionAction']['scale'])
        self.pelvis, self.torso = self.model.body('pelvis').id, self.model.body('torso_link').id
        self.obstacle_geoms = {
            self.model.geom(f'fixture_{i}').id for i,f in enumerate(self.task['fixtures'])
            if f['center'][2]+f['half_size'][2] > .1
        }
        self.initial_height = float(self.data.qpos[2])
        self.dt = float(self.deploy['step_dt'])
        self.substeps = round(self.dt/self.model.opt.timestep)
        self.route = Route(self.task)
        self.action = np.zeros(29)
        self.phase = 0.
        self.sim_time = 0.
        self.step_count = 0
        self.force = np.zeros(3)
        self.manual = False
        self.drive = np.zeros(3)
        self.drive_until = 0.
        self.user_pushes = []
        self.history.clear()
        self.events.clear()
        self.state = 'ready'
        self.last_error = None
        self.result = None
        self.scene_version += 1
        self.last_wall_step = time.monotonic()
        self.wall_start = None
        self.compute_seconds = 0.
        self.collision_steps = 0
        self.max_tilt = 0.
        self.active_pulses = set()
        self.fall_events=[]
        self.hazard_contacts=[]
        self.contact_keys=set()
        self.recovery_state='walking'
        self.active_fall=None
        self.upright_elapsed=0.
        self.intervened=False
        self.analysis=None
        self.run_id = None
        self._event('Scene ready. Start a trial to run live physics.')
        self._publish()

    def _start(self, command):
        if self.recorder:
            self._finish('restarted')
        settings = command.get('settings', {})
        self.settings = dict(seed=int(settings.get('seed', 0)),
                             force_scale=float(np.clip(settings.get('force_scale',1.),0,3)),
                             speed=float(np.clip(settings.get('speed',.4),.1,.8)),
                             controller=settings.get('controller','amp'),navigation=settings.get('navigation','direct'),
                             amp_yaw_gain=float(settings.get('amp_yaw_gain',1.)),arrival_mode=settings.get('arrival_mode','legacy'))
        self._load(command.get('scenario', self.task['id']))
        if self.initial_state is not None:
            checkpoint=self.initial_state
            flags=mujoco.mjtState.mjSTATE_INTEGRATION
            assert len(checkpoint['integration'])==mujoco.mj_stateSize(self.model,flags)
            mujoco.mj_setState(self.model,self.data,checkpoint['integration'],flags)
            mujoco.mj_forward(self.model,self.data)
            assert self.amp is not None, 'Checkpoint branch currently supports AMP only'
            self.amp.history.clear()
            self.amp.history.extend(row.copy() for row in checkpoint['history'])
            self.amp.last=checkpoint['amp_last'].copy()
            self.action=checkpoint['action'].copy()
        self.label = str(command.get('label',''))[:100]
        self.run_id = time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
        self.recorder = self.output_root / self.run_id
        self.recorder.mkdir(parents=True, exist_ok=False)
        from beyond_recovery.cli import provenance
        atomic_json(self.recorder/'manifest.json', provenance() | dict(
            task=self.task, settings=self.settings, label=self.label, policy=self.policy_name,
            recovery_reference=json.loads((ROOT/'configs/recovery_reference.json').read_text()) if self.amp else None,
            video_recorded=self.capture_video,execution_mode='live' if self.capture_video else 'accelerated physics, state traces saved',
            initial_condition='physics and controller checkpoint' if self.initial_state is not None else 'seeded standing reset',
            reference=json.loads((ROOT/'configs/reference.json').read_text()),
            backend='native-mujoco', live=self.capture_video, physics_dt=float(self.model.opt.timestep),
            control_dt=self.dt, note='Pilot baseline; geometric diagnostics are not recoverability estimates'))
        self.log = (self.recorder/'telemetry.jsonl').open('w', buffering=1)
        self.event_log = (self.recorder/'events.jsonl').open('w', buffering=1)
        self.qpos_log = []
        self.metric_log = []
        if self.capture_video:
            self.renderer = mujoco.Renderer(self.model, height=540, width=960)
            self.writer = imageio.get_writer(self.recorder/'video.mp4', fps=25, codec='libx264',
                                             quality=7, macro_block_size=2)
        self.camera = mujoco.MjvCamera()
        self.camera.distance, self.camera.azimuth, self.camera.elevation = 4.8, 135, -45
        self.visual = mujoco.MjvOption()
        self.visual.geomgroup[3:] = 0
        self.frames = 0
        self.state = 'running'
        self.wall_start = time.time()
        # Even an immediately stopped trial has an initial trace, figure and video.
        initial_tilt=math.degrees(math.acos(float(np.clip(self.data.xmat[self.pelvis].reshape(3,3)[2,2],-1,1))))
        initial=dict(time=0.,height=float(self.data.qpos[2]),tilt=initial_tilt,effort=0.,speed=float(np.linalg.norm(self.data.qvel[:2])),
                     target_speed=0.,support_margin=None,clearance=None,
                     x=float(self.data.qpos[0]),y=float(self.data.qpos[1]),
                     force=0.,phase=0,collision=False)
        self.history.append(initial)
        self.metric_log.append(initial)
        self.qpos_log.append(self.data.qpos.copy())
        self.log.write(json.dumps(initial | dict(qpos=self.data.qpos.tolist(),qvel=self.data.qvel.tolist(),
                       action=self.action.tolist(),command=[0,0,0],force_xyz=[0,0,0],
                       actuator_force=self.data.actuator_force.tolist(),manual=False))+'\n')
        self.camera.lookat[:]=self.data.qpos[:3]
        if self.capture_video:
            self.renderer.update_scene(self.data,camera=self.camera,scene_option=self.visual)
            self.writer.append_data(self.renderer.render())
            self.frames=1
        self._event('Trial started. Physics and policy are running on Thor.', 'start')
        atomic_json(self.recorder/'summary.json', self._summary('running'))

    def _summary(self, result):
        return dict(id=self.run_id, scenario=self.task['id'], title=self.task['title'],
                    label=getattr(self,'label',''),
                    result=result, simulated_seconds=round(self.sim_time,3),
                    completed_subgoals=self.route.phase, total_subgoals=len(self.task['waypoints']),
                    max_tilt_deg=round(self.max_tilt,2), collision_steps=self.collision_steps,
                    operator_intervention=self.intervened,
                    planner_replans=self.navigator.replans if self.navigator else 0,
                    planner_no_path=self.navigator.no_path if self.navigator else 0,
                    video_recorded=self.capture_video,
                    seed=self.settings['seed'], settings=self.settings,
                    policy=self.policy_name, controller=self.settings['controller'],
                    fall_events=self.fall_events,analysis=self.analysis,saved_at=time.time())

    def _finish(self, result):
        if not self.recorder:
            return
        self.state = 'saving'
        self._publish()
        self._event(f'Trial {result}; finalizing recording and figures.', 'finish')
        if self.writer:self.writer.close()
        if self.renderer:self.renderer.close()
        self.log.close()
        self.event_log.close()
        np.savez_compressed(self.recorder/'trace.npz', qpos=np.array(self.qpos_log),
                            time=np.array([m['time'] for m in self.metric_log]))
        if self.metric_log:
            self._figures()
        self.analysis=interpret(self.task,self.metric_log,result,self.fall_events,self.hazard_contacts,
                                self.settings['controller'],self.intervened)
        atomic_json(self.recorder/'analysis.json',self.analysis)
        (self.recorder/'analysis.md').write_text(markdown(self.analysis))
        atomic_json(self.recorder/'summary.json', self._summary(result))
        self.last_run = str(self.recorder)
        self.recorder = self.writer = self.renderer = self.log = None
        self.result = result
        self.state = 'finished'
        self._publish()

    def _figures(self):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        rows = self.metric_log
        t = [r['time'] for r in rows]
        fig, ax = plt.subplots(2,3,figsize=(14,7))
        fig.suptitle(f"{self.task['title']} · {self.run_id}")
        for axis,key,label,threshold in [
            (ax[0,0],'height','Pelvis height (m)',.35),
            (ax[0,1],'tilt','Base tilt (degrees)',70),
            (ax[0,2],'effort','Peak actuator utilization (%)',100),
            (ax[1,0],'head_contact_n','Head contact force (N)',None),
            (ax[1,1],'support_margin','Static support margin (m)',0)]:
            axis.plot(t,[np.nan if r.get(key) is None else r[key] for r in rows],lw=1)
            if key=='head_contact_n':
                axis.plot(t,[r.get('body_contact_n',0) for r in rows],lw=1,label='Other body')
                axis.legend()
            axis.set(xlabel='Simulated time (s)',ylabel=label)
            if threshold is not None: axis.axhline(threshold,color='#d86955',ls='--',lw=1)
            axis.grid(alpha=.2)
        ax[1,2].plot([r['x'] for r in rows],[r['y'] for r in rows])
        ax[1,2].set(xlabel='x (m)',ylabel='y (m)',title='Executed route',aspect='equal')
        fig.tight_layout()
        fig.savefig(self.recorder/'figures.png',dpi=150)
        plt.close(fig)

    def _handle(self, command):
        kind = command['action']
        if kind == 'start':
            self._start(command)
        elif kind == 'select':
            if self.recorder: self._finish('scene_changed')
            self._load(command['scenario'])
        elif kind == 'pause' and self.state == 'running':
            self.state = 'paused'
            self._event('Paused. Simulated time is frozen.')
        elif kind == 'resume' and self.state == 'paused':
            self.state = 'running'
            self._event('Resumed.')
        elif kind == 'step' and self.state == 'paused':
            self._step()
        elif kind == 'stop' and self.recorder:
            self._finish('stopped')
        elif kind == 'manual' and self.state in ('running','paused'):
            self.manual = bool(command.get('enabled',False))
            self.intervened=self.intervened or self.manual
            self.drive[:] = 0
            self._event('Manual driving enabled.' if self.manual else 'Waypoint policy resumed.')
        elif kind == 'drive' and self.manual:
            self.drive = np.clip(np.array(command['velocity'],dtype=float),[-.6,-.4,-.7],[.6,.4,.7])
            self.drive_until = time.monotonic()+.35
        elif kind == 'push' and self.state == 'running':
            self.intervened=True
            strength = float(np.clip(command.get('strength',80),0,250))
            direction = command.get('direction','+y')
            unit = {'+y':[0,1,0],'-y':[0,-1,0],'+x':[1,0,0],'-x':[-1,0,0]}[direction]
            duration = float(np.clip(command.get('duration',.2),.04,.6))
            event = dict(time=self.sim_time,duration=duration,
                         force=(np.array(unit)*strength).tolist(),label='Manual push '+direction)
            self.user_pushes.append(event)
            self._event(f'Manual push {direction}: {strength:g} N × {duration:g} s.', 'push')
        self._publish()

    def _step(self):
        started = time.perf_counter()
        rotation = self.data.xmat[self.pelvis].reshape(3,3)
        yaw = math.atan2(rotation[1,0],rotation[0,0])
        previous_phase = self.route.phase
        command = (self.route.command(self.data.qpos[:2],yaw,self.sim_time,self.dt)
                   if self.recovery_state=='walking' else np.zeros(3))
        if self.route.phase != previous_phase:
            label = self.task['labels'][previous_phase]
            self._event(f'Completed {label} ({self.route.phase}/{len(self.task["waypoints"])}).','goal')
            for fall in self.fall_events:
                if fall.get('recovered_at') is not None and fall.get('task_resumed_at') is None:
                    fall['task_resumed_at']=round(self.sim_time,3)
        if self.manual:
            command = self.drive if time.monotonic() < self.drive_until else np.zeros(3)
        elif (self.navigator and self.recovery_state=='walking' and not self.route.complete
              and self.route.dwell_elapsed==0 and self.sim_time>=max(self.task.get('settle',2),self.task.get('navigation_activate_at',0))):
            goal=self.task['waypoints'][self.route.phase]
            if np.linalg.norm(np.asarray(goal)-self.data.qpos[:2])>self.task.get('arrival_radius',.25):
                command=self.navigator.command(self.data.qpos[:2],yaw,goal,self.sim_time)
        self.phase = (self.phase+self.dt/.6)%1
        gait = [math.sin(self.phase*2*math.pi),math.cos(self.phase*2*math.pi)] if np.linalg.norm(command)>=.1 else [0,0]
        obs = np.concatenate([self.data.sensor('imu_ang_vel').data,
                              rotation.T@[0,0,-1],command,gait,
                              self.data.qpos[7:]-self.default,self.data.qvel[6:],self.action]).astype(np.float32)[None]
        if self.amp:
            policy_command=command.copy();policy_command[2]=np.clip(policy_command[2]*self.settings.get('amp_yaw_gain',1.),-2.,2.)
            self.action,target=self.amp.step(self.data,policy_command)
        else:
            self.action = self.policy.run(None,{self.input_name:obs})[0].reshape(-1)
            target=self.offset+self.action*self.scale
        if not np.isfinite(self.action).all():
            raise RuntimeError('Policy produced a non-finite action')
        self.data.ctrl[:] = target
        pulses = self.task['pushes']+self.user_pushes
        for index,event in enumerate(pulses):
            if event['time'] <= self.sim_time < event['time']+event['duration'] and index not in self.active_pulses:
                self._event(f"{event.get('label','Push')}: {np.linalg.norm(event['force']):g} N for {event['duration']:g} s.",'push')
                self.active_pulses.add(index)
        self.force = average_force(pulses,self.sim_time,self.dt)
        head_peak=body_peak=0.
        for sub in range(self.substeps):
            self.data.xfrc_applied[self.torso,:3] = average_force(
                pulses,self.sim_time+sub*self.model.opt.timestep,self.model.opt.timestep)
            mujoco.mj_step(self.model,self.data)
            for ci in range(self.data.ncon):
                contact=self.data.contact[ci]
                a,b=map(int,contact.geom)
                if self.model.geom_bodyid[a]==self.model.geom_bodyid[b]:continue
                if self.model.geom_bodyid[a]!=0 and self.model.geom_bodyid[b]!=0:continue
                robot_geom=b if self.model.geom_bodyid[a]==0 else a
                other=a if robot_geom==b else b
                name=self.model.geom(robot_geom).name or ''
                region='head' if 'head' in name else 'foot' if 'foot' in name else 'body'
                wrench=np.zeros(6);mujoco.mj_contactForce(self.model,self.data,ci,wrench)
                force=float(np.linalg.norm(wrench[:3]))
                if region=='head':head_peak=max(head_peak,force)
                elif region=='body':body_peak=max(body_peak,force)
                other_name=self.model.geom(other).name or ''
                if force>1 and other_name.startswith('fixture_'):
                    index=int(other_name.split('_')[1]);fixture=self.task['fixtures'][index]
                    key=(index,region)
                    if key not in self.contact_keys:
                        self.contact_keys.add(key)
                        event=dict(time=round(self.sim_time+(sub+1)*self.model.opt.timestep,3),
                                   region=region,label=fixture.get('label',f'Fixture {index}'),force_n=force)
                        self.hazard_contacts.append(event)
                        self._event(f"{region.capitalize()} contacted {event['label']} ({force:.0f} N at first contact).",'contact')
        mujoco.mj_forward(self.model,self.data)
        if not np.isfinite(self.data.qpos).all() or not np.isfinite(self.data.qvel).all():
            raise RuntimeError('Non-finite physics state; trial stopped rather than reset')
        self.sim_time += self.dt
        self.step_count += 1
        rotation = self.data.xmat[self.pelvis].reshape(3,3)
        tilt = math.degrees(math.acos(float(np.clip(rotation[2,2],-1,1))))
        self.max_tilt = max(self.max_tilt,tilt)
        limits = np.max(np.abs(self.model.actuator_forcerange),axis=1)
        effort = float(np.max(np.abs(self.data.actuator_force)/np.maximum(limits,1e-8))*100)
        points, collision = [],False
        for i in range(self.data.ncon):
            contact = self.data.contact[i]
            a,b = int(contact.geom[0]),int(contact.geom[1])
            names = [self.model.geom(a).name or '', self.model.geom(b).name or '']
            if (any('foot' in n for n in names)
                    and (self.model.geom_bodyid[a]==0 or self.model.geom_bodyid[b]==0)
                    and abs(contact.frame[2]) > .7):
                points.append(contact.pos.copy())
            if a in self.obstacle_geoms or b in self.obstacle_geoms:
                if self.model.geom_bodyid[a] != self.model.geom_bodyid[b]: collision=True
        self.collision_steps += int(collision)
        mass = self.model.body_mass
        com = np.sum(self.data.xipos*mass[:,None],axis=0)/sum(mass)
        obstacles = self.task['walls'] + [f for f in self.task['fixtures'] if f['center'][2]+f['half_size'][2]>.1]
        clearance = wall_clearance(self.data.qpos[:2],obstacles)
        row = dict(time=round(self.sim_time,4),height=float(self.data.qpos[2]),tilt=tilt,
                   effort=effort,speed=float(np.linalg.norm(self.data.qvel[:2])),
                   target_speed=float(np.linalg.norm(command[:2])),
                   support_margin=support_margin(points,com[:2]),clearance=clearance,
                   x=float(self.data.qpos[0]),y=float(self.data.qpos[1]),
                   force=float(np.linalg.norm(self.force)),phase=self.route.phase,collision=collision,
                   head_contact_n=head_peak,body_contact_n=body_peak,recovery_state=self.recovery_state)
        self.history.append(row)
        self.metric_log.append(row)
        self.qpos_log.append(self.data.qpos.copy())
        self.log.write(json.dumps(row | dict(qpos=self.data.qpos.tolist(),qvel=self.data.qvel.tolist(),
                        action=self.action.tolist(),command=command.tolist(),policy_command=(policy_command if self.amp else command).tolist(),force_xyz=self.force.tolist(),
                        actuator_force=self.data.actuator_force.tolist(),manual=self.manual))+'\n')
        if self.step_count%50 == 0:
            atomic_json(self.recorder/'summary.json',self._summary('running'))
        if self.writer and self.step_count%2 == 0:
            self.camera.lookat[:] = self.data.qpos[:3]
            self.renderer.update_scene(self.data,camera=self.camera,scene_option=self.visual)
            self.writer.append_data(self.renderer.render())
            self.frames += 1
        self.compute_seconds += time.perf_counter()-started
        if (tilt>70 or self.data.qpos[2]<.35) and self.active_fall is None:
            self.active_fall=dict(start=round(self.sim_time,3),phase=self.route.phase,recovered_at=None)
            self.fall_events.append(self.active_fall)
            self.recovery_state='falling'
            self._event('Balance lost. Physics continues through the fall and impact; the state is not reset.','fall')
            self.upright_elapsed=0.
        if self.active_fall is not None:
            elapsed=self.sim_time-self.active_fall['start']
            if elapsed>.5 and self.recovery_state=='falling':
                self.recovery_state='recovering' if self.amp else 'observing_fall'
                self._event('Learned AMP controller is attempting to get up.' if self.amp else
                            'Walking-only policy has no trained get-up skill; observing its post-fall response.','recovery')
            standing=tilt<25 and self.data.qpos[2]>.65 and np.linalg.norm(self.data.qvel[3:6])<2
            self.upright_elapsed=self.upright_elapsed+self.dt if standing else 0.
            if self.upright_elapsed>=1:
                self.active_fall['recovered_at']=round(self.sim_time,3)
                self._event('Upright stance sustained for 1 second. Resuming the original subgoal.','recovery')
                self.active_fall=None;self.recovery_state='walking';self.upright_elapsed=0.
            elif elapsed>=20:
                self._finish('recovery_failed')
        elif self.route.complete:
            self._finish('success')
        elif self.sim_time >= self.task['duration']:
            self._finish('timeout')

    def _publish(self):
        self.sequence += 1
        current = dict(state=self.state,result=self.result,scene_version=self.scene_version,
                       seq=self.sequence,sim_time=round(self.sim_time,3),scenario=self.task['id'],
                       phase=self.route.phase,total=len(self.task['waypoints']),
                       dwell=self.route.dwell_elapsed,run_id=self.run_id,
                       manual=self.manual,force=self.force.tolist(),
                       recovery_state=self.recovery_state,controller=self.settings.get('controller'),
                       navigation=self.settings.get('navigation','direct'),capabilities={'navigation':True,'amp_yaw_gain':True,'arrival_mode':True},
                       falls=self.fall_events,analysis=self.analysis,
                       positions=self.data.xpos.round(5).tolist(),quaternions=self.data.xquat.round(6).tolist(),
                       telemetry=list(self.history)[-1] if self.history else None,
                       events=list(self.events)[-15:],error=self.last_error,
                       compute_rtf=(self.sim_time/self.compute_seconds if self.compute_seconds else None))
        with self.lock: self.snapshot = current

    def _loop(self):
        deadline = time.monotonic()
        try:
            while not self.closing:
                try:
                    while True: self._handle(self.commands.get_nowait())
                except queue.Empty:
                    pass
                if self.state == 'running':
                    self._step()
                    self._publish()
                    deadline += self.dt
                    if deadline < time.monotonic()-.2: deadline=time.monotonic()
                    time.sleep(max(0,deadline-time.monotonic()))
                else:
                    self._publish()
                    time.sleep(.02)
                    deadline=time.monotonic()
        except Exception as error:
            import traceback
            traceback.print_exc()
            self.last_error = str(error)
            try:
                self._finish('error')
            finally:
                self.state='error'
                self._publish()
        finally:
            if self.recorder: self._finish('server_stopped')

    def read(self):
        with self.lock: return deepcopy(self.snapshot)


def validate_command(command):
    if not isinstance(command,dict): raise ValueError('Expected a JSON object')
    action=command.get('action')
    if action not in {'start','select','pause','resume','step','stop','manual','drive','push'}:
        raise ValueError('Unknown action')
    if action in {'start','select'}:
        id=command.get('scenario','open_floor')
        if id not in {s['id'] for s in scenarios()}: raise ValueError('Unknown scenario')
    if action=='drive':
        v=command.get('velocity')
        if not isinstance(v,list) or len(v)!=3 or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in v):
            raise ValueError('Velocity must have three finite values')
    if action=='push' and command.get('direction','+y') not in {'+x','-x','+y','-y'}:
        raise ValueError('Unknown push direction')
    for key in ('strength','duration'):
        if key in command and (not isinstance(command[key],(int,float)) or not math.isfinite(command[key])):
            raise ValueError(f'Invalid {key}')
    for key,value in command.get('settings',{}).items():
        if key=='controller':
            if value not in {'amp','reference'}:raise ValueError('Unknown controller')
            continue
        if key=='arrival_mode':
            if value not in {'legacy','centered'}:raise ValueError('Unknown arrival mode')
            continue
        if key=='navigation':
            if value not in {'direct','astar'}:raise ValueError('Unknown navigation mode')
            continue
        if key not in {'seed','force_scale','speed','amp_yaw_gain'} or not isinstance(value,(int,float)) or not math.isfinite(value):
            raise ValueError('Invalid settings')
    gain=command.get('settings',{}).get('amp_yaw_gain',1.)
    if not 1<=gain<=4:raise ValueError('AMP yaw gain must be between 1 and 4')
    seed=command.get('settings',{}).get('seed',0)
    if int(seed) != seed or not 0 <= seed <= 2147483647:
        raise ValueError('Seed must be an integer between 0 and 2147483647')
    return command


async def serve(args):
    engine=LiveEngine()
    app=web.Application(client_max_size=16384)
    sockets=set()
    async def index(request): return web.FileResponse(ROOT/'web/dist/index.html')
    async def scenario_api(request): return web.json_response(scenarios())
    async def status(request): return web.json_response(engine.read())
    async def action(request):
        if engine.closing:
            return web.json_response({'error':'Service is restarting; reconnect shortly'},status=503)
        try:
            command=validate_command(await request.json())
            engine.commands.put(command)
            return web.json_response({'queued':True})
        except (ValueError,TypeError,AttributeError) as error:
            return web.json_response({'error':str(error)},status=400)
    async def scene(request):
        return web.json_response({'task':engine.task,'version':engine.scene_version,'asset':'/robot.glb'})
    async def runs(request):
        root=ROOT/'artifacts/live'
        rows=[]
        for p in sorted(root.glob('*/summary.json'),reverse=True)[:100]:
            try: rows.append(json.loads(p.read_text()))
            except (ValueError,OSError): pass
        return web.json_response(rows)
    async def download(request):
        run,name=request.match_info['run'],request.match_info['name']
        if '/' in run or '..' in run or name not in {'video.mp4','figures.png','trace.npz','telemetry.jsonl','events.jsonl','manifest.json','summary.json','analysis.json','analysis.md'}:
            raise web.HTTPNotFound()
        path=ROOT/'artifacts/live'/run/name
        if not path.is_file(): raise web.HTTPNotFound()
        return web.FileResponse(path)
    async def socket(request):
        ws=web.WebSocketResponse(heartbeat=15,timeout=2)
        await ws.prepare(request)
        sockets.add(ws)
        await ws.send_json(engine.read() | {'history':list(engine.history)})
        async def send():
            last_time=-1
            last_run=None
            while not ws.closed:
                snapshot=engine.read()
                if snapshot['run_id']!=last_run:
                    last_run=snapshot['run_id'];last_time=-1
                samples=[row for row in list(engine.history) if row['time']>last_time]
                if samples:last_time=samples[-1]['time']
                await ws.send_json(snapshot | {'samples':samples})
                await asyncio.sleep(.04)
        sender=asyncio.create_task(send())
        try:
            async for message in ws:
                if message.type==web.WSMsgType.TEXT:
                    try: engine.commands.put(validate_command(json.loads(message.data)))
                    except (ValueError,TypeError,AttributeError) as error: await ws.send_json({'error':str(error)})
        finally:
            sender.cancel()
            sockets.discard(ws)
        return ws
    async def shutdown(app):
        await asyncio.gather(*(ws.close(code=1001,message=b'Service restarting') for ws in list(sockets)))
    app.on_shutdown.append(shutdown)
    app.router.add_get('/',index)
    app.router.add_get('/api/scenarios',scenario_api)
    app.router.add_get('/api/status',status)
    app.router.add_get('/api/scene',scene)
    app.router.add_get('/api/runs',runs)
    app.router.add_post('/api/action',action)
    app.router.add_get('/ws',socket)
    app.router.add_get('/robot.glb',lambda request:web.FileResponse(engine.mesh))
    app.router.add_get('/runs/{run}/{name}',download)
    app.router.add_static('/assets',ROOT/'web/dist')
    runner=web.AppRunner(app,shutdown_timeout=3)
    await runner.setup()
    site=web.TCPSite(runner,'127.0.0.1',args.port)
    await site.start()
    print(f'LIVE physics console ready at http://127.0.0.1:{args.port}',flush=True)
    stopping=asyncio.Event()
    for sig in (signal.SIGINT,signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(sig,stopping.set)
    try: await stopping.wait()
    finally:
        engine.closing=True
        await asyncio.to_thread(engine.thread.join,30)
        await runner.cleanup()


def run(args):
    asyncio.run(serve(args))
