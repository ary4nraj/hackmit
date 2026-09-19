"""Closed-loop radio homing: MEASURE -> MOVE -> MEASURE -> COMPARE -> repeat. Explicit state machine."""

import asyncio
import logging
import time

from signalhound.homing.history import History
from signalhound.homing.strategies import IMPROVED, INCONCLUSIVE, HillClimb, compare

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
        self.strategy = HillClimb(patience=cfg.probe_patience, trend_db=cfg.trend_db)
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
        self.on_update(self)

    async def _measure(self, label=""):
        """Fresh window after a move; returns filtered RSSI or None if the target is silent."""
        self.radio.reset_window()
        ok = await asyncio.to_thread(self.radio.wait_for_samples, self.cfg.rssi_min_samples, self.cfg.measure_timeout_seconds)
        rssi = self.radio.get_filtered_rssi() if ok else None
        x, y = await self.robot.get_position()
        yaw = await self.robot.get_yaw()
        self.history.add(x, y, yaw, rssi, self.state, label)
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
        self._set("CALIBRATING", "collecting baseline")
        baseline = await self._measure("baseline")
        self._set("CALIBRATING", f"baseline {baseline:.1f} dBm" if baseline is not None else "no baseline")
        if self.confirm and not await self.confirm(self):
            return self._set("STOPPED", "operator declined")
        self.started = self.clock()
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
                self._set("SIGNAL_LOST", "target silent; rotating slowly to re-acquire")
                await self.guard.rotate(+1, seconds=self.cfg.rotate_step_seconds)
                self.moves += 1
                current = await self._measure("reacquire")
                ref = current
                continue
            if await self._obstacle_ahead():
                self._set("AVOIDING_OBSTACLE", "obstacle ahead; turning")
                await self.guard.rotate(self.strategy.next_turn(), seconds=self.cfg.rotate_step_seconds)
                self.moves += 1
                current = await self._measure("avoid")
                ref = current if current is not None else ref
                continue
            # --- ONE bounded action, then stop, settle, measure ---
            if action.startswith("turn"):
                self._set("SEARCHING", f"{action} then probe")
                big = action.endswith("_big")
                await self.guard.rotate(+1 if "left" in action else -1,
                                        seconds=min(self.cfg.rotate_step_seconds * (2 if big else 1), self.cfg.max_burst_seconds))
                self.moves += 1
                ref = current  # new heading: judge it against where we are now
                self._set("PROBING", "probing new heading")
            else:
                self._set("ADVANCING", "moving forward")
            await self.guard.forward(seconds=self.cfg.move_step_seconds)
            self.moves += 1
            await self.sleep(self.cfg.settle_seconds)
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
