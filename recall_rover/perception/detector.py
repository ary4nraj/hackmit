"""Optional local image detection. Models are explicitly provisioned, not downloaded per frame."""

import asyncio
import os
import time
from pathlib import Path
from uuid import uuid4

from recall_rover.memory.models import Detection
from recall_rover.perception.embeddings import appearance_signature

DEFAULT_LABELS = "backpack,bottle,person,chair,laptop,handbag,suitcase,cup"


class LocalDetectorProvider:
    """YOLO on the local device (GX10 CUDA or laptop CPU). Crops get an appearance signature."""

    def __init__(self, model=None, device=None, evidence_dir="data/evidence", labels=None):
        from ultralytics import YOLO

        self.model_name = model or os.getenv("DETECTOR_MODEL", "yolo11n.pt")
        self.model = YOLO(self.model_name)
        self.device = device or os.getenv("PERCEPTION_DEVICE", "cpu")
        self.labels = set((labels or os.getenv("DETECTOR_LABELS", DEFAULT_LABELS)).split(","))
        self.evidence = Path(evidence_dir)
        self.evidence.mkdir(parents=True, exist_ok=True)
        self.last_save = 0
        self.last_annotated = None

    async def detect(self, frame):
        return await asyncio.to_thread(self._detect, frame)

    def _detect(self, frame):
        import cv2

        if frame is None or not hasattr(frame, "shape"):
            raise ValueError("Local detector requires a camera image")
        predictions = self.model.predict(frame, device=self.device, conf=0.4, verbose=False)[0]
        result = []
        evidence = None
        if len(predictions.boxes):
            self.last_annotated = predictions.plot()
            if time.monotonic() - self.last_save > 2:
                path = self.evidence / (uuid4().hex + ".jpg")
                if cv2.imwrite(str(path), self.last_annotated):
                    evidence = str(path)
                    self.last_save = time.monotonic()
        for box in predictions.boxes:
            label = self.model.names[int(box.cls.item())]
            if label not in self.labels:
                continue
            bbox = box.xyxy[0].tolist()
            result.append(
                Detection(
                    label=label,
                    confidence=float(box.conf.item()),
                    bbox=bbox,
                    image_path=evidence,
                    embedding=appearance_signature(frame, bbox),
                )
            )
        return result


class TagDetectorProvider:
    """DICT_4X4_50 marker IDs are registered identities, not semantic AI guesses."""

    def __init__(self, labels=None):
        import cv2

        self.cv2 = cv2
        self.labels = labels or {0: "package", 1: "backpack", 2: "bottle"}
        self.detector = cv2.aruco.ArucoDetector(
            cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        )
        self.device = "cpu"
        self.model_name = "aruco-4x4-50"

    async def detect(self, frame):
        return await asyncio.to_thread(self._detect, frame)

    def _detect(self, frame):
        corners, ids, _ = self.detector.detectMarkers(frame)
        if ids is None:
            return []
        result = []
        for pts, raw_id in zip(corners, ids.flatten()):
            tag = int(raw_id)
            if tag not in self.labels:
                continue
            points = pts.reshape(-1, 2)
            lo = points.min(axis=0)
            hi = points.max(axis=0)
            result.append(
                Detection(
                    label=self.labels[tag],
                    identity=f"aruco:4x4_50:{tag}",
                    confidence=1,
                    description=f"Registered marker {tag}; identity requires unique physical tags",
                    bbox=[*lo.tolist(), *hi.tolist()],
                )
            )
        return result


class CombinedProvider:
    """YOLO for ordinary objects plus ArUco for the tagged package. Failure of one is an error."""

    def __init__(self, *providers):
        self.providers = providers
        self.device = getattr(providers[0], "device", "cpu")
        self.model_name = "+".join(getattr(p, "model_name", type(p).__name__) for p in providers)

    async def detect(self, frame):
        result = []
        for provider in self.providers:
            result.extend(await provider.detect(frame))
        return result

    @property
    def last_annotated(self):
        return getattr(self.providers[0], "last_annotated", None)
