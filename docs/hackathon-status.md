# SignalHound status — 2026-09-19 (pivot night)

## WORKING
- Golden path in simulation: `./scripts/demo.sh --mock --yes` → calibrates, hill-climbs, prints TARGET FOUND (12 moves for a target 3.6 m away). 12 SignalHound tests pass (`pytest tests_sh`).
- Radio stack: `signalhound/radio/` (auto-detect J-Link VCOM, reconnect, CSV protocol, rolling median + EMA, quality/staleness), `python scripts/radio_monitor.py --raw`.
- Firmware built for the nRF7002-DK: app core scanner (`firmware/nordic/signalhound_scanner`, upstream Zephyr 4.2) + network core `hci_ipc`. Hex files ready; `scripts/flash_nordic.sh` flashes both.
- Go2 layer written on the teammate-verified `unitree_webrtc_connect` LocalAP path with the documented Move/StopMove/StandUp formats; imports verified in `.dimos-venv`. Central `MotionGuard` caps speed/burst, latches STOP on any exception.
- Homing controller with explicit states, reference-based hill climbing, 90° sweep turns, arrival hold, budgets, signal-loss and obstacle branches; terminal dashboard.

## BROKEN
- Not yet flashed: J-Link mass-storage programming fails on this board (FAIL.TXT) and JLinkExe cannot open the probe because `/dev/bus/usb/003/007` is root-only. Needs the sudo command below.
- Untested on hardware: Go2 motion commands (robot AP `Go2_61034` not visible from the laptop right now; no `.env` credentials yet). `range_obstacle` semantics unverified.

## NEXT 3 TASKS
1. Flash the DK (`./scripts/flash_nordic.sh`), run `python scripts/radio_monitor.py --raw`, walk the phone: fill TEST 1 in `docs/experiment-log.md`.
2. Join the Go2 WLAN with `.env` filled in; run `go2_status.py`, `go2_stop.py`, `go2_forward_test.py`, `go2_rotate_test.py` in that order.
3. First physical closed loop with `./scripts/demo.sh` (ENTER gate), tune thresholds from the log.

## MANUAL ACTION NEEDED
- Run once (gives the user write access to the J-Link probe), then unplug/replug the DK:
  `sudo cp ~/dev/jlink/extracted/etc/udev/rules.d/99-jlink.rules /etc/udev/rules.d/ && sudo udevadm control --reload-rules && sudo udevadm trigger`
  (quick alternative until replug: `sudo chmod 666 /dev/bus/usb/003/007`)
- Create `.env` from `.env.example` with `GO2_AES_KEY` (and SSID/password for reference), power the Go2 on, connect the laptop to the Go2 WLAN.
- Keep the phone unlocked with nRF Connect advertising "Galaxy S25".

## DEMO READINESS
- Simulation: READY. Radio-only proof: blocked on the one sudo command (minutes). Robot motion: blocked on WLAN + credentials. Autonomous physical homing: not yet attempted.
