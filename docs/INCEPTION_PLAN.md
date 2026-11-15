# Beyond Recovery — inception plan

Date: 2026-11-15. Status: baseline implementation is installed on Thor. CUDA, batched physics, headless rendering and a PPO update pass. The released Unitree G1 reference policy completes the route suite, including a 122.56-second, 12-subgoal trial. A compound-disturbance pilot terminates at 8.44 seconds. Nominal PPO training is running; convergence is not established. See README.md for the implemented commands and policy distinctions. Later preservation/recovery-learning milestones remain research work.

## 1. Purpose and first deliverable

Build a reproducible humanoid simulation laboratory in which we can watch standard policies execute long-horizon tasks, inspect their failures, and measure whether task decisions consume future recovery capability. Establish ordinary-policy and ordinary-training results before implementing the proposed preservation algorithm.

First visible deliverable: a G1 walks a multi-stage route, turns, stops at a station, and returns. Show a clean run and a reproducibly disturbed run, with synchronized video and telemetry. Then introduce a short/narrow route and a longer/wider route to expose the trade-off between task progress and corrective stepping space.

Research hypothesis: at matched task progress and comparable resource budgets, a policy that preserves task-resuming recovery capability completes more tasks under held-out disturbances. A robot standing still, taking arbitrarily long detours, or abandoning its payload must not win this comparison.

The first build is a baseline laboratory. Adversarial exploration, learned recoverability estimation, and recovery learning are later experiments within the same interfaces.

## 2. Verified infrastructure

Observed through SSH over Tailscale on 2026-11-15; values are snapshots, not resource reservations.

| Item | Observation | Consequence |
|---|---|---|
| Local workstation | x86_64; 7.1 GiB usable RAM, about 1.8 GiB available | Editing, SSH, plots, and video playback locally; heavy jobs remotely |
| Thor access | `saidevdhal@agx-thor.taila0fc70.ts.net` | SSH succeeded using the host keys advertised by the Tailscale peer |
| Thor architecture / OS | aarch64; Ubuntu 26.04.1 LTS | ARM64 dependencies required; do not use x86 installer instructions |
| Thor memory | 122 GiB total; about 103 GiB available | Shared CPU/GPU memory; measure peak use under actual workloads |
| Thor storage | 936 GiB root volume; 176 GiB available | Cap checkpoints, caches, and videos; avoid unnecessary large images |
| Thor GPU | NVIDIA Thor; driver 595.78 | CUDA execution must still be tested inside the chosen environment |
| Driver CUDA capability | `nvidia-smi` reports 13.2 | This does not establish an installed CUDA toolkit or framework compatibility |
| Jetson Linux | release R39, revision 2.1 | Select packages for the actual installed platform |
| Python | default 3.14.4; `/usr/bin/python3.12` is 3.12.3 | Prefer an explicit Python 3.12 environment |
| Existing sim environment | `~/sim-env` resolves to Python 3.14 despite a 3.12-named symlink | Do not reuse based on its filename |
| Docker | executable exists; current account gets socket permission denied | Use a dedicated venv first; container option requires access repair |
| Utilities | SSH, rsync, tmux, ffmpeg available | Remote jobs, artifact synchronization, and recordings are feasible |
| Existing workloads | Other GPU processes active | Preserve other projects and processes; benchmark available capacity |

No prior local source, Asimov policies, recovery checkpoints, or working training environment were found in this project. Earlier conversational claims about available policies are unverified. Installed packages inside other projects were not exhaustively inventoried.

## 3. Technology decisions

