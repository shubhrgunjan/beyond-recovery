# Live-console validation — 2026-11-15

The primary service is `br live --port 8080` on Thor, exposed by the existing Tailscale SSH tunnel. The old replay service has been replaced. Initial state is ready on the open-floor test; physics advances after Start.

Validated on the actual Thor service:

- Robot state and simulated time advance under the published policy.
- Pause freezes simulated time; single-step advances exactly 0.02 seconds.
- Manual driving, its watchdog, manual torso force pulses and scheduled pulses are processed by the physics owner and logged.
- WebSocket messages contain current poses and telemetry; a reconnect includes recent history.
- Stop finalizes all recording artifacts and publishes downloadable links.
- An immediate stop at 0.00 seconds also produces a nonempty video, figures, trace, event/telemetry logs and manifest.
- All eight physical scene configurations load.
- A full live open-floor task succeeds: four subgoals in 41.86 simulated seconds.
- A live compound-disturbance trial falls at 8.10 seconds and finalizes automatically.
- Eight targeted unit/integration tests pass. Frontend bundling, JavaScript syntax and Python compilation pass.

The robot's browser asset is about 2.6 MB, simplified for visualization only; collision/physics geometry is not simplified. Browser code is bundled locally with no external asset/CDN requirement.

The doorway return route was corrected to pass back through the opening rather than cross the solid wall. A regression test checks every crossing of the wall plane. Earlier user and verification trials remain saved with their exact original task definitions; they were not overwritten or relabeled as corrected trials.

Browser automation was unavailable, so there is no claim of an automated visual/camera/layout test. Live protocol controls, generated simulator recordings/plots and static frontend checks were verified. The user can exercise camera behavior directly in the live console.

Raw verification reports are on Thor under `artifacts/live-validation.json` and `artifacts/live-immediate-stop.json`, with protocol output in `live-verification-final.log` and test output in `live-tests-final.log`. All trials are in `artifacts/live/`.
