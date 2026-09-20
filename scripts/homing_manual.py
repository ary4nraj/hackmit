"""LEVEL 0: a human moves the dog (or just walks the phone); we print RSSI + robot telemetry.

  python scripts/homing_manual.py            # radio only (no robot)
  python scripts/homing_manual.py --robot    # also connect the Go2 for telemetry (no motion)
Optionally log to a CSV with --log for docs/experiment-log.md.
"""

import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))
import argparse
import asyncio
import time

from signalhound.config import Config
from signalhound.dashboard import render
from signalhound.radio import make_radio
from signalhound.robot.mock import MockRobot


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--robot", action="store_true")
    p.add_argument("--log", default="")
    a = p.parse_args()
    cfg = Config()
    radio = make_radio(cfg).start()
    robot = MockRobot()
    if a.robot:
        from signalhound.robot.go2 import Go2Robot

        robot = Go2Robot(cfg)
        await robot.connect()
    log = open(a.log, "a") if a.log else None
    try:
        while True:
            render(cfg, radio, robot, None, "manual mode: no motion commands are sent")
            if log:
                s = radio.snapshot()
                st = robot.status()
                log.write(f"{time.time():.2f},{s['raw']},{s['filtered']},{st.get('x')},{st.get('y')},{st.get('yaw')}\n")
                log.flush()
            await asyncio.sleep(0.3)
    except KeyboardInterrupt:
        pass
    finally:
        radio.stop()
        if a.robot:
            await robot.disconnect()
        if log:
            log.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
