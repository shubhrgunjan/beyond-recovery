"""Fetch the publisher's G1 velocity policy and its deployment definitions."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REVISION = "1425b15f73bd4095f0df53709d7c389c3eb9e790"
BASE = f"https://raw.githubusercontent.com/unitreerobotics/unitree_rl_mjlab/{REVISION}/"
FILES = {
    "policy.onnx": "deploy/robots/g1/config/policy/velocity/v0/exported/policy.onnx",
    "deploy.yaml": "deploy/robots/g1/config/policy/velocity/v0/params/deploy.yaml",
    "g1.xml": "src/assets/robots/unitree_g1/xmls/g1.xml",
    "LICENCE": "LICENCE",
    "observations.h": "deploy/include/isaaclab/envs/mdp/observations/observations.h",
}
target = ROOT / "third_party/unitree_reference"
target.mkdir(parents=True, exist_ok=True)
expected_path = ROOT / 'configs/reference.json'
expected = json.loads(expected_path.read_text()) if expected_path.exists() else None
manifest = {"repository": "https://github.com/unitreerobotics/unitree_rl_mjlab",
            "revision": REVISION, "files": {}}
for name, path in FILES.items():
    output = target / name
    if not output.exists():
        with urllib.request.urlopen(BASE + path, timeout=30) as response:
            temporary = output.with_suffix(output.suffix + '.download')
            temporary.write_bytes(response.read())
            temporary.replace(output)
    manifest['files'][name] = {'url': BASE + path,
                              'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}
    if expected:
        assert manifest['files'][name]['sha256'] == expected['files'][name]['sha256'], name
(target / "manifest.json").write_text(json.dumps(manifest, indent=2) + '\n')
print(target)