| Component | Initial choice | Rationale / condition |
|---|---|---|
| Physics | MuJoCo CPU for reference rollouts; MuJoCo Warp for batched GPU training | Native inspection plus scalable training; compare contact behavior across backends |
| Training framework | mjlab with its compatible RSL-RL PPO implementation | Existing G1 velocity-tracking recipe; avoid building a trainer from scratch |
| Robot | Unitree G1 configuration matching the selected upstream task and checkpoint | Start from a supported controller/model pair; record exact actuated joints |
| Robot extension | Asimov-1 after model/checkpoint audit | Relevant future morphology; do not assume G1 weights transfer |
| Learning | PyTorch, compatible ARM64 CUDA build | Verify kernels on this Thor, then pin the successful build |
| Runtime | Dedicated Python 3.12 venv under the new remote project directory | Avoid changing system Python or other projects |
| Configuration | Versioned YAML task, disturbance, and experiment files | Reproduce runs and keep train/evaluation settings explicit |
| Viewer | mjlab's supported browser viewer through SSH forwarding | Thin local display; simulation and inference stay on Thor |
| Recording | Remote headless rendering plus MP4; numerical traces independently logged | Videos remain usable if interactive viewing is unavailable |
| Metrics | JSONL summaries, NPZ state traces, TensorBoard; Matplotlib for reports | Offline operation, no external account required |
| Jobs / transfer | tmux, SSH, rsync | Keep rollouts running if the workstation disconnects |
| Test tooling | pytest for restore, disturbance, adapter, and metric correctness | Protect experimental validity rather than mirror implementation |

mjlab currently documents G1 training and MuJoCo Warp integration [S1, S2]. Unitree also provides its own mjlab-based implementation [S3]. Select one primary implementation and lock its compatible dependencies; do not combine unrelated versions from both repositories.

Version policy: inspect release/tag metadata and dependency constraints at setup time, resolve a coherent ARM64 stack, run the compatibility gates, then record exact commits, package versions, wheel provenance, and checkpoint hashes. Do not install moving `main` branches for reproducible experiments. The fetched mjlab metadata requires recent Torch/Warp versions [S4]; a generic Jetson PyTorch image is not automatically compatible.

Fallback: if GPU training fails on Thor, retain native MuJoCo evaluation and investigate a compatible tagged stack. Small CPU PPO runs can validate plumbing but are not a substitute for measured GPU training throughput. Evaluate MuJoCo Playground/JAX only as a deliberate fallback, not as a second parallel training stack.

## 4. Control hierarchy

VLA and language-model integration have been removed from scope at the user's request.
The task sequencer supplies waypoints to a velocity follower, which commands a learned
G1 locomotion policy. Joint targets drive the upstream actuator model in MuJoCo.
Preserve the checkpoint's observation order, normalization, action scale and decimation.

## 5. Baseline policies and learning sequence

| Baseline | What it establishes | Availability |
|---|---|---|
| PD posture hold | Model loads, actuator signs/gains and contacts make sense | Implement as a diagnostic; not a locomotion baseline |
| Standard velocity-tracking PPO | Ordinary learned walking with the upstream reward/configuration | Use compatible released weights if verified; otherwise train |
| PPO plus domain randomization | Standard robustness to selected pushes, friction and inertial variation | Train with documented distributions and matched budgets |
| Task-only route policy | Ordinary task progress under a fixed low-level controller | Start with scripted route selection; then train a small high-level PPO policy |
| Reactive recovery baseline | Response after a disturbance or trigger | Add only once the recovery behavior is independently validated |
| Simple preservation baseline | Slowdown/clearance heuristic or measured-recoverability threshold | Needed before claiming value from a new learned algorithm |

Train short-horizon locomotion first; evaluate its use over genuinely long task sequences. Do not expect a flat-walking checkpoint to handle carrying, reaching, bracing, or standing up. Each additional skill needs a compatible trained controller and validation.

Recovery portfolio starts small: (1) in-place stabilization and (2) corrective stepping, with explicit skill-conditioned variants where necessary. If both are merely outcomes of one controller and cannot be selected independently, report one recovery policy with multiple observed behaviors, not two independent options. Bracing, safe falling, and get-up enter only after separate training and contact/task validation. Some tasks must label a fall as failure even if get-up succeeds.

For the first causal comparison, freeze the same low-level and recovery controllers across task policies. Otherwise, better recovery skill could be mistaken for better option preservation.

## 6. Long-horizon task suite

Build parametric indoor scenes rather than a visually elaborate world. Suggested durations are targets, not achieved capabilities. Register subgoal completion, timeouts, failure conditions, task state, and phase boundaries explicitly.

