# Baseline validation — 2026-11-15

These are deterministic pilot runs of the released Unitree G1 velocity policy in our native MuJoCo adapter. They validate the environment and expose a failure case; they are not statistical evidence for the research hypothesis.

| Task | Outcome | Subgoals | Simulated time |
|---|---|---|---|
| t0 | success | 4/4 | 40.94 s |
| t0_endurance | success | 12/12 | 122.56 s |
| t0_push | success | 4/4 | 43.62 s |
| t1_compound | terminated | 0/5 | 8.44 s |
| t1_narrow | success | 5/5 | 65.68 s |
| t1_wide | success | 7/7 | 86.84 s |

All tasks execute continuously without intermediate resets. The mild-push trial applies two 12 N·s pulses. The compound pilot applies two 40 N·s pulses and terminates after losing upright posture/height; it is intentionally a stress case, not a calibrated distribution.

Remote recordings and telemetry are in `artifacts/reference-final/`. Local copies are in `artifacts/thor/reference-final/`. The browser replay uses the full T0 recording; TensorBoard shows ongoing PPO training.

The independently trained PPO baseline has passed an optimizer-update test and is still learning. Its iteration-300 checkpoint stayed upright for a 120-second evaluation but completed zero route subgoals, so it is not yet a working locomotion baseline. A working reference-policy demonstration does not establish that the PPO checkpoint has converged. The raw upstream reward pilot learned early termination; nominal/randomized variants use the documented conventional survival/fall penalty changes.

GPU smoke tests cover CUDA tensors, batched physics, rendering and a PPO update. Four targeted tests cover force timing, task dwell/completion, wall geometry and an uninterrupted GPU step. Native policy trials exercise all six scenario configurations. Browser replay and TensorBoard both respond over the SSH tunnel.

No physical robot, calibrated recovery estimator, adversarial generator or recoverability-preservation algorithm has been validated.
