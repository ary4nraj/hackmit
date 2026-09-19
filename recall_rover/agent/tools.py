from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal[
        "search_memory",
        "last_seen",
        "object_history",
        "what_changed",
        "inspect_current_view",
        "find_object",
        "go_to_object",
        "inspect_zone",
        "get_robot_status",
        "stop_robot",
    ]
    target: str = Field(max_length=100)
    since: float = Field(ge=0, allow_inf_nan=False)


class Tools:
    def __init__(self, memory, robot, safety, pipeline, investigator, emit):
        self.memory = memory
        self.robot = robot
        self.safety = safety
        self.pipeline = pipeline
        self.investigator = investigator
        self.emit = emit

    async def call(self, raw):
        args = ToolArgs.model_validate(raw)
        self.emit("agent.tool_call", args.model_dump())
        try:
            match args.action:
                case "search_memory" | "last_seen":
                    result = self.memory.entities(args.target)
                case "object_history":
                    entity = self.memory.find_best_match(args.target)
                    result = (
                        self.memory.get_object_history(entity["id"]) if entity else []
                    )
                case "what_changed":
                    result = self.memory.changes(args.since)
                case "inspect_current_view":
                    result = [o.model_dump() for o in await self.pipeline.inspect()]
                case "find_object" | "go_to_object":
                    if args.target == "person":
                        raise ValueError(
                            "Do not approach people; inspect the entrance observation waypoint"
                        )
                    result = await self.investigator.find_object(args.target)
                case "inspect_zone":
                    if args.target not in self.investigator.zones:
                        raise ValueError("Unknown zone")
                    result = [
                        o.model_dump()
                        for o in await self.investigator.inspect_zone(args.target)
                    ]
                case "get_robot_status":
                    result = await self.robot.get_health()
                case "stop_robot":
                    await self.safety.stop_now()
                    result = {"stopped": True, "latched": True}
            self.emit("agent.tool_result", {"action": args.action, "result": result})
            return result
        except BaseException:
            if self.robot.moving:
                await self.safety.stop_now()
            raise