| Task | Sequence / target duration | Research variable | Stage |
|---|---|---|---|
| T0: route loop | Stand, walk to stations A/B/C, turn, dwell, return; 60–120 simulated seconds | Basic policy reliability and accumulated errors | First demo |
| T1: route choice | Repeated delivery-like visits via short/narrow or long/wide passages; 90–180 s | Corrective-step clearance versus route cost | First research scene |
| T2: stop and reach | Approach station, stop, reach a target, retract, continue; 60–150 s | Arm configuration and balance authority | After whole-body skill works |
| T3: load transport | Carry from A through route choices to B, place, return; 90–240 s | Payload retention, posture, momentum and task commitment | After carrying/placement skills work |
| T4: compound challenge | T1/T3 with separated pushes, slip regions, or brief actuation degradation | Sequential loss of recovery alternatives | After single-event calibration |

T1 is the initial controlled experiment: alter corridor clearance while holding route stage, speed, and disturbance conditions comparable. A scene is useful only if ordinary policies succeed often enough without perturbations to distinguish fragility from inability to perform the task.

T3 begins, if needed, with a torso-mounted inertial payload to study locomotion under load. Label it as an attached-load approximation. Actual carrying requires object contacts, grasp retention and placement; it is a separate milestone. No invisible weld should be presented as dexterous transport.

## 7. Disturbance protocol

Implement event schedules with seeded parameters, affected body/site, onset, duration, and logged realized values. Initial families:

- External force pulses: vary direction, duration and impulse; report N and N·s, and impulse relative to robot mass. Apply forces through physics rather than teleporting velocity in the headline experiments.
- Friction: fixed spatial low-friction patches first; evaluate contact-consistent friction changes separately.
- Payload: mass and center-of-mass offsets within explicit bounds.
- Actuation: bounded torque derating or command delay, introduced after the nominal actuator model is validated.

Select ranges from isolated pilot sweeps: include mild disturbances that a nominal policy usually survives and a nontrivial transition to failure. Publish the resulting numerical ranges before the main comparison. Do not silently tune evaluation difficulty to favor our method.

Separate nominal, randomized-training, held-out single-event, and held-out compound-event sets. Split layouts, seeds, timings and disturbance combinations; include held-out magnitudes/directions without conflating all generalization tests. A learned adversary trains on its own set; final tests include fixed independent scenarios. Give every compared method the same event budget and information.

Do not reset between long-horizon subgoals. Recovery must happen in the actual current state. Save/restore is permitted in offline measurement branches, never as execution-time recovery.

## 8. Measuring recoverability before learning it

First build an empirical branching evaluator. Save complete simulator and controller/task state at selected trajectory points. Restore each checkpoint into independent branches, apply sampled disturbance sequences, invoke each available recovery option, and test whether the robot stabilizes and resumes the task within a defined horizon.

State restoration includes physics integration state, modified model parameters, controller recurrent/history buffers, action queues, task phase, object/grasp state, disturbance scheduler and RNG state. Compare restored and uninterrupted trajectories within numerical tolerance. GPU and CPU engines need not be bit-identical; validate behavior and contact statistics before transferring labels between them.

Define each estimate relative to a disturbance distribution D, option set O, recovery horizon H_r, task-resumption horizon H_t, and task state z. Task state includes completed subgoals and payload constraints. An initial diagnostic is:

    R_selector(s,z) = P[the specified option selector chooses a recovery
                        that stabilizes by H_r and resumes the task by H_t]

Also report option-wise success probabilities and an offline oracle portfolio score. The oracle selects a successful option after seeing the disturbance realization and is an upper bound; it is not an executable recovery guarantee. Later causal selectors can observe the disturbance only through available measurements. Do not confuse max-over-options expected success with the probability that some option would have worked for each sampled event.

For pilot measurements, try H_r = 3–5 s and H_t = 10–20 s, then freeze task-specific definitions based on dynamics. Stability requires sustained posture/velocity/contact conditions, not a single upright frame. Task resumption requires observable progress on an unfinished subgoal while respecting the payload/task constraints.

