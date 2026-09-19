#!/usr/bin/env bash
# GOLDEN PATH. One command for the judge demo.
#   ./scripts/demo.sh            -> mock world (always works)
#   ./scripts/demo.sh webcam     -> real camera + YOLO, frame thirds are zones
#   ./scripts/demo.sh replay     -> real dimOS unitree-go2 blueprint on recorded Go2 data (no robot)
#   ./scripts/demo.sh go2        -> physical Go2: needs ROBOT_IP and ZONES_FILE; THE ROBOT STANDS UP
# Env overrides: PORT, DATABASE_URL (default: fresh db per run), PERCEPTION_PROVIDER, DIMOS_NERF_SPEED
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
mode="${1:-${DEMO_TARGET:-mock}}"
port="${PORT:-8000}"
log_dir="data/logs"; mkdir -p "$log_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
export DATABASE_URL="${DATABASE_URL:-sqlite:///data/demo-$stamp.db}"
[ -f .env ] && set -a && . ./.env && set +a
if curl -sf "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
  echo "[demo] port $port already serves something (another Recall Rover?). Use PORT=8001 or stop it:"
  pgrep -af "uvicorn recall_rove[r]" || true
  exit 1
fi
pids=()
cleanup() {
  echo; echo "[demo] shutting down"
  for p in "${pids[@]:-}"; do [ -n "$p" ] && kill "$p" 2>/dev/null || true; done
  sleep 3
  for p in "${pids[@]:-}"; do [ -n "$p" ] && kill -9 "$p" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait_for_modules() {  # $1 = log file
  for _ in $(seq 1 90); do
    sleep 1
    n="$(tr '\r' '\n' < "$1" | grep -ac 'Deployed module' || true)"
    [ "${n:-0}" -ge 8 ] && return 0
    grep -aq "Traceback\|Error" "$1" && { echo "[demo] dimOS failed to start; see $1"; tail -20 "$1"; return 1; }
  done
  echo "[demo] dimOS did not deploy modules in 90 s; see $1"; return 1
}

start_coordinator() {  # $@ = dimos args
  if pgrep -f "venv/bin/dimo[s] .*run unitree-go2" >/dev/null; then
    echo "[demo] dimOS coordinator already running; reusing it"; return 0
  fi
  local log="$log_dir/dimos-$stamp.log"
  echo "[demo] starting dimOS: dimos $* (log: $log)"
  ./scripts/dimos.sh "$@" > "$log" 2>&1 &
  pids+=($!)
  wait_for_modules "$log"
}

python=".venv/bin/python"; [ -x "$python" ] || python="python3"
case "$mode" in
  mock)
    export ROBOT_BACKEND=mock PERCEPTION_PROVIDER=mock ;;
  webcam)
    export ROBOT_BACKEND=webcam PERCEPTION_PROVIDER="${PERCEPTION_PROVIDER:-local}" ;;
  replay)
    start_coordinator --replay --viewer none run unitree-go2
    export ROBOT_BACKEND=dimos PERCEPTION_PROVIDER="${PERCEPTION_PROVIDER:-local}"
    export ZONES_FILE="${ZONES_FILE:-config/zones.example.json}" NAVIGATION_TIMEOUT="${NAVIGATION_TIMEOUT:-15}"
    python="./scripts/dimos-python.sh" ;;
  go2)
    : "${ROBOT_IP:?set ROBOT_IP to the Go2 address}"
    : "${ZONES_FILE:?set ZONES_FILE to surveyed waypoints (copy config/zones.example.json)}"
    echo "[demo] !!! The Go2 will STAND UP when dimOS starts. Clear the floor; hold the physical stop. !!!"
    echo "[demo] speed cap: planner nerf ${DIMOS_NERF_SPEED:-0.45} x 0.55 m/s; Safety limit ${ROBOT_MAX_LINEAR_SPEED:-0.25} m/s"
    sleep 3
    start_coordinator --robot-ip "$ROBOT_IP" --nerf-speed "${DIMOS_NERF_SPEED:-0.45}" run unitree-go2
    export ROBOT_BACKEND=dimos PERCEPTION_PROVIDER="${PERCEPTION_PROVIDER:-combined}"
    python="./scripts/dimos-python.sh" ;;
  *) echo "usage: $0 [mock|webcam|replay|go2]"; exit 2 ;;
esac

echo "[demo] mode=$mode backend=$ROBOT_BACKEND perception=$PERCEPTION_PROVIDER db=$DATABASE_URL"
$python -m uvicorn recall_rover.api.app:app --host 127.0.0.1 --port "$port" > "$log_dir/api-$stamp.log" 2>&1 &
pids+=($!)
for _ in $(seq 1 60); do sleep 1; curl -sf "http://127.0.0.1:$port/health" >/dev/null && break; done
if ! curl -sf "http://127.0.0.1:$port/health" >/dev/null; then
  echo "[demo] API failed to start; see $log_dir/api-$stamp.log"; tail -30 "$log_dir/api-$stamp.log"; exit 1
fi
url="http://127.0.0.1:$port"
echo "[demo] READY  $url   (agent: $(curl -s $url/state | $python -c 'import sys,json;print(json.load(sys.stdin)["agent_mode"])' 2>/dev/null || echo '?'))"
cat <<TXT
[demo] Judge script:
  1. "Where is my backpack?"        -> last seen + age + confidence
  2. move the backpack (mock: click 'Demo: move backpack'; real: physically move it)
  3. "Find my backpack"             -> checks old spot, INVALIDATED, bounded search, MOVED
  4. "What changed?"                -> the change timeline
  STOP button latches motion; Resume clears it.
TXT
command -v xdg-open >/dev/null && [ -z "${NO_BROWSER:-}" ] && xdg-open "$url" >/dev/null 2>&1 || true
wait "${pids[-1]}"
