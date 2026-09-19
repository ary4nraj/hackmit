from typing import Protocol

from recall_rover.memory.models import Detection


class PerceptionProvider(Protocol):
    async def detect(self, frame) -> list[Detection]: ...
