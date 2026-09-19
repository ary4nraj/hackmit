import asyncio
import logging
import math

from recall_rover.memory.models import Pose

log = logging.getLogger(__name__)


class Safety:
    def __init__(self, robot, settings, emit=lambda *a: None):
        self.robot = robot
        self.settings = settings
        self.emit = emit
        self.latched = False
        self.lock = asyncio.Lock()

    def validate(self, pose):
        pose = Pose.model_validate(pose)
        if not any(
            math.hypot(pose.x - x, pose.y - y) < 0.01
            for x, y in self.settings.zones.values()
        ):
            raise ValueError("Target is outside surveyed allowed waypoints")
        return pose

    async def _run(self, operation, args):
        if self.latched:
            raise RuntimeError("STOP is latched; operator must resume")
        if self.lock.locked():
            raise RuntimeError("Another motion is in progress")
        async with self.lock:
            log.info("motion.request %s %s", operation, args)
            self.emit(
                "robot.navigation.started", {"operation": operation, "args": str(args)}
            )
            try:
                async with asyncio.timeout(self.settings.navigation_timeout):
                    await getattr(self.robot, operation)(*args)
                if self.latched:
                    raise RuntimeError("Emergency stop interrupted motion")
                self.emit("robot.navigation.completed", {})
            except BaseException:
                await self.stop_now()
                self.emit("robot.navigation.failed", {})
                raise

    async def safe_navigate_to(self, pose):
        await self._run("navigate_to", (self.validate(pose), self.settings.max_linear))

    async def safe_rotate(self, angle):
        if not math.isfinite(angle) or abs(angle) > math.pi:
            raise ValueError("Rotation must be finite and at most pi radians")
        await self._run("rotate", (angle, self.settings.max_angular))

    async def stop_now(self):
        self.latched = True
        await self.robot.stop()
        self.emit("robot.stopped", {"latched": True})

    def resume(self):
        if self.lock.locked():
            raise RuntimeError("Wait for active motion to stop before resuming")
        self.latched = False
