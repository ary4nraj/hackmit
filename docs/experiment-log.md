# Experiment log (real hardware)

Record medians from `python scripts/radio_monitor.py --log data/rssi.csv`.

## TEST 0 — first detection (19:15, DK on the laptop, phone somewhere on the table)
`TARGET,Galaxy S25,-78/-72/-62 dBm, addr 5A:1F:02:4D:D9:9A (random)`; ~0.4 target packets/s at
the phone's default advertising interval with a 50% scan duty cycle. Other advertisers in the hall:
100–150 packets/s total. Action: continuous scan window in firmware; ask for a 100 ms advertising
interval + high TX power in nRF Connect.

## TEST 1 — RSSI vs distance (19:23–19:25, phone at 100 ms interval, DK on the laptop, positions NOT measured)
191 samples over 115 s. Rate ≈1.7/s near, drops to ≈0.2/s when far/occluded (packets are lost, not just weak).
| situation (from the trace) | median RSSI | spread | notes |
|---|---|---|---|
| phone touching / on the DK | −22 to −24 dBm | ±1 | 100–110 s |
| phone ~arm's length | −38 to −41 dBm | ±3 | |
| phone on the table nearby | −57 to −62 dBm | ±5 (min −74) | 0–30 s |
| walking away / around the hall | −75 → −86 dBm | 1 pkt / 5 s | 30–95 s, effectively "lost" |
Takeaways: overall −21…−86 dBm, σ within a 5 s bucket ≈3–5 dB near, so ±3 dB thresholds need ≥5-sample medians (kept).
Arrival threshold −45 dBm ≈ phone within ~1 m of the DK: good. Below ≈−78 dBm the beacon is sporadic:
the controller's SIGNAL_LOST branch (rotate slowly, re-acquire) will trigger there, and the
6 s stale / 8 s measure windows are necessary.

## TEST 2 — orientation-only scan (DK on the dog, dog rotates in place)
| heading | median RSSI |
|---|---|
| 0° | |
| 90° | |
| 180° | |
| 270° | |
Conclusion: (fill in) "orientation scan insufficient; use translational probing" or otherwise.

## TEST 2b — first Go2 motion (20:3x, `go2_forward_test.py --yes`, 0.2 m/s x 0.5 s)
before x=0.504 y=0.012 yaw=-1.540 → after x=0.497 y=-0.091: |Δ| = 0.10 m along the heading, Δyaw -0.04 rad.
StandUp + BalanceStand accepted (mode 0, body_height 0.32), Move 1008 streamed, StopMove 1003 stopped it
cleanly, WebRTC disconnected cleanly. `range_obstacle` stayed [0,0,0,0]: not usable as-is.

## TEST 2c — first Go2 rotation (`go2_rotate_test.py --yes`, left 0.5 rad/s x 0.5 s)
yaw -1.706 → -1.563 rad (Δ +0.143 rad ≈ 8°), position drift < 2 cm. Clean stop/disconnect.
Commanded 0.25 rad, got 0.14: the dog ramps up, so a rotate burst yields ~55% of the nominal angle.

## TEST 3 — first closed-loop bursts
| step | position | RSSI before | RSSI after | verdict |
|---|---|---|---|---|

## Tuning decisions
- RSSI_IMPROVEMENT_DB / RSSI_WORSEN_DB:
- MOVE_STEP_SECONDS / PROBE_PATIENCE:
- TARGET_RSSI_THRESHOLD (arrival):
