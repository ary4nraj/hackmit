#!/usr/bin/env bash
# Python with unitree_webrtc_connect (lives in .dimos-venv) and this repo importable.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$root${PYTHONPATH:+:$PYTHONPATH}"
exec "$root/.dimos-venv/bin/python" "$@"
