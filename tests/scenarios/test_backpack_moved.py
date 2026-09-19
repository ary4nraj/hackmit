import asyncio

from recall_rover.config import Settings
from recall_rover.memory.repository import Memory
from recall_rover.perception.pipeline import MockPerceptionProvider, Pipeline
from recall_rover.robot.exploration import Investigator
from recall_rover.robot.mock_robot import MockRobot
from recall_rover.robot.safety import Safety


def test_backpack_moved(tmp_path):
    async def run():
        s = Settings(
            database=str(tmp_path / "memory.db"), backend="mock", perception="mock"
        )
        m = Memory(s.database)
        r = MockRobot(s.zones, delay=0)
        p = Pipeline(r, MockPerceptionProvider(), m, s.zones)
        search = Investigator(m, Safety(r, s), p, s.zones)
        await p.inspect()
        a = m.find_best_match("backpack")
        assert a["observation"]["zone"] == "entrance table"
        r.move_object("backpack", "back wall")
        # Moving ground truth must NOT update memory.
        assert m.find_best_match("backpack")["observation"]["zone"] == "entrance table"
        result = await search.find_object("backpack")
        assert result["found"]
        b = m.find_best_match("backpack")
        assert b["id"] == a["id"]
        assert b["observation"]["zone"] == "back wall"
        assert m.observation(a["latest"]).status == "invalidated"
        events = list(reversed(m.changes()))
        kinds = [e["type"] for e in events]
        assert kinds.index("INVALIDATED") < kinds.index("MOVED")
        assert len(r.motion_log) >= 2
        m.close()
        reopened = Memory(s.database)
        assert (
            reopened.find_best_match("backpack")["observation"]["zone"] == "back wall"
        )
        reopened.close()

    asyncio.run(run())
