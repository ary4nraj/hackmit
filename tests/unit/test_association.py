"""Appearance-based association: same-looking object across zones is one entity; different ones are not."""

from recall_rover.memory.models import Detection, Pose
from recall_rover.memory.repository import Memory
from recall_rover.perception.embeddings import similarity


def sig(kind):
    base = [0.0] * 128
    if kind == "black":
        base[0] = 0.9
        base[1] = 0.1
    elif kind == "red":
        base[100] = 0.8
        base[101] = 0.2
    elif kind == "near-black":
        base[0] = 0.85
        base[1] = 0.12
        base[5] = 0.03
    return base


def test_similarity_bounds():
    assert similarity(sig("black"), sig("black")) > 0.999
    assert similarity(sig("black"), sig("red")) < 0.1
    assert similarity(sig("black"), sig("near-black")) > 0.95
    assert similarity(None, sig("red")) == 0.0


def test_same_appearance_across_zones_becomes_moved():
    now = [1000.0]
    m = Memory(clock=lambda: now[0])
    a = m.remember_observation(
        Detection(label="backpack", confidence=0.9, bbox=[0, 0, 50, 50], embedding=sig("black")), Pose(), "entrance table"
    )
    now[0] += 120  # long after the IoU window
    b = m.remember_observation(
        Detection(label="backpack", confidence=0.88, bbox=[400, 200, 460, 260], embedding=sig("near-black")),
        Pose(x=1, y=1),
        "back wall",
    )
    assert a.entity_id == b.entity_id
    moved = [e for e in m.changes() if e["type"] == "MOVED"]
    assert moved and "entrance table → back wall" in moved[0]["summary"]
    assert "appearance" in moved[0]["summary"]
    assert m.find_best_match("backpack")["observation"]["zone"] == "back wall"
    m.close()


def test_different_appearance_stays_distinct():
    m = Memory()
    a = m.remember_observation(
        Detection(label="backpack", confidence=0.9, bbox=[0, 0, 50, 50], embedding=sig("black")), Pose(), "entrance table"
    )
    b = m.remember_observation(
        Detection(label="backpack", confidence=0.9, bbox=[300, 0, 350, 50], embedding=sig("red")), Pose(), "back wall"
    )
    assert a.entity_id != b.entity_id
    assert not any(e["type"] == "MOVED" for e in m.changes())
    assert len(m.entities("backpack")) == 2
    m.close()


def test_ambiguous_lookalikes_do_not_merge():
    """Two look-alike backpacks seen in one frame stay distinct; a later sighting refuses to guess."""
    now = [1000.0]
    m = Memory(clock=lambda: now[0])
    a = m.remember_observation(
        Detection(label="backpack", confidence=0.9, bbox=[0, 0, 50, 50], embedding=sig("black")),
        Pose(),
        "entrance table",
        frame_id="frame-1",
    )
    b = m.remember_observation(
        Detection(label="backpack", confidence=0.9, bbox=[200, 0, 250, 50], embedding=sig("near-black")),
        Pose(),
        "entrance table",
        frame_id="frame-1",
    )
    assert a.entity_id != b.entity_id  # both visible in one frame at different boxes
    now[0] += 10
    c = m.remember_observation(
        Detection(label="backpack", confidence=0.9, bbox=[400, 0, 450, 50], embedding=sig("black")), Pose(), "back wall"
    )
    # Best match 1.0 vs ~0.999: margin below 0.05, so no MOVED is claimed for either candidate.
    assert c.entity_id not in {a.entity_id, b.entity_id}
    assert len(m.entities("backpack")) == 3
    assert not any(e["type"] == "MOVED" for e in m.changes())
    m.close()


def test_rediscovery_after_invalidation_relinks_entity():
    now = [1000.0]
    m = Memory(clock=lambda: now[0])
    a = m.remember_observation(
        Detection(label="bottle", confidence=0.9, bbox=[0, 0, 30, 60], embedding=sig("red")), Pose(), "left side"
    )
    m.invalidate(a.entity_id)
    assert m.find_best_match("bottle")["knowledge_state"] == "INVALIDATED"
    now[0] += 5
    b = m.remember_observation(
        Detection(label="bottle", confidence=0.9, bbox=[500, 0, 530, 60], embedding=sig("red")), Pose(), "entrance"
    )
    assert b.entity_id == a.entity_id
    best = m.find_best_match("bottle")
    assert best["status"] == "active" and best["observation"]["zone"] == "entrance"
    kinds = [e["type"] for e in reversed(m.changes())]
    assert kinds.index("INVALIDATED") < kinds.index("MOVED")
    assert "rediscovered" in [e for e in m.changes() if e["type"] == "MOVED"][0]["summary"]
    assert m.what_changed_since(0)[-1]["type"] == "MOVED"
    m.close()


def test_one_object_does_not_fragment_across_frames():
    """A person shifting in view over several frames stays one entity (no ambiguity cascade)."""
    now = [1000.0]
    m = Memory(clock=lambda: now[0])
    ids = set()
    for i in range(6):
        now[0] += 2
        x = 100 + i * 40  # drifts across the frame; boxes may stop overlapping
        obs = m.remember_observation(
            Detection(label="person", confidence=0.6 + 0.05 * i, bbox=[x, 50, x + 120, 400], embedding=sig("black")),
            Pose(),
            "camera center",
            frame_id=f"f{i}",
        )
        ids.add(obs.entity_id)
    assert len(ids) == 1
    assert len(m.entities("person")) == 1
    assert not any(e["type"] == "MOVED" for e in m.changes())
    m.close()


def test_ambiguous_cross_zone_lookalikes_never_fabricate_a_move():
    now = [1000.0]
    m = Memory(clock=lambda: now[0])
    a = m.remember_observation(
        Detection(label="backpack", confidence=0.9, bbox=[0, 0, 50, 50], embedding=sig("black")), Pose(), "entrance table", frame_id="f1"
    )
    # Two look-alikes in one wide view (same frame): distinct objects in different zones.
    b = m.remember_observation(
        Detection(label="backpack", confidence=0.9, bbox=[300, 0, 350, 50], embedding=sig("near-black")), Pose(), "left side", frame_id="f1"
    )
    now[0] += 10
    c = m.remember_observation(
        Detection(label="backpack", confidence=0.9, bbox=[0, 0, 50, 50], embedding=sig("black")), Pose(), "back wall", frame_id="f3"
    )
    assert c.entity_id not in {a.entity_id, b.entity_id}
    assert not any(e["type"] == "MOVED" for e in m.changes())
    m.close()
