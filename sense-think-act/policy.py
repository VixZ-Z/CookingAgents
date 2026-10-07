"""THINK part 2: MDP value iteration, QMDP action choice, safety rule."""
import numpy as np

import config as C


def build_transitions() -> np.ndarray:
    """P[a, s, s'] used by the MDP: same dynamics except Fetch helps."""
    P = np.stack([C.T_PRIOR.copy() for _ in C.ACTIONS])
    P[C.FETCH, C.NEEDS_HELP] = C.T_FETCH_FROM_NEEDS_HELP
    return P


def value_iteration(tol: float = 1e-6, max_iter: int = 1000) -> np.ndarray:
    """Solve the MDP over hidden states -> Q[s, a]."""
    P = build_transitions()
    V = np.zeros(len(C.STATES))
    for _ in range(max_iter):
        Q = C.REWARD + C.GAMMA * np.einsum("ast,t->sa", P, V)
        V_new = Q.max(axis=1)
        if np.abs(V_new - V).max() < tol:
            break
        V = V_new
    return Q


class Policy:
    """QMDP: act on the belief with Q[s, a] solved as if s were known."""

    def __init__(self) -> None:
        self.Q = value_iteration()
        self.safety_fired = False

    def choose(self, belief: np.ndarray, context: dict) -> int:
        """Pick argmax_a sum_s b(s) Q(s, a), then apply the safety rule."""
        action = int(np.argmax(belief @ self.Q))
        return self._safety(action, context)

    def choose_from_obs(self, obs, context: dict) -> int:
        """Baseline: react to the raw observation only (no belief)."""
        action = C.WAIT
        if obs is not None:
            if obs["verbal"] or (obs["gesture"] and obs["idle"]):
                action = C.FETCH
            elif obs["idle"] and obs["zone"] == C.ZONES.index("Chair"):
                action = C.KEEP_DISTANCE
        return self._safety(action, context)

    def _safety(self, action: int, context: dict) -> int:
        """Hard rule, outside the learned policy.

        Never fetch autonomously while the stove is on and the person is
        next to it, unless the person has confirmed they want help: ask.
        """
        self.safety_fired = False
        if (C.SAFETY_RULE and action == C.FETCH and context["hazard"]
                and not context["confirmed"]):
            self.safety_fired = True
            return C.ASK
        return action
