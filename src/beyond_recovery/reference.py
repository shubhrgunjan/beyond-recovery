"""Native MuJoCo runner for Unitree's released G1 velocity ONNX policy.

This policy has a different observation space from the mjlab PPO training task.
It is deliberately kept as a separate reference, never loaded as a PPO checkpoint.
"""

import json
import math
from pathlib import Path
import time

import imageio.v2 as imageio
import mujoco
import numpy as np
import onnxruntime as ort
import yaml

from beyond_recovery.task import Route, average_force, wall_clearance


def build_robot(task, seed=0):
    """Shared native robot/policy construction for batch and live experiments."""
    from beyond_recovery.cli import ROOT
    folder = ROOT / 'third_party/unitree_reference'
    deploy = yaml.safe_load((folder / 'deploy.yaml').read_text())
    meshdir = ROOT / 'third_party/mjlab/src/mjlab/asset_zoo/robots/unitree_g1/xmls/assets'
    xml = (folder / 'g1.xml').read_text().replace('meshdir="assets"', f'meshdir="{meshdir}"')
    spec = mujoco.MjSpec.from_string(xml)
    spec.option.timestep = .002
    spec.option.iterations = spec.option.ls_iterations = 50
    spec.option.integrator = mujoco.mjtIntegrator.mjINT_IMPLICITFAST
    spec.worldbody.add_light(pos=[0, 0, 5], dir=[0, 0, -1], diffuse=[.8, .8, .8])
    spec.add_texture(name='floor', type=mujoco.mjtTexture.mjTEXTURE_2D,
                     builtin=mujoco.mjtBuiltin.mjBUILTIN_CHECKER,
                     width=512, height=512, rgb1=[.18, .23, .28], rgb2=[.28, .33, .38])
    spec.add_material(name='floor', textures=['', 'floor', '', '', '', '', '', '', '', ''],
                      texrepeat=[1, 1], texuniform=True)
    spec.worldbody.add_geom(name='floor', type=mujoco.mjtGeom.mjGEOM_PLANE,
                            size=[0, 0, .1], material='floor', friction=[.6, .005, .0001])
    # Reuse the same walls/waypoint markers as the GPU task suite.
    for i, wall in enumerate(task.get('walls', [])):
        spec.worldbody.add_geom(name=f'route_wall_{i}', type=mujoco.mjtGeom.mjGEOM_BOX,
                                pos=wall['center'], size=wall['half_size'],
                                rgba=[.35, .45, .6, 1])
    for i, xy in enumerate(task['waypoints']):
        spec.worldbody.add_site(name=f'station_{i}', type=mujoco.mjtGeom.mjGEOM_CYLINDER,
                                pos=[*xy, .012], size=[.22, .01, .01], rgba=[.1,.8,.4,.7])
    for i, fixture in enumerate(task.get('fixtures', [])):
        spec.worldbody.add_geom(
            name=f'fixture_{i}', type=mujoco.mjtGeom.mjGEOM_BOX,
            pos=fixture['center'], size=fixture['half_size'],
            rgba=fixture.get('color', [.40, .45, .52, 1]),
            friction=fixture.get('friction', [.6, .005, .0001]),
            priority=fixture.get('priority', 0), contype=1, conaffinity=1)
    joints = [joint for joint in spec.joints if joint.type != mujoco.mjtJoint.mjJNT_FREE]
    assert len(joints) == 29 and deploy['joint_ids_map'] == list(range(29))
    kp, kd = np.array(deploy['stiffness']), np.array(deploy['damping'])
    for i, joint in enumerate(joints):
        joint.armature = float(kp[i] / (10 * 2 * math.pi)**2)
        limit = (5 if 'wrist_pitch' in joint.name or 'wrist_yaw' in joint.name else
                 139 if 'hip_roll' in joint.name or 'knee' in joint.name else
                 88 if 'hip_pitch' in joint.name or 'hip_yaw' in joint.name or 'waist_yaw' in joint.name else
                 50 if 'ankle' in joint.name or 'waist' in joint.name else 25)
        gain, bias = np.zeros(10), np.zeros(10)
        gain[0], bias[1], bias[2] = kp[i], -kp[i], -kd[i]
        spec.add_actuator(name=joint.name + '_position',
                          trntype=mujoco.mjtTrn.mjTRN_JOINT, target=joint.name,
                          gaintype=mujoco.mjtGain.mjGAIN_FIXED,
                          biastype=mujoco.mjtBias.mjBIAS_AFFINE,
                          gainprm=gain, biasprm=bias,
                          forcelimited=True, forcerange=[-limit, limit])
    model = spec.compile()
    model.vis.global_.offwidth, model.vis.global_.offheight = 960, 640
    data = mujoco.MjData(model)
    default = np.array(deploy['default_joint_pos'])
    data.qpos[2] = .80
    data.qpos[3:7] = [1, 0, 0, 0]
    jitter = task.get('reset_jitter', {})
    rng = np.random.default_rng(seed)
    position_jitter = jitter.get('position', 0)
    data.qpos[:2] = rng.uniform(-position_jitter, position_jitter, size=2)
    initial_yaw = rng.uniform(-jitter.get('yaw', 0), jitter.get('yaw', 0))
    data.qpos[3:7] = [math.cos(initial_yaw / 2), 0, 0, math.sin(initial_yaw / 2)]
    data.qpos[7:] = default
    data.ctrl[:] = default
    mujoco.mj_forward(model, data)
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 2
    opts.inter_op_num_threads = 1
    session = ort.InferenceSession(str(folder / 'policy.onnx'), opts,
                                   providers=['CPUExecutionProvider'])
    assert session.get_inputs()[0].shape[-1] == 98
    input_name = session.get_inputs()[0].name
    return model, data, deploy, session, [joint.name for joint in joints], kp, kd


