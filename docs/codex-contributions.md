# Codex session contributions — 2026-09-19

Actual work performed:
- Inspected empty repository, Linux/Python/GPU, packages, network interfaces, USB and serial devices.
- Retrieved official dimOS source; recorded commit and exact pose/camera/planner/stop interfaces.
- Implemented SQLite observations/entities/events, confidence decay, conservative association.
- Built MockRobot and bounded relocation investigator; proved invalidation precedes MOVED.
- Added centralized waypoint validation, velocity settings, timeout, serialized motion, latched STOP.
- Implemented FastAPI, live event queues, dashboard, offline commands and Responses tool adapter.
- Added optional local YOLO/ArUco providers and read-only dimOS preflight.
- Installed YOLO only into a project virtualenv; exercised sample-image and real laptop webcam inference.
- Diagnosed sandbox async thread wakeup hang; host test execution succeeds.
- Added regression coverage for persistence, disappearance, camera failure, candidate identities,
  motion timeout, STOP interruption, API validation, WebSocket events, and cloud tool protocol.
- Rendered dashboard in headless Chrome and visually inspected it.

No real OpenAI request, GX10 execution, or Go2 motion is claimed. No secondary-board firmware was flashed.
Logs from runtime actions are in ignored data/demo.jsonl. Images/databases remain ignored local artifacts.

Additional hardware preparation:
- Provisioned an isolated dimOS 0.0.14 environment, resolving missing native dependencies through
  local package extraction instead of system installation.
- Official dimOS BLE discovery identified Go2_61034 at 94:BA:06:F6:DE:C3.
- Detected startup side effects in official Go2 modules (automatic standup/liedown), documented them.
- Automated Wi-Fi provisioning was blocked by approval review before execution because it would
  transfer a saved Wi-Fi credential to the robot. Requested specific user approval; no credential
  was printed or transmitted by the rejected action.

# Continuation session — Claude Code (2026-09-19)

Codex ran out of credits after the work above. The following was done by Claude Code (Fable 5.1)
in the same repository. It is recorded separately so the OpenAI-track evidence stays accurate:
these are not Codex contributions.

- Read the installed dimOS 0.0.14 source to find the real speed cap (`nerf_speed`) and the WebRTC
  0.2 s deadman, executed the message constructors in `.dimos-venv`, and documented them.
- Implemented `DimosRobot.navigate_to` / `rotate` / `connect` preflight with an odometry speed
  watchdog, plus seven fake-backed contract tests.
- Added appearance signatures (HSV histogram, `perception/embeddings.py`) to detections and a
  three-stage association (identity → same-view overlap → appearance with margin and per-frame
  exclusion). Fixed the fragmentation cascade found in a live webcam run.
- Added the stationary `WebcamRobot` backend with image-region zones, `combined` YOLO+ArUco
  provider, configurable labels, annotated `/camera/latest`, `/memory/what-changed`.
- Wrote the real-pixel relocation test (`tests/integration/test_webcam_relocation.py`): YOLO on a
  photographed person placed left then right → INVALIDATE-free MOVED with one entity.
- Ran the service on the laptop webcam: real detections, JPEG stream, offline agent answers.
- Config, Makefile targets, `.env.example`, `config/zones.example.json`, commissioning script,
  dashboard telemetry (LOCAL model/device vs CLOUD agent mode), and these docs.
- Got the official `unitree-go2` blueprint running headless in replay mode on the laptop (two
  venv-local fixes: `coverage` upgrade, local `git-lfs`), validated every adapter RPC against it
  (`scripts/test_dimos_rpc.py`), ran the whole service in `dimos` mode with YOLO on recorded Go2
  camera frames, and drove one goal through the real A* planner (goal accepted, path found,
  watchdog halt). Details and log excerpts in docs/dimos-notes.md.
Not done: no physical Go2 motion (network provisioning pending), no real OpenAI call (no key
configured), no ESP32/Nordic/Arduino firmware.
