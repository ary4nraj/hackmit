import asyncio

import pytest

from recall_rover.config import Settings
from recall_rover.memory.repository import Memory
from recall_rover.perception.pipeline import MockPerceptionProvider, Pipeline
from recall_rover.robot.exploration import Investigator
from recall_rover.robot.mock_robot import MockRobot
from recall_rover.robot.safety import Safety


def test_disappearance_bounded_and_no_hallucinated_location():
    async def run():
        s = Settings()
        m = Memory()
        r = MockRobot(s.zones, delay=0)
        p = Pipeline(r, MockPerceptionProvider(), m, s.zones)
        safe = Safety(r, s)
        await p.inspect()
        r.move_object("backpack", None)
        result = await Investigator(m, safe, p, s.zones).find_object("backpack")
        assert not result["found"] and len(result["checked"]) == len(s.zones)
        assert m.find_best_match("backpack")["status"] == "missing"
        assert not any(e["type"] == "MOVED" for e in m.changes())
        m.close()

    asyncio.run(run())


def test_camera_error_does_not_invalidate():
    async def run():
        s = Settings()
        m = Memory()
        r = MockRobot(s.zones, delay=0)
        p = Pipeline(r, MockPerceptionProvider(), m, s.zones)
        await p.inspect()

        async def broken():
            raise RuntimeError("camera offline")

        r.get_camera_frame = broken
        with pytest.raises(RuntimeError):
            await Investigator(m, Safety(r, s), p, s.zones).find_object("backpack")
        assert m.find_best_match("backpack")["status"] == "active"
        m.close()

    asyncio.run(run())
