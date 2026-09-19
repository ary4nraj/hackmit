# Sponsor fit: evidence and remaining work

| Track | Implemented evidence | Required before claiming hardware integration |
|---|---|---|
| Dimensional | dimOS 0.0.14 source-verified adapter: navigation/rotate/stop/battery, speed cap via `--nerf-speed`, 0.2 s WebRTC deadman + odometry watchdog; bounded embodied loop in mock and on a real camera | Put Go2 on the network; run `scripts/test_navigation.py`; run the physical relocation loop |
| OpenAI | Responses tool orchestration, strict tool schema, mocked roundtrip tests, Codex implementation log (Codex phase) plus a clearly separated Claude Code continuation log | Configure key/model and run real cloud interaction |
| ASUS | Local YOLO + appearance signatures, image evidence, LOCAL vs CLOUD telemetry on the dashboard, `PERCEPTION_DEVICE=cuda` switch | Run on GX10 GPU and measure workload |
| Espressif | Browser terminal fallback | Real BOX-3 status/voice firmware |
| Nordic | USB J-Link discovery only | Confirm board; real Wi-Fi scan firmware and calibrated context |
| Arduino | No integration claimed | Useful sensor plus real readings |
| Deepgram | Browser speech fallback only | Credentials and actual STT/TTS integration |

The technical demonstration is invalidation and physical investigation of stale memory, not a
camera-to-chatbot pipeline. Sponsor eligibility still depends on actual hardware execution and rules.
