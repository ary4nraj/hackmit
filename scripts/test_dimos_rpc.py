"""Validate every dimOS RPC/stream the adapter relies on, without commanding motion.

Works against a live `dimos run unitree-go2` or a `dimos --replay run unitree-go2` coordinator.
The only 'actuation' calls are cancel_goal (no goal is set) and stop_movement (zero twist).
"""

import asyncio
import json
import time

from recall_rover.robot.dimos_robot import DimosRobot


async def check(name, coro):
    start = time.monotonic()
    try:
        result = await coro
        print(f"OK   {name:34s} {round((time.monotonic()-start)*1000):5d} ms  {str(result)[:90]}")
        return result
    except Exception as exc:
        print(f"FAIL {name:34s} {round((time.monotonic()-start)*1000):5d} ms  {type(exc).__name__}: {str(exc)[:120]}")
        return None


async def main():
    robot = await DimosRobot.connect(timeout=10.0)
    print("motion_enabled:", robot.motion_enabled, "|", robot.last_status)
    await check("list_modules", robot.module_names())
    pose = await check("peek odom -> Pose", robot.get_pose())
    frame = await check("peek color_image -> BGR", robot.get_camera_frame())
    if frame is not None:
        print("     frame shape:", getattr(frame, "shape", None))
    await check("planner.get_state", robot.rpc("ReplanningAStarPlanner", "get_state"))
    await check("planner.is_goal_reached", robot.rpc("ReplanningAStarPlanner", "is_goal_reached"))
    await check("planner.cancel_goal (no goal)", robot.rpc("ReplanningAStarPlanner", "cancel_goal"))
    await check("go2.battery_soc", robot.rpc("GO2Connection", "battery_soc"))
    await check("go2.stop_movement (zero twist)", robot.rpc("GO2Connection", "stop_movement"))
    await check("build goal message", asyncio.to_thread(robot._goal, pose) if pose else asyncio.sleep(0))
    print(json.dumps(await robot.get_health(), indent=2, default=str))
    await asyncio.to_thread(robot.app.stop)  # disconnect only


if __name__ == "__main__":
    asyncio.run(main())
