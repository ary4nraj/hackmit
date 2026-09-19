from fastapi.testclient import TestClient

from recall_rover.api.app import create_app
from recall_rover.config import Settings


def test_api_demo(tmp_path):
    with TestClient(create_app(Settings(database=str(tmp_path / "api.db")))) as client:
        assert client.get("/").status_code == 200
        assert client.get("/health").json()["backend"] == "mock"
        assert client.get("/robot/status").json()["connected"]
        assert (
            client.get("/camera/latest")
            .headers["content-type"]
            .startswith("image/svg+xml")
        )
        assert (
            "entrance table"
            in client.post(
                "/agent/message", json={"text": "Where is my backpack?"}
            ).json()["answer"]
        )
        assert (
            client.post(
                "/demo/relocate", json={"label": "backpack", "zone": "back wall"}
            ).status_code
            == 200
        )
        result = client.post("/agent/message", json={"text": "Find backpack"}).json()
        assert "back wall" in result["answer"]
        assert any(x["type"] == "MOVED" for x in client.get("/changes").json())
        assert client.post("/robot/stop").json()["latched"]
        assert (
            client.post("/robot/navigate", json={"zone": "left side"}).status_code
            == 409
        )
        assert client.post("/robot/resume").status_code == 200
        assert (
            client.post("/robot/navigate", json={"zone": "outside"}).status_code == 400
        )
        assert (
            client.post(
                "/robot/stop", headers={"Origin": "https://evil.test"}
            ).status_code
            == 403
        )
        assert client.post("/agent/message", json={"text": ""}).status_code == 422


def test_websocket(tmp_path):
    with TestClient(create_app(Settings(database=str(tmp_path / "ws.db")))) as client:
        with client.websocket_connect("/ws/events") as ws:
            client.post("/robot/stop")
            assert ws.receive_json()["type"] == "robot.stopped"
