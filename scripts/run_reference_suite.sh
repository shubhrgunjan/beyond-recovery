#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${1:-artifacts/reference-suite}"
mkdir -p "$OUT"
for TASK in t0 t0_push t1_narrow t1_wide t0_endurance t1_compound; do
  .venv/bin/br reference --config "configs/$TASK.yaml" --video --output "$OUT/$TASK" > "$OUT/$TASK.log" 2>&1
  cat "$OUT/$TASK/summary.json"
done
