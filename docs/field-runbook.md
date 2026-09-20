# Field runbook (run these yourself while the laptop is on the dog's Wi-Fi)

Everything logs to files; switch back to HackMIT afterwards and the agent reads the logs.
All commands from the repo root. Ctrl+C always stops the dog.

## 0. Network (once per robot boot)
    ./scripts/net_go2.sh            # joins Go2_61034_<random>; prints robot: reachable
    ./scripts/net_go2.sh off        # back to HackMIT.2026 when done

## 1. Radio only (DK on the dog with power bank, RADIO_LINK=ble in .env)
    python scripts/radio_monitor.py --log data/rssi.csv
Walk the phone; watch RSSI. Ctrl+C.

## 2. Radio + robot telemetry, no motion (Level 0)
    ./scripts/sh-python.sh scripts/homing_manual.py --robot --log data/manual.csv
Drive the dog with the remote or carry the phone around it. Check RSSI tracks and telemetry stays fresh.
Rotate the dog in place through 4 headings and note the median RSSI at each (docs/experiment-log.md TEST 2).

## 3. Motion sanity (each is one tiny burst behind a typed YES)
    ./scripts/sh-python.sh scripts/go2_stop.py
    ./scripts/sh-python.sh scripts/go2_forward_test.py
    ./scripts/sh-python.sh scripts/go2_rotate_test.py

## 4. Autonomous homing (golden path)
    ./scripts/demo.sh
Waits for the beacon, prints the baseline, asks for ENTER, then searches. Stops at FOUND / budget / Ctrl+C.
Logs: data/logs/homing-<stamp>.log (one line per decision) and data/homing-history.jsonl (pose + RSSI).
Rehearsal without hardware: ./scripts/demo.sh --mock --yes

## 5. Tuning knobs (.env)
MOVE_SPEED / MOVE_STEP_SECONDS (burst size), PROBE_PATIENCE (steps per heading), RSSI_IMPROVEMENT_DB /
RSSI_WORSEN_DB (hysteresis), TARGET_RSSI_THRESHOLD (arrival), SEARCH_TIMEOUT_SECONDS / MAX_MOVES.
Rotate bursts deliver ~55% of nominal angle (ramp-up): ROTATE_STEP_SECONDS=2.0 at 0.8 rad/s ≈ 50°.

## If something is wrong
- "No fresh Go2 telemetry": robot not connected; re-run net_go2.sh.
- Radio "lost": phone screen off / nRF Connect stopped advertising, or DK power bank off.
- The dog keeps turning: lower RSSI_WORSEN_DB or raise PROBE_PATIENCE; check the DK antenna isn't covered.
