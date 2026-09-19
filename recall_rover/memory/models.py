import time
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class Pose(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    x: float = 0
    y: float = 0
    yaw: float = 0


class Detection(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    label: str = Field(min_length=1, max_length=80)
    confidence: float = Field(ge=0, le=1)
    # Stable identity only from mock truth or a uniquely registered fiducial.
    identity: str | None = None
    description: str = ""
    bbox: list[float] | None = None
    image_path: str | None = None
    # Appearance signature (HSV histogram or learned embedding); enables cross-zone association.
    embedding: list[float] | None = None


class Observation(BaseModel):
    observation_id: str = Field(default_factory=lambda: uuid4().hex)
    entity_id: str
    label: str
    timestamp: float = Field(default_factory=time.time)
    confidence: float
    pose: Pose
    zone: str
    status: Literal["active", "invalidated", "stale"] = "active"
    detection: Detection
    # Identifies the camera frame; two detections sharing it are distinct physical objects.
    frame_id: str | None = None
    localization: str = "semantic zone / observer pose; not object coordinates"
