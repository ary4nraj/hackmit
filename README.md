# Recall Rover

**An AI robot that gives physical spaces a memory.**

Recall Rover stores what it saw and where, then checks whether its memory is still true.
If a backpack disappears from its remembered location, it invalidates that observation,
searches a bounded set of zones, and records a move when it recognizes the same object elsewhere.

## Working now

- **Milestone 1 (software):** remember A → relocate to B → verify A → INVALIDATED → bounded search → discover B → MOVED. Deterministic, `make demo`.
- **Milestone 2 (real perception):** the same loop with real YOLO detections on real pixels through the stationary-camera backend (`tests/integration/test_webcam_relocation.py`), and live on the laptop webcam (`make run-webcam`).
- Persistent SQLite evidence/history, age-decayed confidence, explicit knowledge states (KNOWN CURRENT / KNOWN BUT OLD / UNCERTAIN / INVALIDATED).
- Entity association: registered identity (ArUco/mock) → same-view box overlap → appearance signature with an ambiguity margin. Look-alikes never fabricate a MOVED event.
- FastAPI dashboard, WebSocket events, annotated camera, memory cards, change timeline, tool trace, STOP.
- Safety layer: waypoint validation, speed limits, timeouts, serialized motion, latched STOP; dimOS adapter adds an odometry overspeed watchdog on top of dimOS's 0.2 s deadman.
- OpenAI Responses tool loop when credentials/model are configured; offline commands otherwise.
- dimOS Go2 adapter with navigation, rotation, stop, battery/health (verified against installed 0.0.14 source, fake-tested). **Milestone 3 (physical Go2 investigation) awaits network provisioning and on-robot commissioning.**

## Quick start

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
make test
make demo
make run
```

Open http://127.0.0.1:8000. Default configuration is explicitly simulated; it never silently
substitutes fake observations for hardware. Existing development environment can also run
`python3 -m pytest -q` and `make run` directly.

Click **Recall**, then **Demo: move backpack to back wall**, then **Investigate**.
Watch `INVALIDATED` and `MOVED` in the timeline. Ask **What changed?**
The robot’s simulated world is seeded on process start; SQLite memory persists between starts.
For a fresh demo, use a new database path, e.g. `DATABASE_URL=sqlite:///data/demo-new.db make run`.

## Local camera / GX10

```bash
pip install -e '.[vision]'
make run-webcam                       # stationary real camera, YOLO, image-region zones
python -m scripts.test_camera --source 0 --frames 10
# Package/tag fallback, no YOLO weights required:
python -m scripts.test_camera --source 0 --tags
```

`ROBOT_BACKEND=webcam` treats the frame's left/centre/right thirds as zones, so moving a real
object across the view produces the full remember → invalidate → rediscover → MOVED loop with
genuine detections. `PERCEPTION_PROVIDER=combined` runs YOLO and ArUco together (tagged package).

YOLO weights download on first initialization. Set `DETECTOR_MODEL` to an existing local `.pt`
file for offline operation. `PERCEPTION_DEVICE=cpu` works on this laptop; set `cuda` on GX10 after
verifying its installed PyTorch supports the device. Camera CLI writes `data/camera.db` separately
from mock demo memory. It labels location as the configured stationary camera zone.
ArUco DICT_4X4_50 IDs: 0 package, 1 backpack, 2 bottle. Use unique physical markers.

## OpenAI

```bash
pip install -e '.[agent]'
cp .env.example .env
# Set OPENAI_API_KEY and OPENAI_MODEL in .env; restart the service.
```

The cloud chooses constrained, schema-validated tools. Perception and memory stay local.
No API key is exposed to the browser. Tool contracts are tested using a fake API transport;
cloud calls have not been verified without credentials. A cloud failure stops the task;
it does not retry physical actions through the offline parser. Direct inspection, memory endpoints,
and STOP remain available. Offline commands are explicitly labeled and are not an LLM.

## Hardware

See [hardware setup](docs/hardware-setup.md), [verified dimOS APIs](docs/dimos-notes.md),
[environment findings](docs/environment.md), and [architecture](docs/architecture.md).

```bash
make replay       # no robot: the real unitree-go2 blueprint on dimOS's recorded Go2 data
make rpc-check    # verifies every adapter RPC/stream against whichever coordinator is running
make dimos        # ROBOT_IP=<go2> ./scripts/dimos.sh --nerf-speed 0.45 run unitree-go2 (robot stands up)
make preflight    # read-only pose/modules/camera check
ZONES_FILE=config/zones.json ROBOT_BACKEND=dimos PERCEPTION_PROVIDER=local \
  ./scripts/dimos-python.sh -m scripts.test_navigation --rotate 0.5   # one confirmed bounded move
make run-dimos    # full service on the robot
```

Do not treat the software STOP as a substitute for a physical stop.

## API

Interactive API docs: http://127.0.0.1:8000/docs

| Endpoint | Purpose |
|---|---|
| GET /health, /robot/status, /state | Mode, state, dashboard snapshot |
| POST /agent/message | `{ "text": "Find my backpack" }` |
| GET /memory/entities, /memory/search?q=backpack | Evidence with freshness |
| GET /memory/entity/{id} | Complete observation history |
| GET /changes?since=0 | Unix-seconds event filter |
| GET /memory/what-changed?since=0 | Only MOVED/APPEARED/INVALIDATED/DISAPPEARED, oldest first |
| POST /robot/navigate | Approved zone, e.g. `{ "zone": "entrance" }` |
| POST /robot/stop, /robot/resume | Latched stop / operator reset |
| POST /perception/inspect | Observe the current view |
| POST /demo/relocate | Mock-only `{ "label": "backpack", "zone": "back wall" }`; null hides it |
| GET /camera/latest | Simulated SVG or real JPEG |
| WS /ws/events | Bounded live action/result stream |

Bind to loopback. Remote robot deployments should use SSH forwarding or an authenticated reverse
proxy. This hackathon service is single-process; do not add multiple Uvicorn workers controlling one robot.

## Scope and limitations

Milestones 1 and 2 are complete in software and on a laptop webcam (YOLO11n ~84–130 ms per frame on
CPU). That is not a GX10 or Go2 benchmark.
A generated-image ArUco relocation scenario exercises real OpenCV algorithms, but is synthetic
and does not establish the full live-camera relocation milestone.

Observer pose/semantic zone (or image third) is not the object's measured position. Detector
class alone cannot identify *your* backpack: relocation of untagged objects is linked by an HSV
appearance signature with a similarity threshold and margin, which distinguishes a black backpack
from a red one but not two identical black backpacks (those stay separate candidates, never a
fabricated MOVED). Mock/ArUco identities remain exact. Occlusion can produce failed verification; the UI reports “not observed,” not certainty
that an object was removed. Dates in conversational queries require the cloud tool or numeric API filter;
the offline parser does not interpret arbitrary natural language or time expressions.
No ESP32, Nordic, Arduino, or Deepgram firmware/integration is claimed. Browser speech is optional
and may use the browser vendor’s speech service. See [judging](docs/judging.md) for implemented vs planned sponsor use.
