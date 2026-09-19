"""The controller must converge on a synthetic beacon from several starts, with noise and dropouts."""

import asyncio
import math

import pytest

from signalhound.config import Config
from signalhound.homing.controller import HomingController
from signalhound.robot.mock import MockRadio, MockRobot, RadioField
from signalhound.robot.safety import MotionGuard


async def no_sleep(_):
    return None


def run_case(tx, ty, yaw=0.0, noise=2.0, dropout=0.0, seed=1, max_moves=80):
    cfg = Config()
    cfg.max_moves = max_moves
    cfg.search_timeout_seconds = 10_000
    cfg.settle_seconds = 0
    cfg.target_rssi_threshold = -47
    cfg.target_rssi_hold_seconds = 0
    robot = MockRobot(yaw=yaw)
    field = RadioField(tx, ty, noise_db=noise, dropout=dropout, seed=seed)
    radio = MockRadio(cfg, robot, field)
    ctl = HomingController(cfg, radio, robot, MotionGuard(robot, cfg), sleep=no_sleep)
    asyncio.run(ctl.run())
    return ctl, robot, math.hypot(tx - robot.x, ty - robot.y)


@pytest.mark.parametrize("tx,ty,yaw", [(4, 0, 0), (-4, 0, 0), (0, 4, 0), (0, -4, 0), (3, 3, math.pi)])
def test_converges_from_each_side(tx, ty, yaw):
    ctl, robot, dist = run_case(tx, ty, yaw)
    assert ctl.state == "FOUND", (ctl.state, ctl.decision, dist)
    assert dist < 2.5, dist
    assert robot.stops >= ctl.moves  # every burst ended with a stop


def test_noisy_and_dropouts_still_converge():
    ctl, robot, dist = run_case(4, 2, noise=4.0, dropout=0.15, seed=3, max_moves=120)
    assert ctl.state == "FOUND", (ctl.state, ctl.decision, dist)
    assert dist < 3.0


def test_budget_exhaustion_stops_safely():
    ctl, robot, _ = run_case(30, 30, max_moves=5)
    assert ctl.state == "STOPPED" and "budget" in ctl.decision
    assert ctl.moves <= 6  # a turn+probe pair may straddle the budget check


def test_guard_caps_are_enforced():
    cfg = Config()
    robot = MockRobot()
    guard = MotionGuard(robot, cfg)
    with pytest.raises(ValueError):
        asyncio.run(guard.forward(5.0, 0.5))
    with pytest.raises(ValueError):
        asyncio.run(guard.forward(0.2, 10))
    asyncio.run(guard.stop())
    with pytest.raises(RuntimeError):
        asyncio.run(guard.forward())
    assert not robot.bursts
