"""Read-only dimOS preflight. Never issues a movement command."""

import asyncio
import json

from recall_rover.robot.dimos_robot import DimosRobot


async def main():
    robot = await DimosRobot.connect()
    print(json.dumps(await robot.get_health(), indent=2))
    modules = await asyncio.to_thread(robot.app.list_modules)
    print(modules)
    frame = await robot.get_camera_frame()
    print("camera shape:", getattr(frame, "shape", None))
    await asyncio.to_thread(robot.app.stop)  # Remote disconnect only.


if __name__ == "__main__":
    asyncio.run(main())
