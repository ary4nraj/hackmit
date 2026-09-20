# SignalHound status — 2026-09-19 (pivot night)

## WORKING
- **RADIO MILESTONE (real hardware):** nRF7002-DK flashed (app scanner + hci_ipc), streams `TARGET,Galaxy S25,<rssi>,<addr>` over USB; `python scripts/radio_monitor.py` shows raw/filtered RSSI and tracking status. First readings −62…−78 dBm.
- **CABLE-FREE RADIO:** the DK rebroadcasts its measurements over BLE; the laptop reads them with its own Bluetooth (`RADIO_LINK=ble`, ~1.2 samples/s). The DK can ride on the dog with just a power bank.
- **GO2 CONNECTION (real hardware):** `scripts/go2_status.py` connected over WebRTC LocalAP and streamed telemetry (position, yaw, velocity, range_obstacle, body_height), then disconnected cleanly. Motion not yet tested.
- Golden path in simulation: `./scripts/demo.sh --mock --yes` → calibrates, hill-climbs, prints TARGET FOUND (12 moves for a target 3.6 m away). 12 SignalHound tests pass (`pytest tests_sh`).
- Radio stack: `signalhound/radio/` (auto-detect J-Link VCOM, reconnect, CSV protocol, rolling median + EMA, quality/staleness), `python scripts/radio_monitor.py --raw`.
- Firmware built for the nRF7002-DK: app core scanner (`firmware/nordic/signalhound_scanner`, upstream Zephyr 4.2) + network core `hci_ipc`. Hex files ready; `scripts/flash_nordic.sh` flashes both.
- Go2 layer written on the teammate-verified `unitree_webrtc_connect` LocalAP path with the documented Move/StopMove/StandUp formats; imports verified in `.dimos-venv`. Central `MotionGuard` caps speed/burst, latches STOP on any exception.
- Homing controller with explicit states, reference-based hill climbing, 90° sweep turns, arrival hold, budgets, signal-loss and obstacle branches; terminal dashboard.

## BROKEN
- Target packet rate is low (~0.4/s) because the phone advertises slowly; homing decisions would be sluggish until the interval is lowered (see manual action).
- Go2 motion commands untested. `range_obstacle` read as [0,0,0,0] at rest: semantics unverified, treat as unavailable.
- Joining the Go2 WLAN drops the laptop's internet, which also cuts off the coding agent. Needs a second uplink (phone USB tethering) — `scripts/net_go2.sh` keeps the default route off the robot link.

## NEXT 3 TASKS
1. With USB tethering up: `./scripts/net_go2.sh`, then `go2_stop.py`, `go2_forward_test.py`, `go2_rotate_test.py` (each behind a typed YES).
2. Tape the DK + a USB power bank on the dog's back (antenna edge forward), set `RADIO_LINK=ble`, run `homing_manual.py --robot` while walking the phone: check RSSI tracks and telemetry stays fresh.
3. First physical closed loop with `./scripts/demo.sh` (ENTER gate); tune thresholds from `data/homing-history.jsonl`.

## MANUAL ACTION NEEDED
- Keep the iPhone USB-tethered to the laptop (internet) and the Galaxy S25 advertising "Galaxy S25" at 100 ms. A small USB power bank for the DK on the dog.
- Keep the Go2 powered; its AP name changes every boot (`Go2_61034_<random>`), the scripts handle that. AP password was reset to the value in `.env`.
- Stand next to the dog with the remote for every motion test.

## DEMO READINESS
- Simulation: READY. Radio-only proof: DONE (live RSSI on the laptop). Robot link: DONE (telemetry). Robot motion: ready to test once the laptop has a second uplink. Autonomous physical homing: not yet attempted.
