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

## TEST 2 (partial, 21:01–21:05) — manual log with the dog stationary (yaw ≈ −127°), phone walked around
777 rows / 234 s, ~3 samples/s. RSSI −84…−23, 5 s medians −70…−30 depending on where the phone was.
The four-heading rotation scan was NOT done yet (yaw never changed). Still open.

## TEST 3 — first end-to-end run (21:05:52) — INVALID as a closed loop
The DK was NOT mounted on the dog and the phone was not fixed: both were hand-held and moving, so the
RSSI trajectory below is unrelated to the robot's motion. It only proves the plumbing (radio → decision →
bursts → stop) works on hardware. Do not tune thresholds from it.
| step | position (x,y,yaw°) | RSSI ref → after | n | verdict / action |
|---|---|---|---|---|
| baseline | 0.50,−0.34,−137 | −65 | | |
| 1 forward 0.42 m | 0.23,−0.66,−136 | −65 → −50 | | IMPROVED → advance |
| 2 forward | — | −50 → (fewer than 5 fresh packets in 8 s) | <5 | treated as signal lost → 90° re-acquire turn |
| 3 after turn | 0.29,−0.80,−71 | −75 | | |
| 4 forward | 0.42,−1.19,−66 | −75 → −72 | | IMPROVED → advance |
| 5 forward | 0.60,−1.55,−62 | −72 → −74 | | INCONCLUSIVE; operator Ctrl+C |
Lessons (plumbing only): (1) a 5-sample window can time out at the observed beacon rate;
now any ≥2-sample window is used and only silence counts as lost. (2) A single burst can swing RSSI
15 dB (−65→−50→−73): multipath + bodies; hysteresis must come from more samples per decision, not
from smaller thresholds. (3) ~11 s per step with the old timeouts; settle/timeout reduced to 1 s / 5 s.

## Tuning decisions
- RSSI_IMPROVEMENT_DB / RSSI_WORSEN_DB:
- MOVE_STEP_SECONDS / PROBE_PATIENCE:
- TARGET_RSSI_THRESHOLD (arrival):

## TEST 4 — run 2 (21:16:53): phone taped on the dog, DK + laptop with the person. First VALID closed loop.
Baseline −87 dBm (!), windows of 1–4 packets: the beacon on the dog is at the DK's receiver floor.
Trajectory: −87 → −75 (IMPROVED, advance) → −79 (WORSENED, turn) → −80.5 → 1-packet window → lost →
rotate → −87 → operator stop after 7 moves, ~1.4 m travelled. Mechanically correct; radio hopeless.
Compare: same phone reads −40 at arm's length and −58 on a table. Taped flat against the dog's body/battery
it is losing ~20 dB. FIX THE MOUNT before the next run: phone upright or on foam, top edge (antenna) up
and clear of the metal body, screen on; verify with `radio_monitor.py` that the baseline at the start
distance is better than −75 dBm. The controller now warns on a baseline ≤ −80 and, when a step silences
the beacon, backs up before rotating. Steps are now 0.6 m (2 s) and WORSEN needs 5 dB.

## TEST 5 — run 3 (09:27, DK + power bank on the dog, BLE link, person holding the phone)
Baseline −67.8 dBm, n=8 (healthy). Forward x3 (1.25 m, heading ~10°): −70, −68, −70 = flat →
patience exhausted → TURN LEFT (default sweep direction) → probe 0.5 m: −64.4 (+6 dB) → advance → operator
stop ("turned the wrong direction"). By RSSI the left probe was the best reading of the run, so either the
person was left-ish or the +6 dB was a noisy high (n=4). Person position relative to the dog: to be confirmed.

Conclusion on "wrong direction": with one omnidirectional antenna the first side turn is a coin flip; there
is no information to choose left vs right until the dog has moved. Simulation of alternatives (16 cases,
3–5 dB noise, 10% packet loss): plain sweep w/ 3-step probes 16/16 (36 moves); shorter post-turn probes
15/16 with 8 m runaways; two-sided probing 11–14/16 with 12–17 m runaways (noisy references cause false
commits). Kept the plain sweep. A wrong first turn costs one 1.3 m probe, then the sweep continues.
Demo tip: start the dog roughly facing the area to search; it does not need to face the person.

## TEST 6 — run 4 (10:01, DK on dog via BLE, climb mode): 16 moves, ~6 m, walked a loop, no approach
Baseline −63 (n=7). Headings: S 1.3 m (−62,−60,−66) → L → −73 → L big → −70 → −67 → −72 → L → −66 → −66,
−70,−71 → L → −66; ended 0.9 m from the start after a full loop. RSSI rippled −60…−73 with no consistent
gradient over the 1.3 m probes: classic indoor multipath (standing-wave ripple is a function of position, so
time-averaging in one spot cannot remove it). Best reading −60.5 at 0.9 m south of the start.
Change: Level-3 plane fit. When a heading goes flat, fit RSSI ≈ a·x + b·y + c over the last 12 odometry
points (needs ≥0.8 m span in both axes, i.e. after the first turn) and turn along (a,b) instead of the
blind sweep. Simulation with a 5 dB ripple model: 10/12 → 12/12, 44 → 36 moves, worst wander 8.4 → 4.0 m.
Still untested: the dog's own body-shadow directional contrast (`scripts/spin_scan.py`, 40 s).
