"""Hidden human state, fatigue and the noisy observation model (SENSE)."""
from typing import Optional

import numpy as np

import config as C

Observation = Optional[dict]  # None means a sensor dropout


class Human:
    """Simulated elderly person. The robot never reads this state."""

    def __init__(self, seed: int = C.SEED) -> None:
        self.rng = np.random.default_rng(seed)
        self.t = 0
        self.state = C.COOKING
        self.fatigue = 0.0
        self.zone = C.ZONES.index("Counter")

    @property
    def cell(self) -> tuple:
        """Grid cell of the person (derived from the current zone)."""
        return C.LOCATIONS[C.ZONES[self.zone]]

    def _transition_row(self) -> np.ndarray:
        """Row of the true transition matrix, depending on fatigue."""
        if self.state == C.NEEDS_HELP:
            return C.T_NEEDS_HELP
        if self.state == C.RESTING:
            return C.T_RESTING
        to_help = C.T_BASE_COOKING[1] + C.FATIGUE_TO_HELP * self.fatigue
        to_rest = C.T_BASE_COOKING[2] + C.FATIGUE_TO_REST * self.fatigue
        return np.array([1 - to_help - to_rest, to_help, to_rest])

    def _update_fatigue(self) -> None:
        if self.state == C.COOKING:
            changed = self.t >= C.ROUTINE_CHANGE_STEP
            gain = C.FATIGUE_GAIN_AFTER if changed else C.FATIGUE_GAIN
            self.fatigue += gain
        elif self.state == C.RESTING:
            self.fatigue -= C.FATIGUE_RECOVERY
        self.fatigue = float(np.clip(self.fatigue, 0.0, 1.0))

    def receive_help(self) -> None:
        """The robot fetched what was needed: back to cooking, less tired."""
        self.state = C.COOKING
        self.fatigue = max(0.0, self.fatigue - C.FATIGUE_RELIEF)

    def _observe(self) -> Observation:
        """Sample a noisy observation of the current state."""
        rng, s = self.rng, self.state
        if rng.random() < C.P_DROPOUT:
            return None
        zone = self.zone
        if rng.random() < C.POS_ERR:
            zone = int(rng.choice([z for z in range(5) if z != self.zone]))
        return {
            "zone": zone,
            "gesture": int(rng.random() < C.EMIT_GESTURE[s]),
            "idle": int(rng.random() < C.EMIT_IDLE[s]),
            "verbal": int(rng.random() < C.EMIT_VERBAL[s]),
        }

    def step(self) -> tuple:
        """Advance one time-step -> (true_state, observation)."""
        old_state = self.state
        self.state = int(self.rng.choice(3, p=self._transition_row()))
        self._update_fatigue()
        moved = self.rng.random() < C.ZONE_MOVE_PROB
        if self.state != old_state or moved:
            self.zone = int(self.rng.choice(5, p=C.ZONE_PROBS[self.state]))
        self.t += 1
        return self.state, self._observe()
