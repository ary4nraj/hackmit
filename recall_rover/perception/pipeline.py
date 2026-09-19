import asyncio
import time
from uuid import uuid4

from recall_rover.memory.models import Detection


class MockPerceptionProvider:
    async def detect(self, frame):
        if not isinstance(frame, dict) or not frame.get("mock"):
            raise ValueError("Mock perception only accepts simulated frames")
        return [
            Detection(
                label=x,
                identity="mock:" + x,
                confidence=0.94,
                description="simulated " + x,
            )
            for x in frame["objects"]
        ]


class Pipeline:
    """camera frame -> detector -> zone assignment -> memory. Never calls the cloud."""

    def __init__(self, robot, provider, memory, zones, emit=lambda *a: None):
        self.robot = robot
        self.provider = provider
        self.memory = memory
        self.zones = zones
        self.emit = emit
        self.last_frame = None
        self.last_detections = []
        self.telemetry = {}
        self.lock = asyncio.Lock()
        self.frames = 0

    def observer_zone(self, pose):
        return min(
            self.zones,
            key=lambda z: (self.zones[z][0] - pose.x) ** 2 + (self.zones[z][1] - pose.y) ** 2,
        )

    def zone_for(self, pose, detection, frame):
        locate = getattr(self.robot, "locate", None)
        if locate:
            return locate(pose, detection, frame)
        return self.observer_zone(pose)

    async def inspect(self):
        async with self.lock:
            start = time.monotonic()
            pose = await self.robot.get_pose()
            frame = await self.robot.get_camera_frame()
            if frame is None:
                raise RuntimeError("Camera unavailable; cannot infer absence")
            detections = await self.provider.detect(frame)
            detect_ms = (time.monotonic() - start) * 1000
            self.last_frame = frame
            self.last_detections = detections
            self.frames += 1
            observer = self.observer_zone(pose)
            frame_id = uuid4().hex
            obs = [
                self.memory.remember_observation(d, pose, self.zone_for(pose, d, frame), frame_id)
                for d in detections
                if d.confidence >= 0.5
            ]
            visible = getattr(self.robot, "visible_zones", None)
            for zone in visible() if visible else [observer]:
                self.memory.checked(zone)
            self.telemetry = {
                "latency_ms": round((time.monotonic() - start) * 1000, 1),
                "detect_ms": round(detect_ms, 1),
                "detections": len(obs),
                "provider": type(self.provider).__name__,
                "device": getattr(self.provider, "device", "n/a"),
                "model": getattr(self.provider, "model_name", type(self.provider).__name__),
                "frames": self.frames,
            }
            self.emit(
                "perception.detection",
                {"zone": observer, "observations": [o.model_dump(exclude={"detection": {"embedding"}}) for o in obs]},
            )
            return obs
