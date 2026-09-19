import asyncio

import httpx

from recall_rover.api.app import create_app
from recall_rover.config import Settings


def test_stop_during_api_search(tmp_path):
    async def run():
        app = create_app(Settings(database=str(tmp_path / "stop.db")))
        async with app.router.lifespan_context(app), httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://testserver"
        ) as c:
            await c.post(
                "/demo/relocate", json={"label": "backpack", "zone": "back wall"}
            )
            task = asyncio.create_task(
                c.post("/agent/message", json={"text": "Find backpack"})
            )
            await asyncio.sleep(0.05)
            stop = await c.post("/robot/stop")
            assert stop.status_code == 200
            result = await task
            assert result.status_code == 409
            rt = app.state.rt
            assert rt.safety.latched and not rt.robot.moving
            assert len(rt.robot.motion_log) == 1
            assert (
                rt.memory.find_best_match("backpack")["observation"]["zone"]
                == "entrance table"
            )

    asyncio.run(run())