def run(args):
    from beyond_recovery.cli import ROOT, plot_trace, provenance, write_json
    task = yaml.safe_load(Path(args.config).read_text())
    if args.duration:
        task['duration'] = args.duration
    folder = ROOT / 'third_party/unitree_reference'
    model, data, deploy, session, joint_names, kp, kd = build_robot(task, args.seed)
    default = np.array(deploy['default_joint_pos'])
    input_name = session.get_inputs()[0].name
    output = Path(args.output or f'artifacts/reference_{task["name"]}_{time.time_ns()}')
    output.mkdir(parents=True, exist_ok=False)
    mujoco.mj_saveModel(model, str(output / 'scene.mjb'))
    write_json(output / 'manifest.json', provenance() | {
        'reference': json.loads((folder / 'manifest.json').read_text()),
        'task': task, 'seed': args.seed, 'backend': 'native-mujoco',
        'note': 'Published policy, deployment gains/observations; local MuJoCo adapter, not publisher benchmark results',
        'joint_order': joint_names, 'actuator_kp': kp.tolist(),
        'actuator_kd': kd.tolist(), 'physics_dt': model.opt.timestep,
    })
    (output / 'task.yaml').write_text(yaml.safe_dump(task))
    route = Route(task)
    dt = float(deploy['step_dt'])
    decimation = round(dt / model.opt.timestep)
    assert abs(decimation * model.opt.timestep - dt) < 1e-10
    action = np.zeros(29)
    scale = np.array(deploy['actions']['JointPositionAction']['scale'])
    offset = np.array(deploy['actions']['JointPositionAction']['offset'])
    pelvis = model.body('pelvis').id
    torso = model.body('torso_link').id
    phase = 0.0
    renderer = writer = None
    camera = mujoco.MjvCamera()
    camera.distance, camera.azimuth, camera.elevation = 4, 135, -25
    visual = mujoco.MjvOption()
    visual.geomgroup[3:] = 0
    if args.video:
        renderer = mujoco.Renderer(model, height=640, width=960)
        every = max(1, round(1 / (args.fps * dt)))
        writer = imageio.get_writer(output / 'rollout.mp4', fps=1 / (every * dt),
                                     codec='libx264', quality=7, macro_block_size=8)
    records = []
    result = 'timeout'
    started = time.perf_counter()
    try:
        with (output / 'telemetry.jsonl').open('w') as log:
            for step in range(math.ceil(task['duration'] / dt)):
                t = step * dt
                rotation = data.xmat[pelvis].reshape(3, 3)
                yaw = math.atan2(rotation[1, 0], rotation[0, 0])
                command = route.command(data.qpos[:2], yaw, t, dt)
                phase = (phase + dt / .6) % 1.0
                gait = [math.sin(phase * 2 * math.pi), math.cos(phase * 2 * math.pi)]
                if np.linalg.norm(command) < .1:
                    gait = [0, 0]
                obs = np.concatenate([data.sensor('imu_ang_vel').data,
                                      rotation.T @ [0, 0, -1], command, gait,
                                      data.qpos[7:] - default, data.qvel[6:], action]).astype(np.float32)[None]
                action = session.run(None, {input_name: obs})[0].reshape(-1)
                assert np.isfinite(action).all()
                data.ctrl[:] = offset + action * scale
                for substep in range(decimation):
                    data.xfrc_applied[torso, :3] = average_force(
                        task.get('pushes', []), t + substep * model.opt.timestep,
                        model.opt.timestep)
                    mujoco.mj_step(model, data)
                mujoco.mj_forward(model, data)
                record = {'time': (step + 1) * dt, 'phase': route.phase,
                          'position': data.qpos[:3].tolist(),
                          'command': command.tolist(),
                          'force': average_force(task.get('pushes', []), t, dt).tolist(),
                          'joint_position': data.qpos[7:].tolist(),
                          'joint_velocity': data.qvel[6:].tolist(),
                          'joint_torque': data.qfrc_actuator[6:].tolist(),
                          'action': action.tolist(), 'qpos': data.qpos.tolist(),
                          'wall_clearance_point': wall_clearance(data.qpos[:2], task.get('walls', []))}
                records.append(record)
                log.write(json.dumps(record) + '\n')
                if writer and step % every == 0:
                    camera.lookat[:] = data.qpos[:3]
                    renderer.update_scene(data, camera=camera, scene_option=visual)
                    writer.append_data(renderer.render())
                upright = data.xmat[pelvis].reshape(3, 3)[2, 2]
                if upright < math.cos(math.radians(70)) or data.qpos[2] < .35:
                    result = 'terminated'
                    break
                if route.complete:
                    result = 'success'
                    break
        elapsed = time.perf_counter() - started
        summary = {'result': result, 'completed_subgoals': route.phase,
                   'total_subgoals': len(task['waypoints']), 'steps': len(records),
                   'simulated_seconds': len(records) * dt, 'wall_seconds': elapsed,
                   'policy': 'unitree-released-velocity-v0', 'seed': args.seed}
        write_json(output / 'summary.json', summary)
        np.savez_compressed(output / 'trace.npz', **{
            key: np.array([r[key] for r in records]) for key in
            ['time', 'position', 'command', 'force', 'qpos', 'action', 'joint_torque']})
        plot_trace(output, records)
        print(json.dumps(summary, indent=2), '\nArtifacts:', output, flush=True)
    finally:
        if writer:
            writer.close()
        if renderer:
            renderer.close()
