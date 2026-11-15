# Live humanoid test console

The default interface at http://localhost:8080 is a live console. It replaces the Viser playback UI. All physics and policy inference execute on the AGX Thor. The browser only receives body poses and telemetry and renders a lightweight 2.6 MB robot asset with Three.js.

## What this tests

The baseline question is whether a policy that succeeds on a clear floor becomes fragile as its route limits stepping room, contacts or traction. Begin with the matched open-floor control. Fourteen scenes include physical rough slabs, a 13 cm trip box with open or constrained recovery space, a low overhead beam and loading steps. Compare it with the warehouse aisle, open detour or low-friction patch, and inspect the response to timed or manual pushes. The console describes each test's specific question and upcoming disturbance.

Scenes use actual fixed MuJoCo collision geometry: racks and boxes, desk and chair-shaped obstacles, doorway walls, and a friction-priority floor patch. The floor patch has friction 0.08 and a 1 cm lip; this is a traction-plus-small-lip experiment, not a pure friction-only ablation. The fixtures are static, and the robot uses the published idealized actuator setup. There is no payload manipulation or physical robot in this build.

The warehouse aisle and detour share scenery, policy, speed and a timed force pulse. They are exploratory tests, not a matched-progress causal experiment. Different routes encounter the timed pulse at different spatial/task states. Use the saved manifests and events to design controlled comparisons later.

## Controls

- **Start live trial:** create a unique recording and reset the selected scenario to its seeded initial state. Trial settings apply at this point.
- **Pause / Resume:** freeze or resume simulated time. Recording does not count paused wall time as simulation time.
- **Step 20 ms:** execute one policy step and ten 2 ms physics substeps while paused.
- **Stop & save:** end the current trial and finalize its artifacts. Starting again or selecting a different scene finalizes the previous trial first.
- **Force pulses:** apply bounded world-axis torso forces, with editable force and duration. These are physical forces, not velocity teleports. The orange arrow and plot bands indicate applied force.
- **Manual driving:** WASD commands body-frame walking velocity; Q/E commands yaw. Releasing the keys or losing focus zeros the command through a 350 ms watchdog. Manual interventions are logged; a manual trial is not an autonomous-policy benchmark.
- **Camera:** drag to orbit, right-drag to pan, scroll to zoom. Presets offer follow, overview, side and top views. Grabbing the camera disables follow so the camera does not fight the user.

A disconnected browser does not reset or pause the robot. The trial continues on Thor and saves when it finishes. On reconnect, the client receives the recent metric history. The UI reports a lost connection rather than continuing to label a frozen view as live.

The viewport uses 72% of the browser height, with fullscreen and focus modes. Start, pause, stop and push controls are also over the scene.

Choose the experimental **AMP walk + get-up** controller to observe physical get-up attempts. A detected fall does not freeze physics: the controller has up to 20 simulated seconds to regain standing. Recovery requires height >0.65 m, tilt <25° and bounded angular speed continuously for one second. The original route then continues; standing and task resumption are logged separately. No root pose reset is used during recovery. The original walking-only controller is available as a baseline, but has no trained get-up skill. The two controllers use different published actuator profiles; compare research conditions within one controller profile.

## Measurements

| Measurement | Meaning | Limitation |
|---|---|---|
| Task progress | Completed stations with continuous dwell inside the arrival radius | Does not measure recovery capacity |
| Pelvis height | Actual base height; balance loss is detected below 0.35 m | A fall detector, not a damage model |
| Base tilt | Angle between pelvis vertical and world vertical; balance loss is detected above 70° | Healthy gait may include temporary tilt |
| Actuator use | Maximum absolute actuator force divided by its torque limit | A control-authority proxy, not a viability estimate |
| Static support margin | Signed distance from CoM projection to the horizontal foot-contact hull | Dynamic walking can have negative margin; no stability certificate |
| Fixture contact steps | Control steps containing robot contact with elevated fixtures | Contact count does not quantify injury or damage |

Live charts show the last 30 simulated seconds. Saved figures cover the entire trial and also include actual planar speed and the executed x/y route. All values are measured from the running simulator. No learned recoverability score is fabricated.

