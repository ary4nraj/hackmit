import asyncio
import contextlib
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from recall_rover.agent.agent import Agent
from recall_rover.agent.tools import Tools
from recall_rover.config import Settings
from recall_rover.memory.repository import Memory
from recall_rover.perception.pipeline import MockPerceptionProvider, Pipeline
from recall_rover.robot.exploration import Investigator
from recall_rover.robot.mock_robot import MockRobot
from recall_rover.robot.safety import Safety

ROOT = Path(__file__).resolve().parents[2]


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=2000)


class Target(BaseModel):
    model_config = ConfigDict(extra="forbid")
    zone: str


class Relocate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    zone: str | None


class Runtime:
    def __init__(self, settings, robot, provider):
        self.settings = settings
        self.robot = robot
        self.memory = Memory(settings.database)
        self.events = []
        self.subscribers = set()
        self.task_lock = asyncio.Lock()
        self.active_task = None
        self.log_path = Path("data/demo.jsonl")
        self.log_path.parent.mkdir(exist_ok=True)
        self.safety = Safety(robot, settings, self.emit)
        self.pipeline = Pipeline(
            robot, provider, self.memory, settings.zones, self.emit
        )
        self.investigator = Investigator(
            self.memory, self.safety, self.pipeline, settings.zones, self.emit
        )
        self.tools = Tools(
            self.memory, robot, self.safety, self.pipeline, self.investigator, self.emit
        )
        self.agent = Agent(self.tools, self.emit)

    def emit(self, kind, data):
        event = {"type": kind, "timestamp": time.time(), "data": data}
        self.events.append(event)
        self.events = self.events[-150:]
        with self.log_path.open("a") as f:
            f.write(json.dumps(event) + "\n")
        for queue in tuple(self.subscribers):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(event)

    async def exclusive(self, fn):
        if self.task_lock.locked():
            raise HTTPException(409, "Task in progress; STOP remains available")
        async with self.task_lock:
            self.active_task = asyncio.current_task()
            try:
                return await fn()
            except asyncio.CancelledError:
                raise HTTPException(409, "Task interrupted by STOP")
            finally:
                self.active_task = None


