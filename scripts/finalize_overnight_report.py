"""Put the current evidence and usable entry points before detailed study appendices."""
from datetime import datetime,timezone
import json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def latest(prefix):
    roots=sorted((ROOT/'artifacts/research').glob(prefix+'-*'))
    return json.loads((roots[-1]/'results.json').read_text()) if roots else []
legacy=latest('matched');probes=latest('probes');astar=latest('replanning');impact=latest('impact');cal=latest('calibrated')
end=[]
for p in (ROOT/'artifacts/research').glob('endurance-*/results.json'):end+=json.loads(p.read_text())
progress=[('Legacy trip / clearance',len(legacy),144),('State-matched initial pushes',len(probes),768),('Legacy-map replanning control',len(astar),144),('Stronger-impulse physical recovery',len(impact),288),('Nominal endurance qualification',len(end),32),('Post-yaw-calibration repeats',len(cal),432)]
complete=all(n==total for _,n,total in progress)
openi=[r for r in impact if r['width'] is None];narrow=[r for r in impact if r['width']==.9]
tuned=[r for r in end if r['controller']=='amp' and r.get('arrival_mode')=='centered']
text=f'''# Beyond Recovery — wake-up report

Saved: {datetime.now(timezone.utc).isoformat(timespec='seconds')} UTC. **{'All planned studies below completed' if complete else 'Checkpoint saved; final calibration repeats are still running'}.**

## Start here

Open **[the live lab](http://localhost:8080)** and refresh once. Use **AMP walk + get-up**, **Turn + arrival tuning**, and begin with **Flat hazard-course control** or **Long-horizon endurance**. Then try **Trip box — open space**, **Trip box — constrained space**, **Rough pavement** and **Low overhead beam**. Scene descriptions state the question and the physical hazard. The viewer is live; the recordings embedded below are explicitly saved traces.

The viewport now occupies 72% of browser height and has fullscreen/focus controls. Start, pause, stop/save and push controls are over the scene. Physics and inference stay on Thor; the browser renders locally. A fall no longer freezes physics: the learned controller gets up physically and resumes the route. Every live trial saves video, telemetry, state trace, contact events, plots and written interpretation on Thor. No VLA is used.

## What we learned

1. **The baseline needed fixing before making research claims.** The AMP model barely turned in place at the old yaw command. Some waypoint arrivals also stalled at the edge of the dwell region. Empirical yaw mapping and a centering approach completed the 12-goal, three-round route in **{sum(r['result']=='success' for r in tuned)}/{len(tuned)} development seeds**, without falls. This is baseline engineering, not a new recovery algorithm. The legacy protocol remains selectable and all earlier results remain saved.
2. **Physical get-up works, and task resumption can be observed live.** The tuned live validation fell at **8.98 s**, recovered sustained standing at **11.62 s**, and advanced the original subgoal at **21.18 s**, with no execution-time state reset. Qualification also tested settled back, side and front falls. This does not mean every fall is recoverable.
3. **The initial “more room is better” story did not replicate reliably.** With the legacy protocol and 13 cm box, matrix seeds gave open **6/8** versus 0.90 m **3/8** completion; additional seeds gave **6/12 versus 7/12**. Do not use the pilot video as a novelty claim. The later calibrated repeat is reported separately below.
4. **Most of the initial standing-versus-task gap disappeared after a baseline fix.** In the legacy trip study, **26/61** trials that regained standing after every loss still failed completion. With yaw ×4 in the full repeated 144-trial design, that count is **1/37**. The set of trials that fell also changed, so these fractions are not a matched causal decomposition. They nevertheless show that the original gap was strongly protocol-dependent; it cannot establish a new preservation-learning problem by itself.
5. **Useful contact can outweigh empty space.** In the stronger-impulse grid, open space had **{sum(r['fell'] for r in openi)}/{len(openi)}** balance-loss trials; 0.90 m barriers had **{sum(r['fell'] for r in narrow)}/{len(narrow)}**. Every constrained trial in that latter group physically contacted a barrier with the body. This supports a contact-support explanation, not proof of an intelligent bracing strategy. Barrier contacts can be severe; the force table below exposes that cost rather than equating “did not fall” with safe success.
6. **Task failure is not proof of physical unrecoverability.** All **768** initial 80/140/200 N branches remained above our balance-loss thresholds, yet many did not finish. The first map planner alone changed completion from **59/144 to 58/144**. After correcting yaw response, conventional A* raises 0.75 m entrance completion from **11/48 to 44/48**, and 0.90 m completion from **10/48 to 41/48**, using the same parent states and force cases. The turning/planning interaction explains much of this apparent failure mode. These 48 cases reuse eight parent seeds; they are not 48 independent robots or environments.

## Research decision

**Go on the lab; no-go on using these initial failures as a new algorithm claim.** Freeze the corrected baseline, establish a residual problem beyond ordinary planning/control, then develop a task-conditioned continuation metric. Measure task progress, physical stabilization, task resumption and prohibited-contact outcomes separately. Preserve access to useful support as well as stepping space.

**Do not yet claim:** a learned recovery-preservation algorithm, multiple independently selectable recovery strategies, calibrated uncertainty bounds, a new literature gap, physical impossibility from a failed policy, or hardware validation. The system currently has one unified AMP walk/get-up policy and a conventional optional map planner. The experiments are exploratory simulation development on a limited disturbance family.

The next defensible step is to freeze the corrected task protocol, collect fresh task/controller-state branches, validate a continuation estimator on new seeds and dynamics, and compare actions that preserve that estimate against task-only control and conventional planning. [Research formulation](data/RESEARCH_FORMULATION.md).

## Experiment inventory

'''
text+='| Study | Saved trials | Planned |\n|---|---|---|\n'
for label,n,total in progress:text+=f'| {label} | {n} | {total} |\n'
text+=f'\n**{sum(n for _,n,total in progress)} saved research trials** in this inventory, plus twenty command-tracking qualifications and live/integration checks. These are not independent statistical samples: most studies reuse eight parent seeds and paired disturbance cases.\n'
text+='''
## Inspect the recordings

These videos render saved qpos traces at 25 fps. Support barriers are shown translucent for visibility; collision physics is unchanged. They do not rerun physics or stand in for the live app. Examples were selected for explanation; aggregate results take precedence. The trip examples use the legacy protocol and illustrate both a pilot difference and a held-out counterexample.

### Trip: seed 0, open space
<video controls preload="none" src="clips/trip-seed0-open.mp4"></video>

### Same seed and box, 0.90 m space
<video controls preload="none" src="clips/trip-seed0-narrow.mp4"></video>

### Counterexample: seed 17, open space
<video controls preload="none" src="clips/trip-seed17-open.mp4"></video>

### Same held-out seed, 0.90 m space
<video controls preload="none" src="clips/trip-seed17-narrow.mp4"></video>

### Same initial state and 300 N lateral pulse: open space
<video controls preload="none" src="clips/support-open.mp4"></video>

### Same pulse, with physical support barriers
<video controls preload="none" src="clips/support-narrow.mp4"></video>

## Practical limits and verification

Physics is native MuJoCo at 2 ms, policy control at 20 ms. Browser geometry is simplified for rendering only; physics collision geometry is retained. The robot has idealized actuators, rigid static fixtures and no payload task or real hardware. The AMP and original walking controllers use different published actuator profiles, so the clean research comparisons are within one profile. Apparent impacts are simulator force proxies, not injury estimates.

The targeted project suite has 16 passing tests. Frontend bundling and JavaScript syntax checks pass. HTTP/WebSocket integration checks exercised real physics, pause/step, manual control, pushes and recording; a 0 s immediate stop still saves its artifacts. The tuned live get-up/resumption check passed. Automated browser interaction was unavailable because no browser surface was connected; interactive layout/camera comfort still needs your feedback.

Reports were checkpointed before and during long jobs and are stored on both Thor and the workstation at completion. The browser report supports printing to PDF. Trial-level CSV downloads and detailed figures are below; raw state/action logs and source snapshots remain on Thor under `/home/saidevdhal/beyond-recovery/artifacts/research/`. Source sync excludes generated report assets, preventing stale local copies from overwriting results.

## Detailed legacy-protocol trip experiment

'''
report=ROOT/'reports/WAKE_UP_REPORT.md';old=report.read_text()
if '## Detailed legacy-protocol trip experiment\n\n' in old:detail=old.split('## Detailed legacy-protocol trip experiment\n\n',1)[1]
else:detail='## What is being tested'+old.split('## What is being tested',1)[1]
detail=detail.replace('## Results so far','## Completed legacy matrix results').replace('Twelve targeted tests pass.','The initial twelve targeted checks passed; the final project suite contains sixteen passing tests.').replace('Later sections will add trajectory-mechanism checks and selected recordings when available.','Trajectory-mechanism checks and selected recordings appear in this report.')
audit=ROOT/'reports/data/record_audit.json'
if audit.exists():
    a=json.loads(audit.read_text());text+=f'\nRecord audit: **{a["passed"]}/{a["audited"]}** research records passed artifact, finite-state, time and log-count checks. [Audit details](data/record_audit.json). A legacy live/accelerated metadata flag was corrected with an explicit audit trail; physics data were unchanged.\n\n'
shutil.copyfile(ROOT/'docs/RESEARCH_FORMULATION.md',ROOT/'reports/data/RESEARCH_FORMULATION.md')
report.write_text(text+detail)
print('Final-summary checkpoint',complete,sum(n for _,n,total in progress),flush=True)
