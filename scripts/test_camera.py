"""Capture camera evidence and run local perception; does not move any robot."""

import argparse
import asyncio
import json
import time
from pathlib import Path

import cv2

from recall_rover.memory.models import Pose
from recall_rover.memory.repository import Memory
from recall_rover.perception.detector import LocalDetectorProvider, TagDetectorProvider


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="0")
    parser.add_argument("--tags", action="store_true")
    parser.add_argument("--frames", type=int, default=5)
    parser.add_argument("--zone", default="laptop camera")
    args = parser.parse_args()
    camera = cv2.VideoCapture(
        int(args.source) if args.source.isdigit() else args.source
    )
    if not camera.isOpened():
        raise SystemExit("Camera not available")
    provider = TagDetectorProvider() if args.tags else LocalDetectorProvider()
    memory = Memory("data/camera.db")
    Path("data/evidence").mkdir(exist_ok=True)

    async def run():
        for i in range(args.frames):
            ok, frame = camera.read()
            if not ok:
                raise RuntimeError("Camera read failed; cannot infer absence")
            start = time.monotonic()
            detections = await provider.detect(frame)
            for d in detections:
                memory.remember_observation(d, Pose(), args.zone)
            cv2.imwrite("data/evidence/camera-latest.jpg", frame)
            print(
                json.dumps(
                    {
                        "frame": i,
                        "latency_ms": round((time.monotonic() - start) * 1000),
                        "detections": [d.model_dump() for d in detections],
                    }
                )
            )

    try:
        asyncio.run(run())
    finally:
        camera.release()
        memory.close()


if __name__ == "__main__":
    main()
