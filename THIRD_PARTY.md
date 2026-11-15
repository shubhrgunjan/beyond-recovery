# Third-party provenance

Upstream code, robot assets and pretrained controller weights remain governed by their upstream licenses. They are fetched from their publishers, not copied into this repository's Git history.

- **mjlab / Unitree G1 robot assets:** https://github.com/mujocolab/mjlab at the revision in `configs/upstream.json`. Fetch with `scripts/fetch_upstream.py`; retain upstream license files.
- **Released Unitree walking controller:** https://github.com/unitreerobotics/unitree_rl_mjlab at the revision and file checksums in `configs/reference.json`. `scripts/fetch_reference.py` also fetches the publisher's `LICENCE`.
- **Experimental G1 AMP controller:** https://github.com/ccrpRepo/wbc_fsm at revision `4b9afa27ad4eeab8e95584c67c91275b9831fc4d`. `configs/recovery_reference.json` pins the ONNX model and deployment definitions. Inspect the publisher's applicable terms before using the weights outside the documented simulation experiments.
- **Three.js / esbuild:** browser dependencies are pinned in `web/package-lock.json`; their upstream license notices remain in the packages and built bundle where applicable.
- **MuJoCo, MuJoCo Warp, PyTorch, RSL-RL and other Python dependencies:** exact versions are recorded in `requirements-thor.lock`; installed packages retain their respective licenses.
- **cloudflared:** an optional external tunnel executable, not committed to this repository. Obtain it from https://github.com/cloudflare/cloudflared/releases and verify the publisher's release digest. It supplies transport only; it does not run the robot controller.

Public research archives contain project-generated telemetry, simulator recordings, experiment inputs, source snapshots and baseline/training outputs. Publisher-fetched policy weights are obtained separately using the scripts above. Publishing the research record does not confer ownership of upstream assets or imply hardware validation or publisher endorsement.