Budget example: 20 checkpoints × 16 disturbance samples × 2 options × 5 s = 3,200 simulated seconds per episode before additional task continuation. Sample sparsely, batch branches, and measure cost. These are initial diagnostic estimates, not calibrated guarantees. Report Monte Carlo uncertainty; do not claim an LCB is valid against unseen dynamics simply because it has a binomial interval.

Once labels are reliable, train a task-conditioned estimator and evaluate calibration on held-out episodes and disturbance families. Search for option-loss boundaries with bounded simulator-based adversarial sampling before introducing a learned world model. Dreaming adds value only if it improves search/data efficiency without producing misleading dynamics.

## 9. Metrics and experimental comparisons

Primary outcomes:

- Whole-task completion and completion time, with timeouts counted as failures.
- Task resumption following disturbances, including preservation of object/task commitments.
- Empirical recovery probability over task progress, with uncertainty and evaluation cost.
- Exposure below a specified recoverability threshold, versus useful progress.
- Falls, body/environment impacts, payload drops, energy and actuator saturation.
- Option-wise success and overlap of failures; count options only under a stated viability threshold.

Initial development: 10–20 seeded episodes per configuration. Formal comparisons: at least three independently trained seeds with paired evaluation scenarios; choose evaluation count by interval precision (100 episodes per condition is a starting target, not a sufficiency guarantee). Bootstrap at episode/training-seed level, not at every correlated timestep. Show task progress/time versus recoverability trade-offs rather than rewarding indefinite caution.

Preserve raw nominal results, training curves, checkpoints and disturbance manifests. Separate pretrained out-of-distribution evaluation from retrained baselines. For new preservation methods compare task-only PPO, domain randomization, reactive recovery, simple clearance/slowdown preservation, and preservation without adversarial sampling. Reproductions of named research systems require a separate verified paper/code audit; they are not initial infrastructure dependencies.

## 10. Remote workflow and resource budget

Local project: `/home/shubhr/Shubhr/Projects/Research/beyond-recovery`.
Remote project: `/home/saidevdhal/beyond-recovery` (created during implementation).

All simulation, training, model inference, headless rendering and large data stay on Thor. The workstation edits source, forwards the viewer/TensorBoard ports, and downloads selected MP4s and summaries. Keep the physical control loop entirely on Thor; network latency must not affect simulation dynamics.

Start with a 1-environment rollout; then benchmark 64, 128, 256 and 512 worlds, increasing only if throughput and memory improve. Report aggregate transitions/s, simulated seconds/wall-second, startup/JIT cost and peak unified memory. Upstream examples using thousands of worlds are not Thor capacity estimates. Render one demonstration environment; keep bulk PPO rollouts camera-free initially.

Initial project limits: target at most 48 GiB measured memory for training; leave at least 24 GiB available to the host/other workloads; maintain at least 60 GiB free disk; cap project artifacts at approximately 60 GiB including the environment and caches. Adjust batch sizes before violating these limits. Never terminate another project's jobs or alter global power/clock settings as part of this setup.

Keep best, latest and milestone checkpoints; record short fixed evaluation videos rather than all training frames. Use tmux and periodic resumable checkpoints. Set Torch/Warp caches within the project where practical. SSH host identity must remain verified; use an audited known-hosts entry, not disabled checking. Bind viewers to loopback and access through SSH forwarding.

## 11. Proposed repository layout

```text
docs/                   plan, infrastructure audit, experiment protocol
configs/                robot, task, disturbance and PPO configurations
src/beyond_recovery/
  robots/               model metadata and policy I/O adapters
  envs/                 scenes, task sequencer, rewards, terminations
  policies/             nominal / recovery / high-level policy interfaces
  disturbances/         reproducible event application
  evaluation/           branch restore, resumption and portfolio metrics
  recording/            viewer, telemetry and video synchronization
scripts/                doctor, play, train, evaluate, remote sync
tests/                  correctness checks for experimental machinery
third_party/            pinned external sources or revision manifests
artifacts/              ignored runtime outputs; authoritative copies on Thor
```

