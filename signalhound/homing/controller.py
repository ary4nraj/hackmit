"""Closed-loop radio homing: MEASURE -> MOVE -> MEASURE -> COMPARE -> repeat. Explicit state machine."""

import asyncio
import logging
import math
import time

from signalhound.homing.history import History
from signalhound.homing.strategies import IMPROVED, INCONCLUSIVE, HillClimb, compare
from signalhound.homing import scan as scanmod

log = logging.getLogger("signalhound.homing")

STATES = ("WAITING_FOR_SIGNAL", "CALIBRATING", "SEARCHING", "PROBING", "ADVANCING", "SIGNAL_LOST",
          "AVOIDING_OBSTACLE", "FOUND", "STOPPED", "ERROR")


class HomingController:
    def __init__(self, cfg, radio, robot, guard, history=None, sleep=asyncio.sleep, clock=time.time,
                 on_update=None, confirm=None):
        self.cfg, self.radio, self.robot, self.guard = cfg, radio, robot, guard
        self.history = history or History()
        self.sleep, self.clock = sleep, clock
        self.on_update = on_update or (lambda c: None)
        self.confirm = confirm  # async callable returning True to start moving
        self.log_file = None
        self.last_measure_n = 0
        self.lost_streak = 0
        self.strategy = HillClimb(patience=cfg.probe_patience, trend_db=cfg.trend_db, turn_patience=cfg.turn_patience)
        self.state = "WAITING_FOR_SIGNAL"
        self.decision = ""
        self.best_rssi = None
        self.moves = 0
        self.started = None
        self.strong_since = None
        self.last_rssi = None
        self.stop_requested = False

    # ---- helpers ----------------------------------------------------------
    def _set(self, state, decision=None):
        self.state = state
        if decision is not None:
            self.decision = decision
        if self.log_file:
            snap = self.radio.snapshot()
            self.log_file.write(
                f"{time.strftime('%H:%M:%S')} {state:18s} moves={self.moves:3d} n={self.last_measure_n:2d} "
                f"rssi={None if snap.get('filtered') is None else round(snap['filtered'], 1)} "
                f"best={None if self.best_rssi is None else round(self.best_rssi, 1)} | {self.decision}\n"
            )
            self.log_file.flush()
        self.on_update(self)

    async def _measure(self, label=""):
        """Fresh window after a move; returns filtered RSSI or None if the target is silent."""
        self.radio.reset_window()
        ok = await asyncio.to_thread(self.radio.wait_for_samples, self.cfg.rssi_min_samples, self.cfg.measure_timeout_seconds)
        snap = self.radio.snapshot()
        n = snap.get("samples") or 0
        # A slow beacon must not look like a lost one: accept a thin window, give up only on (near) silence.
        if not ok and n < self.cfg.decision_min_samples:
            # Thin window: give the beacon one more chance before judging.
            await asyncio.to_thread(self.radio.wait_for_samples, self.cfg.decision_min_samples, self.cfg.measure_timeout_seconds)
            snap = self.radio.snapshot()
            n = snap.get("samples") or 0
        rssi = snap.get("filtered") if n >= 2 else None
        self.last_measure_n = n
        x, y = await self.robot.get_position()
        yaw = await self.robot.get_yaw()
        self.history.add(x, y, yaw, rssi, self.state, f"{label} n={n}")
        if rssi is not None:
            self.last_rssi = rssi
            if self.best_rssi is None or rssi > self.best_rssi:
                self.best_rssi = rssi
        return rssi

    def _found(self, rssi):
        if rssi is not None and rssi >= self.cfg.target_rssi_threshold:
            self.strong_since = self.strong_since or self.clock()
            return self.clock() - self.strong_since >= self.cfg.target_rssi_hold_seconds
        self.strong_since = None
        return False

    async def _obstacle_ahead(self):
        ranges = await self.robot.get_obstacle_ranges()
        if not ranges:
            return False
        try:
            front = min(float(r) for r in ranges[:1]) if len(ranges) >= 1 else None
        except (TypeError, ValueError):
            return False
        return front is not None and 0 < front < self.cfg.obstacle_stop_m

    async def _turn(self, direction, big=False):
        secs = min(self.cfg.rotate_step_seconds * (2 if big else 1), self.cfg.max_burst_seconds)
        await self.guard.rotate(direction, seconds=secs)
        self.moves += 1

    async def _step(self):
        await self.guard.forward(seconds=self.cfg.move_step_seconds)
        self.moves += 1
        await self.sleep(self.cfg.settle_seconds)

    def _budget_left(self):
        return not self.stop_requested and self.elapsed() <= self.cfg.search_timeout_seconds and self.moves < self.cfg.max_moves

    async def _probe_sides(self, ref0, first_dir, d_forward=None):
        """Level 2: when the current heading is flat/worse, test BOTH sides with short probes and commit
        to the better one. Returns (rssi_now, committed_dir, delta) with committed_dir in {+1,-1}."""
        steps = self.cfg.side_probe_steps
        names = {1: "left", -1: "right"}
        # A single noisy reading must not become the yardstick: re-measure here without moving.
        again = await self._measure("recheck")
        if again is not None and ref0 is not None:
            ref0 = (ref0 + again) / 2
        elif again is not None:
            ref0 = again
        # Side A
        self._set("PROBING", f"flat heading (ref {ref0 if ref0 is None else round(ref0,1)}): probing {names[first_dir]} ({steps} steps)")
        await self._turn(first_dir)
        for _ in range(steps):
            if not self._budget_left():
                return None, first_dir, None
            await self._step()
        rA = await self._measure(f"probe {names[first_dir]}")
        dA = None if (rA is None or ref0 is None) else rA - ref0
        if dA is not None and dA >= self.cfg.trend_db:
            self._set("PROBING", f"{names[first_dir]} probe {dA:+.1f} dB → commit {names[first_dir]}")
            return rA, first_dir, dA
        # Side B: turn around, pass back through the decision point, probe the other side
        self._set("PROBING", f"{names[first_dir]} probe {'n/a' if dA is None else f'{dA:+.1f} dB'}: trying {names[-first_dir]}")
        await self._turn(first_dir)
        await self._turn(first_dir)
        for _ in range(2 * steps):
            if not self._budget_left():
                return None, -first_dir, None
            await self._step()
        rB = await self._measure(f"probe {names[-first_dir]}")
        dB = None if (rB is None or ref0 is None) else rB - ref0
        if dB is not None and dB >= self.cfg.trend_db and (dA is None or dB >= dA):
            self._set("PROBING", f"{names[-first_dir]} probe {dB:+.1f} dB → commit {names[-first_dir]}")
            return rB, -first_dir, dB
        # Nothing clearly better: pick the least-bad of forward / A / B.
        cands = {"forward": d_forward, names[first_dir]: dA, names[-first_dir]: dB}
        best = max((k for k in cands if cands[k] is not None), key=lambda k: cands[k], default=names[-first_dir])
        fmt = lambda v: "n/a" if v is None else f"{v:+.1f}"  # noqa: E731
        self._set("PROBING", f"all flat (fwd {fmt(d_forward)} / {names[first_dir]} {fmt(dA)} / {names[-first_dir]} {fmt(dB)}): continuing {best}")
        if best == "forward":
            await self._turn(first_dir)            # from B's heading, one turn back to the original heading
            return rB, first_dir, d_forward
        if best == names[first_dir]:
            await self._turn(first_dir)
            await self._turn(first_dir)            # turn around: head back through the decision point toward A
            return rB, first_dir, dA
        return rB, -first_dir, dB

    async def _run_scan(self, current):
        """Spin-scan → face best → go; repeat. Arrival and budgets checked after every measurement."""
        while True:
            if self.stop_requested:
                return self._set("STOPPED", "operator stop")
            if not self._budget_left():
                return self._set("STOPPED", "search budget exhausted")
            if self._found(current):
                return self._set("FOUND", f"sustained {current:.1f} dBm ≥ {self.cfg.target_rssi_threshold} dBm")
            self._set("SEARCHING", "spin scan")
            readings = await scanmod.spin_scan(self)
            yaw, r_best = scanmod.best_heading(readings)
            c = scanmod.contrast(readings)
            if yaw is None:
                self._set("SIGNAL_LOST", "no beacon on any heading; waiting")
                current = await self._measure("wait")
                continue
            summary = " ".join(f"{scanmod.deg(y)}°:{'n/a' if v is None else f'{v:.0f}'}" for y, v, _ in readings)
            self._set("SEARCHING", f"scan [{summary}] contrast {c:.0f} dB → face {scanmod.deg(yaw)}°")
            await scanmod.rotate_to(self, yaw)
            current = r_best
            if self._found(current):
                continue
            # Drive along the best heading; bail if the signal collapses (we passed it or it was noise).
            for i in range(self.cfg.scan_go_steps):
                if not self._budget_left() or self.stop_requested:
                    break
                self._set("ADVANCING", f"go {i + 1}/{self.cfg.scan_go_steps} toward {scanmod.deg(yaw)}°")
                await self._step()
                r = await self._measure(f"go {i + 1}")
                if r is not None:
                    current = r
                    if self._found(current):
                        break
                    if r_best is not None and r < r_best - self.cfg.scan_abort_drop_db:
                        self._set("ADVANCING", f"signal fell {r_best - r:.0f} dB on this heading; rescanning")
                        break

    def _why_no_signal(self):
        snap = self.radio.snapshot()
        link = getattr(self.cfg, "radio_link", "serial")
        if not snap.get("connected"):
            if link == "ble":
                return "no broadcasts from the DK: is it powered (power bank auto-off? LED1 blinking?) and within ~10 m?"
            return f"no serial port / no lines from the DK (port={snap.get('port')}): USB cable? firmware running?"
        dk_age = getattr(self.radio, "dk_age", None)
        if link == "ble" and dk_age == 255:
            return f"DK alive (link {getattr(self.radio, 'link_rssi', '?')} dBm) but it does NOT hear '{self.cfg.target_name}': phone screen on? nRF Connect advertising?"
        return f"DK alive, waiting for '{self.cfg.target_name}' packets (heartbeat {snap.get('heartbeat_age')} s ago)"

    def elapsed(self):
        return 0.0 if self.started is None else self.clock() - self.started

    # ---- main loop --------------------------------------------------------
    async def run(self):
        try:
            await self._run()
        except asyncio.CancelledError:
            self._set("STOPPED", "cancelled")
            raise
        except Exception as exc:  # noqa: BLE001
            log.exception("homing error")
            self._set("ERROR", f"{type(exc).__name__}: {exc}")
        finally:
            await self.guard.stop()
            await self.robot.stop()

    async def _run(self):
        self._set("WAITING_FOR_SIGNAL", "waiting for target beacon")
        while self.radio.get_filtered_rssi() is None:
            if self.stop_requested:
                return self._set("STOPPED", "operator stop")
            await asyncio.to_thread(self.radio.wait_for_samples, 1, 1.0)
            self._set("WAITING_FOR_SIGNAL", self._why_no_signal())
        self._set("CALIBRATING", "collecting baseline")
        baseline = await self._measure("baseline")
        if baseline is None:
            self._set("CALIBRATING", "no baseline")
        elif baseline <= self.cfg.weak_signal_dbm:
            self._set("CALIBRATING", f"baseline {baseline:.1f} dBm is at the receiver floor (<= {self.cfg.weak_signal_dbm}): "
                      "homing will be noise. Fix the beacon mounting / move closer before starting.")
        else:
            self._set("CALIBRATING", f"baseline {baseline:.1f} dBm")
        if self.confirm and not await self.confirm(self):
            return self._set("STOPPED", "operator declined")
        self.started = self.clock()
        if self.cfg.homing_mode == "scan":
            return await self._run_scan(baseline)
        ref = baseline          # RSSI at the last decision point (heading chosen here)
        current = baseline
        action = "advance"
        while True:
            if self.stop_requested:
                return self._set("STOPPED", "operator stop")
            if self.elapsed() > self.cfg.search_timeout_seconds or self.moves >= self.cfg.max_moves:
                return self._set("STOPPED", "search budget exhausted")
            if self._found(current):
                return self._set("FOUND", f"sustained {current:.1f} dBm ≥ {self.cfg.target_rssi_threshold} dBm")
            if current is None:
                self.lost_streak += 1
                if self.lost_streak == 1 and self.moves > 0:
                    # The last step probably carried us out of range: undo it before anything else.
                    self._set("SIGNAL_LOST", "target silent after a step; backing up to the last good spot")
                    await self.guard.backward(seconds=self.cfg.move_step_seconds)
                else:
                    self._set("SIGNAL_LOST", "target still silent; rotating slowly to re-acquire")
                    await self.guard.rotate(+1, seconds=self.cfg.rotate_step_seconds)
                self.moves += 1
                current = await self._measure("reacquire")
                ref = current
                continue
            self.lost_streak = 0
            if await self._obstacle_ahead():
                self._set("AVOIDING_OBSTACLE", "obstacle ahead; turning")
                await self.guard.rotate(self.strategy.next_turn(), seconds=self.cfg.rotate_step_seconds)
                self.moves += 1
                current = await self._measure("avoid")
                ref = current if current is not None else ref
                continue
            # --- ONE bounded action, then stop, settle, measure ---
            if action.startswith("turn") and self.cfg.side_probe_steps > 0:
                first_dir = +1 if "left" in action else -1
                d_forward = None if (current is None or ref is None) else current - ref
                r1, chosen, delta = await self._probe_sides(current, first_dir, d_forward)
                self.strategy.turn_dir = chosen
                self.strategy.inconclusive = 0
                if delta is not None and delta >= self.cfg.trend_db:
                    self.strategy.turns_in_a_row = 0
                ref = current if r1 is not None else ref
                action = "advance"
                current = r1 if r1 is not None else current
                if r1 is not None:
                    ref = r1 - (delta or 0.0)  # keep the pre-probe reference so gains keep accumulating
                continue
            if action.startswith("turn") and self.cfg.gradient_points > 0:
                g = self.history.gradient(k=self.cfg.gradient_points)
                if g is not None:
                    a, b, r2 = g
                    mag = math.hypot(a, b)
                    if mag >= self.cfg.gradient_min_db_per_m and r2 >= self.cfg.gradient_min_r2:
                        heading = math.atan2(b, a)
                        self._set("SEARCHING", f"plane fit over last {self.cfg.gradient_points} points: {mag:.1f} dB/m toward {round(math.degrees(heading))}° (R²={r2:.2f}) → turning there")
                        await scanmod.rotate_to(self, heading)
                        self.strategy.inconclusive = 0
                        ref = current
                        action = "advance"
                        self._set("PROBING", "probing gradient heading")
                        await self._step()
                        r1 = await self._measure("gradient")
                        verdict = compare(ref, r1, self.cfg.rssi_improvement_db, self.cfg.rssi_worsen_db)
                        delta = None if (ref is None or r1 is None) else r1 - ref
                        action = self.strategy.decide(verdict, delta)
                        self._set(self.state, f"ref {'n/a' if ref is None else f'{ref:.1f}'} → now {'n/a' if r1 is None else f'{r1:.1f}'} dBm {verdict} → {action.upper()}")
                        if verdict != INCONCLUSIVE:
                            ref = r1
                        current = r1
                        continue
            if action.startswith("turn"):
                self._set("SEARCHING", f"{action} then probe")
                await self._turn(+1 if "left" in action else -1, big=action.endswith("_big"))
                ref = current  # new heading: judge it against where we are now
                self._set("PROBING", "probing new heading")
            else:
                self._set("ADVANCING", "moving forward")
            await self._step()
            r1 = await self._measure(action)
            verdict = compare(ref, r1, self.cfg.rssi_improvement_db, self.cfg.rssi_worsen_db)
            delta = None if (ref is None or r1 is None) else r1 - ref
            action = self.strategy.decide(verdict, delta)
            arrow = "↑" if verdict == IMPROVED else "↓" if verdict == "WORSENED" else "→"
            fmt = lambda v: "n/a" if v is None else f"{v:.1f}"  # noqa: E731
            self._set(self.state, f"ref {fmt(ref)} → now {fmt(r1)} dBm {arrow} {verdict} → {action.upper()}")
            if verdict != INCONCLUSIVE:
                ref = r1
            current = r1