def create_app(settings=None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        if settings.backend == "mock":
            robot = MockRobot(settings.zones, delay=0.45)
        elif settings.backend == "webcam":
            from recall_rover.robot.webcam_robot import WebcamRobot

            robot = WebcamRobot(settings.camera_source, settings.zones)
        else:
            from recall_rover.robot.dimos_robot import DimosRobot

            robot = await DimosRobot.connect()
        if settings.perception == "mock":
            provider = MockPerceptionProvider()
        else:
            from recall_rover.perception.detector import (
                CombinedProvider,
                LocalDetectorProvider,
                TagDetectorProvider,
            )

            provider = {
                "local": LocalDetectorProvider,
                "tags": TagDetectorProvider,
                "combined": lambda: CombinedProvider(LocalDetectorProvider(), TagDetectorProvider()),
            }[settings.perception]()
        rt = Runtime(settings, robot, provider)
        app.state.rt = rt
        # Initial perception, never pre-populate fictional observations for hardware.
        try:
            await rt.pipeline.inspect()
        except Exception as exc:
            rt.emit("perception.error", {"error": str(exc)})

        async def continuous():
            while True:
                await asyncio.sleep(settings.perception_interval)
                if rt.task_lock.locked() or robot.moving:
                    continue
                try:
                    await rt.pipeline.inspect()
                except Exception as exc:
                    rt.emit("perception.error", {"error": str(exc)})
                    if robot.moving:
                        await rt.safety.stop_now()

        worker = asyncio.create_task(continuous())
        try:
            yield
        finally:
            worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker
            try:
                await rt.safety.stop_now()
            finally:
                rt.memory.close()
                if hasattr(robot, "close"):
                    robot.close()

    app = FastAPI(title="Recall Rover", lifespan=lifespan)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"]
    )

    @app.middleware("http")
    async def origin_guard(request: Request, call_next):
        origin = request.headers.get("origin")
        if (
            request.method == "POST"
            and origin
            and origin not in {str(request.base_url).rstrip("/")}
        ):
            return JSONResponse(
                {"detail": "Cross-origin robot commands forbidden"}, status_code=403
            )
        return await call_next(request)

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(RuntimeError)
    async def runtime_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.get("/")
    async def dashboard():
        return FileResponse(ROOT / "apps/dashboard/index.html")

    @app.get("/health")
    async def health():
        return {
            "ok": True,
            "backend": settings.backend,
            "perception": settings.perception,
        }

    @app.get("/robot/status")
    async def status():
        return await app.state.rt.robot.get_health() | {
            "stop_latched": app.state.rt.safety.latched
        }

    @app.post("/robot/stop")
    async def stop():
        rt = app.state.rt
        # Latch BEFORE cancellation so search cannot issue a subsequent navigation.
        rt.safety.latched = True
        if rt.active_task and rt.active_task is not asyncio.current_task():
            rt.active_task.cancel()
        await rt.safety.stop_now()
        return {"stopped": True, "latched": True}

    @app.post("/robot/resume")
    async def resume():
        rt = app.state.rt
        if rt.task_lock.locked():
            raise HTTPException(409, "Wait for task cancellation")
        rt.safety.resume()
        return {"latched": False}

    @app.post("/robot/navigate")
    async def navigate(target: Target):
        rt = app.state.rt
        if target.zone not in settings.zones:
            raise ValueError("Unknown zone")

        async def operation():
            return [
                o.model_dump() for o in await rt.investigator.inspect_zone(target.zone)
            ]

        return await rt.exclusive(operation)

    @app.post("/perception/inspect")
    async def inspect():
        rt = app.state.rt

        async def operation():
            return [o.model_dump() for o in await rt.pipeline.inspect()]

        return await rt.exclusive(operation)

    @app.get("/memory/entities")
    async def entities():
        return app.state.rt.memory.entities()

    @app.get("/memory/search")
    async def search(q: str = ""):
        return app.state.rt.memory.entities(q)

    @app.get("/memory/entity/{eid}")
    async def history(eid: str):
        return app.state.rt.memory.get_object_history(eid)

    @app.get("/changes")
    @app.get("/memory/changes")
    @app.get("/memory/timeline")
    async def changes(since: float = 0):
        return app.state.rt.memory.changes(since)

    @app.get("/state")
    async def state():
        rt = app.state.rt
        return {
            "robot": await status(),
            "entities": rt.memory.entities(),
            "changes": rt.memory.changes(),
            "events": rt.events[-30:],
            "zones": settings.zones,
            "telemetry": rt.pipeline.telemetry,
            "busy": rt.task_lock.locked(),
            "backend": settings.backend,
            "perception": settings.perception,
            "agent_mode": "OpenAI" if os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_MODEL") else "offline commands",
        }

    @app.get("/memory/what-changed")
    async def what_changed(since: float = 0):
        return app.state.rt.memory.what_changed_since(since)

    @app.post("/agent/message")
    async def message(body: Message):
        rt = app.state.rt
        if body.text.lower().strip() in {"stop", "emergency stop", "stop robot"}:
            await stop()
            return {
                "answer": "Stopped. Motion is latched.",
                "mode": "safety",
                "latency_ms": 0,
            }
        return await rt.exclusive(lambda: rt.agent.message(body.text))

    @app.post("/demo/relocate")
    async def relocate(body: Relocate):
        rt = app.state.rt
        if settings.backend != "mock":
            raise HTTPException(403, "Only available with MockRobot")
        rt.robot.move_object(body.label, body.zone)
        rt.emit(
            "demo.world_changed",
            {"label": body.label, "note": "Ground truth changed; memory not updated"},
        )
        return {"ok": True}

    @app.get("/camera/latest")
    async def camera():
        frame = app.state.rt.pipeline.last_frame
        if isinstance(frame, dict):
            from html import escape

            labels = escape(", ".join(frame["objects"]) or "No target detected")
            svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="400"><rect width="100%" height="100%" fill="#122c37"/><text x="35" y="60" fill="#6de4bb" font-size="18">SIMULATED VIEW · {escape(frame["zone"])}</text><rect x="150" y="110" width="500" height="200" rx="12" stroke="#6de4bb" fill="none"/><text x="190" y="220" fill="white" font-size="25">{labels}</text></svg>'
            return Response(svg, media_type="image/svg+xml")
        if frame is None:
            raise HTTPException(503, "No camera frame")
        import cv2

        annotated = getattr(app.state.rt.pipeline.provider, "last_annotated", None)
        if annotated is not None and getattr(annotated, "shape", None) == frame.shape:
            frame = annotated
        ok, encoded = await asyncio.to_thread(cv2.imencode, ".jpg", frame)
        if not ok:
            raise HTTPException(503, "JPEG encoding failed")
        return Response(encoded.tobytes(), media_type="image/jpeg")

    @app.websocket("/ws/events")
    async def websocket(ws: WebSocket):
        if ws.headers.get("origin") not in {None, f"http://{ws.headers.get('host')}"}:
            await ws.close(code=1008)
            return
        await ws.accept()
        queue = asyncio.Queue(maxsize=100)
        rt = app.state.rt
        rt.subscribers.add(queue)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), 10)
                except TimeoutError:
                    event = {"type": "heartbeat"}
                await ws.send_json(event)
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            rt.subscribers.discard(queue)

    return app


app = create_app()
