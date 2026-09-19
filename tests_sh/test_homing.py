from signalhound.homing.strategies import IMPROVED, INCONCLUSIVE, WORSENED, HillClimb, compare


def test_compare_hysteresis():
    assert compare(-70, -66, 3, 3) == IMPROVED
    assert compare(-70, -74, 3, 3) == WORSENED
    assert compare(-70, -71, 3, 3) == INCONCLUSIVE
    assert compare(None, -60, 3, 3) == INCONCLUSIVE


def test_hillclimb_turns_after_worsening_and_alternates():
    h = HillClimb(patience=2)
    assert h.decide(IMPROVED) == "advance"
    assert h.decide(WORSENED) == "turn_left"
    assert h.decide(WORSENED) == "turn_left_big"  # keep sweeping the same way, harder
    assert h.decide(IMPROVED) == "advance"
    assert h.decide(INCONCLUSIVE) == "advance"
    assert h.decide(INCONCLUSIVE).startswith("turn")
