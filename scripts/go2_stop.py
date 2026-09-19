"""Emergency: connect and send StopMove twice, then StandDown if --down."""

import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))
import asyncio
import sys

from signalhound.config import Config
from signalhound.robot.go2 import Go2Robot


async def main():
    robot = Go2Robot(Config())
    await robot.connect()
    try:
        await robot.stop()
        print("StopMove sent")
        if "--down" in sys.argv:
            await robot.stand_down()
            print("StandDown sent")
    finally:
        await robot.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
