# Environment discovery — 2026-09-19

Repository initially empty except Git and agent metadata. No applicable AGENTS.md found.
Host: Dell Latitude 5550, Ubuntu 24.04-derived Linux, x86_64, kernel 7.0.0-31.
Python 3.12.3; pip, Docker, Node 20.20.2 available; uv not found.
FastAPI 0.136.1, Pydantic 2, pytest, OpenAI 2.9.0, OpenCV 4.13,
PyTorch 2.11 installed. CUDA Python packages exist but CUDA is unavailable and GPU count is zero.
No dimOS, ROS2 Python package, Unitree checkout, or ASUS examples found in /opt and nearby development directories.

Sandbox prevented initial network/USB discovery; approved read-only host discovery succeeded:
Wi-Fi wlp1s0 at 10.189.85.6/19; Ethernet down. Neighbor cache contains only gateway.
No robot address configured; no MCP listener on localhost:9990.
Integrated USB webcam exists at /dev/video0 and /dev/video1.
No serial /dev/ttyUSB* or /dev/ttyACM* devices. No secondary sponsor board identified.
OPENAI_API_KEY, OPENAI_MODEL, ROBOT_IP, CAMERA_SOURCE unset (values never printed).
Shell DNS requires network permission; official docs fetched successfully with it.
No sponsor software removed or global packages changed.

This host is not the ASUS GX10. GPU throughput and Go2 motion cannot be validated here yet.

## Later hardware update
After the user powered on the Go2, a fresh Wi-Fi scan identified
`Go2_61034_bad22205` at 95% signal. The laptop remains on HackMIT.2026;
robot address is pending app network configuration.
SEGGER J-Link subsequently appeared on USB with ttyACM0/ttyACM1; no USB network
interface appeared. GX10 ownership/setup still needs confirmation.

## Validation
18 tests passed on host (2.40 s), including API STOP during active search.
Headless Chrome rendered the dashboard successfully. Real laptop webcam: three frames,
people detected, SQLite camera observations and evidence images written. Warmed YOLO
CPU latency 100–109 ms; first inference about 2 s. Not a GX10 benchmark.

## Isolated dimOS preparation

Installed dimOS 0.0.14 and unitree-webrtc-connect 2.2.0 into `.dimos-venv`.
Verified `from dimos import Dimos`, `Dimos.connect(timeout=5.0)`, and
`peek_stream(name, timeout=1.0)` from the installed distribution.
PortAudio header was missing: downloaded the Ubuntu development package and extracted it
locally to compile PyAudio against the existing system runtime. TurboJPEG runtime was also
extracted locally to ignored `data/native`; `scripts/dimos.sh` supplies its library path.
No apt install, system package removal, or system Python upgrade occurred.
The venv inherits existing system packages; pip reported unrelated pre-existing optional
package conflicts. Core import and discovery are checked separately; full navigation startup is not verified.

Official dimOS BLE discovery confirmed Go2_61034, address 94:BA:06:F6:DE:C3.

## Continuation session (Claude Code, 2026-09-19, after Codex credits ran out)

Re-verified on the same Dell Latitude 5550 (14 cores, 30 GiB RAM, no NVIDIA GPU; `torch 2.11+cu130`
reports `cuda=False`). Project venv `.venv` has ultralytics 8.4, OpenCV 4.13, openai 2.9, pyserial.
Isolated `.dimos-venv` has dimOS 0.0.14, unitree-webrtc-connect 2.2.0, eclipse-zenoh 1.10; MuJoCo 3.13
was added to it for future simulation work (the Go2 sim additionally needs `mujoco_playground`
data downloads and a GUI viewer, so it was not exercised).

Network at check time: laptop on `HackMIT.2026` (10.189.85.6/19). Visible robot APs:
`Go2_61034_56fa1ae6` (ours, 92%), `Go2_61331_29d4be72`, `Go2_61824`. The Go2 is still in its own
access-point mode, so it is not reachable from the laptop's current network. Two options remain,
both needing a human decision: provision the Go2 onto `HackMIT.2026` (transfers the Wi-Fi credential
to the robot) or join the laptop to the Go2 AP (laptop loses internet; cloud agent then unavailable).

USB: SEGGER J-Link `001050742694` exposes `/dev/ttyACM0` and `/dev/ttyACM1` (consistent with the
nRF7002-DK's onboard debugger). Neither port emitted bytes at 115200 baud over 4 s, so no firmware
is currently printing. No nRF Connect SDK, `west`, `nrfjprog`, `esptool`, or `arduino-cli` is
installed; flashing sponsor boards needs those toolchains first. `/dev/video0` is the laptop webcam.

Real-perception measurements on this laptop (CPU, YOLO11n, 640x480 webcam frames):
first inference ~1.8 s (model load), then 84–130 ms per frame; full pipeline (capture, detect,
signature, SQLite write) ~97 ms. These are laptop numbers, not GX10 numbers.

### Replay-mode validation
The installed dimOS 0.0.14 `unitree-go2` blueprint runs on this laptop in `--replay` mode with
`--viewer none` after two venv-local fixes (`coverage` upgrade for numba, local `git-lfs` binary).
`scripts/test_dimos_rpc.py` passed every adapter call against it; see docs/dimos-notes.md.
