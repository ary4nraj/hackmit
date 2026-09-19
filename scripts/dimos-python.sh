#!/usr/bin/env bash
# Run Python inside the isolated dimOS venv with the repo on sys.path (for DimosRobot clients).
set -euo pipefail
rover_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export LD_LIBRARY_PATH="$rover_root/data/native/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PATH="$rover_root/.dimos-venv/bin:$PATH"
export PYTHONPATH="$rover_root${PYTHONPATH:+:$PYTHONPATH}"
exec "$rover_root/.dimos-venv/bin/python" "$@"
