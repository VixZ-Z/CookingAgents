"""Common interface for every robot (scripted, reactive, anticipatory)."""
from __future__ import annotations

from game import Player


class RobotBase(Player):
    enabled = True
    status = ""

    def update_ai(self, dt: float, state) -> None:
        """Advance the robot by dt seconds given the full GameState."""
        raise NotImplementedError
