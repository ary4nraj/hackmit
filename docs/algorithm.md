# SignalHound homing algorithm

RSSI gives strength, not direction, so the robot infers direction by moving. It treats RSSI as a
noisy scalar field and does closed-loop hill climbing with bursts: MEASURE → MOVE → STOP → MEASURE →
COMPARE → repeat.

Measurement: the Nordic DK streams every target packet; the laptop keeps a rolling median (10) +
EMA. Each decision waits for ≥5 fresh samples after a 1.5 s settle.

Decision (`signalhound/homing/strategies.py`): compare the current filtered RSSI to the RSSI at the
last *decision point* (reference), not the previous step. Gains accumulate along a heading.
- Δ ≥ +3 dB → IMPROVED: keep heading, reference := current.
- Δ ≤ −3 dB → WORSENED: reference := current, turn ~90° (0.8 rad/s × 2 s) and probe.
- otherwise after `PROBE_PATIENCE` (4) steps: if Δ ≥ +1.5 dB keep going, else turn.
Turns keep one direction (sweep) and flip after 6 consecutive turns, so the robot does not oscillate.
Arrival: filtered RSSI ≥ −45 dBm sustained 2 s → FOUND, stop. Budget: 180 s / 60 moves.
Signal lost → rotate slowly to re-acquire; obstacle ahead → turn.

Why these numbers (from simulation, `tests_sh/test_mock_search.py`): with path-loss slope ≈22 dB/decade,
moving 0.9 m at 4–6 m range changes RSSI by <3 dB in *every* direction, so short probes are
inconclusive and the robot random-walks. Probes of ~1.8 m (4 × 0.45 m) and ~90° turns converge in
9/10 synthetic cases with 2–5 dB noise. Real-world numbers go in `docs/experiment-log.md`.
