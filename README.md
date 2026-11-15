# Beyond Recovery

[Public research site](https://beyond-recovery.vercel.app) · [Full report](https://beyond-recovery.vercel.app/report/) · [Data and downloads](https://beyond-recovery.vercel.app/downloads/) · [Raw research release](https://github.com/shubhrgunjan/beyond-recovery/releases/tag/research-2026-11-15) · [Live simulator](https://beyond-recovery.vercel.app/lab)

The public site is static and remains readable independently of Thor. The shared live lab runs native physics on AGX Thor through a Cloudflare Quick Tunnel. Its availability depends on Thor and the tunnel staying online; restarting the tunnel changes its address. Publication settings live in [deployment/public.json](deployment/public.json).

The overnight study saved 1,808 planned research trials. After ordinary task-control fixes, the tuned AMP controller completed the twelve-goal endurance route in 8/8 development seeds. Many initial failures were explained by steering and navigation; this is an instrumented baseline, **not a demonstrated recovery-preservation algorithm**. See the report for paired controls, repeated parent seeds, negative results and limits.

A humanoid baseline laboratory for studying whether task execution consumes future recovery options. Simulation and training run on the AGX Thor; the workstation only edits code and displays results. VLA integration is outside scope.

The environment is installed at `/home/saidevdhal/beyond-recovery` on `agx-thor.taila0fc70.ts.net`.

## Live test console

Open **[http://localhost:8080](http://localhost:8080)** and refresh the old page. This is a live simulation console. Native MuJoCo physics and the released walking policy execute on Thor; your browser renders streamed robot poses locally. The console starts ready, with no trial running.

1. Begin with **Open-floor reference**, read the highlighted test question, and click **Start live trial**.
2. Use **Follow**, **Overview**, **Side**, **Top**, or **Focus robot**. Drag to orbit, right-drag to pan, and scroll to zoom. Grabbing the camera turns follow off.
3. Watch task stations, progress, height, tilt, actuator use, and head/body contact forces. The static support-margin diagnostic is also recorded. Orange plot bands indicate an applied force.
4. Pause or advance exactly one 20 ms control step. Apply a bounded world-direction force pulse, or enable manual driving with WASD and Q/E.
5. Use **Stop & save**, or let success, timeout or an unrecovered fall end the trial. Balance loss itself continues through impact and get-up attempts for up to twenty simulated seconds. Changing scenes or restarting also saves the preceding trial.

Fourteen physical scenes include rough paving, open/constrained trip boxes, a low overhead beam, loading steps, warehouse/office/doorway tasks, a low-friction patch and a twelve-goal endurance route. These are tests of a baseline policy; no recoverability-preservation algorithm is active.

Every trial automatically saves video, per-step state/action/force telemetry, intervention events, configuration and provenance, compressed state traces, a summary, and six overview figures. **Saved trials** in the console links to these artifacts. The authoritative directory is `/home/saidevdhal/beyond-recovery/artifacts/live/` on Thor. Recordings use a fixed research camera independently of your browser camera.

The static support margin is the signed geometric distance of projected CoM from a contact polygon. Negative values can occur in normal dynamic walking. It is not a recoverability probability or a stability guarantee.

The configured SSH tunnel also exposes [TensorBoard](http://localhost:6006). If it disconnects, run `bash scripts/remote.sh tunnel` and keep that terminal open. Both services bind to Thor loopback. Start the live service remotely with `.venv/bin/br live --port 8080`; it runs in tmux session `br-live`. The old replay command is retained for archived data, but is not the primary interface.

Implementation, controls, APIs, and validation are documented in [docs/LIVE_CONSOLE.md](docs/LIVE_CONSOLE.md).

To download a particular live trial without its large logs:

```bash
# Run on this workstation; replace RUN_ID with the ID shown in Saved trials.
rsync -az -e 'ssh -o UserKnownHostsFile=.cache/thor_known_hosts' \
  saidevdhal@agx-thor.taila0fc70.ts.net:/home/saidevdhal/beyond-recovery/artifacts/live/RUN_ID/ \
  artifacts/live/RUN_ID/
```

Archived batch recordings remain in `artifacts/reference-final/` remotely and `artifacts/thor/reference-final/` locally. `scripts/remote.sh fetch` downloads that archived batch suite. Live trials are separate.

## Two distinct policy paths

**Released reference policy:** Unitree's G1 velocity ONNX policy, its deployment configuration and robot XML are pinned to commit `1425b15f73bd4095f0df53709d7c389c3eb9e790`, with checksums and license information in [configs/reference.json](configs/reference.json). Native MuJoCo physics and ONNX CPU inference both run on Thor. The adapter implements its 98-dimensional observation, command-gated gait phase, published joint order, action scales, gains, torque limits and initial posture. It uses the pinned mjlab visual meshes and reflected-inertia convention. This is a local simulation adapter, not a reproduction of Unitree's reported benchmark or physical validation.

**Trainable baseline:** mjlab G1 velocity tracking, PyTorch, MuJoCo Warp and PPO. It retains the upstream observation/action definitions, including simulator-derived base velocity. Its checkpoint format and observation space differ from the reference ONNX policy. Never interchange their weights.

Nominal and randomized training share a conventional locomotion reward configuration: a terminal-fall penalty of -200 (multiplied by the 0.02 s control interval by the reward manager), alive weight 0.5, action-change weight -0.01, and initial action standard deviation 0.5. These changes address the early-termination shortcut found in initial pilots. Neither baseline optimizes a recoverability measure. The `upstream` variant retains the upstream reward and randomization settings for comparison. All variants use solver and line-search budgets of 50 because the smaller upstream limits overflowed during contact tests.

`nominal` removes push, friction, encoder-bias and center-of-mass randomization. `randomized` retains those upstream events, including velocity-based training pushes. Evaluation uses actual external force pulses. Actor observation noise, initial-state sampling, velocity commands, and the upstream command curriculum remain part of ordinary training. The two simulation paths use different physics steps: 0.002 s for the released reference, 0.005 s for the GPU baseline, both with 0.02 s policy control. Their results should not be treated as a controlled algorithm comparison.

## Run experiments

From this workstation:

```bash
# Released policy on an uninterrupted long task; outputs run on Thor.
bash scripts/remote.sh run reference --config configs/t0_endurance.yaml --video

# Inspect the newest locally trained PPO checkpoint.
bash scripts/remote.sh run rollout --config configs/t0.yaml --checkpoint latest --video

# Start another training run only when the existing run is finished.
bash scripts/remote.sh run train --baseline randomized --num-envs 512 --iterations 1500 --seed 1

# Check the active job and resource use.
bash scripts/remote.sh status
```

An explicit checkpoint path is preferable to `latest` when comparing conditions. `latest` resolves once at the start of a rollout, so it does not change mid-trial. `scripts/evaluate_baselines.py` freezes a PPO checkpoint across multiple task/seed conditions; run it with the remote environment's Python.

Remote shell examples:

```bash
cd /home/saidevdhal/beyond-recovery
.venv/bin/python scripts/evaluate_baselines.py --checkpoint /absolute/path/model_1000.pt --seeds 0 1 2
.venv/bin/br replay --run artifacts/reference-final/t1_narrow --port 8081
```

The second example requires forwarding local port 8081 to Thor's loopback port 8081. `br view` provides the upstream interactive PPO viewer with velocity controls; `br replay` displays recorded reference trials. Both bind to loopback. The primary live service uses port 8080; start archived replay services on another forwarded port.

## Tasks

| Configuration | Purpose |
|---|---|
| `t0.yaml` | Visit four stations, turn, dwell, and return |
| `t0_push.yaml` | Same route with two 60 N, 0.2 s world-frame force pulses |
| `t0_endurance.yaml` | Three consecutive route loops, 12 subgoals, no intermediate resets |
| `t1_narrow.yaml` | Traverse a physical corridor and continue around a larger loop |
| `t1_wide.yaml` | Same walls and destination, with a longer route around the corridor |
| `t1_compound.yaml` | Exploratory sequential 160 N, 0.25 s pulses in the corridor task |

All values are pilot choices. Disturbance severity is not yet a calibrated benchmark distribution. The narrow/wide task pair exposes a geometric trade-off; it does not by itself prove one route preserves recoverability. Arrival requires continuous dwell inside the arrival radius. The legacy batch reference runner ends on falls or timeouts. The live AMP console continues through impact and physical get-up attempts, with a 20 s unrecovered-fall limit. There are no subgoal resets, teleports or hidden state rollback.

Provided reference tasks are deterministic. Repeating them with different seed labels alone does not create independent evidence. For randomized initial-condition pilots, add `reset_jitter: {position: 0.02, yaw: 0.02}` to a copied task YAML; the seed then controls bounded starting x/y and yaw offsets. Preserve the same disturbance schedule across paired conditions.

`wall_clearance_point` is distance from the pelvis's horizontal position to a wall surface. It is a geometric diagnostic, **not** body clearance or a recoverability probability. No learned recovery estimator, recovery portfolio, adversary or preservation algorithm has been claimed or implemented yet.

## Setup and reproducibility

Current stack: Python 3.12, Torch 2.14.0+cu130, MuJoCo/MuJoCo Warp 4.0.1, Warp 1.19.0, mjlab 1.6.0 and RSL-RL 5.5.2. The upstream mjlab source revision is recorded in [configs/upstream.json](configs/upstream.json). [requirements-thor.lock](requirements-thor.lock) records the installed dependency set. Exact run inputs, source checksums and policy hashes accompany outputs.

For a fresh checkout:

```bash
python3 scripts/fetch_upstream.py
python3 scripts/fetch_reference.py
python3 scripts/fetch_recovery.py
bash scripts/remote.sh sync
# On Thor, in the synced project:
bash scripts/bootstrap_thor.sh
```

The bootstrap uses an isolated venv; it does not change system Python, Docker access, clocks or other projects. [scripts/fix_thor_wheel.py](scripts/fix_thor_wheel.py) documents a required packaging repair: the pinned NVIDIA cuSPARSELt wheel's filename says `aarch64`, but its embedded platform tag says `sbsa`. The script verifies the original hash and corrects only WHEEL/RECORD metadata; it does not change library binaries or dependency versions. `pip check` passes after repair.

Validation:

```bash
# On Thor:
.venv/bin/br doctor
MUJOCO_GL=egl .venv/bin/python -m pytest tests -q
.venv/bin/br benchmark --counts 64 256 512
```

Doctor checks a CUDA matrix operation, batched physics/contact execution, rendering and a PPO update. Tests check force impulse timing, task state, physical corridor geometry and an uninterrupted GPU step. The initial zero-action physics benchmark is not policy/training throughput, and its Torch allocation counters exclude Warp/driver allocations.

The first training pilots are retained as diagnostics. Their low-reward/short-episode behavior is not a successful locomotion result. Training output remains in `train.log`; checkpoints and TensorBoard summaries are under `logs/g1_nominal/`. Completing a training run does not establish task competence.

Measured reference results and the limitations of the early PPO checkpoint are recorded in [docs/BASELINE_RESULTS.md](docs/BASELINE_RESULTS.md).

The broader research scope and later milestones are in [docs/INCEPTION_PLAN.md](docs/INCEPTION_PLAN.md).


The latest live-console changes and overnight experiments are described in [docs/LIVE_CONSOLE.md](docs/LIVE_CONSOLE.md). The checkpointed wake-up report is served at [localhost:8080/assets/research-report.html](http://localhost:8080/assets/research-report.html). Reports and raw trial records are authoritative on Thor; source synchronization excludes generated report assets so they cannot be overwritten by stale workstation copies.


## Public-site development and deployment

```bash
npm ci
npm run build
npm run test:publication
# Optional local static preview:
python3 -m http.server 8787 --directory public
```

The build uses Node only, copies the report/figures/recordings, replaces local-only report links, and creates the downloads index from `deployment/dataset-index.json`. `vercel.json` publishes `public/`; `/lab` redirects to the actual Thor host rather than running MuJoCo inside a serverless function. The linked Vercel project deploys the GitHub production branch. Credentials, `.env` files, `.vercel`, caches, upstream weights and multi-gigabyte raw artifacts are excluded from Git.

Raw archives are attached to the research GitHub Release with SHA-256 checksums. They restore original `artifacts/...` and `logs/...` paths when extracted into the repository. Downloading them is optional; the report and CSV tables are much smaller. [Publication operations](docs/PUBLICATION.md) documents updating the live tunnel and release. [Third-party provenance](THIRD_PARTY.md) identifies the upstream code and policies.
