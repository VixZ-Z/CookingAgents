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
        self.chop_left = 0         # steps left of the current Chop
        self.confirmed = False     # person said "yes, help me"

    def context(self) -> dict:
        """What the robot knows about the world (smart pot, positions)."""
        pot_on = self.human.state in (C.COOKING, C.NEEDS_HELP)
        near = _dist(self.human.cell, C.POT_CELL) <= C.NEAR_POT_DIST
        return {
            "pot_on": pot_on,
            "human_near_pot": near,
            "hazard": pot_on and near,
            "confirmed": self.confirmed,
            "fetch_left": self.fetch_left,
            "chop_left": self.chop_left,
            "food_on_board": self.human.food_on_board,
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

    def _keep_distance(self) -> None:
        """Step away only while closer than KEEP_DISTANCE_CELLS.

        One cell of space is enough comfort; do not flee across the grid.
        """
        if _dist(self.robot_cell, self.human.cell) <= C.KEEP_DISTANCE_CELLS:
            self._move(toward=False)

    def _approach(self) -> None:
        """Move closer for Ask/Fetch, but stop once adjacent (1 cell)."""
        if _dist(self.robot_cell, self.human.cell) > C.KEEP_DISTANCE_CELLS:
            self._move(toward=True)

    def _place(self, target: Cell) -> None:
        """Stand on a station for the whole task (fetch or chop).

        If the person is already on that cell, stand in an adjacent free
        cell so both stay visible next to the station.
        """
        if target != self.human.cell:
            self.robot_cell = target
            return
        r, c = target
        options = [(r + dr, c + dc)
                   for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        options = [p for p in options
                   if 0 <= p[0] < C.GRID_SIZE and 0 <= p[1] < C.GRID_SIZE
                   and p != self.human.cell]
        self.robot_cell = min(options, key=lambda p: _dist(p, target))

    def apply(self, action: int) -> tuple:
        """Execute the action -> (reward, new_context)."""
        s = self.human.state
        hazard = self.context()["hazard"]
        reward = float(C.REWARD[s, action])

        if action == C.FETCH:
            if self.fetch_left == 0:               # a new Fetch begins
                self.fetch_left = C.FETCH_STEPS
                if hazard and not self.confirmed:  # autonomous = unsafe
                    reward += C.POT_PENALTY
            else:                                  # continuing: cost only
                reward = -C.ACTION_COST
            self.fetch_left -= 1
            if self.fetch_left == 0:               # Fetch completed
                if s == C.NEEDS_HELP:
                    self.human.receive_help()
                self.confirmed = False
            self._place(C.FRIDGE_CELL)
            self.chop_left = 0
        elif action == C.CHOP:
            self.fetch_left = 0
            if self.chop_left == 0:
                self.chop_left = C.CHOP_STEPS
                if self.human.food_on_board:
                    reward = C.CHOP_HELP_REWARD
            else:
                reward = -C.ACTION_COST
            self.chop_left -= 1
            self._place(C.BOARD_CELL)
            if self.chop_left == 0 and self.human.food_on_board:
                self.human.food_chopped()
        else:
            self.fetch_left = 0
            self.chop_left = 0
            # Asking a person who needs help yields a "yes".
            self.confirmed = (action == C.ASK and s == C.NEEDS_HELP)
            if action == C.ASK:
                self._approach()
            elif action == C.KEEP_DISTANCE:
                self._keep_distance()
        return reward, self.context()
