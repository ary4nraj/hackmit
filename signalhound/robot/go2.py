"""Unitree Go2 over WebRTC (LocalAP, 192.168.12.1) using the teammate-verified connection.

Wire formats copied from the installed, working dimOS wrapper and the unitree_webrtc_connect README:
  Move      SPORT_MOD  {"api_id": 1008, "parameter": {"x": vx, "y": vy, "z": vyaw}}   (m/s, m/s, rad/s)
  StopMove  SPORT_MOD  {"api_id": 1003}
  StandUp   SPORT_MOD  {"api_id": 1004},  BalanceStand 1002, StandDown 1005
Telemetry: subscribe LF_SPORT_MOD_STATE -> position[3], velocity[3], imu_state.rpy[3], range_obstacle[4].
A Move command is a velocity that the robot keeps for a short time; we resend it every 0.1 s during a
burst and always finish with StopMove.
"""

import asyncio
import logging
import os
import time

log = logging.getLogger("signalhound.go2")

MOVE_RESEND_S = 0.1


class Go2Robot:
    def __init__(self, cfg):
        self.cfg = cfg
        self.conn = None
        self.state = {}
        self.state_time = None
        self.connected = False
        self._moving = False

    # ---- connection ---------------------------------------------------
    async def connect(self, timeout=20.0):
        from unitree_webrtc_connect import RTC_TOPIC, UnitreeWebRTCConnection, WebRTCConnectionMethod

        key = self.cfg.go2_aes_key or os.getenv("GO2_AES_KEY") or None
        self.conn = UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalAP, aes_128_key=key)
        async with asyncio.timeout(timeout):
            await self.conn.connect()
        self.conn.datachannel.pub_sub.subscribe(RTC_TOPIC["LF_SPORT_MOD_STATE"], self._on_state)
        self.connected = True
        log.info("Go2 connected via LocalAP")

    def _on_state(self, msg):
        data = msg.get("data", msg) if isinstance(msg, dict) else msg
        if isinstance(data, dict):
            self.state = data
            self.state_time = time.time()

    async def disconnect(self):
        try:
            await self.stop()
        finally:
            self.connected = False
            if self.conn:
                try:
                    await self.conn.disconnect()
                except Exception:
                    pass

    # ---- commands -----------------------------------------------------
    async def _sport(self, api_id, parameter=None, timeout=3.0):
        from unitree_webrtc_connect import RTC_TOPIC

        options = {"api_id": api_id}
        if parameter is not None:
            options["parameter"] = parameter
        try:
            async with asyncio.timeout(timeout):
                return await self.conn.datachannel.pub_sub.publish_request_new(RTC_TOPIC["SPORT_MOD"], options)
        except TimeoutError:
            log.warning("sport %s timed out (no ack); robot may still have executed it", api_id)
            return None

    async def stand_up(self):
        await self._sport(1004)  # StandUp
        await asyncio.sleep(2.0)
        await self._sport(1002)  # BalanceStand: required before Move on many firmwares

    async def stand_down(self):
        await self._sport(1005)

    async def stop(self):
        """StopMove, sent twice for good measure. Never raises."""
        self._moving = False
        for _ in range(2):
            try:
                await self._sport(1003, timeout=1.5)
            except Exception as exc:  # noqa: BLE001
                log.error("StopMove failed: %s", exc)
            await asyncio.sleep(0.05)

    async def burst(self, vx, vyaw, seconds):
        """Body-frame velocity for `seconds`, resent every 0.1 s, then StopMove (guard also stops)."""
        self._moving = True
        end = time.monotonic() + seconds
        try:
            while self._moving and time.monotonic() < end:
                await self._sport(1008, {"x": float(vx), "y": 0.0, "z": float(vyaw)}, timeout=1.0)
                await asyncio.sleep(MOVE_RESEND_S)
        finally:
            await self.stop()

    # ---- telemetry ----------------------------------------------------
    def _fresh(self):
        return self.state_time is not None and time.time() - self.state_time < 2.0

    async def get_yaw(self):
        imu = self.state.get("imu_state") or {}
        rpy = imu.get("rpy") or [None, None, None]
        return rpy[2]

    async def get_position(self):
        pos = self.state.get("position") or [None, None, None]
        return (pos[0], pos[1])

    async def get_obstacle_ranges(self):
        return self.state.get("range_obstacle")

    def status(self):
        s = self.state
        return {
            "connected": self.connected,
            "telemetry_fresh": self._fresh(),
            "mode": s.get("mode"),
            "gait": s.get("gait_type"),
            "x": (s.get("position") or [None])[0],
            "y": (s.get("position") or [None, None])[1] if s.get("position") else None,
            "yaw": ((s.get("imu_state") or {}).get("rpy") or [None, None, None])[2],
            "velocity": s.get("velocity"),
            "range_obstacle": s.get("range_obstacle"),
            "body_height": s.get("body_height"),
        }
