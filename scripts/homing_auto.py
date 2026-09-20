"""Autonomous radio homing. --mock runs the 2D simulation; without it, the real Nordic DK + Go2.

Safety: Ctrl+C, any exception, serial loss or robot loss -> StopMove. Operator must type ENTER
after calibration before the first motion.
"""

import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))
import argparse
import asyncio
import signal
import sys
import time

from signalhound.config import Config
from signalhound.dashboard import Ticker, render
from signalhound.homing.controller import HomingController
from signalhound.homing.history import History
from signalhound.robot.safety import MotionGuard


async def confirm(ctl):
    print(f"\nTarget detected: {ctl.cfg.target_name}\nBaseline RSSI: {ctl.last_rssi:.1f} dBm\n")
    ans = await asyncio.to_thread(input, "Press ENTER to begin autonomous search (q to abort): ")
    return ans.strip().lower() != "q"


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mock", action="store_true", help="simulate radio + robot")
    p.add_argument("--target", default="4,2", help="mock target x,y")
    p.add_argument("--yes", action="store_true", help="skip the ENTER confirmation (mock only)")
    p.add_argument("--history", default="data/homing-history.jsonl")
    a = p.parse_args()
    cfg = Config()
    if a.mock:
        from signalhound.robot.mock import MockRadio, MockRobot, RadioField

        tx, ty = (float(v) for v in a.target.split(","))
        robot = MockRobot(realtime=True)
        radio = MockRadio(cfg, robot, RadioField(tx, ty, noise_db=3.0))
        cfg.settle_seconds = 0.2
    else:
        from signalhound.radio import make_radio
        from signalhound.robot.go2 import Go2Robot

        radio = make_radio(cfg).start()
        robot = Go2Robot(cfg)
        await robot.connect()
        await asyncio.sleep(1.0)
        if not robot.status()["telemetry_fresh"]:
            print("No fresh Go2 telemetry; refusing to move.")
            await robot.disconnect()
            return 2
    guard = MotionGuard(robot, cfg)
    import os

    os.makedirs("data", exist_ok=True)
    ctl = HomingController(cfg, radio, robot, guard, History(a.history), confirm=None if (a.mock and a.yes) else confirm)
    os.makedirs("data/logs", exist_ok=True)
    ctl.log_file = open(f"data/logs/homing-{time.strftime('%Y%m%d-%H%M%S')}.log", "a")
    ctl.log_file.write(f"# mode={'mock' if a.mock else 'hardware'} radio={cfg.radio_link} target={cfg.target_name} cfg={vars(cfg)}\n")
    tick = Ticker()
    ctl.on_update = lambda c: render(cfg, radio, robot, c) if tick.due() or c.state in ("FOUND", "STOPPED", "ERROR") else None
    task = asyncio.create_task(ctl.run())
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, lambda: (setattr(ctl, "stop_requested", True), task.cancel()))
    try:
        if not a.mock:
            await robot.stand_up()
        await task
    except asyncio.CancelledError:
        pass
    finally:
        await guard.stop()
        await robot.stop()
        render(cfg, radio, robot, ctl)
        if ctl.state == "FOUND":
            print("\nTARGET FOUND\nSignalHound located the target without vision.\n")
        else:
            print(f"\nEnded in state {ctl.state}: {ctl.decision}\n")
        radio.stop()
        if ctl.log_file:
            ctl.log_file.write(f"# END state={ctl.state} moves={ctl.moves} best={ctl.best_rssi}\n")
            ctl.log_file.close()
        if not a.mock:
            await robot.disconnect()
    return 0 if ctl.state == "FOUND" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
