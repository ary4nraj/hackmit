# Hardware setup

## Go2 + dimOS

User reports robot name `Go2_61034`. As of the session's network check, that SSID/hostname was
initially not visible; after power-on, `Go2_61034_bad22205` appeared at 95% signal.
A different `Go2_61824` was also visible and was NOT connected to or controlled.
The current laptop is on HackMIT.2026. Get the actual robot network/address before continuing.

Use the official dimOS installation procedure on a dedicated environment (Python 3.12):
https://github.com/dimensionalOS/dimos . The official installer changes system dependencies,
so it was not run on this laptop merely to make an import succeed.
Match the source revision recorded in dimos-notes.md or recheck interfaces for a newer install.

Once configured on the robot's network, note that **starting the standard Go2 blueprint
stands the robot up**, and stopping its module may make it lie down. Clear the area and
have the operator beside the physical stop before launching it. The following is NOT a
camera-only startup:

```bash
export ROBOT_IP=<verified-address>
dimos run unitree-go2
# In a second terminal using that same environment/transport:
python -m scripts.test_robot
```

This script reads pose, deployed modules, and camera. It does not move or stand the dog up.
For Recall Rover live sensing set ROBOT_BACKEND=dimos and PERCEPTION_PROVIDER=local (or tags).
No implicit mock fallback is allowed. Hardware navigation is refused until commissioning adds
and verifies the actuator-side speed clamp/deadman described in dimos-notes.md.
A user-side timeout cannot stop a robot whose network link is already lost.

Survey flat zones in the odometry/map frame. No stairs; observation waypoints must maintain clearance
from people. Place them at safe observation positions rather than on top of target objects.
ZONES_FILE is a JSON mapping from zone names to `[x,y]`; sample mock coordinates are not safe
hardware coordinates. Verify localization after every stack restart; do not reuse an old frame silently.

## ASUS Ascent GX10

User attached USB-C. No new USB network interface was exposed to the laptop.
A `gx10-f3bc` Wi-Fi network is visible, but ownership and initial setup are unconfirmed.
The USB device newly enumerated was SEGGER J-Link, with ttyACM0/ttyACM1; it is not evidence of
GX10 compute connectivity. Use completed GX10 setup plus Wi-Fi/Ethernet and an SSH hostname/login.

On GX10, inspect `nvidia-smi`, Python architecture, and `torch.cuda.is_available()` before installing
packages. Preserve sponsor-provided NVIDIA/PyTorch builds. Install Recall Rover in a virtual environment
that can access compatible PyTorch, then use PERCEPTION_DEVICE=cuda for local inference.
Verify camera and model throughput before using it in the robot loop.

ASUS hardware reference:
https://dlcdnwebimgs.asus.com/files/media/202506/5c0fb57c-4e48-4e96-8c97-04bf8df2677c/asus-ascent-gx10-datasheet.pdf

## Secondary boards

ESP32-S3-BOX-3: deferred until physical relocation works; browser text/voice is the current terminal.
Nordic nRF7002-DK: possible J-Link device detected, but board identity not confirmed; no firmware flashed.
Future Wi-Fi fingerprints must be calibrated and labeled coarse context, never precise positioning.
Arduino UNO Q: no useful sensor confirmed; no implementation claimed.
Deepgram: no configured credentials; browser speech remains optional.

## Prepared laptop environment

This session installed dimOS 0.0.14 and Go2 WebRTC 2.2.0 into `.dimos-venv`.
Run `./scripts/dimos.sh go2tool discover --timeout 7` for bounded read-only discovery.
The wrapper loads locally extracted TurboJPEG from `data/native`. These ignored machine-specific
artifacts are not included in a Git checkout; use official installation on the GX10.

## Go2 commissioning checklist (continuation session)

1. Put the laptop (or GX10) and the Go2 on one network and set `ROBOT_IP`. The Go2 is currently in
   AP mode (`Go2_61034_56fa1ae6`); a human must decide between provisioning it onto `HackMIT.2026`
   (Unitree app, or dimOS's provisioning tool which transfers the Wi-Fi password) or joining the
   laptop to the Go2 AP (no internet, so run the agent in offline-command mode).
2. Copy `config/zones.example.json`, survey real waypoints, set `ZONES_FILE`. Settings refuses
   `ROBOT_BACKEND=dimos` without it.
3. Clear the floor. One person holds the Unitree remote / app stop. Launch, expecting the robot to
   **stand up** on start: `make dimos` (equals `./scripts/dimos.sh --nerf-speed 0.45 run unitree-go2`).
4. Read-only preflight: `make preflight` (pose, modules, camera frame; no motion).
5. First motion, one bounded action with explicit typed confirmation:
   `ROBOT_BACKEND=dimos PERCEPTION_PROVIDER=local ZONES_FILE=... ./scripts/dimos-python.sh -m scripts.test_navigation --rotate 0.5`
   then `--zone "entrance table"`. Watch the `robot.navigation.*` trace it prints.
6. Only then start the service: `make run-dimos` (YOLO + ArUco combined perception).

Speed cap is layered: Safety refuses > 0.5 m/s config, DimosRobot aborts on measured overspeed,
the planner is nerfed at launch, and the WebRTC layer zeroes the base 0.2 s after the last command.
