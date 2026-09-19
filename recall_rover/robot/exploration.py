"""Bounded physical investigation: remembered zone first, then least-recently checked zones."""

from recall_rover.memory.models import Pose


class Investigator:
    def __init__(self, memory, safety, pipeline, zones, emit=lambda *a: None):
        self.memory = memory
        self.safety = safety
        self.pipeline = pipeline
        self.zones = zones
        self.emit = emit

    async def inspect_zone(self, zone):
        x, y = self.zones[zone]
        await self.safety.safe_navigate_to(Pose(x=x, y=y))
        return await self.pipeline.inspect()

    def _matches(self, seen, label, known):
        matches = [o for o in seen if o.label == label]
        if known and known["identity"]:
            matches = [o for o in matches if o.detection.identity == known["identity"]]
        # Prefer the remembered entity when association linked it; else any class match.
        if known:
            same = [o for o in matches if o.entity_id == known["id"]]
            if same:
                return same
        return matches

    def _result(self, match, known, checked):
        same = bool(known and match.entity_id == known["id"])
        return {
            "found": True,
            "observation": match.model_dump(exclude={"detection": {"embedding"}}),
            "checked": checked,
            "identity_confirmed": bool(match.detection.identity),
            "same_entity": same or not known,
            "zone": match.zone,
            "previous_zone": known["observation"]["zone"] if known else None,
        }

    async def find_object(self, label):
        known = self.memory.find_best_match(label)
        checked = []
        zones = self.memory.regions_to_check(self.zones)
        if known:
            remembered = known["observation"]["zone"]
            zones = [remembered] + [z for z in zones if z != remembered]
        for zone in zones:
            if self.safety.latched:
                raise RuntimeError("Search stopped")
            self.emit("agent.search", {"target": label, "zone": zone})
            seen = await self.inspect_zone(zone)
            checked.append(zone)
            matches = self._matches(seen, label, known)
            if matches:
                return self._result(matches[0], known, checked)
            if known and zone == known["observation"]["zone"] and known["status"] == "active":
                # A second successful view reduces transient detector misses. No camera errors mean absence.
                second = await self.pipeline.inspect()
                matches = self._matches(second, label, known)
                if matches:
                    return self._result(matches[0], known, checked)
                self.memory.invalidate(known["id"])
                self.emit("memory.invalidated", {"entity": known["id"], "zone": zone})
        return {
            "found": False,
            "checked": checked,
            "summary": f"{label} not observed in the bounded search; it may be occluded or elsewhere.",
        }
