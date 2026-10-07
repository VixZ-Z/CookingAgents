"""Anticipatory robot (TODO): same task as the reactive robot, but it
predicts the human's next action (model.py) and prefetches raw items so they
are on the shared counter in time. Wrong guesses clog the shared counter.
"""
from robot_base import RobotBase


class AnticipatoryRobot(RobotBase):
    def __init__(self, state):
        raise NotImplementedError("Anticipatory robot: not implemented yet")
