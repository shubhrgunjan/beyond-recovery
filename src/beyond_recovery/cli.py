"""Remote simulation, baseline training, and reproducible task evaluation."""

import argparse
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import time

os.environ.setdefault("MUJOCO_GL", "egl")
os.environ.setdefault("WANDB_MODE", "disabled")
os.environ.setdefault("OMP_NUM_THREADS", "4")

import numpy as np
import yaml

from beyond_recovery.task import Route, average_force, wall_clearance

ROOT = Path(__file__).resolve().parents[2]


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def provenance():
    packages = {}
    for name in ("torch", "mujoco-core", "mujoco-warp", "warp-lang", "mjlab", "rsl-rl-lib"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    digest = hashlib.sha256()
    for path in sorted((ROOT / 'src').rglob('*.py')):
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return {"python": platform.python_version(), "machine": platform.machine(),
            "project_source_sha256": digest.hexdigest(),
            "packages": packages,
            "upstream_revision": json.loads((ROOT / "configs/upstream.json").read_text())}


def doctor(args):
    import torch
    from beyond_recovery.environment import config
    from mjlab.envs import ManagerBasedRlEnv
    from mjlab.rl import MjlabOnPolicyRunner, RslRlVecEnvWrapper
    from mjlab.tasks.registry import load_rl_cfg
    from beyond_recovery.environment import TASK
    assert torch.cuda.is_available(), "CUDA is required on the Thor"
    x = torch.randn(256, 256, device="cuda")
    assert torch.isfinite(x @ x).all()
    cfg = config(num_envs=args.num_envs)
    env = ManagerBasedRlEnv(cfg=cfg, device="cuda:0", render_mode="rgb_array")
    env.reset(seed=0)
    start = time.perf_counter()
    for _ in range(10):
        env.step(torch.zeros((args.num_envs, env.action_manager.total_action_dim), device="cuda"))
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - start
    image = env.render()
    assert image is not None and image.ndim == 3
    agent = load_rl_cfg(TASK)
    agent.logger, agent.upload_model = "tensorboard", False
    runner = MjlabOnPolicyRunner(RslRlVecEnvWrapper(env), asdict(agent),
                                str(ROOT / "artifacts/doctor-ppo"), "cuda:0")
    runner.learn(num_learning_iterations=1, init_at_random_ep_len=False)
    report = provenance() | {"gpu": torch.cuda.get_device_name(),
                            "gpu_capability": list(torch.cuda.get_device_capability()),
                            "num_envs": args.num_envs, "steps_seconds": elapsed,
                            "render_shape": list(image.shape), "ppo_update": True}
    write_json(ROOT / "artifacts/doctor.json", report)
    import imageio.v2 as imageio
    imageio.imwrite(ROOT / "artifacts/doctor.png", image)
    env.close()
    print(json.dumps(report, indent=2))


def train(args):
    from beyond_recovery.environment import TASK, config
    from mjlab.scripts.train import TrainConfig, launch_training
    from mjlab.tasks.registry import load_rl_cfg
    cfg = config(num_envs=args.num_envs, seed=args.seed, baseline=args.baseline)
    agent = load_rl_cfg(TASK)
    agent.seed = args.seed
    if args.baseline != "upstream":
        agent.actor.distribution_cfg["init_std"] = 0.5
    agent.logger, agent.upload_model = "tensorboard", False
    agent.max_iterations = args.iterations
    agent.save_interval = args.save_interval
    agent.experiment_name = f"g1_{args.baseline}"
    agent.run_name = f"seed{args.seed}"
    if args.resume:
        agent.resume = True
        checkpoint = Path(args.resume).resolve()
        agent.load_run = checkpoint.parent.name
        agent.load_checkpoint = checkpoint.name
        if checkpoint.parent.parent != (ROOT / "logs" / agent.experiment_name).resolve():
            raise ValueError("Resume checkpoint must belong to this baseline's logs directory")
    write_json(ROOT / "artifacts" / f"train_{args.baseline}_seed{args.seed}.json",
               provenance() | vars(args))
    launch_training(TASK, TrainConfig(env=cfg, agent=agent, log_root=str(ROOT / "logs")))


def benchmark(args):
    import torch
    from beyond_recovery.environment import config
    from mjlab.envs import ManagerBasedRlEnv
    results = []
    for count in args.counts:
        env = ManagerBasedRlEnv(cfg=config(num_envs=count), device="cuda:0")
        try:
            env.reset(seed=0)
            action = torch.zeros((count, env.action_manager.total_action_dim), device="cuda")
            for _ in range(10):
                env.step(action)
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()
            start = time.perf_counter()
            for _ in range(args.steps):
                env.step(action)
            torch.cuda.synchronize()
            elapsed = time.perf_counter() - start
            row = {"num_envs": count, "steps": args.steps, "seconds": elapsed,
                   "transitions_per_second": count * args.steps / elapsed,
                   "aggregate_sim_seconds_per_wall_second": count * args.steps * env.step_dt / elapsed,
                   "torch_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                   "note": "Zero-action physics benchmark; Torch allocation excludes Warp/driver memory"}
            results.append(row)
            print(json.dumps(row), flush=True)
        finally:
            env.close()
    write_json(ROOT / "artifacts/benchmark.json", provenance() | {"results": results})


def resolve_checkpoint(value):
    if value != "latest":
        path = Path(value).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        return path
    files = list((ROOT / "logs").glob("g1_*/*/model_*.pt"))
    if not files:
        raise FileNotFoundError("No policy checkpoint: train a baseline first")
    return max(files, key=lambda p: p.stat().st_mtime)


def rollout(args):
    import torch
    import imageio.v2 as imageio
    from beyond_recovery.environment import make_env, make_policy, set_command
    config_path = Path(args.config)
    task = yaml.safe_load(config_path.read_text())
    if args.duration:
        task["duration"] = args.duration
    checkpoint = resolve_checkpoint(args.checkpoint)
    output = Path(args.output or f"artifacts/{task['name']}_seed{args.seed}_{time.time_ns()}")
    output.mkdir(parents=True, exist_ok=False)
    (output / "task.yaml").write_text(yaml.safe_dump(task))
    write_json(output / "manifest.json", provenance() | {
        "checkpoint": str(checkpoint), "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "seed": args.seed, "task": task, "auto_reset": False, "backend": "mujoco-warp",
    })
    env = make_env(task, args.seed, args.video)
    writer = None
    records = []
    result = "timeout"
    started = time.perf_counter()
    try:
        wrapper, policy = make_policy(env, checkpoint)
        env.reset(seed=args.seed)
        robot = env.scene["robot"]
        torso_ids, _ = robot.find_bodies("torso_link")
        route = Route(task)
        dt = env.step_dt
        render_every = max(1, round(1 / (args.fps * dt)))
        actual_fps = 1 / (render_every * dt)
        if args.video:
            writer = imageio.get_writer(output / "rollout.mp4", fps=actual_fps,
                                        codec="libx264", quality=7, macro_block_size=8)
        forces = torch.zeros((1, 1, 3), device=env.device)
        torques = torch.zeros_like(forces)
        with (output / "telemetry.jsonl").open("w") as telemetry, torch.inference_mode():
            for step in range(int(np.ceil(task["duration"] / dt))):
                t = step * dt
                pos = robot.data.root_link_pos_w[0].cpu().numpy().copy()
                yaw = robot.data.heading_w[0].item()
                command = route.command(pos[:2], yaw, t, dt)
                set_command(env, command)
                force = average_force(task.get("pushes", []), t, dt)
                forces[:] = torch.as_tensor(force, device=env.device)
                robot.write_external_wrench_to_sim(forces, torques, body_ids=torso_ids)
                # Refresh the command observation before policy inference.
                obs = wrapper.get_observations()
                action = policy(obs)
                _, reward, done, extra = wrapper.step(action)
                post_pos = robot.data.root_link_pos_w[0].cpu().numpy().copy()
                record = {"time": (step + 1) * dt, "command_time": t,
                          "phase": route.phase, "position": post_pos.tolist(),
                          "yaw": robot.data.heading_w[0].item(),
                          "velocity": robot.data.root_link_lin_vel_w[0].cpu().tolist(),
                          "gravity": robot.data.projected_gravity_b[0].cpu().tolist(),
                          "command": command.tolist(), "force": force.tolist(),
                          "reward": reward[0].item(),
                          "joint_position": robot.data.joint_pos[0].cpu().tolist(),
                          "joint_velocity": robot.data.joint_vel[0].cpu().tolist(),
                          "joint_torque": robot.data.qfrc_actuator[0].cpu().tolist(),
                          "action": action[0].cpu().tolist(),
                          "wall_clearance_point": wall_clearance(post_pos[:2], task.get("walls", [])),
                          "terminated": bool(done[0])}
                records.append(record)
                telemetry.write(json.dumps(record) + "\n")
                if writer and step % render_every == 0:
                    writer.append_data(env.render())
                if bool(done[0]):
                    result = "terminated"
                    break
                if route.complete:
                    result = "success"
                    break
        elapsed = time.perf_counter() - started
        summary = {"result": result, "completed_subgoals": route.phase,
                   "total_subgoals": len(task["waypoints"]), "steps": len(records),
                   "simulated_seconds": len(records) * dt, "wall_seconds": elapsed,
                   "sim_seconds_per_wall_second": len(records) * dt / elapsed,
                   "control_dt": dt, "physics_dt": env.physics_dt,
                   "seed": args.seed, "checkpoint": str(checkpoint)}
        write_json(output / "summary.json", summary)
        np.savez_compressed(output / "trace.npz", time=[r["time"] for r in records],
                            position=[r["position"] for r in records],
                            command=[r["command"] for r in records],
                            force=[r["force"] for r in records],
                            joint_position=[r["joint_position"] for r in records],
                            joint_velocity=[r["joint_velocity"] for r in records],
                            joint_torque=[r["joint_torque"] for r in records],
                            action=[r["action"] for r in records])
        plot_trace(output, records)
        print(json.dumps(summary, indent=2), "\nArtifacts:", output)
    finally:
        if writer is not None:
            writer.close()
        env.close()


def plot_trace(output, records):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    t = np.array([r["time"] for r in records])
    p = np.array([r["position"] for r in records])
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    axes[0].plot(p[:, 0], p[:, 1])
    axes[0].set(xlabel="x (m)", ylabel="y (m)", title="Executed route", aspect="equal")
    axes[1].plot(t, p[:, 2])
    axes[1].set(xlabel="Time (s)", ylabel="Pelvis height (m)")
    axes[2].plot(t, [np.linalg.norm(r["force"]) for r in records])
    axes[2].set(xlabel="Time (s)", ylabel="Applied force (N)")
    fig.tight_layout()
    fig.savefig(output / "telemetry.png", dpi=140)
    plt.close(fig)


def view(args):
    import viser
    from beyond_recovery.environment import TASK
    from mjlab.scripts.play import PlayConfig, run_play
    from mjlab.viewer import ViserPlayViewer
    # Upstream accepts an externally constructed loopback-only server.
    original = ViserPlayViewer.__init__
    def init(self, *a, **kw):
        kw["viser_server"] = viser.ViserServer(host="127.0.0.1", port=args.port)
        original(self, *a, **kw)
    ViserPlayViewer.__init__ = init
    run_play(TASK, PlayConfig(checkpoint_file=str(resolve_checkpoint(args.checkpoint)),
                             num_envs=1, viewer="viser"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("doctor", help="Test CUDA, contacts, rendering and one PPO update")
    p.add_argument("--num-envs", type=int, default=4)
    p = sub.add_parser("train", help="Train standard G1 PPO locomotion")
    p.add_argument("--baseline", choices=["nominal", "randomized", "upstream"], default="nominal")
    p.add_argument("--num-envs", type=int, default=256)
    p.add_argument("--iterations", type=int, default=3000)
    p.add_argument("--save-interval", type=int, default=100)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--resume")
    p = sub.add_parser("rollout", help="Execute an uninterrupted task and save telemetry")
    p.add_argument("--config", default="configs/t0.yaml")
    p.add_argument("--checkpoint", default="latest")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--duration", type=float)
    p.add_argument("--video", action="store_true")
    p.add_argument("--fps", type=int, default=25)
    p.add_argument("--output")
    p = sub.add_parser("live", help="Live Thor physics, local 3D console, automatic trial recording")
    p.add_argument("--port", type=int, default=8080)
    p = sub.add_parser("replay", help="Inspect a recorded reference trial in the browser")
    p.add_argument("--run", required=True)
    p.add_argument("--port", type=int, default=8080)
    p = sub.add_parser("view", help="Interactive upstream G1 viewer with velocity controls")
    p.add_argument("--checkpoint", default="latest")
    p.add_argument("--port", type=int, default=8080)
    p = sub.add_parser("benchmark", help="Measure batched physics throughput after warmup")
    p.add_argument("--counts", nargs="+", type=int, default=[64, 128, 256, 512])
    p.add_argument("--steps", type=int, default=100)
    p = sub.add_parser("reference", help="Run Unitree's released ONNX walking policy in native MuJoCo")
    p.add_argument("--config", default="configs/t0.yaml")
    p.add_argument("--duration", type=float)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--video", action="store_true")
    p.add_argument("--fps", type=int, default=25)
    p.add_argument("--output")
    args = parser.parse_args()
    if hasattr(args, "num_envs") and args.num_envs < 1:
        parser.error("--num-envs must be positive")
    if hasattr(args, "fps") and args.fps < 1:
        parser.error("--fps must be positive")
    if args.command == "live":
        from beyond_recovery.live import run
        run(args)
    elif args.command == "reference":
        from beyond_recovery.reference import run
        run(args)
    elif args.command == "replay":
        from beyond_recovery.replay import run
        run(args)
    else:
        globals()[args.command](args)


if __name__ == "__main__":
    main()
