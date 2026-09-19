import asyncio
import json
from types import SimpleNamespace

import pytest

from recall_rover.agent.agent import Agent
from recall_rover.api.app import Runtime
from recall_rover.config import Settings
from recall_rover.perception.pipeline import MockPerceptionProvider
from recall_rover.robot.mock_robot import MockRobot


class FakeResponses:
    def __init__(self):
        self.requests = []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        if len(self.requests) == 1:
            call = SimpleNamespace(
                type="function_call",
                name="rover",
                arguments=json.dumps(
                    {"action": "search_memory", "target": "backpack", "since": 0}
                ),
                call_id="test-call",
            )
            return SimpleNamespace(output=[call], output_text="")
        result = json.loads(kwargs["input"][-1]["output"])
        assert result[0]["observation"]["zone"] == "entrance table"
        assert kwargs["input"][-1]["call_id"] == "test-call"
        return SimpleNamespace(output=[], output_text="Last seen near entrance table.")


def test_cloud_tool_roundtrip_without_api_key():
    async def run():
        s = Settings(database=":memory:")
        rt = Runtime(s, MockRobot(s.zones, delay=0), MockPerceptionProvider())
        await rt.pipeline.inspect()
        fake = FakeResponses()
        agent = Agent(rt.tools, rt.emit, SimpleNamespace(responses=fake))
        result = await agent.message("Where is my backpack?")
        assert result["answer"] == "Last seen near entrance table."
        assert fake.requests[0]["parallel_tool_calls"] is False
        assert len(fake.requests) == 2
        rt.memory.close()

    asyncio.run(run())


def test_multistep_and_people_constraint():
    async def run():
        s = Settings(database=":memory:")
        rt = Runtime(s, MockRobot(s.zones, delay=0), MockPerceptionProvider())
        await rt.pipeline.inspect()
        answer = await rt.agent.offline(
            "Find backpack and then check whether anyone is near the door"
        )
        assert "backpack" in answer and "person" in answer
        with pytest.raises(ValueError):
            await rt.tools.call(
                {"action": "find_object", "target": "person", "since": 0}
            )
        rt.memory.close()

    asyncio.run(run())
