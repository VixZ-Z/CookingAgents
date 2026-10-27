"""The kitchen world: robot sensors (sense) and action effects (act)."""
import config as C
from human import Human, Observation

Cell = tuple
ALL_CELLS = [(r, c) for r in range(C.GRID_SIZE) for c in range(C.GRID_SIZE)]


def dist(a: Cell, b: Cell) -> int:
    """Chebyshev distance: 1 means the two cells touch."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


class Environment:
    def __init__(self, human: Human) -> None:
        self.human = human
        self.robot_cell: Cell = C.ROBOT_START
        self.task = C.WAIT        # the action currently being executed
        self.task_left = 0        # steps left of a multi-step action
        self.confirmed = False    # the person answered "yes" to Ask
        self.unsafe = False       # last action was a Fetch at a hot pot

    # ---------------------------------------------------------------- SENSE
    def sense(self, obs: Observation) -> dict:
        """Robot-side readings that do not reveal the person's intent.

        Pot and board state come from a smart stove and a board camera,
        so they are reliable. Whether the person is near the pot is taken
        from the noisy zone observation; during a dropout the robot
        assumes the worst (near the pot).
        """
        return {
            "pot_on": self.human.pot_on,
            "food_on_board": self.human.food_on_board,
            "person_near_pot": obs is None or obs["zone"] == C.POT,
            "confirmed": self.confirmed,
            "task": self.task,
            "task_left": self.task_left,
        }

    # ------------------------------------------------------------------ ACT
    def apply(self, action: int) -> float:
        """Execute one step of the action -> reward of this step."""
        human, state = self.human, self.human.state
        reward, self.unsafe = 0.0, False
        if self.task_left == 0:                 # a new action starts
            self.task = action
            self.task_left = C.DURATION.get(action, 1)
            reward = self._reward(state, action)
        self.task_left -= 1
        done = self.task_left == 0

        if action == C.FETCH:
            if not done:                        # step 1: get the item
                self._go_next_to(C.LOCATIONS["Fridge"])
            else:                               # step 2: hand it over
                self._go_next_to(human.cell)
                if state == C.NEEDS_HELP:
                    human.receive_help()
                self.confirmed = False
        elif action == C.CHOP:
            self._go_next_to(C.LOCATIONS["Board"])
            if done and human.food_on_board:
                human.food_chopped()
        elif action == C.ASK:
            self._step(toward=True)
            self.confirmed = state == C.NEEDS_HELP  # they answer "yes"
        elif dist(self.robot_cell, human.cell) <= C.PERSONAL_SPACE:
            self._step(toward=False)            # Wait: give them space
        if action not in (C.ASK, C.FETCH):
            self.confirmed = False
        return reward

    def _reward(self, state: int, action: int) -> float:
        """R[state, action], plus a large penalty for an unsafe Fetch."""
        self.unsafe = (action == C.FETCH and self.human.pot_on
                       and self.human.zone == C.POT and not self.confirmed)
        return float(C.REWARD[state, action]) + C.POT_PENALTY * self.unsafe

    # ------------------------------------------------------------- movement
    def _step(self, toward: bool) -> None:
        """Move one cell toward / away from the person; never onto them.

        Approaching stops once adjacent, so Ask respects personal space.
        """
        here, person = self.robot_cell, self.human.cell
        if toward and dist(here, person) <= C.PERSONAL_SPACE:
            return
        options = [c for c in ALL_CELLS if dist(c, here) <= 1 and c != person]
        pick = min if toward else max
        self.robot_cell = pick(options, key=lambda c: dist(c, person))

    def _go_next_to(self, target: Cell) -> None:
        """Stand on the target cell, or as close as possible if occupied."""
        free = [c for c in ALL_CELLS if c != self.human.cell]
        self.robot_cell = min(free, key=lambda c: dist(c, target))
