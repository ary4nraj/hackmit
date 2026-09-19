"""SQLite evidence store. Historical observations are never replaced by new guesses."""

import json
import math
import os
import sqlite3
import time
from pathlib import Path
from uuid import uuid4

from recall_rover.perception.embeddings import similarity

from .models import Detection, Observation, Pose

# Appearance association thresholds: cosine similarity of HSV signatures.
APPEARANCE_MATCH = float(os.getenv("APPEARANCE_MATCH_THRESHOLD", "0.85"))
APPEARANCE_MARGIN = float(os.getenv("APPEARANCE_MATCH_MARGIN", "0.05"))
DECAY_SECONDS = 300


def _iou(a, b):
    overlap = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - overlap
    return overlap / union if union > 0 else 0.0


class Memory:
    def __init__(self, path=":memory:", clock=time.time):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.clock = clock
        self.db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS entities(id TEXT PRIMARY KEY, label TEXT, identity TEXT UNIQUE,
          latest TEXT, status TEXT, first_seen REAL, last_seen REAL);
        CREATE TABLE IF NOT EXISTS observations(id TEXT PRIMARY KEY, entity_id TEXT, timestamp REAL, data TEXT);
        CREATE INDEX IF NOT EXISTS observations_entity ON observations(entity_id,timestamp);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp REAL, type TEXT,
          entity_id TEXT, previous_observation TEXT, new_observation TEXT, summary TEXT);
        CREATE TABLE IF NOT EXISTS regions(zone TEXT PRIMARY KEY, checked REAL);
        """)

    def close(self):
        self.db.close()

    # ---------------------------------------------------------------- events
    def event(self, kind, summary, entity=None, previous=None, new=None):
        self.db.execute(
            "INSERT INTO events(timestamp,type,entity_id,previous_observation,new_observation,summary) VALUES(?,?,?,?,?,?)",
            (self.clock(), kind, entity, previous, new, summary),
        )

    record_change = event

    def observation(self, oid):
        row = self.db.execute("SELECT data FROM observations WHERE id=?", (oid,)).fetchone()
        return Observation.model_validate_json(row[0]) if row else None

    # ----------------------------------------------------------- association
    def _associate(self, detection, zone, now, frame_id=None):
        """Return (entity_row | None, how). Conservative: unsure means a new candidate entity."""
        if detection.identity:
            row = self.db.execute("SELECT * FROM entities WHERE identity=?", (detection.identity,)).fetchone()
            if row and row["label"] != detection.label:
                raise ValueError("Identity cannot change category")
            return row, "identity" if row else "new"
        candidates = self.db.execute(
            "SELECT * FROM entities WHERE label=? AND identity IS NULL AND status IN ('active','missing')",
            (detection.label,),
        ).fetchall()
        # 1. Short-term same-view continuity: same zone, recent, overlapping box.
        scored = []
        for candidate in candidates:
            old = self.observation(candidate["latest"])
            if (
                candidate["status"] == "active"
                and old.zone == zone
                and now - candidate["last_seen"] < 30
                and old.detection.description == detection.description
                and old.detection.bbox
                and detection.bbox
                and (frame_id is None or old.frame_id != frame_id)
            ):
                iou = _iou(old.detection.bbox, detection.bbox)
                if iou > 0.3:
                    scored.append((iou, candidate))
        scored.sort(key=lambda item: item[0], reverse=True)
        if scored and (len(scored) == 1 or scored[0][0] - scored[1][0] > 0.15):
            return scored[0][1], "overlap"
        # 2. Appearance: same class and the crop looks like the remembered object.
        if detection.embedding:
            looks = []
            for candidate in candidates:
                old = self.observation(candidate["latest"])
                if not old.detection.embedding:
                    continue
                # Already recorded from this very frame at a different box: it is visible
                # elsewhere in the same image, so it cannot be this detection. Prevents merging
                # two look-alike objects that appear together.
                if frame_id and old.frame_id == frame_id:
                    continue
                looks.append((similarity(old.detection.embedding, detection.embedding), candidate))
            looks.sort(key=lambda item: item[0], reverse=True)
            if looks and looks[0][0] >= APPEARANCE_MATCH:
                best, runner_up = looks[0], looks[1] if len(looks) > 1 else None
                if runner_up is None or best[0] - runner_up[0] >= APPEARANCE_MARGIN:
                    return best[1], f"appearance {best[0]:.2f}"
                # Ambiguous. Claiming a MOVE between look-alikes would be a fabrication, but
                # linking to a look-alike already in THIS zone only yields REOBSERVED, which is
                # safe and prevents one object fragmenting into many entities.
                tied = [c for sim, c in looks if best[0] - sim < APPEARANCE_MARGIN]
                here = [c for c in tied if self.observation(c["latest"]).zone == zone]
                if here:
                    newest = max(here, key=lambda c: c["last_seen"])
                    return newest, f"appearance {best[0]:.2f} (ambiguous; same zone)"
        return None, "new"

    def remember_observation(self, detection: Detection, pose: Pose, zone: str, frame_id: str | None = None):
        now = self.clock()
        row, how = self._associate(detection, zone, now, frame_id)
        eid = row["id"] if row else uuid4().hex
        previous = self.observation(row["latest"]) if row else None
        if previous and previous.status == "active" and previous.zone == zone and now - previous.timestamp < 1:
            return previous  # throttle: same view, same second
        obs = Observation(
            entity_id=eid,
            label=detection.label,
            timestamp=now,
            confidence=detection.confidence,
            pose=pose,
            zone=zone,
            detection=detection,
            frame_id=frame_id,
        )
        with self.db:
            self.db.execute(
                "INSERT INTO observations VALUES(?,?,?,?)",
                (obs.observation_id, eid, now, obs.model_dump_json()),
            )
            self.db.execute(
                "INSERT INTO entities VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET latest=excluded.latest,status=excluded.status,last_seen=excluded.last_seen",
                (eid, detection.label, detection.identity, obs.observation_id, "active", now, now),
            )
            if not previous:
                kind, summary = "APPEARED", f"{detection.label} appeared near {zone}"
            elif previous.zone != zone:
                kind = "MOVED"
                summary = f"{detection.label} moved: {previous.zone} → {zone}"
                if row["status"] == "missing":
                    summary += " (rediscovered after invalidation)"
                if how.startswith("appearance"):
                    summary += f" [matched by appearance {how.split()[1]}]"
            else:
                kind, summary = "REOBSERVED", f"{detection.label} reobserved near {zone}"
            self.event(kind, summary, eid, previous.observation_id if previous else None, obs.observation_id)
            if detection.label == "person":
                self.event("PERSON_SEEN", f"Person observed near {zone}", eid, new=obs.observation_id)
        return obs

    # -------------------------------------------------------------- queries
    def entities(self, query=""):
        rows = self.db.execute("SELECT * FROM entities ORDER BY last_seen DESC").fetchall()
        result = []
        q = query.lower().strip()
        for r in rows:
            if q and q not in r["label"].lower() and query != r["id"]:
                continue
            o = self.observation(r["latest"])
            age = max(0, self.clock() - o.timestamp)
            confidence = o.confidence * math.exp(-age / DECAY_SECONDS) * (1 if r["status"] == "active" else 0.05)
            state = (
                "INVALIDATED"
                if r["status"] == "missing"
                else "KNOWN CURRENT"
                if age < 60 and confidence >= 0.7
                else "KNOWN BUT OLD"
                if age >= 60
                else "UNCERTAIN"
            )
            result.append(
                dict(r)
                | {
                    "observation": o.model_dump(exclude={"detection": {"embedding"}}),
                    "age_seconds": round(age, 1),
                    "effective_confidence": round(confidence, 3),
                    "knowledge_state": state,
                }
            )
        return result

    def find_best_match(self, query):
        results = self.entities(query)
        return max(results, key=lambda r: (r["status"] == "active", r["last_seen"])) if results else None

    get_last_seen = find_best_match

    def get_object_history(self, entity):
        return [
            json.loads(r[0])
            for r in self.db.execute(
                "SELECT data FROM observations WHERE entity_id=? ORDER BY timestamp", (entity,)
            )
        ]

    def invalidate(self, eid, reason="Target not observed after checking remembered zone"):
        row = self.db.execute("SELECT * FROM entities WHERE id=?", (eid,)).fetchone()
        if not row or row["status"] == "missing":
            return
        obs = self.observation(row["latest"])
        obs.status = "invalidated"
        with self.db:
            self.db.execute("UPDATE observations SET data=? WHERE id=?", (obs.model_dump_json(), obs.observation_id))
            self.db.execute('UPDATE entities SET status="missing" WHERE id=?', (eid,))
            self.event(
                "INVALIDATED",
                f"{obs.label}: previous location {obs.zone} invalidated. {reason}",
                eid,
                obs.observation_id,
            )
            self.event(
                "DISAPPEARED",
                f"{obs.label} was not observed near {obs.zone}; absence is not proof of removal",
                eid,
                obs.observation_id,
            )

    mark_entity_missing = invalidate
    mark_observation_stale = invalidate

    def checked(self, zone):
        with self.db:
            self.db.execute(
                "INSERT INTO regions VALUES(?,?) ON CONFLICT(zone) DO UPDATE SET checked=excluded.checked",
                (zone, self.clock()),
            )
            self.event("LOCATION_CHECKED", f"Checked {zone}")

    def regions_to_check(self, zones):
        seen = dict(self.db.execute("SELECT zone,checked FROM regions").fetchall())
        return sorted(zones, key=lambda z: seen.get(z, 0))

    def get_unexplored_or_stale_regions(self, zones, max_age=120):
        seen = dict(self.db.execute("SELECT zone,checked FROM regions").fetchall())
        now = self.clock()
        return [z for z in zones if now - seen.get(z, 0) > max_age]

    def changes(self, since=0):
        return [
            dict(r)
            for r in self.db.execute(
                "SELECT * FROM events WHERE timestamp>=? ORDER BY id DESC LIMIT 500", (since,)
            )
        ]

    def what_changed_since(self, since=0):
        """Human-readable diff of the world since `since` (Unix seconds), newest last."""
        interesting = {"MOVED", "APPEARED", "INVALIDATED", "DISAPPEARED"}
        return [e for e in reversed(self.changes(since)) if e["type"] in interesting]

    get_recent_changes = what_changed_since

    def observations_since(self, timestamp):
        return [
            json.loads(r[0])
            for r in self.db.execute(
                "SELECT data FROM observations WHERE timestamp>=? ORDER BY timestamp", (timestamp,)
            )
        ]

    def objects_near(self, pose, radius=1):
        return [
            r
            for r in self.entities()
            if math.hypot(r["observation"]["pose"]["x"] - pose.x, r["observation"]["pose"]["y"] - pose.y) <= radius
        ]
