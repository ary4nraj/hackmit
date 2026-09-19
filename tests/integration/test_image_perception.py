"""Real OpenCV algorithm on generated pixels. Synthetic fixture, not a hardware claim."""

import asyncio

import cv2
import numpy as np

from recall_rover.config import Settings
from recall_rover.memory.repository import Memory
from recall_rover.perception.detector import TagDetectorProvider
from recall_rover.perception.pipeline import Pipeline
from recall_rover.robot.exploration import Investigator
from recall_rover.robot.mock_robot import MockRobot
from recall_rover.robot.safety import Safety


def test_moved_tag_using_image_pixels():
    async def run():
        s = Settings()
        m = Memory()
        r = MockRobot(s.zones, delay=0)
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        marker = cv2.aruco.generateImageMarker(dictionary, 1, 160)

        async def frame():
            image = np.full((400, 600), 255, np.uint8)
            if r.world["backpack"] == r.zone():
                image[120:280, 220:380] = marker
            return image

        r.get_camera_frame = frame
        p = Pipeline(r, TagDetectorProvider(), m, s.zones)
        await p.inspect()
        assert m.find_best_match("backpack")
        r.move_object("backpack", "back wall")
        result = await Investigator(m, Safety(r, s), p, s.zones).find_object("backpack")
        assert result["found"] and result["observation"]["zone"] == "back wall"
        assert any(e["type"] == "MOVED" for e in m.changes())
        m.close()

    asyncio.run(run())
