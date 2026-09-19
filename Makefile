PYTHON ?= python3
.PHONY: run run-webcam run-dimos test demo camera dimos replay preflight rpc-check
run:
	$(PYTHON) -m uvicorn recall_rover.api.app:app --host 127.0.0.1 --port 8000
run-webcam:
	ROBOT_BACKEND=webcam PERCEPTION_PROVIDER=$${PERCEPTION_PROVIDER:-local} $(PYTHON) -m uvicorn recall_rover.api.app:app --host 127.0.0.1 --port 8000
run-dimos:
	ROBOT_BACKEND=dimos PERCEPTION_PROVIDER=$${PERCEPTION_PROVIDER:-combined} ./scripts/dimos-python.sh -m uvicorn recall_rover.api.app:app --host 127.0.0.1 --port 8000
test:
	$(PYTHON) -m pytest -q
demo:
	$(PYTHON) -m scripts.run_mock_demo
camera:
	$(PYTHON) -m scripts.test_camera --frames 5
dimos:
	./scripts/dimos.sh --nerf-speed $${DIMOS_NERF_SPEED:-0.45} run unitree-go2
replay:
	./scripts/dimos.sh --replay --viewer none run unitree-go2
preflight:
	./scripts/dimos-python.sh -m scripts.test_robot
rpc-check:
	./scripts/dimos-python.sh -m scripts.test_dimos_rpc
