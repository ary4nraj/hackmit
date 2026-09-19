import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

MOCK_ZONES = {
    "entrance table": [0.0, 0.0],
    "left side": [1.0, 0.0],
    "back wall": [1.0, 1.0],
    "entrance": [0.0, 1.0],
}
WEBCAM_ZONES = {"camera left": [-1.0, 0.0], "camera center": [0.0, 0.0], "camera right": [1.0, 0.0]}


@dataclass
class Settings:
    backend: str = field(default_factory=lambda: os.getenv("ROBOT_BACKEND", "mock"))
    database: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///data/recall.db").removeprefix(
            "sqlite:///"
        )
    )
    max_linear: float = field(default_factory=lambda: float(os.getenv("ROBOT_MAX_LINEAR_SPEED", ".25")))
    max_angular: float = field(default_factory=lambda: float(os.getenv("ROBOT_MAX_ANGULAR_SPEED", ".4")))
    navigation_timeout: float = field(default_factory=lambda: float(os.getenv("NAVIGATION_TIMEOUT", "30")))
    perception: str = field(default_factory=lambda: os.getenv("PERCEPTION_PROVIDER", "mock"))
    camera_source: str = field(default_factory=lambda: os.getenv("CAMERA_SOURCE", "0"))
    perception_interval: float = field(default_factory=lambda: float(os.getenv("PERCEPTION_INTERVAL", "2")))
    zones: dict | None = None

    def __post_init__(self):
        path = os.getenv("ZONES_FILE")
        explicit = self.zones is not None
        if self.zones is None:
            if path:
                self.zones = {k: v for k, v in json.loads(Path(path).read_text()).items() if not k.startswith("_")}
            elif self.backend == "webcam":
                self.zones = dict(WEBCAM_ZONES)
            else:
                self.zones = dict(MOCK_ZONES)
        if self.backend not in {"mock", "dimos", "webcam"}:
            raise ValueError("ROBOT_BACKEND must be mock, webcam or dimos")
        if self.backend != "mock" and self.perception == "mock":
            raise ValueError("Real cameras require PERCEPTION_PROVIDER=local, tags or combined")
        if self.perception not in {"mock", "local", "tags", "combined"}:
            raise ValueError("Unknown perception provider")
        if self.backend == "dimos" and not path and not explicit:
            raise ValueError("ROBOT_BACKEND=dimos requires ZONES_FILE with surveyed waypoints")
        for name, xy in self.zones.items():
            if not (isinstance(xy, list) and len(xy) == 2 and all(isinstance(v, (int, float)) for v in xy)):
                raise ValueError(f"Zone {name!r} must be [x, y]")
        if not 0 < self.max_linear <= 0.5 or not 0 < self.max_angular <= 0.8:
            raise ValueError("Speed limits must be positive and at most .5 m/s, .8 rad/s")
        if not 0 < self.navigation_timeout <= 120:
            raise ValueError("Navigation timeout must be in (0, 120]")
        if not 0.2 <= self.perception_interval <= 60:
            raise ValueError("PERCEPTION_INTERVAL must be in [0.2, 60] seconds")
