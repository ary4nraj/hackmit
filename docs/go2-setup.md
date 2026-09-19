# Unitree Go2 setup (SignalHound)

Connection: `unitree_webrtc_connect` 2.2.0 (already in `.dimos-venv`), `WebRTCConnectionMethod.LocalAP`,
robot at 192.168.12.1. The laptop must be on the robot's WLAN (`GO2_SSID`); credentials and the AES
key live in `.env` only. Run everything with `./scripts/sh-python.sh` (or `./scripts/demo.sh`).

Verified wire formats (from the installed working wrapper + package README):
- `SPORT_MOD` `{"api_id": 1008, "parameter": {"x": vx, "y": 0, "z": vyaw}}` Move (m/s, rad/s), resent every 0.1 s
- `1003` StopMove, `1004` StandUp, `1002` BalanceStand, `1005` StandDown
- telemetry: `LF_SPORT_MOD_STATE` → position, velocity, imu_state.rpy (yaw = rpy[2]), range_obstacle

Order of operations on hardware:
1. `python scripts/go2_status.py` — connect + 5 s telemetry, no motion.
2. `python scripts/go2_stop.py` — proves StopMove works.
3. `python scripts/go2_forward_test.py` — 0.2 m/s for 0.5 s after typing YES.
4. `python scripts/go2_rotate_test.py [--right]` — 0.5 rad/s for 0.5 s.
Only then `./scripts/demo.sh`.

Safety: all motion goes through `signalhound/robot/safety.py` (caps 0.5 m/s, 1.0 rad/s, 2 s per
burst, latched stop on any exception, StopMove after every burst). Ctrl+C in any script stops.
`range_obstacle` semantics are not verified; treat index 0 as "front" until confirmed on the dog.

## Bring-up notes (2026-09-19, verified)
- The AP is named `Go2_61034_<8 hex>` and the suffix changes on every boot; `scripts/net_go2.sh` picks the strongest match.
- Wrong AP password shows up in `journalctl` as `CTRL-EVENT-SSID-TEMP-DISABLED ... reason=WRONG_KEY`; the password was reset from the Unitree app.
- First successful `go2_status.py`: mode 0, gait 0, body_height 0.32, `range_obstacle` all zeros while standing still, telemetry keys: body_height, error_code, foot_force, foot_position_body, foot_raise_height, foot_speed_body, gait_type, imu_state, mode, position, progress, range_obstacle, stamp, velocity, yaw_speed.
- The robot's AP has no internet. Use `scripts/net_go2.sh` (never-default route) plus phone USB tethering for a second uplink.
