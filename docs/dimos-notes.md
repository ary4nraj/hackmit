# Verified dimOS interfaces

Inspected official main on 2026-09-19 at commit
`c1c3cdc9d2ee54ca72259465688395699d7d99a2`.
Initially no installed dimOS to inspect locally; later installed 0.0.14 in .dimos-venv and verified Python entry points. Do not assume historical examples match this revision.

Sources:
- https://github.com/dimensionalOS/dimos
- https://github.com/dimensionalOS/dimos/blob/c1c3cdc9d2ee54ca72259465688395699d7d99a2/docs/usage/python-api.md
- https://github.com/dimensionalOS/dimos/blob/c1c3cdc9d2ee54ca72259465688395699d7d99a2/docs/usage/cli.md
- https://github.com/dimensionalOS/dimos/blob/c1c3cdc9d2ee54ca72259465688395699d7d99a2/dimos/robot/unitree/go2/connection.py
- https://github.com/dimensionalOS/dimos/blob/c1c3cdc9d2ee54ca72259465688395699d7d99a2/dimos/navigation/replanning_a_star/module.py
- https://github.com/dimensionalOS/dimos/blob/c1c3cdc9d2ee54ca72259465688395699d7d99a2/docs/capabilities/navigation/deep_dive.md

Current official setup uses Python 3.12 and Go2 WebRTC; ROS is not required.
`ROBOT_IP=<address> dimos run unitree-go2` launches mapping/navigation.
`dimos --replay run unitree-go2` uses recorded data, NOT live hardware.
`dimos --simulation run unitree-go2` uses MuJoCo.
`unitree-go2-agentic` includes MCP; default endpoint http://localhost:9990/mcp.
`dimos mcp list-tools` returns actual skill names/schemas. Never assume available skills.
`DIMOS_TRANSPORT=zenoh` is documented; transport configuration must match between processes.

Chosen Python adapter: `from dimos import Dimos; Dimos.connect()` attaches to an existing
coordinator. `peek_stream("odom", 1.0)` and `peek_stream("color_image", 1.0)` retrieve pose
and image. Camera image exposes `.data`. `list_modules()` and `list_rpcs()` support preflight.
`GO2Connection.stop_movement()` stops motion. Planner `cancel_goal()` cancels goal generation;
use BOTH for stopping. `Dimos.stop()` on a remote client only disconnects: it is NOT emergency stop.
`ReplanningAStarPlanner.set_goal(PoseStamped)` returns acceptance, not arrival;
`get_state()` and `is_goal_reached()` expose progress.

Mapping: Go2 lidar/odom → voxel grid → costmap → replanning A* → navigation velocity stream.
Camera calibration and lidar are available, but this implementation uses semantic observer zones.
It does not pretend observer pose is precise object geometry.

Hardware motion is deliberately unavailable in this initial adapter until velocity caps and
communication-loss deadman are enforced at the dimOS actuator-side stream. A planner speed
setting alone does not establish a maximum angular velocity. Merely passing a speed to a
wrapper would falsely imply enforcement. Read-only pose/camera and real stop APIs are implemented.
Next hardware work: install verified revision on GX10, inspect deployed RPCs, add/test actuator-side
velocity clamp + watchdog, survey flat waypoints, verify controller stop, then enable navigation.

## Startup side effects found during source review

`GO2Connection.start()` calls `standup()`, waits three seconds, and calls `balance_stand()`.
Its `stop()` calls `liedown()`. Therefore starting/stopping an official Go2 blueprint is NOT
read-only, even `unitree-go2-basic`. The read-only preflight script attaches to an already-running
coordinator and does not invoke module lifecycle methods. `UnitreeWebRTCConnection` also changes
motion mode while connecting. Do not describe direct connection construction as side-effect-free.

Image conversion: verified `Image.to_opencv()` supplies BGR pixels, avoiding accidental RGB/BGR inversion.
Source: https://github.com/dimensionalOS/dimos/blob/c1c3cdc9d2ee54ca72259465688395699d7d99a2/dimos/msgs/sensor_msgs/Image.py

Go2 Wi-Fi discovery/provisioning:
https://github.com/dimensionalOS/dimos/blob/main/docs/platforms/quadruped/go2/setup.md
Read-only LAN discovery sends `{ "name": "unitree_dapengche" }` to multicast 231.1.1.1:10131
and listens on UDP 10134. A three-second probe on HackMIT.2026 found no robot before provisioning.

## Navigation commissioning design (continuation session, verified against installed 0.0.14)

`dimos run unitree-go2` resolves (dimos/robot/all_blueprints.py) to
`dimos.robot.unitree.go2.blueprints.smart.unitree_go2:unitree_go2`, which composes
`GO2Connection`, `VoxelGridMapper`, `CostMapper`, `ReplanningAStarPlanner`,
`WavefrontFrontierExplorer`, `PatrollingModule`, `MovementManager` and the Rerun visualiser.

Motion facts read from source:
- `ReplanningAStarPlanner.set_goal(PoseStamped)` always returns True and only *requests* a goal
  (`global_planner.handle_goal_request`). Arrival is `is_goal_reached()`; the planner drops to
  `NavigationState.IDLE` when it finishes or gives up, and `_goal_reached` resets on each new goal.
  `cancel_goal()` returns True unconditionally.
- Local planner speed is `_speed = 0.55 m/s`, multiplied by `global_config.nerf_speed` when < 1.0
  (`navigation/replanning_a_star/local_planner.py`). Angular velocity is clipped to the same value
  (`controllers.py`), floor 0.2 rad/s. So `dimos --nerf-speed 0.45 run unitree-go2` caps the
  planner at ~0.25 m/s. This is a launch-time setting; there is no RPC to change it later.
