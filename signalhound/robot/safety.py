"""The ONLY path to the motors. Bounded bursts, latched stop, timeouts, always-stop on error."""

import asyncio
import logging
import time

log = logging.getLogger("signalhound.safety")


class MotionGuard:
    def __init__(self, robot, cfg):
        self.robot = robot
        self.cfg = cfg
        self.latched = False
        self.lock = asyncio.Lock()
        self.log = []  # (t, op, value, seconds)

    def _check(self, speed, seconds, cap):
        if self.latched:
            raise RuntimeError("STOP latched")
        if not (0 < speed <= cap):
            raise ValueError(f"speed {speed} outside (0, {cap}]")
        if not (0 < seconds <= self.cfg.max_burst_seconds):
            raise ValueError(f"burst {seconds}s outside (0, {self.cfg.max_burst_seconds}]")

    async def _burst(self, op, vx, vyaw, seconds):
        if self.lock.locked():
            raise RuntimeError("motion already in progress")
        async with self.lock:
            self.log.append((time.time(), op, vx or vyaw, seconds))
            log.info("burst %s vx=%.2f vyaw=%.2f %.2fs", op, vx, vyaw, seconds)
            try:
                async with asyncio.timeout(seconds + 2.0):
                    await self.robot.burst(vx, vyaw, seconds)
            except BaseException:
                self.latched = True
                await self.robot.stop()
                raise
            finally:
                await self.robot.stop()

    async def forward(self, speed=None, seconds=None):
        speed = self.cfg.move_speed if speed is None else speed
        seconds = self.cfg.move_step_seconds if seconds is None else seconds
        self._check(speed, seconds, self.cfg.max_move_speed)
        await self._burst("forward", speed, 0.0, seconds)

    async def backward(self, speed=None, seconds=None):
        speed = self.cfg.move_speed if speed is None else speed
        seconds = self.cfg.move_step_seconds if seconds is None else seconds
        self._check(speed, seconds, self.cfg.max_move_speed)
        await self._burst("backward", -speed, 0.0, seconds)

    async def rotate(self, direction, speed=None, seconds=None):
        """direction +1 = left (CCW, positive yaw), -1 = right."""
        speed = self.cfg.rotate_speed if speed is None else speed
        seconds = self.cfg.rotate_step_seconds if seconds is None else seconds
        self._check(speed, seconds, self.cfg.max_rotate_speed)
        await self._burst("rotate_left" if direction > 0 else "rotate_right", 0.0, speed * (1 if direction > 0 else -1), seconds)

    async def stop(self):
        self.latched = True
        await self.robot.stop()

    def resume(self):
        self.latched = False