## Automatic records

Each trial gets a unique ID under `artifacts/live/`:

- `manifest.json`: source checksum, reference-policy provenance, exact scenario, settings, simulator steps and modeling notes.
- `telemetry.jsonl`: every 20 ms state, qpos/qvel, actions, command, actuator forces, realized force, manual-mode flag and diagnostics.
- `events.jsonl`: start, task phases, pause/resume, manual controls, pushes and termination.
- `video.mp4`: automatically recorded at 25 fps with a fixed overview camera.
- `trace.npz`: compressed poses and timestamps.
- `figures.png`: six plots summarizing the full trial.
- `summary.json`: result, duration, completed subgoals, settings, peak tilt and recovery episodes.
- `analysis.json` / `analysis.md`: measured evidence, interpretation, importance, limitations and a suggested next experiment. Head/body contact peaks are simulator force proxies, not injury estimates.

During a running trial the summary is checkpointed once per simulated second. Telemetry/events are line-flushed. Normal stop, scene change, restart, task completion, unrecovered fall, timeout and graceful server shutdown finalize the recording. Abrupt machine/power failure may leave an unfinished video, while the flushed raw logs remain available.

Video and figure links are published as complete when finalization finishes. Saved verification trials are labeled as such and retained; they are not silently deleted.

## Run and develop

```bash
# Build browser assets on the workstation (no simulation runs locally).
npm ci --prefix web
npm run build --prefix web
bash scripts/remote.sh sync

# On Thor:
cd /home/saidevdhal/beyond-recovery
.venv/bin/pip install -e .
.venv/bin/br live --port 8080
```

For a persistent service use tmux. The service binds to `127.0.0.1`; use the existing Tailscale SSH port forward. The app is self-contained after the build and has no external font, JS or asset CDN requirement.

Interfaces: `GET /api/scenarios`, `/api/scene`, `/api/status`, `/api/runs`, `POST /api/action`, and WebSocket `/ws`. Trial artifacts are exposed by `/runs/{id}/{filename}` through an explicit filename allowlist. Physics mutations are queued and applied by the single simulation-owner thread.

## Validation

`tests/test_live.py` checks signed support margin, invalid/non-finite controls, independent scenario configurations and floor-patch properties. Existing timing/task/geometry tests remain in place.

`scripts/verify_live.py` drives the actual staging service on port 8082. It checks advancing physical states, frozen pause time, an exact 20 ms single-step, manual driving, actual force events, WebSocket updates, scene loading, automatic failure, and every saved artifact. This is a live protocol/integration test, not a mock.

Browser automation was unavailable in this session (no connected browser surface). The frontend build and JavaScript syntax were checked, the streamed geometry and live protocols were inspected, and saved simulator frames/plots can be rendered for visual inspection. Interactive camera and layout behavior still benefits from user feedback in the browser.

## Overnight research

The console links to `/assets/research-report.html`, generated from `reports/WAKE_UP_REPORT.md`. Research scripts run accelerated native physics on Thor without video rendering; all state traces, telemetry, inputs and per-trial interpretations remain saved. Selected videos are explicitly labeled saved physics traces. They do not replace the live interactive console.

`scripts/research_sweep.py` runs matched box/clearance trials and additional seeds. `scripts/counterfactual_probes.py` restores identical physics and controller checkpoints to test finite force grids. `scripts/replanning_control.py` tests a conventional perfect-map A* baseline after the pulse. That planner is a navigation control, not a learned recoverability estimator. Source snapshots and checkpoint checksums accompany research experiments.


The **Turn + arrival tuning** protocol multiplies the AMP yaw input by four (capped at ±2) and approaches waypoint centres before stopping. It retains the same outer arrival acceptance and continuous dwell requirement. The **Legacy research protocol** retains yaw gain one and the original stop-at-boundary rule. The optional A* mode uses the perfect static map; these are conventional task-control baselines, not preservation learning. Settings and the actual network command are recorded. Initial nominal endurance qualification used eight development seeds, so it is not independent confirmation of generalization.
