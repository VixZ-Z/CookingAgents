"""Overcooked-style colours for matplotlib (RGB 0-1).

Copied from overcookedAI/render.py palette; no pygame dependency.
"""


def _rgb(r: int, g: int, b: int) -> tuple:
    return (r / 255.0, g / 255.0, b / 255.0)


FLOOR = _rgb(211, 199, 176)
GRID = _rgb(190, 178, 155)
WHITE = _rgb(245, 245, 245)
DARK = _rgb(35, 35, 35)
ORANGE = _rgb(235, 130, 55)
YELLOW = _rgb(240, 210, 70)
RED = _rgb(210, 60, 55)

# Agent colours match Overcooked OWNER_EDGE
HUMAN = _rgb(90, 150, 235)
ROBOT = _rgb(55, 205, 210)

# Station fills. Board matches Overcooked's chopping station.
BOARD = _rgb(40, 88, 65)
BOARD_TOP = _rgb(190, 150, 100)
STATION = {
    "Fridge": _rgb(120, 82, 55),
    "Pot": _rgb(48, 66, 100),
    "Board": BOARD,
    "Table": _rgb(52, 99, 41),
    "Chair": _rgb(66, 91, 107),
}
STATION_EDGE = _rgb(75, 50, 34)

# Belief / true-state colours (Cooking, NeedsHelp, Resting)
STATE = [_rgb(80, 180, 90), RED, HUMAN]
