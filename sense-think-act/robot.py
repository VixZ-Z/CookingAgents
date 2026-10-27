"""The robot's THINK step, organised as a small BDI agent.

  Beliefs    : the HMM belief over the person's state (hmm.py) plus the
               reliable readings in `context` (pot, board, own task).
  Desires    : help when needed, do not intrude, never be unsafe. They are
               encoded in the MDP reward table and the safety rule.
  Intentions : the chosen action. Fetch and Chop take several steps and
               are finished before anything new is decided, so the robot
               does not flip-flop on every noisy observation.
"""
import config as C
from hmm import HMM
from human import Observation
from policy import Policy


class Robot:
    def __init__(self, adaptive: bool = True, use_belief: bool = True,
                 safety: bool = C.SAFETY_RULE) -> None:
        self.hmm = HMM(adaptive)
        self.policy = Policy(safety)
        self.use_belief = use_belief   # False = observation-only baseline
        self.belief = self.hmm.belief
        self.safety_fired = False

    def think(self, obs: Observation, context: dict) -> int:
        """Update the belief, then keep or choose an intention -> action."""
        self.belief = self.hmm.update(obs)
        self.safety_fired = False
        if context["task_left"] > 0:            # committed: finish the task
            return context["task"]
        if self.use_belief:
            action, self.safety_fired = self.policy.choose(self.belief,
                                                           context)
        else:
            action, self.safety_fired = self.policy.choose_from_obs(obs,
                                                                    context)
        return action
