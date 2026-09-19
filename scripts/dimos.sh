#!/usr/bin/env bash
# Run the isolated, session-provisioned dimOS CLI. Does not choose a robot/blueprint.
# Typical live launch (planner speed capped to ~0.25 m/s by nerf_speed 0.45 x 0.55 m/s):
#   ROBOT_IP=<go2 address> ./scripts/dimos.sh --nerf-speed "${DIMOS_NERF_SPEED:-0.45}" run unitree-go2
set -euo pipefail
rover_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export LD_LIBRARY_PATH="$rover_root/data/native/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PATH="$rover_root/.dimos-venv/bin:$PATH"
exec "$rover_root/.dimos-venv/bin/dimos" "$@"
