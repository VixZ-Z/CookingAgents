"""THINK part 1: intent recognition with an HMM forward filter.

The belief b(s) = P(person is in state s | all observations so far).
Every step: predict with the transition matrix, then correct with the
observation likelihood (Bayes' rule).
"""
import numpy as np

import config as C
from human import Observation


class HMM:
    """Belief over the 3 hidden states, with online transition learning.

    adaptive=False keeps the prior transition matrix (static baseline).
    """

    def __init__(self, adaptive: bool = True) -> None:
        self.adaptive = adaptive
        self.prior_counts = C.PRIOR_STRENGTH * C.T_PRIOR
        self.counts = self.prior_counts.copy()
        self.belief = C.INITIAL_BELIEF.copy()

    @property
    def T(self) -> np.ndarray:
        """Current transition matrix: normalised counts (rows sum to 1)."""
        return self.counts / self.counts.sum(axis=1, keepdims=True)

    @staticmethod
    def likelihood(obs: dict) -> np.ndarray:
        """P(obs | s) for every state; the four signals are independent."""
        like = C.EMIT_ZONE[:, obs["zone"]].copy()
        for key, table in (("gesture", C.EMIT_GESTURE),
                           ("idle", C.EMIT_IDLE),
                           ("verbal", C.EMIT_VERBAL)):
            like *= table if obs[key] else 1.0 - table
        return like

    def update(self, obs: Observation) -> np.ndarray:
        """One forward step -> new belief."""
        prev = self.belief
        predicted = prev @ self.T
        if obs is None:                 # dropout: only predict, no correction
            self.belief = predicted
            return self.belief.copy()
        posterior = predicted * self.likelihood(obs)
        posterior /= posterior.sum()
        if self.adaptive:
            # outer(prev, posterior) is a soft count of the transition that
            # just happened (a one-step simplification of Baum-Welch).
            # Decay pulls old counts back toward the prior, so the model
            # forgets old routines but never drifts to extreme values.
            self.counts = (C.DECAY * self.counts
                           + (1 - C.DECAY) * self.prior_counts
                           + np.outer(prev, posterior))
        self.belief = posterior
        return self.belief.copy()
