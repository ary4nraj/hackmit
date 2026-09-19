"""Go2Robot wire format against a fake data channel: Move 1008 stream, StopMove 1003 last, stand sequence."""

import asyncio
import json
from types import SimpleNamespace

from signalhound.config import Config
from signalhound.robot.go2 import Go2Robot
from signalhound.robot.safety import MotionGuard


class FakePubSub:
    def __init__(self):
        self.sent = []
        self.subs = {}

    async def publish_request_new(self, topic, options=None):
        self.sent.append((topic, json.loads(json.dumps(options))))
        return {"ok": True}

    def subscribe(self, topic, callback=None):
        self.subs[topic] = callback


def make_robot():
    cfg = Config()
    robot = Go2Robot(cfg)
    ps = FakePubSub()
    robot.conn = SimpleNamespace(datachannel=SimpleNamespace(pub_sub=ps), disconnect=lambda: asyncio.sleep(0))
    robot.connected = True
    return cfg, robot, ps


def test_burst_streams_move_and_ends_with_stop():
    cfg, robot, ps = make_robot()
    guard = MotionGuard(robot, cfg)
    asyncio.run(guard.forward(0.2, 0.35))
    topics = {t for t, _ in ps.sent}
    assert topics == {"rt/api/sport/request"}
    moves = [o for _, o in ps.sent if o["api_id"] == 1008]
    assert 2 <= len(moves) <= 5, len(moves)
    assert all(o["parameter"] == {"x": 0.2, "y": 0.0, "z": 0.0} for o in moves)
    assert ps.sent[-1][1]["api_id"] == 1003  # StopMove is always last
    assert sum(1 for _, o in ps.sent if o["api_id"] == 1003) >= 2


def test_rotate_sign_and_stand_sequence():
    cfg, robot, ps = make_robot()
    guard = MotionGuard(robot, cfg)
    asyncio.run(guard.rotate(-1, 0.5, 0.25))
    z = [o["parameter"]["z"] for _, o in ps.sent if o["api_id"] == 1008]
    assert z and all(v == -0.5 for v in z)
    ps.sent.clear()
    asyncio.run(robot.stand_up())
    assert [o["api_id"] for _, o in ps.sent] == [1004, 1002]


def test_state_callback_and_status():
    cfg, robot, ps = make_robot()
    robot._on_state({"type": "msg", "topic": "rt/lf/sportmodestate", "data": {
        "mode": 1, "gait_type": 1, "position": [1.5, -0.5, 0.3], "velocity": [0, 0, 0],
        "imu_state": {"rpy": [0.0, 0.0, 1.2]}, "range_obstacle": [1.0, 2.0, 3.0, 4.0], "body_height": 0.3}})
    st = robot.status()
    assert st["x"] == 1.5 and st["y"] == -0.5 and st["yaw"] == 1.2 and st["telemetry_fresh"]
    assert asyncio.run(robot.get_obstacle_ranges()) == [1.0, 2.0, 3.0, 4.0]
