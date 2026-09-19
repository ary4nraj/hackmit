#!/usr/bin/env bash
# GOLDEN PATH for SignalHound. Usage: ./scripts/demo.sh [--mock]
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
[ -f .env ] || echo "[demo] no .env: copy .env.example and set GO2_AES_KEY (skip for --mock)"
exec ./scripts/sh-python.sh scripts/homing_auto.py "$@"