Intended entry points are `doctor`, `play`, `train`, `evaluate`, and `measure-recoverability`; exact CLI syntax will be documented only after implementation. Each run records source commit, configuration, dependencies, robot/checkpoint hashes, training/evaluation seeds and backend. Weight provenance includes observation normalization and licensing.

## 12. Implementation milestones and acceptance gates

| Milestone | Work | Evidence required to proceed |
|---|---|---|
| M0: compatibility | Dedicated remote directory/venv; resolve ARM64 Torch/MuJoCo/Warp/mjlab versions | CUDA tensor kernel, Warp kernel, batched contacts, headless video, one PPO update; exact manifest |
| M1: first robot | Import matched G1 model/policy; posture and locomotion checks | Watchable unassisted walking/turning/stopping video; units and policy I/O validated |
| M2: long task | Implement T0 and T1; task logs and disturbances | Clean and pushed runs; no hidden phase resets; reproducible event schedule |
| M3: ordinary training | Reproduce PPO, add domain randomization, train high-level route baseline | Training curves, three-seed plan, held-out route and disturbance results |
| M4: recovery measurement | Validate independently executable recovery behaviors and state branching | Paired checkpoints showing different recovery capacity; held-out task-resumption estimates |
| M5: preservation prototype | Clearance heuristic, learned estimator, bounded adversarial search | Gains at matched progress; estimator ablations; no stationary-policy loophole |
| M6: richer tasks | Whole-body tasks, payload contacts, whole-body control | Independent skill tests; validated control interfaces |
| M7: morphology / hardware | Asimov transfer and physical experiments if resources exist | New model/controllers validated; no assumption of cross-robot checkpoint compatibility |

If pretrained weights cannot be obtained or reproduced with matching model/configuration, M1 requires locomotion training before the first walking demo. If M0 GPU checks fail, fix/pin the stack before long jobs. If nominal T1 completion is poor, simplify the scene or improve baseline skills before studying recovery preservation. If different task decisions do not measurably change recoverability at comparable task progress, revise the task design or hypothesis before adding architecture.

Implementation effort is best estimated after M0 throughput and M1 checkpoint validation. There is no defensible training-runtime promise yet. The first implementation target is M0–M2, with ordinary-policy video as the visible result.

## 13. Decisions and open evidence

Decided for inception: Thor is the compute host; G1 is the initial reference morphology; MuJoCo + Warp/mjlab + PPO is the preferred stack; T0/T1 precede manipulation; task state and recoverability measurement are explicit; language models are outside scope.

Still to establish by implementation/audit: coherent ARM64 package versions; actual GPU throughput; usable checkpoint locations and licenses; the robot's physical task competence; independently valid recovery options; exact disturbance ranges and calibrated estimators. If the intended physical platform is Asimov, revisit robot choice before investing in payload/contact training. No user answer is required to begin M0–M2 with G1.

## Sources checked

- [S1: mjlab overview and G1 training](https://github.com/mujocolab/mjlab)
- [S2: MuJoCo Warp documentation and backend limitations](https://github.com/google-deepmind/mujoco_warp)
- [S3: Unitree's mjlab-based training implementation](https://github.com/unitreerobotics/unitree_rl_mjlab)
- [S4: mjlab dependency metadata](https://github.com/mujocolab/mjlab/blob/main/pyproject.toml)
- [S5: Asimov-1 source and simulation model](https://github.com/menloresearch/asimov-1)
- [S6: NVIDIA PyTorch for Jetson compatibility notes](https://docs.nvidia.com/deeplearning/frameworks/install-pytorch-jetson-platform-release-notes/pytorch-jetson-rel.html)
- [S7: Thor Docker setup](https://docs.nvidia.com/jetson/agx-thor-devkit/user-guide/latest/setup_docker.html)

Source links support component selection, not a claim that this combined system has already worked. Hardware observations above come from the SSH audit. This inception plan does not establish literature novelty.
