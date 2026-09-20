"""Spin-scan homing: turn the robot into a direction finder.

At each decision point the dog rotates through N headings (closed loop on its own yaw sensor), measures
RSSI at each, faces the strongest, drives a few steps, repeats. With a reflector behind the DK's antenna
the pattern is directional enough that the best heading points at the beacon. Each decision uses N
measurement windows instead of one, and the behaviour is easy to read from the outside.
"""

import math


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def deg(a):
    return None if a is None else round(math.degrees(a))


async def rotate_to(controller, target, tol=0.17, max_bursts=8):
    """Closed-loop yaw: short bursts until |error| < tol (rad). Returns final yaw."""
    cfg, robot, guard = controller.cfg, controller.robot, controller.guard
    yaw = await robot.get_yaw()
    for _ in range(max_bursts):
        if yaw is None:
            raise RuntimeError("no yaw telemetry")
        err = wrap(target - yaw)
        if abs(err) < tol:
            break
        # The dog ramps up, so a burst yields ~60% of nominal angle; ask for a bit more, capped.
        secs = max(0.3, min(cfg.max_burst_seconds, abs(err) / cfg.rotate_speed / 0.6))
        await guard.rotate(1 if err > 0 else -1, seconds=secs)
        controller.moves += 1
        await controller.sleep(0.4)
        yaw = await robot.get_yaw()
    return yaw


async def spin_scan(controller, n=None):
    """Measure RSSI on n evenly spaced headings starting from the current yaw. Returns list of (yaw, rssi, n_samples)."""
    cfg = controller.cfg
    n = n or cfg.scan_headings
    yaw0 = await controller.robot.get_yaw()
    if yaw0 is None:
        raise RuntimeError("no yaw telemetry")
    readings = []
    for k in range(n):
        if not controller._budget_left():
            break
        target = wrap(yaw0 + k * 2 * math.pi / n)
        controller._set("PROBING", f"scan {k + 1}/{n}: turning to {deg(target)}°")
        yaw = await rotate_to(controller, target)
        r = await controller._measure(f"scan {deg(yaw)}")
        readings.append((yaw, r, controller.last_measure_n))
        got = " ".join(f"{deg(y)}°:{'n/a' if v is None else f'{v:.0f}'}" for y, v, _ in readings)
        controller._set("PROBING", f"scan {got}")
    return readings


def best_heading(readings):
    valid = [(y, r) for y, r, _ in readings if r is not None]
    if not valid:
        return None, None
    y, r = max(valid, key=lambda t: t[1])
    return y, r


def contrast(readings):
    vals = [r for _, r, _ in readings if r is not None]
    return None if len(vals) < 2 else max(vals) - min(vals)
