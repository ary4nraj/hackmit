# SignalHound status — 2026-09-19 (pivot night)

## WORKING
- **RADIO MILESTONE (real hardware):** nRF7002-DK flashed (app scanner + hci_ipc), streams `TARGET,Galaxy S25,<rssi>,<addr>` over USB; `python scripts/radio_monitor.py` shows raw/filtered RSSI and tracking status. First readings −62…−78 dBm.
- Golden path in simulation: `./scripts/demo.sh --mock --yes` → calibrates, hill-climbs, prints TARGET FOUND (12 moves for a target 3.6 m away). 12 SignalHound tests pass (`pytest tests_sh`).
- Radio stack: `signalhound/radio/` (auto-detect J-Link VCOM, reconnect, CSV protocol, rolling median + EMA, quality/staleness), `python scripts/radio_monitor.py --raw`.
- Firmware built for the nRF7002-DK: app core scanner (`firmware/nordic/signalhound_scanner`, upstream Zephyr 4.2) + network core `hci_ipc`. Hex files ready; `scripts/flash_nordic.sh` flashes both.
- Go2 layer written on the teammate-verified `unitree_webrtc_connect` LocalAP path with the documented Move/StopMove/StandUp formats; imports verified in `.dimos-venv`. Central `MotionGuard` caps speed/burst, latches STOP on any exception.
- Homing controller with explicit states, reference-based hill climbing, 90° sweep turns, arrival hold, budgets, signal-loss and obstacle branches; terminal dashboard.

## BROKEN
- Target packet rate is low (~0.4/s) because the phone advertises slowly; homing decisions would be sluggish until the interval is lowered (see manual action).
- Untested on hardware: Go2 motion commands (robot AP `Go2_61034` not visible from the laptop right now; no `.env` credentials yet). `range_obstacle` semantics unverified.

## NEXT 3 TASKS
1. Walk the phone 0.5 / 2 / 5 m and behind a wall while `python scripts/radio_monitor.py --log data/rssi.csv` runs; fill TEST 1 in `docs/experiment-log.md`.
2. Join the Go2 WLAN with `.env` filled in; run `go2_status.py`, `go2_stop.py`, `go2_forward_test.py`, `go2_rotate_test.py` in that order.
3. First physical closed loop with `./scripts/demo.sh` (ENTER gate), tune thresholds from the log.

## MANUAL ACTION NEEDED
- On the phone, in nRF Connect → Advertiser → the "Galaxy S25" packet: set advertising interval to 100 ms and TX power to high, keep it advertising.
- Create `.env` from `.env.example` with `GO2_AES_KEY` (and SSID/password for reference), power the Go2 on, connect the laptop to the Go2 WLAN.
- Keep the phone unlocked with nRF Connect advertising "Galaxy S25".

## DEMO READINESS
- Simulation: READY. Radio-only proof: DONE (live RSSI on the laptop). Robot motion: blocked on WLAN + credentials. Autonomous physical homing: not yet attempted.
