"""ACT side: grid, robot position, action effects and reward."""
import config as C
from human import Human

Cell = tuple


def _dist(a: Cell, b: Cell) -> int:
    """Chebyshev distance between two cells."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


class Environment:
    """5x5 kitchen with a human and a robot, each in one cell."""

    def __init__(self, human: Human) -> None:
        self.human = human
        self.robot_cell: Cell = C.ROBOT_START
        self.fetch_left = 0        # steps left of the current Fetch
        self.confirmed = False     # person said "yes, help me"

    def context(self) -> dict:
        """What the robot knows about the world (smart stove, positions)."""
        stove_on = self.human.state in (C.COOKING, C.NEEDS_HELP)
        near = _dist(self.human.cell, C.STOVE_CELL) <= C.NEAR_STOVE_DIST
        return {
            "stove_on": stove_on,
            "human_near_stove": near,
            "hazard": stove_on and near,
            "confirmed": self.confirmed,
            "fetch_left": self.fetch_left,
            "human_cell": self.human.cell,
            "robot_cell": self.robot_cell,
        }

    def _move(self, toward: bool) -> None:
        """One step toward / away from the person (never onto them)."""
        r, c = self.robot_cell
        options = [(r + dr, c + dc)
                   for dr, dc in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))]
        options = [p for p in options
                   if 0 <= p[0] < C.GRID_SIZE and 0 <= p[1] < C.GRID_SIZE
                   and p != self.human.cell]
        pick = min if toward else max
        self.robot_cell = pick(options,
                               key=lambda p: _dist(p, self.human.cell))

    def apply(self, action: int) -> tuple:
        """Execute the action -> (reward, new_context)."""
        s = self.human.state
        hazard = self.context()["hazard"]
        reward = float(C.REWARD[s, action])

        if action == C.FETCH:
            if self.fetch_left == 0:               # a new Fetch begins
                self.fetch_left = C.FETCH_STEPS
                if hazard and not self.confirmed:  # autonomous = unsafe
                    reward += C.STOVE_PENALTY
            else:                                  # continuing: cost only
                reward = -C.ACTION_COST
            self.fetch_left -= 1
            if self.fetch_left == 0:               # Fetch completed
                if s == C.NEEDS_HELP:
                    self.human.receive_help()
                self.confirmed = False
            self._move(toward=True)
        else:
            self.fetch_left = 0
            # Asking a person who needs help yields a "yes".
            self.confirmed = (action == C.ASK and s == C.NEEDS_HELP)
            if action == C.ASK:
                self._move(toward=True)
            elif action == C.KEEP_DISTANCE:
                self._move(toward=False)
        return reward, self.context()
