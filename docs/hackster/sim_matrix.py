"""12-case simulator matrix for the Hackster write-up. Usage: python docs/hackster/sim_matrix.py OUT.json (from the repo root)."""
import asyncio, json, math, sys
sys.path.insert(0, ".")
from signalhound.config import Config
from signalhound.homing.controller import HomingController
from signalhound.homing.history import History
from signalhound.robot.mock import MockRadio, MockRobot, RadioField
from signalhound.robot.safety import MotionGuard

async def no_sleep(_): return None

out = []
for i in range(12):
    a = math.radians(15 + 30 * i)
    tx, ty = 4 * math.cos(a), 4 * math.sin(a)
    cfg = Config(); cfg.homing_mode = "climb"; cfg.max_moves = 80
    cfg.search_timeout_seconds = 10_000; cfg.settle_seconds = 0
    cfg.target_rssi_hold_seconds = 0
    robot = MockRobot()
    field = RadioField(tx, ty, noise_db=3.0, dropout=0.1, seed=i + 1, ripple_db=5.0)
    ctl = HomingController(cfg, MockRadio(cfg, robot, field), robot, MotionGuard(robot, cfg), sleep=no_sleep)
    asyncio.run(ctl.run())
    pts = [(p.x, p.y, p.rssi) for p in ctl.history.points] if hasattr(ctl.history, "points") else None
    out.append(dict(tx=tx, ty=ty, state=ctl.state, moves=ctl.moves, x=robot.x, y=robot.y,
                    dist=math.hypot(tx - robot.x, ty - robot.y), threshold=cfg.target_rssi_threshold, pts=pts))
    print(i, ctl.state, ctl.moves, round(out[-1]["dist"], 2), ctl.decision)
json.dump(out, open(sys.argv[1], "w"))
