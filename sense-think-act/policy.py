"""THINK part 2: decision making.

1. Value iteration solves a small MDP over the hidden states -> Q[s, a].
2. QMDP acts on the belief: choose argmax_a  sum_s b(s) Q(s, a).
3. A hard safety rule can override the choice (it is not learned).
"""
import numpy as np

import config as C


def value_iteration(tol: float = 1e-6) -> np.ndarray:
    """Solve the MDP as if the state were known -> Q[s, a]."""
    # P[a, s, s']: every action follows the prior routine, except that a
    # Fetch usually ends NeedsHelp.
    P = np.stack([C.T_PRIOR] * len(C.ACTIONS))
    P[C.FETCH, C.NEEDS_HELP] = C.T_AFTER_FETCH
    V = np.zeros(len(C.STATES))
    while True:
        Q = C.REWARD + C.GAMMA * np.einsum("ast,t->sa", P, V)
        if np.abs(Q.max(axis=1) - V).max() < tol:
            return Q
        V = Q.max(axis=1)


class Policy:
    def __init__(self, safety: bool = C.SAFETY_RULE) -> None:
        self.Q = value_iteration()
        self.safety = safety

    def choose(self, belief: np.ndarray, context: dict) -> tuple:
        """QMDP choice -> (action, safety_fired)."""
        if context["confirmed"]:        # the person just said "yes, please"
            return self._safe(C.FETCH, context)
        scores = belief @ self.Q
        if not context["food_on_board"]:
            scores[C.CHOP] = -np.inf    # nothing to chop
        return self._safe(int(np.argmax(scores)), context)

    def choose_from_obs(self, obs, context: dict) -> tuple:
        """Baseline without a belief: hand-written rules on the raw signals."""
        action = C.WAIT
        if context["confirmed"]:
            action = C.FETCH
        elif obs is not None:
            if obs["verbal"] or (obs["gesture"] and obs["idle"]):
                action = C.FETCH
            elif obs["gesture"]:
                action = C.ASK
            elif context["food_on_board"] and obs["zone"] == C.CHAIR:
                action = C.CHOP
        return self._safe(action, context)

    def _safe(self, action: int, context: dict) -> tuple:
        """Safety rule: no autonomous Fetch while the person is at a hot pot.

        The robot cannot move freely around someone handling a hot pot, so
        it asks first; after a "yes" the person expects it and Fetch is
        allowed.
        """
        unsafe = (action == C.FETCH and context["pot_on"]
                  and context["person_near_pot"] and not context["confirmed"])
        if self.safety and unsafe:
            return C.ASK, True
        return action, False
