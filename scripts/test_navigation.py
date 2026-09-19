"""Go2 commissioning: ONE bounded move to a surveyed waypoint with an operator beside the robot.

Prerequisites (see docs/hardware-setup.md):
  1. `./scripts/dimos.sh --nerf-speed 0.45 run unitree-go2` running with ROBOT_IP set.
  2. ZONES_FILE pointing at surveyed [x, y] waypoints in the odometry frame.
  3. A clear, flat area and a person holding the Unitree remote/app stop.
"""

import argparse
import asyncio
import json
import time

from recall_rover.config import Settings
from recall_rover.memory.models import Pose
from recall_rover.robot.dimos_robot import DimosRobot
from recall_rover.robot.safety import Safety


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zone", help="Waypoint name from ZONES_FILE (omit for a rotate-only check)")
    parser.add_argument("--rotate", type=float, default=0.0, help="Radians to rotate in place, at most pi")
    args = parser.parse_args()
    settings = Settings()
    if settings.backend != "dimos":
        raise SystemExit("Set ROBOT_BACKEND=dimos, PERCEPTION_PROVIDER=local, ZONES_FILE=... first")
    robot = await DimosRobot.connect()
    health = await robot.get_health()
    print(json.dumps(health, indent=2))
    if not health.get("connected"):
        raise SystemExit("Robot not connected; refusing to move")
    print("modules:", await robot.module_names())
    events = []
    safety = Safety(robot, settings, lambda kind, data: events.append((time.time(), kind, data)))
    plan = f"rotate {args.rotate:.2f} rad" if args.rotate else f"navigate to {args.zone} {settings.zones.get(args.zone)}"
    print(f"\nPLAN: {plan} at <= {settings.max_linear} m/s, timeout {settings.navigation_timeout}s")
    if input("Area clear and operator ready with physical stop? type YES to move: ").strip() != "YES":
        raise SystemExit("Aborted; nothing moved")
    try:
        if args.rotate:
            await safety.safe_rotate(args.rotate)
        else:
            x, y = settings.zones[args.zone]
            await safety.safe_navigate_to(Pose(x=x, y=y))
        print("DONE:", json.dumps(await robot.get_health(), indent=2))
    finally:
        await robot._halt(strict=False)
        for stamp, kind, data in events:
            print(time.strftime("%H:%M:%S", time.localtime(stamp)), kind, data)


if __name__ == "__main__":
    asyncio.run(main())
