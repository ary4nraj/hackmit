import pytest

from recall_rover.memory.models import Detection, Pose
from recall_rover.memory.repository import Memory


def test_freshness_missing_and_history():
    now = [1000.0]
    m = Memory(clock=lambda: now[0])
    a = m.remember_observation(
        Detection(label="bottle", identity="tag1", confidence=0.95), Pose(), "table"
    )
    assert m.find_best_match("bottle")["knowledge_state"] == "KNOWN CURRENT"
    now[0] += 600
    assert m.find_best_match("bottle")["effective_confidence"] < 0.2
    assert m.find_best_match("bottle")["knowledge_state"] == "KNOWN BUT OLD"
    m.invalidate(a.entity_id)
    assert m.find_best_match("bottle")["knowledge_state"] == "INVALIDATED"
    assert m.get_object_history(a.entity_id)[0]["status"] == "invalidated"
    assert not m.find_best_match("unseen")
    m.close()


def test_conservative_association_and_throttle():
    m = Memory()
    d = Detection(label="backpack", confidence=0.8, bbox=[0, 0, 10, 10])
    a = m.remember_observation(d, Pose(), "A")
    b = m.remember_observation(d, Pose(), "B")
    assert a.entity_id != b.entity_id  # same category is not proof of relocation
    c = m.remember_observation(d, Pose(), "A")
    assert c.observation_id == a.observation_id
    distinct = m.remember_observation(
        Detection(label="backpack", confidence=0.9, bbox=[30, 30, 40, 40]), Pose(), "A"
    )
    assert distinct.entity_id != a.entity_id
    assert not any(e["type"] == "MOVED" for e in m.changes())
    m.close()


def test_identity_cannot_change_class():
    m = Memory()
    m.remember_observation(
        Detection(label="bottle", identity="1", confidence=1), Pose(), "A"
    )
    with pytest.raises(ValueError):
        m.remember_observation(
            Detection(label="person", identity="1", confidence=1), Pose(), "A"
        )
    m.close()


def test_multiple_same_class_objects_remain_distinct_across_frames():
    now = [1000.0]
    m = Memory(clock=lambda: now[0])
    a = Detection(label="person", confidence=0.9, bbox=[0, 0, 10, 10])
    b = Detection(label="person", confidence=0.9, bbox=[30, 30, 40, 40])
    first = m.remember_observation(a, Pose(), "A")
    second = m.remember_observation(b, Pose(), "A")
    now[0] += 2
    assert m.remember_observation(a, Pose(), "A").entity_id == first.entity_id
    assert m.remember_observation(b, Pose(), "A").entity_id == second.entity_id
    assert len(m.entities()) == 2
    m.close()
