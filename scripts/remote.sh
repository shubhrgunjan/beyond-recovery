#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
HOST="saidevdhal@agx-thor.taila0fc70.ts.net"
REMOTE="/home/saidevdhal/beyond-recovery"
mkdir -p .cache
if [[ ! -s .cache/thor_known_hosts ]]; then
  python3 - <<'PY'
import json, pathlib, subprocess
status = json.loads(subprocess.check_output(['tailscale', 'status', '--json']))
peer = next(p for p in status['Peer'].values()
            if p.get('DNSName', '').rstrip('.') == 'agx-thor.taila0fc70.ts.net')
keys = peer.get('sshHostKeys', [])
if not keys:
    raise SystemExit('Thor host identity is absent from Tailscale metadata')
pathlib.Path('.cache/thor_known_hosts').write_text(''.join(
    'agx-thor.taila0fc70.ts.net ' + key + '\n' for key in keys))
PY
fi
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=yes
     -o "UserKnownHostsFile=$ROOT/.cache/thor_known_hosts")
export RSYNC_RSH="ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$ROOT/.cache/thor_known_hosts"
case "${1:-help}" in
  sync)
    "${SSH[@]}" "$HOST" "mkdir -p $REMOTE/third_party $REMOTE/reports"
    rsync -az --exclude=.git --exclude=.aws --exclude=/reports/ --exclude=.venv --exclude=.cache --exclude=artifacts \
      --exclude=logs --exclude=third_party --exclude=__pycache__ --exclude=node_modules \
      --exclude=reports/WAKE_UP_REPORT.md --exclude=reports/figures --exclude=reports/clips --exclude=reports/data \
      --exclude=web/dist/research-bundle.zip --exclude=web/dist/research-report.html --exclude=web/dist/WAKE_UP_REPORT.md --exclude=web/dist/figures --exclude=web/dist/clips --exclude=web/dist/data ./ "$HOST:$REMOTE/"
    rsync -az --exclude=.git third_party/mjlab/ "$HOST:$REMOTE/third_party/mjlab/"
    if [[ -d third_party/unitree_reference ]]; then
      rsync -az third_party/unitree_reference/ "$HOST:$REMOTE/third_party/unitree_reference/"
    fi
    if [[ -d third_party/g1_amp ]]; then
      rsync -az third_party/g1_amp/ "$HOST:$REMOTE/third_party/g1_amp/"
    fi
    ;;
  run)
    shift
    # Quote every argument for the remote shell; never interpolate raw CLI text.
    printf -v COMMAND '%q ' "$@"
    "${SSH[@]}" "$HOST" "cd $REMOTE && .venv/bin/br $COMMAND"
    ;;
  fetch)
    mkdir -p artifacts/thor/reference-final
    rsync -az --exclude=scene.mjb "$HOST:$REMOTE/artifacts/reference-final/" artifacts/thor/reference-final/
    ;;
  tunnel)
    "${SSH[@]}" -N -L 8080:127.0.0.1:8080 -L 6006:127.0.0.1:6006 "$HOST"
    ;;
  status)
    "${SSH[@]}" "$HOST" "tmux list-sessions 2>/dev/null || true; tail -12 $REMOTE/train.log 2>/dev/null; free -h; df -h /"
    ;;
  *)
    echo 'Usage: scripts/remote.sh {sync|run <br arguments>|fetch|tunnel|status}'
    ;;
esac
