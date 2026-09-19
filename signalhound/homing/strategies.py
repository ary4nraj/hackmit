"""Decision rules. Pure functions over numbers so they are trivially testable.

RSSI convention: larger (less negative) = stronger.
Key insight from simulation: a single short step changes RSSI by well under the noise floor at
range, so the controller compares against the RSSI at the last DECISION point (reference), not
the previous step. Gains accumulate along a heading; only a clear loss or a run of no-gain steps
triggers a turn. Turns keep the same direction so the robot sweeps headings instead of oscillating.
"""

IMPROVED, WORSENED, INCONCLUSIVE = "IMPROVED", "WORSENED", "INCONCLUSIVE"


def compare(reference, current, improve_db, worsen_db):
    if reference is None or current is None:
        return INCONCLUSIVE
    delta = current - reference
    if delta >= improve_db:
        return IMPROVED
    if delta <= -worsen_db:
        return WORSENED
    return INCONCLUSIVE


class HillClimb:
    def __init__(self, patience=3, sweep_limit=6, trend_db=1.5):
        self.patience = patience          # no-gain steps along a heading before turning
        self.sweep_limit = sweep_limit    # turns in one direction before flipping the sweep
        self.trend_db = trend_db          # a gain this big (below the hard threshold) still counts as "getting warmer"
        self.turn_dir = 1                 # +1 left / -1 right
        self.inconclusive = 0
        self.turns_in_a_row = 0

    def _turn(self):
        self.inconclusive = 0
        self.turns_in_a_row += 1
        if self.turns_in_a_row > self.sweep_limit:
            self.turn_dir = -self.turn_dir
            self.turns_in_a_row = 1
        big = self.turns_in_a_row >= 2
        return ("turn_left" if self.turn_dir > 0 else "turn_right") + ("_big" if big else "")

    def next_turn(self):
        return self.turn_dir

    def decide(self, verdict, delta=None):
        """'advance' | 'turn_left[_big]' | 'turn_right[_big]'.

        `delta` = current - reference (dB). The trend is judged only every `patience` steps so
        single noisy readings cannot keep a bad heading alive or kill a good one.
        """
        if verdict == IMPROVED:
            self.inconclusive = 0
            self.turns_in_a_row = 0
            return "advance"
        if verdict == WORSENED:
            return self._turn()
        self.inconclusive += 1
        if self.inconclusive >= self.patience:
            self.inconclusive = 0
            if delta is not None and delta >= self.trend_db:
                self.turns_in_a_row = 0
                return "advance"     # getting warmer over the last few steps: keep the heading
            return self._turn()
        return "advance"
