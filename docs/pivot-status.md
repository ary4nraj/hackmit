# Pivot status — Recall Rover → SignalHound (2026-09-19)

## USEFUL EXISTING CODE
- `.dimos-venv` already contains `unitree_webrtc_connect 2.2.0` (the teammate-verified WebRTC path) plus aiortc/aioice. Reused as the robot link; run it via `scripts/dimos-python.sh` or the new `scripts/sh-python.sh`.
- `dimos/robot/unitree/connection.py` (installed package, read-only) shows the exact working wire formats: `SPORT_MOD` `{"api_id": 1008, "parameter": {"x","y","z"}}` for Move, `1003` StopMove, `1004` StandUp, `1002` BalanceStand, and a 0.2 s deadman timer pattern. Copied into `signalhound/robot/go2.py`.
- `recall_rover/robot/safety.py` ideas (latched STOP, serialized bursts, timeouts) re-implemented smaller in `signalhound/robot/safety.py`.
- `scripts/dimos.sh` / `scripts/dimos-python.sh`: venv wrappers with the right library paths.
- `.gitignore` already excludes `.env`, `data/`, venvs.

## IRRELEVANT EXISTING CODE (left in place, not imported by the golden path)
- `recall_rover/` (memory, perception/YOLO, OpenAI agent, FastAPI dashboard), `apps/dashboard`, `tests/`, `docs/dimos-notes.md` etc. The old `make`/`scripts/demo.sh` golden path is replaced by `scripts/demo.py`. Moved nothing to avoid breaking teammates' references; see `legacy/README.md`.

## BROKEN CODE
- Nothing known broken. Old suite still passes (31 tests) but is not part of SignalHound.

## CURRENT HARDWARE STATE
- nRF7002-DK on USB: SEGGER J-Link `001050742694`, VCOM `/dev/ttyACM0` (console) and `/dev/ttyACM1`, mass-storage `JLINK` volume mounted (drag-and-drop flashing possible). No firmware output observed yet: the board must be flashed with `firmware/nordic/signalhound_scanner`.
- Toolchain provisioned in `~/dev/zephyr-sh` (Zephyr v4.2.0, SDK 0.17.4 arm, J-Link V9.78 extracted to `~/dev/jlink`). Both core images build. Flashing blocked on USB permissions (see docs/hackathon-status.md).
- Laptop on `HackMIT.2026`. Our Go2 (`Go2_61034`) AP is NOT currently visible (others are). Go2 credentials not yet provided (`GO2_AES_KEY`, `GO2_SSID`, `GO2_WIFI_PASSWORD` expected in `.env`).
- Phone: Galaxy S25 advertising "Galaxy S25" via nRF Connect (assumed BLE legacy advertising with the name in adv or scan response; firmware uses active scanning to catch both).

## NEXT 3 TASKS
1. Build + flash the scanner firmware; run `python -m signalhound.radio.monitor`; walk the phone and log RSSI vs distance in `docs/experiment-log.md`.
2. Put Go2 credentials in `.env`, join the Go2 WLAN, run `scripts/go2_status.py`, then `go2_stop.py`, `go2_forward_test.py`, `go2_rotate_test.py`.
3. Mock homing tests, then one physical closed-loop burst.
