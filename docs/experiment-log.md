# Experiment log (real hardware)

Record medians from `python scripts/radio_monitor.py --log data/rssi.csv`.

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
