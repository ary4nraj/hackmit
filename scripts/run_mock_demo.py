import asyncio
import json

from recall_rover.config import Settings
from recall_rover.memory.repository import Memory
from recall_rover.perception.pipeline import MockPerceptionProvider, Pipeline
from recall_rover.robot.exploration import Investigator
from recall_rover.robot.mock_robot import MockRobot
from recall_rover.robot.safety import Safety


async def main():
    settings = Settings(database=":memory:", backend="mock", perception="mock")
    memory = Memory()
    robot = MockRobot(settings.zones)
    pipe = Pipeline(robot, MockPerceptionProvider(), memory, settings.zones)
    investigator = Investigator(memory, Safety(robot, settings), pipe, settings.zones)
    await pipe.inspect()
    print("REMEMBER:", memory.find_best_match("backpack")["observation"]["zone"])
    robot.move_object("backpack", "back wall")
    result = await investigator.find_object("backpack")
    print("RESULT:", json.dumps(result, indent=2))
    for event in reversed(memory.changes()):
        print(event["type"], event["summary"])
    assert result["found"] and result["observation"]["zone"] == "back wall"
    assert any(e["type"] == "MOVED" for e in memory.changes())
    memory.close()


if __name__ == "__main__":
    asyncio.run(main())
