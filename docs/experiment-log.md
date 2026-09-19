# Experiment log (real hardware)

Record medians from `python scripts/radio_monitor.py --log data/rssi.csv`.

## TEST 0 — first detection (19:15, DK on the laptop, phone somewhere on the table)
`TARGET,Galaxy S25,-78/-72/-62 dBm, addr 5A:1F:02:4D:D9:9A (random)`; ~0.4 target packets/s at
the phone's default advertising interval with a 50% scan duty cycle. Other advertisers in the hall:
100–150 packets/s total. Action: continuous scan window in firmware; ask for a 100 ms advertising
interval + high TX power in nRF Connect.

## TEST 1 — RSSI vs distance (phone in hand, DK on table)
| distance | median RSSI | notes |
|---|---|---|
| 0.5 m | | |
| 2 m | | |
| 5 m | | |
| wall between | | |

## TEST 2 — orientation-only scan (DK on the dog, dog rotates in place)
| heading | median RSSI |
|---|---|
| 0° | |
| 90° | |
| 180° | |
| 270° | |
Conclusion: (fill in) "orientation scan insufficient; use translational probing" or otherwise.

## TEST 3 — first closed-loop bursts
| step | position | RSSI before | RSSI after | verdict |
|---|---|---|---|---|

## Tuning decisions
- RSSI_IMPROVEMENT_DB / RSSI_WORSEN_DB:
- MOVE_STEP_SECONDS / PROBE_PATIENCE:
- TARGET_RSSI_THRESHOLD (arrival):
