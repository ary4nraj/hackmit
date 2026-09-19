"""DimosRobot contract tests with fakes shaped like the verified 0.0.14 RPC surface."""

import asyncio
import math
from types import SimpleNamespace

import pytest

from recall_rover.memory.models import Pose
from recall_rover.robot.dimos_robot import DimosRobot


class FakePlanner:
    def __init__(self, reach_after=2, idle_after=None):
        self.goals = []
        self.cancels = 0
        self.polls = 0
        self.reach_after = reach_after
        self.idle_after = idle_after
        self.reached = False

    def set_goal(self, goal):
        self.goals.append(goal)
        self.reached = False
        return True

    def is_goal_reached(self):
        self.polls += 1
        if self.reach_after is not None and self.polls >= self.reach_after:
            self.reached = True
        return self.reached

    def get_state(self):
        if self.idle_after is not None and self.polls >= self.idle_after:
            return SimpleNamespace(value="idle")
        return SimpleNamespace(value="following_path")

    def cancel_goal(self):
        self.cancels += 1
        return True


class FakeGo2:
    def __init__(self):
        self.stops = 0
        self.moves = []

    def stop_movement(self):
        self.stops += 1

    def move(self, twist, duration=0.0):
        self.moves.append((twist.angular.z, duration))
        return True

    def battery_soc(self):
        return 77


class Vec:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = x, y, z


class Quat:
    @classmethod
    def from_euler(cls, v):
        return cls()


class PoseMsg:
    def __init__(self, position, orientation, frame_id, ts):
        self.position, self.orientation, self.frame_id, self.ts = position, orientation, frame_id, ts


class TwistMsg:
    def __init__(self, linear, angular):
        self.linear, self.angular = linear, angular


MSGS = SimpleNamespace(Vector3=Vec, Quaternion=Quat, PoseStamped=PoseMsg, Twist=TwistMsg)


class FakeApp:
    def __init__(self, planner=None, go2=None, poses=None):
        self.modules = {}
        if planner:
            self.modules["ReplanningAStarPlanner"] = planner
        if go2:
            self.modules["GO2Connection"] = go2
        self.poses = list(poses or [(0, 0)])

    def get_module(self, name):
        if name not in self.modules:
            raise KeyError(f"no module {name}")
        return self.modules[name]

    def list_modules(self):
        return [SimpleNamespace(class_name=n) for n in self.modules]

    def peek_stream(self, name, timeout):
        if name == "odom":
            x, y = self.poses[0] if len(self.poses) == 1 else self.poses.pop(0)
            return SimpleNamespace(
                position=SimpleNamespace(x=x, y=y), orientation=SimpleNamespace(x=0, y=0, z=0, w=1)
            )
        return SimpleNamespace(to_opencv=lambda: "bgr-pixels")


def test_stop_attempts_motor_stop_even_when_planner_missing():
    async def run():
        go2 = FakeGo2()
        robot = DimosRobot(FakeApp(go2=go2))
        with pytest.raises(RuntimeError, match="STOP not confirmed"):
            await robot.stop()
        assert go2.stops == 1

    asyncio.run(run())


def test_pose_and_camera_verified_contracts():
    async def run():
        robot = DimosRobot(FakeApp(poses=[(1, 2)]))
        assert (await robot.get_pose()).x == 1
        assert await robot.get_camera_frame() == "bgr-pixels"

    asyncio.run(run())


def test_navigate_reaches_goal_then_halts():
    async def run():
        planner, go2 = FakePlanner(reach_after=2), FakeGo2()
        robot = DimosRobot(FakeApp(planner, go2, poses=[(0, 0)]), poll=0.001, msgs=MSGS)
        await robot.navigate_to(Pose(x=1, y=0, yaw=0.5), 0.25)
        assert len(planner.goals) == 1 and planner.goals[0].frame_id == "world"
        assert abs(planner.goals[0].position.x - 1) < 1e-6
        assert planner.cancels == 1 and go2.stops == 1 and not robot.moving
        assert robot.last_status == "arrived"
        health = await robot.get_health()
        assert health["battery_soc"] == 77 and health["motion_enabled"]

    asyncio.run(run())


def test_navigate_fails_when_planner_goes_idle_without_arrival():
    async def run():
        planner, go2 = FakePlanner(reach_after=None, idle_after=1), FakeGo2()
        robot = DimosRobot(FakeApp(planner, go2), poll=0.001, msgs=MSGS, idle_grace=0.0)
        with pytest.raises(RuntimeError, match="idle before reaching"):
            await robot.navigate_to(Pose(x=1, y=0), 0.25)
        assert planner.cancels == 1 and go2.stops == 1 and not robot.moving

    asyncio.run(run())


def test_speed_watchdog_halts_when_odometry_moves_too_fast():
    async def run():
        planner, go2 = FakePlanner(reach_after=None), FakeGo2()
        # 5 m jump between polls a millisecond apart: far above any cap.
        robot = DimosRobot(FakeApp(planner, go2, poses=[(0, 0), (5, 0), (10, 0)]), poll=0.001, msgs=MSGS)
        with pytest.raises(RuntimeError, match="exceeds cap"):
            await robot.navigate_to(Pose(x=1, y=0), 0.25)
        assert go2.stops == 1 and planner.cancels == 1 and not robot.moving

    asyncio.run(run())


def test_rotate_streams_bounded_twists_and_stops():
    async def run():
        planner, go2 = FakePlanner(), FakeGo2()
        robot = DimosRobot(FakeApp(planner, go2), msgs=MSGS)
        await robot.rotate(math.pi / 2, 4.0)  # short: ~0.4 s of streaming
        assert go2.moves and all(z == 4.0 and d == 0.0 for z, d in go2.moves)
        assert go2.stops == 1 and not robot.moving

    asyncio.run(run())


def test_motion_disabled_when_modules_missing():
    async def run():
        robot = DimosRobot(FakeApp(go2=FakeGo2()), motion_enabled=False)
        robot.last_status = "missing modules"
        with pytest.raises(RuntimeError, match="motion disabled"):
            await robot.navigate_to(Pose(), 0.2)
        with pytest.raises(RuntimeError, match="motion disabled"):
            await robot.rotate(1.0, 0.4)

    asyncio.run(run())
