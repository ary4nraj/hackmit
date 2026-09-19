# Hackathon status — updated 2026-09-19 (after golden-path script)

## WORKING
- Golden path: `./scripts/demo.sh [mock|webcam|replay|go2]` starts everything (fresh DB per run, opens browser, prints judge script).
- Mock relocation loop end to end: remember → move → verify → INVALIDATED → bounded search → MOVED → "What changed?". `make demo` / `make test` (31 tests, ~7 s).
- Real perception: YOLO11n + appearance-signature association; laptop webcam live (`demo.sh webcam`), 84–130 ms/frame CPU; real-pixel relocation test passes.
- dimOS 0.0.14 adapter verified against the real `unitree-go2` blueprint in replay: streams, planner goal accepted + path planned, cancel/stop/latch, watchdog. Service runs in `dimos` mode with YOLO on recorded Go2 camera frames.
- Dashboard: camera with boxes, memory cards with knowledge state, change timeline, tool trace, LOCAL vs CLOUD telemetry, STOP/Resume.
- Offline command agent (no API key needed) handles the whole demo script.

## BROKEN
- Nothing known broken in software. Untested: real OpenAI tool calling (no key), physical Go2 arrival (robot not on our network yet).
- Two identical-looking objects of one class cannot be told apart (by design they stay separate candidates; use ArUco tags for the hidden package).

## NEXT 3 TASKS
1. Get the Go2 onto the laptop's network (or laptop onto Go2 AP) → `make preflight` → one confirmed move with `scripts/test_navigation.py --rotate 0.5`.
2. Survey 3–4 flat waypoints into `config/zones.json`, run `./scripts/demo.sh go2`, do the backpack relocation live once.
3. Put `OPENAI_API_KEY`/`OPENAI_MODEL` in `.env` and run the judge script through the cloud agent once (offline mode is the fallback).

## MANUAL ACTION NEEDED
- Provision Go2_61034 onto HackMIT.2026 via the Unitree app (or tell me to join the laptop to `Go2_61034_56fa1ae6`, which drops internet). Then give me `ROBOT_IP`.
- Human beside the physical stop for every launch: dimOS start makes the robot STAND UP.
- Optional: OpenAI key in `.env`; a printed ArUco 4x4_50 marker id 0 taped on the "package".
- If port 8000 is busy, `demo.sh` refuses to double-bind: stop the other server or run `PORT=8001 ./scripts/demo.sh`.
- Repo has zero git commits: say the word and I'll commit.

## DEMO READINESS
- Mock demo: READY (one command, deterministic).
- Real-camera demo (laptop/GX10 webcam): READY, needs a backpack or bottle in view.
- Physical Go2 demo: NOT READY — blocked on network access; all software paths exercised against replay. Estimated 30–60 min of commissioning once the robot is reachable.
- Sponsor extras (ESP32/Nordic/Arduino/Deepgram): not started, deliberately.
