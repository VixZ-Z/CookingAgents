"""Reactive robot (TODO): collaborative task on the near/far/mixed/swap maps.

Responds only to the current state: orders, shared-counter contents, what the
human carries. No learning, no prediction. It is the baseline.
"""
from robot_base import RobotBase


class ReactiveRobot(RobotBase):
    def __init__(self, state):
        raise NotImplementedError("Reactive robot: not implemented yet")
