"""Shared body for the tiny movement tests: connect, stand, ONE bounded burst, stop, report pose delta."""

import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))
import asyncio
import json

from signalhound.config import Config
from signalhound.robot.go2 import Go2Robot
from signalhound.robot.safety import MotionGuard


async def run(kind, speed, seconds):
    cfg = Config()
    robot = Go2Robot(cfg)
    guard = MotionGuard(robot, cfg)
    await robot.connect()
    try:
        await asyncio.sleep(1.0)
        before = robot.status()
        print("before:", json.dumps(before, default=str))
        if not before["telemetry_fresh"]:
            print("no fresh telemetry; refusing to move")
            return
        if input(f"{kind} {speed} for {seconds}s. Floor clear? type YES: ").strip() != "YES":
            print("aborted")
            return
        await robot.stand_up()
        if kind == "forward":
            await guard.forward(speed, seconds)
        elif kind == "left":
            await guard.rotate(+1, speed, seconds)
        elif kind == "right":
            await guard.rotate(-1, speed, seconds)
        await asyncio.sleep(1.0)
        after = robot.status()
        print("after: ", json.dumps(after, default=str))
        if before["x"] is not None and after["x"] is not None:
            dx, dy = after["x"] - before["x"], after["y"] - before["y"]
            print(f"delta: dx={dx:.3f} dy={dy:.3f} dyaw={(after['yaw'] or 0) - (before['yaw'] or 0):.3f}")
    finally:
        await robot.stop()
        await robot.disconnect()
        print("stopped + disconnected")
