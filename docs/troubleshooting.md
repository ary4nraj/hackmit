# Troubleshooting

- Async tests hang under a restrictive sandbox: thread wakeups need local sockets. Run pytest in
  the normal host environment. The suite completed normally there.
- “dimOS not installed”: use the official dedicated environment; run read-only preflight before live sensing.
- No CUDA device: this development host is a CPU laptop. Installed CUDA Python packages do not prove GPU access.
- USB-C to GX10 gives no network: inspect enumeration. Use completed GX10 Wi-Fi/Ethernet setup and SSH.
- STOP stays latched: expected. Wait for the current task to end, then press Resume.
- Camera fails: check source and device permissions. No frame is an error, never an empty-room observation.
- Multiple backpacks: class detections do not establish personal identity; use unique tags for reliable relocation.
- “Cannot navigate” in dimOS mode: physical safety commissioning is unfinished. Do not remove the guard to demo.
- API unavailable: `make run`, then open http://127.0.0.1:8000. Only local Host/Origin requests are permitted.
- Cloud unavailable: unset API key/model and restart for offline commands; manual endpoints remain usable.
- Repeated demos: choose a new DATABASE_URL; don't delete historical evidence by default.
- Model dependencies: `pip install -e '.[vision]'` in a venv, preserving the GX10 vendor PyTorch installation.
- One object becomes many entities: check `APPEARANCE_MATCH_THRESHOLD` (default 0.85). Busy
  scenes with several people legitimately create several person entities.
- `ROBOT_BACKEND=dimos requires ZONES_FILE`: copy `config/zones.example.json` and survey real waypoints.
- Webcam backend says "Camera 0 not available": another process holds the device, or set `CAMERA_SOURCE`.
- DimosRobot "motion disabled: missing modules": you launched a blueprint without the planner; use `unitree-go2`.