- `UnitreeWebRTCConnection.move()` (dimos/robot/unitree/connection.py) arms a
  `threading.Timer(cmd_vel_timeout=0.2 s, stop_movement)` on every command: the base zeroes itself
  0.2 s after the last twist. This is the actuator-side deadman Codex asked for. `stop_movement()`
  publishes a zero twist and cancels the timer.
- `GO2Connection.move(twist, duration)` RPC exists; with `duration=0` it sends one command.
  Streaming short twists at 10 Hz is how teleop drives the robot.
- `GO2Connection.battery_soc()` RPC returns 0–100 or None. `set_obstacle_avoidance(bool)` exists;
  `global_config.obstacle_avoidance` defaults True.
- `Quaternion.from_euler(Vector3(0,0,yaw))`, `PoseStamped(position=Vector3, orientation=Quaternion,
  frame_id="world", ts=...)` and `Twist(linear=Vector3, angular=Vector3)` construct correctly in the
  installed package (executed, not assumed). `Dimos.get_module("ReplanningAStarPlanner")` accepts a
  unique class name; `peek_stream("odom")` / `peek_stream("color_image")` as before.

`recall_rover/robot/dimos_robot.py` now implements:
- `navigate_to`: build goal → `set_goal` → poll `is_goal_reached` at 4 Hz → on success/failure
  always `cancel_goal` + `stop_movement`. Failure conditions: planner IDLE without arrival after a
  2 s grace, measured odometry speed above `1.5 × cap + 0.05 m/s` (independent watchdog), or the
  Safety timeout (Safety cancels the coroutine, which hits the same `finally` halt).
- `rotate`: streams `move(twist, 0)` at 10 Hz for `min(|angle|/speed, 12 s)`; the 0.2 s deadman
  stops the base if the client dies.
- `connect`: refuses motion (but keeps sensing) unless both `GO2Connection` and
  `ReplanningAStarPlanner` are deployed.
All of this is exercised with fakes in `tests/unit/test_dimos_adapter.py`; it has NOT run on the
physical Go2 yet. Commissioning procedure: docs/hardware-setup.md and `scripts/test_navigation.py`.

## Replay validation (executed 2026-09-19, continuation session)

`make replay` (= `./scripts/dimos.sh --replay --viewer none run unitree-go2`) starts the real
`unitree-go2` blueprint against dimOS's recorded `go2_short` dataset (84 MB via git-lfs). All seven
modules deployed: GO2Connection, VoxelGridMapper, CostMapper, ReplanningAStarPlanner,
WavefrontFrontierExplorer, PatrollingModule, MovementManager (+ WebsocketVisModule).
`make rpc-check` (`scripts/test_dimos_rpc.py`) then confirmed against that coordinator:

| Call | Result |
|---|---|
| `Dimos.connect(timeout=10)` + `list_modules()` | 8 ms, module names as above |
| `peek_stream("odom")` → Pose | 20 ms, x=-2.17 y=4.78 yaw=1.43 |
| `peek_stream("color_image").to_opencv()` | 113 ms, BGR 720×1280×3 |
| `ReplanningAStarPlanner.get_state()` | `NavigationState.IDLE` |
| `is_goal_reached()` / `cancel_goal()` | False / True |
| `GO2Connection.battery_soc()` | None (no lowstate in replay) |
| `GO2Connection.stop_movement()` | ok |
| `PoseStamped(...Quaternion.from_euler...)` goal | built |

Two environment fixes were needed for the isolated venv (both venv-local, no system changes):
`pip install -U coverage` (system `coverage` broke numba's import) and a `git-lfs` 3.6.1 binary
copied into `.dimos-venv/bin` (dataset download). `scripts/dimos.sh` puts that bin dir on PATH.
`--viewer none` runs headless. Replay's `move()` is a no-op, so navigation goals never arrive:
useful for exercising the failure path (timeout → halt → honest "not arrived"), not for arrival.

### Full service in dimOS mode against replay
`ROBOT_BACKEND=dimos PERCEPTION_PROVIDER=local ZONES_FILE=config/zones.example.json make run-dimos`
(port 8000; the check used 8766) started, connected, and ran YOLO11n on the recorded Go2 camera
(1280×720, ~240 ms/frame on this CPU): person and chair entities, annotated JPEG at
`/camera/latest`, events on the WebSocket. A `POST /robot/navigate` after the recording ended
returned 409 "No fresh odometry; do not navigate", emitted `robot.navigation.started → robot.stopped
→ robot.navigation.failed`, latched STOP, and `/robot/resume` cleared it. The `go2_short` recording
is short and does not loop (`ReplayConfig.loop=False`), so restart `make replay` right before a check.

### Navigation exercise against the real planner (replay, executed)
With a fresh `make replay`, `Safety.safe_navigate_to` → `DimosRobot.navigate_to` to a waypoint
0.5 m ahead of the recorded pose produced, in the coordinator log:
`Found safe goal. x=-1.57 y=8.93` → `Found path 1.1x robot width.` → (our halt) `Cancelling goal.
arrived=False but_will_try_again=False`. The client saw `robot.navigation.started` → `robot.stopped`
→ `robot.navigation.failed` within 0.4 s because the odometry watchdog measured 0.48 m/s: in replay
the recorded robot walks on its own, unrelated to our goal, so exceeding the 0.25 m/s cap is the
expected outcome and demonstrates the watchdog against real odometry. The watchdog now needs two
consecutive overspeed samples so odometry jitter cannot fake one on the real robot.
So far verified end to end without hardware: connect, streams, goal acceptance, real path planning,
polling, cancel, stop, latch. Not yet verified: actual arrival on the physical Go2.
