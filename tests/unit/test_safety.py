import asyncio

import pytest

from recall_rover.agent.tools import ToolArgs
from recall_rover.config import Settings
from recall_rover.memory.models import Pose
from recall_rover.robot.mock_robot import MockRobot
from recall_rover.robot.safety import Safety


def test_restrictions():
    async def run():
        s = Settings()
        r = MockRobot(s.zones)
        safety = Safety(r, s)
        with pytest.raises(ValueError):
            await safety.safe_navigate_to(Pose(x=100))
        with pytest.raises(ValueError):
            await safety.safe_rotate(float("nan"))
        with pytest.raises(ValueError):
            Pose(x=float("inf"))
        with pytest.raises(ValueError):
            ToolArgs(action="shell", target="rm", since=0)
        with pytest.raises(ValueError):
            ToolArgs(action="find_object", target="backpack", since=0, raw_speed=5)
        assert not r.motion_log

    asyncio.run(run())


def test_stop_latches_and_prevents_arrival():
    async def run():
        s = Settings()
        r = MockRobot(s.zones, delay=0.08)
        safe = Safety(r, s)
        task = asyncio.create_task(safe.safe_navigate_to(Pose(x=1, y=1)))
        await asyncio.sleep(0.01)
        await safe.stop_now()
        with pytest.raises(RuntimeError):
            await task
        assert r.pose.x == 0 and not r.moving
        with pytest.raises(RuntimeError):
            await safe.safe_navigate_to(Pose(x=1, y=1))
        safe.resume()
        await safe.safe_navigate_to(Pose(x=1, y=1))
        assert r.pose.x == 1

    asyncio.run(run())


def test_timeout_stops_and_serialization():
    async def run():
        s = Settings(navigation_timeout=0.02)
        r = MockRobot(s.zones, delay=0.2)
        safe = Safety(r, s)
        task = asyncio.create_task(safe.safe_navigate_to(Pose(x=1, y=1)))
        await asyncio.sleep(0.001)
        with pytest.raises(RuntimeError):
            await safe.safe_navigate_to(Pose(x=1, y=1))
        with pytest.raises(TimeoutError):
            await task
        assert safe.latched and not r.moving and r.pose.x == 0

    asyncio.run(run())
