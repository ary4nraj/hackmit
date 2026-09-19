"""Connect to the Go2 (LocalAP) and print live telemetry for a few seconds. NO MOTION."""

import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))
import asyncio
import json
import time

from signalhound.config import Config
from signalhound.robot.go2 import Go2Robot


async def main():
    cfg = Config()
    robot = Go2Robot(cfg)
    print(f"connecting to Go2 at {cfg.go2_ip} via LocalAP (AES key {'set' if cfg.go2_aes_key else 'NOT set'})")
    await robot.connect()
    try:
        for _ in range(10):
            await asyncio.sleep(0.5)
            print(json.dumps(robot.status(), default=str))
        print("raw keys:", sorted(robot.state.keys()))
    finally:
        await robot.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
