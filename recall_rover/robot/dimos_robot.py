"""dimOS Go2 adapter using verified 0.0.14 RPCs (see docs/dimos-notes.md).

Motion path: ReplanningAStarPlanner.set_goal -> poll is_goal_reached/get_state ->
cancel_goal + GO2Connection.stop_movement. Rotation streams short cmd_vel twists through
GO2Connection.move so the connection's 0.2 s deadman timer stops the base if we vanish.
Speed cap: the planner's 0.55 m/s is scaled by `dimos --nerf-speed` at launch; this adapter
additionally watches odometry and halts if measured speed exceeds the configured limit.
"""

import asyncio
import math
import time

from recall_rover.memory.models import Pose

REQUIRED_MODULES = {"GO2Connection", "ReplanningAStarPlanner"}


class DimosRobot:
    def __init__(self, app, poll=0.25, speed_tolerance=1.5, motion_enabled=True, msgs=None, idle_grace=2.0):
        self.app = app
        self.poll = poll
        self.speed_tolerance = speed_tolerance
        self.motion_enabled = motion_enabled
        self._msgs = msgs
        self.idle_grace = idle_grace
        self.moving = False
        self.last_odom = None
        self.last_status = "idle"

    @classmethod
    async def connect(cls, timeout=5.0):
        try:
            from dimos import Dimos
        except ImportError as exc:
            raise RuntimeError(
                "dimOS not installed. See docs/hardware-setup.md; mock fallback is never implicit."
            ) from exc
        app = await asyncio.to_thread(lambda: Dimos.connect(timeout=timeout))
        robot = cls(app)
        modules = await robot.module_names()
        missing = REQUIRED_MODULES - set(modules)
        if missing:
            robot.motion_enabled = False
            robot.last_status = f"motion disabled; missing modules {sorted(missing)}"
        return robot

    async def module_names(self):
        try:
            infos = await asyncio.to_thread(self.app.list_modules)
        except Exception as exc:
            raise RuntimeError(f"dimOS coordinator unreachable: {exc}") from exc
        names = []
        for info in infos:
            for attr in ("class_name", "name", "instance_name"):
                value = getattr(info, attr, None)
                if value and str(value) not in names:
                    names.append(str(value))
        return names

    def module(self, name):
        return self.app.get_module(name)

    async def rpc(self, module, method, *args):
        handle = self.module(module)
        return await asyncio.to_thread(lambda: getattr(handle, method)(*args))

    def _peek(self, stream, timeout=1.0):
        """Read GO2Connection's stream directly; fall back to the coordinator-wide search."""
        try:
            handle = self.module("GO2Connection")
            msg = handle.peek_stream(stream, timeout)
            if msg is not None:
                return msg
        except Exception:
            pass
        return self.app.peek_stream(stream, timeout)

    async def get_pose(self):
        msg = await asyncio.to_thread(self._peek, "odom", 1.0)
        if msg is None:
            raise RuntimeError("No fresh odometry; do not navigate")
        p = msg.position
        q = msg.orientation
        pose = Pose(
            x=float(p.x),
            y=float(p.y),
            yaw=math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z)),
        )
        self.last_odom = (pose, time.monotonic())
        return pose

    async def get_camera_frame(self):
        image = await asyncio.to_thread(self._peek, "color_image", 1.0)
        if image is None:
            raise RuntimeError("No fresh dimOS camera frame")
        return image.to_opencv()

    @property
    def msgs(self):
        """dimOS geometry message types (verified constructors, docs/dimos-notes.md)."""
        if self._msgs is None:
            from types import SimpleNamespace

            from dimos.msgs.geometry_msgs.PoseStamped import PoseStamped
            from dimos.msgs.geometry_msgs.Quaternion import Quaternion
            from dimos.msgs.geometry_msgs.Twist import Twist
            from dimos.msgs.geometry_msgs.Vector3 import Vector3

            self._msgs = SimpleNamespace(PoseStamped=PoseStamped, Quaternion=Quaternion, Twist=Twist, Vector3=Vector3)
        return self._msgs

    def _goal(self, pose):
        m = self.msgs
        return m.PoseStamped(
            position=m.Vector3(pose.x, pose.y, 0.0),
            orientation=m.Quaternion.from_euler(m.Vector3(0.0, 0.0, pose.yaw)),
            frame_id="world",
            ts=time.time(),
        )

    async def _halt(self, strict):
        results = await asyncio.gather(
            self.rpc("ReplanningAStarPlanner", "cancel_goal"),
            self.rpc("GO2Connection", "stop_movement"),
            return_exceptions=True,
        )
        self.moving = False
        errors = [str(x) for x in results if isinstance(x, Exception)]
        if errors and strict:
            raise RuntimeError("STOP not confirmed; use physical stop. " + "; ".join(errors))
        return errors

    async def stop(self):
        await self._halt(strict=True)

    def _require_motion(self):
        if not self.motion_enabled:
            raise RuntimeError("dimOS motion disabled: " + self.last_status)

    async def navigate_to(self, pose, speed):
        self._require_motion()
        start_pose = await self.get_pose()
        goal = await asyncio.to_thread(self._goal, pose)
        accepted = await self.rpc("ReplanningAStarPlanner", "set_goal", goal)
        if not accepted:
            raise RuntimeError("Planner rejected the goal")
        self.moving = True
        self.last_status = "navigating"
        started = time.monotonic()
        previous, previous_t = start_pose, started
        overspeed = 0
        try:
            while True:
                await asyncio.sleep(self.poll)
                if await self.rpc("ReplanningAStarPlanner", "is_goal_reached"):
                    self.last_status = "arrived"
                    return
                current = await self.get_pose()
                now = time.monotonic()
                dt = now - previous_t
                if dt > 0:
                    measured = math.hypot(current.x - previous.x, current.y - previous.y) / dt
                    # Two consecutive samples: odometry jitter must not fake an overspeed.
                    overspeed = overspeed + 1 if measured > speed * self.speed_tolerance + 0.05 else 0
                    if overspeed >= 2:
                        raise RuntimeError(
                            f"Measured speed {measured:.2f} m/s exceeds cap {speed:.2f} m/s; stopped"
                        )
                previous, previous_t = current, now
                state = await self.rpc("ReplanningAStarPlanner", "get_state")
                state_name = getattr(state, "value", state)
                if state_name == "idle" and now - started > self.idle_grace:
                    raise RuntimeError("Planner returned to idle before reaching the goal")
        except BaseException as exc:
            self.last_status = f"halted: {type(exc).__name__}: {str(exc)[:80]}"
            raise
        finally:
            errors = await self._halt(strict=False)
            if errors:
                self.last_status = "halt errors: " + "; ".join(errors)

    async def rotate(self, angle, speed):
        """Rotate in place by streaming bounded twists; each one expires via the deadman."""
        self._require_motion()
        m = self.msgs
        duration = min(abs(angle) / speed, 12.0)
        twist = m.Twist(linear=m.Vector3(0.0, 0.0, 0.0), angular=m.Vector3(0.0, 0.0, math.copysign(speed, angle)))
        self.moving = True
        self.last_status = "rotating"
        started = time.monotonic()
        try:
            while time.monotonic() - started < duration:
                ok = await self.rpc("GO2Connection", "move", twist, 0.0)
                if ok is False:
                    raise RuntimeError("Go2 rejected the movement command")
                await asyncio.sleep(0.1)
        finally:
            await self._halt(strict=False)

    async def get_health(self):
        try:
            pose = await self.get_pose()
        except Exception as exc:
            return {
                "connected": False,
                "backend": "dimos",
                "moving": False,
                "error": str(exc),
                "motion_enabled": False,
            }
        health = {
            "connected": True,
            "backend": "dimos",
            "moving": self.moving,
            "pose": pose.model_dump(),
            "motion_enabled": self.motion_enabled,
            "status": self.last_status,
        }
        try:
            health["battery_soc"] = await self.rpc("GO2Connection", "battery_soc")
        except Exception:
            pass
        return health
