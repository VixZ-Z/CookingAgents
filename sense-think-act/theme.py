"""Overcooked-style colours for matplotlib (RGB 0-1).

Copied from overcookedAI/render.py palette; no pygame dependency.
Also draws the shared kitchen grid used by animate.py / visualize.py.
"""
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle

import config as C


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


def agent_xy(cell: tuple, other: tuple | None,
             side: float = 0.0) -> tuple:
    """Plot (x, y). Agents stand in the lower half of the cell so the
    station furniture (drawn in the upper half) stays readable. When both
    share a cell they sit left/right of centre."""
    row, col = cell
    x, y = float(col), float(row) + 0.18
    if other is not None and cell == other:
        x += side
    return x, y


def draw_kitchen(ax, row: dict) -> tuple:
    """Floor, stations (top of cell), then person and robot on top.

    Returns the robot's plot position, so callers can add a speech bubble.
    """
    n = C.GRID_SIZE
    ax.set_xlim(-0.5, n - 0.5)
    ax.set_ylim(n - 0.5, -0.5)
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_aspect("equal")
    ax.set_facecolor(FLOOR)
    ax.add_patch(Rectangle((-0.5, -0.5), n, n, facecolor=FLOOR,
                           edgecolor="none", zorder=0))
    for i in range(n + 1):
        ax.axhline(i - 0.5, color=GRID, lw=0.8, zorder=0.5)
        ax.axvline(i - 0.5, color=GRID, lw=0.8, zorder=0.5)

    pot_on = row["pot_on"]
    robot_cell = tuple(row["robot_cell"])
    for name, (r, c) in C.LOCATIONS.items():
        hot = name == "Pot" and pot_on
        face = ORANGE if hot else STATION[name]
        # Furniture only in the top strip of the cell (agents stand below).
        ax.add_patch(FancyBboxPatch(
            (c - 0.42, r - 0.45), 0.84, 0.38,
            boxstyle="round,pad=0.01,rounding_size=0.08",
            facecolor=face, edgecolor=STATION_EDGE, linewidth=1.5,
            zorder=1))
        label = name + (" ON" if hot else "")
        ax.text(c, r - 0.28, label, ha="center", va="center", fontsize=7,
                color=WHITE, weight="bold", zorder=2)
        if name == "Board":
            ax.add_patch(Rectangle((c - 0.22, r - 0.18), 0.44, 0.12,
                                   facecolor=BOARD_TOP, zorder=2))
            if row["food_on_board"] or row["action"] == "Chop":
                ax.add_patch(Circle((c + 0.22, r - 0.12), 0.07,
                                    facecolor=RED, zorder=3))
            if row["action"] == "Chop" and row["task_left"]:
                done = 1 - row["task_left"] / C.DURATION[C.CHOP]
                ax.add_patch(Rectangle((c - 0.3, r - 0.02), 0.6 * done, 0.06,
                                       facecolor=YELLOW, zorder=3))
        # Highlight the station the robot is currently using.
        if robot_cell == (r, c):
            ax.add_patch(Rectangle(
                (c - 0.48, r - 0.48), 0.96, 0.96, fill=False,
                edgecolor=ROBOT, linewidth=2.5, linestyle="--", zorder=4))

    human_cell = tuple(row["human_cell"])
    hc, hr = agent_xy(human_cell, None)
    rc, rr = agent_xy(robot_cell, human_cell, side=0.28)
    if robot_cell == human_cell:
        hc, hr = agent_xy(human_cell, robot_cell, side=-0.28)

    ax.add_patch(Circle((hc, hr), 0.28, facecolor=HUMAN, edgecolor=DARK,
                        linewidth=2, zorder=8))
    ax.text(hc, hr, "P", ha="center", va="center", color=WHITE,
            weight="bold", zorder=9, fontsize=10)
    ax.add_patch(FancyBboxPatch(
        (rc - 0.26, rr - 0.26), 0.52, 0.52,
        boxstyle="round,pad=0.01,rounding_size=0.08",
        facecolor=ROBOT, edgecolor=DARK, linewidth=2, zorder=8))
    ax.text(rc, rr, "R", ha="center", va="center", weight="bold",
            zorder=9, color=DARK, fontsize=10)
    return rc, rr
