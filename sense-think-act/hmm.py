"""THINK part 1: HMM forward filter with online transition adaptation."""
import numpy as np

import config as C
from human import Observation


class HMM:
    """Belief over the 3 hidden states, updated from noisy observations.

    adaptive=False keeps the transition matrix fixed (static baseline).
    """

    def __init__(self, adaptive: bool = True) -> None:
        self.adaptive = adaptive
        self.prior_counts = C.PRIOR_STRENGTH * C.T_PRIOR
        self.counts = self.prior_counts.copy()
        self.belief = C.INITIAL_BELIEF.copy()

    @property
    def T(self) -> np.ndarray:
        """Current transition matrix (rows sum to 1)."""
        return self.counts / self.counts.sum(axis=1, keepdims=True)

    @staticmethod
    def likelihood(obs: dict) -> np.ndarray:
        """P(obs | state) for the 3 states; features are independent."""
        like = C.EMIT_POS[:, obs["zone"]].copy()
        for key, table in (("gesture", C.EMIT_GESTURE),
                           ("idle", C.EMIT_IDLE),
                           ("verbal", C.EMIT_VERBAL)):
            like *= table if obs[key] else 1.0 - table
        return like

    def update(self, obs: Observation) -> np.ndarray:
        """Forward step: predict with T, correct with the observation."""
        prev = self.belief
        predicted = prev @ self.T
        if obs is None:                      # dropout: prediction only
            self.belief = predicted
            return self.belief.copy()
        posterior = predicted * self.likelihood(obs)
        posterior /= posterior.sum()
        if self.adaptive:
            # Soft transition counts: outer(prev, posterior) approximates
            # the expected transitions (a simplification of Baum-Welch).
            # Decay pulls old evidence back to the prior, so the matrix
            # forgets old routines but never drifts to extreme values.
            self.counts = (C.DECAY * self.counts
                           + (1 - C.DECAY) * self.prior_counts
                           + np.outer(prev, posterior))
        self.belief = posterior
        return self.belief.copy()
