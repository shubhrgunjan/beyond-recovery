#!/usr/bin/env bash
# Run on Thor after source sync. Does not change system packages or Python.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ "$(uname -m)" == aarch64 ]] || { echo 'Expected the ARM64 Thor'; exit 1; }
/usr/bin/python3.12 -m venv .venv
.venv/bin/python -m pip install 'torch==2.14.0' --index-url https://download.pytorch.org/whl/cu130
if [[ -f requirements-thor.lock ]]; then
  .venv/bin/python -m pip install -r requirements-thor.lock \
    --extra-index-url https://download.pytorch.org/whl/cu130 --extra-index-url https://pypi.nvidia.com
fi
.venv/bin/python scripts/fix_thor_wheel.py
.venv/bin/python -m pip install --no-deps --force-reinstall .cache/wheels/corrected/nvidia_cusparselt_cu13-0.8.1-py3-none-manylinux2014_aarch64.whl
.venv/bin/python -m pip install -e third_party/mjlab --extra-index-url https://pypi.nvidia.com
.venv/bin/python -m pip install -e .
.venv/bin/python scripts/fetch_reference.py
.venv/bin/python -m pip check
.venv/bin/br doctor
