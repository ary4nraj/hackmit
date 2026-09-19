import asyncio

from recall_rover.memory.models import Pose


class MockRobot:
    def __init__(self, zones, delay=0.05):
        self.zones = zones
        self.pose = Pose(x=zones["entrance table"][0], y=zones["entrance table"][1])
        self.moving = False
        self.delay = delay
        self.generation = 0
        self.world = {
            "backpack": "entrance table",
            "bottle": "left side",
            "package": "entrance",
            "person": "entrance",
        }
        self.motion_log = []

    async def get_pose(self):
        return self.pose.model_copy()

    def zone(self):
        return min(
            self.zones,
            key=lambda z: (
                (self.zones[z][0] - self.pose.x) ** 2
                + (self.zones[z][1] - self.pose.y) ** 2
            ),
        )

    async def get_camera_frame(self):
        return {
            "mock": True,
            "zone": self.zone(),
            "objects": [k for k, v in self.world.items() if v == self.zone()],
        }

    async def navigate_to(self, pose, speed):
        generation = self.generation
        self.moving = True
        self.motion_log.append({"target": pose.model_dump(), "speed": speed})
        try:
            await asyncio.sleep(self.delay)
            if generation != self.generation:
                raise RuntimeError("Motion stopped")
            self.pose = pose.model_copy()
        finally:
            self.moving = False

    async def rotate(self, angle, speed):
        p = self.pose.model_copy()
        p.yaw += angle
        await self.navigate_to(p, speed)

    async def stop(self):
        self.generation += 1
        self.moving = False

    async def get_health(self):
        return {
            "connected": True,
            "backend": "mock",
            "moving": self.moving,
            "pose": self.pose.model_dump(),
            "zone": self.zone(),
        }

    def move_object(self, label, zone):
        if label not in self.world or (zone is not None and zone not in self.zones):
            raise ValueError("Unknown object or zone")
        self.world[label] = zone
