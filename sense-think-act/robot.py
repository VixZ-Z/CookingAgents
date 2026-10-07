"""The robot: ties sense, think and act together.

BDI mapping
  Beliefs    : HMM belief over the person's state + robot location.
  Desires    : help when needed, do not intrude, stay safe.
  Intention  : the current action; a Fetch lasts FETCH_STEPS and is not
               re-decided in between, so the robot does not flip-flop.
"""
import numpy as np

import config as C
from environment import Environment
from hmm import HMM
from human import Observation
from policy import Policy


class Robot:
    def __init__(self, env: Environment, hmm: HMM, policy: Policy,
                 use_belief: bool = True) -> None:
        self.env, self.hmm, self.policy = env, hmm, policy
        self.use_belief = use_belief   # False = observation-only baseline

    def step(self, obs: Observation) -> tuple:
        """One loop -> (belief, action, reward, safety_fired)."""
        belief = self.hmm.update(obs)                      # SENSE + THINK
        context = self.env.context()
        if context["fetch_left"] > 0:                      # intention
            action, fired = C.FETCH, False
        else:                                              # THINK
            if self.use_belief:
                action = self.policy.choose(belief, context)
            else:
                action = self.policy.choose_from_obs(obs, context)
            fired = self.policy.safety_fired
        reward, _ = self.env.apply(action)                 # ACT
        return np.asarray(belief), action, reward, fired
