"""Fetch the recorded upstream revision, without following a moving branch."""
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
meta = json.loads((root / 'configs/upstream.json').read_text())
target = root / 'third_party/mjlab'
target.parent.mkdir(exist_ok=True)
if not target.exists():
    subprocess.run(['git', 'clone', '--no-checkout', '--filter=blob:none',
                    meta['repository'], str(target)], check=True)
    subprocess.run(['git', '-C', str(target), 'fetch', 'origin', meta['revision']], check=True)
    subprocess.run(['git', '-C', str(target), 'checkout', '--detach', meta['revision']], check=True)
current = subprocess.check_output(['git', '-C', str(target), 'rev-parse', 'HEAD'],
                                  text=True).strip()
if current != meta['revision']:
    if subprocess.check_output(['git', '-C', str(target), 'status', '--porcelain']):
        raise SystemExit('Upstream has local changes; refusing to replace them')
    subprocess.run(['git', '-C', str(target), 'fetch', 'origin', meta['revision']], check=True)
    subprocess.run(['git', '-C', str(target), 'checkout', '--detach', meta['revision']], check=True)
print(meta['revision'])
