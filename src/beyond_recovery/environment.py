"""Pinned mjlab adapters. Upstream policy observation/action definitions are retained."""

from dataclasses import asdict

import mujoco
import torch

import mjlab.tasks  # Registers upstream tasks.
from mjlab.envs import ManagerBasedRlEnv
from mjlab.rl import MjlabOnPolicyRunner, RslRlVecEnvWrapper
from mjlab.tasks.registry import load_env_cfg, load_rl_cfg
from mjlab.envs import mdp
from mjlab.managers.reward_manager import RewardTermCfg

TASK = "Mjlab-Velocity-Flat-Unitree-G1"


def scene_geometry(spec, task):
    for i, wall in enumerate(task.get("walls", [])):
        spec.worldbody.add_geom(
            name=f"route_wall_{i}", type=mujoco.mjtGeom.mjGEOM_BOX,
            pos=wall["center"], size=wall["half_size"],
            rgba=[0.35, 0.45, 0.6, 1], contype=1, conaffinity=1,
        )
    for i, xy in enumerate(task["waypoints"]):
        spec.worldbody.add_site(
            name=f"station_{i}", type=mujoco.mjtGeom.mjGEOM_CYLINDER,
            pos=[*xy, 0.012], size=[0.22, 0.01, 0.01],
            rgba=[0.1, 0.8, 0.4, 0.7],
        )


def config(*, play=False, num_envs=1, seed=0, baseline="nominal", task=None):
    cfg = load_env_cfg(TASK, play=play)
    cfg.seed = seed
    cfg.scene.num_envs = num_envs
    # The upstream 20-step line search overflowed during the contact smoke test.
    cfg.sim.mujoco.ls_iterations = 50
    cfg.sim.mujoco.iterations = 50
    if baseline == "nominal" or play:
        for name in ("push_robot", "foot_friction", "encoder_bias", "base_com"):
            cfg.events.pop(name, None)
    if baseline != "upstream":
        # Prevent the early-termination shortcut observed in the pilot PPO run.
        cfg.rewards["termination"] = RewardTermCfg(func=mdp.is_terminated, weight=-200.0)
        cfg.rewards["alive"] = RewardTermCfg(func=mdp.is_alive, weight=0.5)
        cfg.rewards["action_rate_l2"].weight = -0.01
    if play:
        cfg.auto_reset = False
        cfg.curriculum = {}
        cfg.episode_length_s = task.get("duration", 120.0) + 1
        jitter = task.get("reset_jitter", {})
        position, yaw = jitter.get("position", 0), jitter.get("yaw", 0)
        cfg.events["reset_base"].params["pose_range"] = {
            "x": (-position, position), "y": (-position, position),
            "z": (0.02, 0.02), "yaw": (-yaw, yaw)
        }
        cmd = cfg.commands["twist"]
        cmd.heading_command = False
        cmd.ranges.heading = None
        cmd.rel_heading_envs = cmd.rel_standing_envs = 0.0
        cmd.rel_forward_envs = cmd.rel_world_envs = 0.0
        cmd.init_velocity_prob = 0.0
        cmd.resampling_time_range = (1e9, 1e9)
        cmd.ranges.lin_vel_x = cmd.ranges.lin_vel_y = cmd.ranges.ang_vel_z = (0, 0)
        cfg.scene.spec_fn = lambda spec: scene_geometry(spec, task)
        cfg.viewer.width, cfg.viewer.height = 960, 640
        cfg.viewer.distance = 4.0
        cfg.viewer.azimuth = 135.0
        cfg.viewer.elevation = -25.0
    return cfg


def make_policy(env, checkpoint):
    agent = load_rl_cfg(TASK)
    agent.logger = "tensorboard"
    agent.upload_model = False
    wrapper = RslRlVecEnvWrapper(env, clip_actions=agent.clip_actions)
    runner = MjlabOnPolicyRunner(wrapper, asdict(agent), device=env.device)
    runner.load(str(checkpoint), load_cfg={"actor": True}, map_location=env.device)
    return wrapper, runner.get_inference_policy(device=env.device)


def make_env(task, seed, video=False):
    return ManagerBasedRlEnv(
        cfg=config(play=True, task=task, seed=seed), device="cuda:0",
        render_mode="rgb_array" if video else None,
    )


def set_command(env, command):
    term = env.command_manager.get_term("twist")
    term.vel_command_b[:] = torch.as_tensor(command, device=env.device)
