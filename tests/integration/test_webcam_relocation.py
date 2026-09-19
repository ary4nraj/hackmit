"""Milestone 2 in software: real YOLO inference on real pixels through the stationary-camera backend.

A real photographed person (Ultralytics sample) is placed on the left of the frame, remembered,
then placed on the right. The pipeline must link the sightings by appearance, invalidate nothing
falsely, and produce a MOVED event with genuine detector output. Not a hardware claim.
"""

import asyncio
from pathlib import Path

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")
ultralytics = pytest.importorskip("ultralytics")

from recall_rover.config import WEBCAM_ZONES, Settings
from recall_rover.memory.repository import Memory
from recall_rover.perception.detector import LocalDetectorProvider
from recall_rover.perception.pipeline import Pipeline
from recall_rover.robot.exploration import Investigator
from recall_rover.robot.safety import Safety
from recall_rover.robot.webcam_robot import WebcamRobot

ASSET = Path(ultralytics.__file__).parent / "assets" / "bus.jpg"
WEIGHTS = Path(__file__).resolve().parents[2] / "yolo11n.pt"


class StagedCamera(WebcamRobot):
    """WebcamRobot whose sensor is a staged frame: left placement, then right placement."""

    def __init__(self):
        super().__init__(source="staged", zones=WEBCAM_ZONES)
        image = cv2.imread(str(ASSET))
        crop = image[375:900, 651:810]  # the highest-confidence person in the sample
        self.crop = crop
        self.height, self.width = crop.shape[0] + 40, crop.shape[1] * 4
        self.position = "left"

    def _read(self):
        canvas = np.full((self.height, self.width, 3), 200, np.uint8)
        offset = 10 if self.position == "left" else self.width - self.crop.shape[1] - 10
        canvas[20 : 20 + self.crop.shape[0], offset : offset + self.crop.shape[1]] = self.crop
        self.frames += 1
        return canvas


@pytest.mark.skipif(not ASSET.exists() or not WEIGHTS.exists(), reason="sample image or local weights missing")
def test_real_detector_relocation(tmp_path):
    async def run():
        s = Settings(backend="webcam", perception="local", database=str(tmp_path / "cam.db"))
        m = Memory(s.database)
        r = StagedCamera()
        provider = LocalDetectorProvider(model=str(WEIGHTS), device="cpu", evidence_dir=str(tmp_path / "ev"))
        p = Pipeline(r, provider, m, s.zones)
        first = await p.inspect()
        assert any(o.label == "person" for o in first)
        known = m.find_best_match("person")
        assert known["observation"]["zone"] == "camera left"
        assert known["observation"]["detection"]["bbox"]
        assert p.telemetry["provider"] == "LocalDetectorProvider"

        r.position = "right"  # the world changes; memory does not
        assert m.find_best_match("person")["observation"]["zone"] == "camera left"

        result = await Investigator(m, Safety(r, s), p, s.zones).find_object("person")
        assert result["found"] and result["zone"] == "camera right"
        assert result["same_entity"] and result["previous_zone"] == "camera left"
        best = m.find_best_match("person")
        assert best["id"] == known["id"] and best["observation"]["zone"] == "camera right"
        moved = [e for e in m.changes() if e["type"] == "MOVED"]
        assert moved and "camera left → camera right" in moved[0]["summary"]
        assert len(m.entities("person")) == 1  # no duplicate entity created
        assert not r.moving and all(x["stationary"] for x in r.motion_log)
        m.close()

    asyncio.run(run())
