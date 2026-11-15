"""Evaluate one frozen checkpoint across paired seeded task conditions on Thor."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from beyond_recovery.cli import resolve_checkpoint

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--checkpoint', default='latest')
parser.add_argument('--configs', nargs='+', default=[
    'configs/t0.yaml', 'configs/t0_push.yaml',
    'configs/t1_narrow.yaml', 'configs/t1_wide.yaml'])
parser.add_argument('--seeds', nargs='+', type=int, default=[0, 1, 2])
parser.add_argument('--output', default=None)
parser.add_argument('--video', action='store_true')
args = parser.parse_args()
checkpoint = resolve_checkpoint(args.checkpoint)  # Resolve once for all conditions.
root = Path(args.output or f'artifacts/evaluation_{time.time_ns()}').resolve()
root.mkdir(parents=True, exist_ok=False)
results = []
for config in args.configs:
    for seed in args.seeds:
        name = f'{Path(config).stem}_seed{seed}'
        output = root / name
        cmd = [sys.executable, '-m', 'beyond_recovery.cli', 'rollout',
               '--checkpoint', str(checkpoint), '--config', config,
               '--seed', str(seed), '--output', str(output)]
        if args.video:
            cmd.append('--video')
        with (root / f'{name}.log').open('w') as log:
            process = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
        if process.returncode:
            raise SystemExit(f'{name} failed; see {root / (name + ".log")}')
        result = json.loads((output / 'summary.json').read_text())
        result['config'] = config
        results.append(result)
        print(name, result['result'], result['completed_subgoals'], flush=True)
(root / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
print('Results:', root)
