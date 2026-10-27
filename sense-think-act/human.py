"""The simulated elderly person: hidden state, fatigue and noisy signals.

step()    advances the hidden world (the robot never reads it).
observe() is the SENSE part: what the robot's person sensors report.
"""
from typing import Optional

import numpy as np

import config as C

Observation = Optional[dict]  # None means a sensor dropout


class Human:
    def __init__(self, seed: int = C.SEED) -> None:
        self.rng = np.random.default_rng(seed)
        self.t = 0
        self.state = C.COOKING
        self.fatigue = 0.0          # hidden, in [0, 1]
        self.zone = C.BOARD
        self.pot_on = False
        self.food_on_board = False  # an ingredient waiting to be chopped

    @property
    def cell(self) -> tuple:
        return C.LOCATIONS[C.ZONES[self.zone]]

    # ---------------------------------------------------------------- world
    def step(self) -> None:
        """Advance the hidden world by one time-step."""
        old_state = self.state
        self.state = int(self.rng.choice(3, p=self._transition_row()))
        self._update_fatigue()
        if self.state != old_state or self.rng.random() < C.ZONE_MOVE_PROB:
            self.zone = int(self.rng.choice(5, p=C.ZONE_PROBS[self.state]))
        self._update_kitchen()
        self.t += 1

    def _transition_row(self) -> np.ndarray:
        """P(next state | current state); the Cooking row uses fatigue."""
        if self.state == C.NEEDS_HELP:
            return C.T_NEEDS_HELP
        if self.state == C.RESTING:
            return C.T_RESTING
        to_help = C.T_COOKING_FRESH[1] + C.FATIGUE_TO_HELP * self.fatigue
        to_rest = C.T_COOKING_FRESH[2] + C.FATIGUE_TO_REST * self.fatigue
        return np.array([1 - to_help - to_rest, to_help, to_rest])

    def _update_fatigue(self) -> None:
        if self.state == C.COOKING:
            late = self.t >= C.ROUTINE_CHANGE_STEP
            self.fatigue += C.FATIGUE_GAIN_AFTER if late else C.FATIGUE_GAIN
        elif self.state == C.RESTING:
            self.fatigue -= C.FATIGUE_RECOVERY
        self.fatigue = float(np.clip(self.fatigue, 0.0, 1.0))

    def _update_kitchen(self) -> None:
        """The person uses the pot and the board while cooking.

        Food left on the board when they stop cooking stays there: that is
        the chopping job the robot may take over.
        """
        rng, cooking = self.rng, self.state == C.COOKING
        if self.pot_on:
            self.pot_on = rng.random() >= C.POT_OFF_PROB
        elif cooking:
            self.pot_on = rng.random() < C.POT_ON_PROB
        if cooking and self.food_on_board:
            self.food_on_board = rng.random() >= C.SELF_CHOP_PROB
        elif cooking:
            self.food_on_board = rng.random() < C.NEW_INGREDIENT_PROB

    # -------------------------------------------------- effects of the robot
    def receive_help(self) -> None:
        """The robot brought what was needed: back to cooking, less tired."""
        self.state = C.COOKING
        self.fatigue = max(0.0, self.fatigue - C.FATIGUE_RELIEF)

    def food_chopped(self) -> None:
        """The robot finished the ingredient on the board."""
        self.food_on_board = False
        self.fatigue = max(0.0, self.fatigue - C.FATIGUE_RELIEF)

    # ---------------------------------------------------------------- SENSE
    def observe(self) -> Observation:
        """Sample one noisy observation of the current hidden state."""
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
