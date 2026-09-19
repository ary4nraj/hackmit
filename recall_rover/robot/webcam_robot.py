"""Stationary camera backend: real perception without a mobile robot.

The 'robot' cannot move. Zones are image regions (left / centre / right third of the
frame), so relocation of a real object across the field of view produces the same
remember -> invalidate -> rediscover -> MOVED loop as the Go2, with genuine pixels.
navigate_to only records where attention is directed; it is never a motion command.
"""

import asyncio
import os

from recall_rover.memory.models import Pose

WEBCAM_ZONES = {"camera left": [-1.0, 0.0], "camera center": [0.0, 0.0], "camera right": [1.0, 0.0]}


class WebcamRobot:
    stationary = True

    def __init__(self, source=None, zones=None):
        self.source = source if source is not None else os.getenv("CAMERA_SOURCE", "0")
        self.zones = zones or WEBCAM_ZONES
        self.pose = Pose()
        self.moving = False
        self.attention = None
        self.capture = None
        self.motion_log = []
        self.frames = 0

    def _open(self):
        import cv2

        if self.capture is None:
            src = int(self.source) if str(self.source).isdigit() else self.source
            self.capture = cv2.VideoCapture(src)
            if not self.capture.isOpened():
                self.capture = None
                raise RuntimeError(f"Camera {self.source!r} not available")
        return self.capture

    def _read(self):
        capture = self._open()
        # Drop buffered frames so an inspection reflects the present, not a stale buffer.
        for _ in range(2):
            capture.grab()
        ok, frame = capture.read()
        if not ok or frame is None:
            raise RuntimeError("Camera read failed; cannot infer absence")
        self.frames += 1
        return frame

    async def get_pose(self):
        return self.pose.model_copy()

    async def get_camera_frame(self):
        return await asyncio.to_thread(self._read)

    async def navigate_to(self, pose, speed):
        # Stationary: attention shifts, nothing moves. Logged for the trace only.
        self.attention = pose.model_copy()
        self.motion_log.append({"target": pose.model_dump(), "speed": 0, "stationary": True})
        await asyncio.sleep(0)

    async def rotate(self, angle, speed):
        await asyncio.sleep(0)

    async def stop(self):
        self.moving = False

    def zone(self):
        return "camera center"

    def locate(self, pose, detection, frame):
        """Image-region zone from the bbox centre. Coarse and honest: not 3D."""
        if not detection.bbox or frame is None or not hasattr(frame, "shape"):
            return "camera center"
        width = frame.shape[1]
        cx = (detection.bbox[0] + detection.bbox[2]) / 2 / max(width, 1)
        return "camera left" if cx < 1 / 3 else "camera right" if cx > 2 / 3 else "camera center"

    def visible_zones(self):
        return list(self.zones)

    async def get_health(self):
        return {
            "connected": self.capture is not None or self.frames > 0,
            "backend": "webcam",
            "moving": False,
            "stationary": True,
            "pose": self.pose.model_dump(),
            "zone": self.zone(),
            "frames": self.frames,
        }

    def close(self):
        if self.capture is not None:
            self.capture.release()
            self.capture = None
