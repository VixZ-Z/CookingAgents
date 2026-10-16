"""Selectable kitchen layouts (select with  python main.py --layout NAME).

scripted : the original map used by the scripted robot.
near / far / mixed / swap : ONE base map where only the distance to the
robot's onion and lettuce crates changes (manipulated variable).

Collaborative base map (columns 1..11, pixels computed from the column):

    col:     1   2   3   4   5 |  6  | 7   8   9   10  11
    Top:     T   B   B   .   . | X1  | Pl  P   P   .   S
    Bottom:  .   .   Tr  .   . | X2  | s7  s8  s9  s10 s11
             human zone          shared       robot zone

T tomato crate, B chopping board, Tr trash, Pl plates, P pot, S serve,
X1/X2 shared counters (capacity 2 items in total), s7..s11 robot crate slots.
The human chops everything: raw items go robot -> shared -> human, chopped
items go human -> shared -> robot.

Crate columns (onion, lettuce):
    near  : 7, 8    control, short lead time
    far   : 10, 11  long lead time
    mixed : 7, 11   soup close, salad far
    swap  : starts as mixed, onion and lettuce crates swap at t = SWAP_TIME
"""
from __future__ import annotations

from dataclasses import dataclass

import config as C

COL_X0, COL_STEP = 50, 92
HUMAN, ROBOT, SHARED = "human", "robot", "shared"


@dataclass(frozen=True)
class Layout:
    name: str
    description: str
    stations: list                 # (x, y, kind, label[, owner])
    player_start: tuple
    robot_start: tuple
    swap_time: float | None = None
    walls: tuple = ()              # (x, y, width, height), solid barriers


def _x(col: int) -> int:
    return COL_X0 + (col - 1) * COL_STEP


def _collab(name, onion_col, lettuce_col, description, swap_time=None):
    top = [(1, "crate_tomato", "Tomato", HUMAN),
           (2, "board", "Chop", HUMAN), (3, "board", "Chop", HUMAN),
           (6, "counter", "Shared", SHARED),
           (7, "plates", "Plates", ROBOT),
           (8, "pot", "Pot", ROBOT), (9, "pot", "Pot", ROBOT),
           (11, "serve", "Serve", ROBOT)]
    bottom = [(3, "trash", "Trash", None),
              (6, "counter", "Shared", SHARED),
              (onion_col, "crate_onion", "Onion", ROBOT),
              (lettuce_col, "crate_lettuce", "Lettuce", ROBOT)]
    stations = ([(_x(c), C.Y_TOP, k, lbl, o) for c, k, lbl, o in top]
                + [(_x(c), C.Y_BOTTOM, k, lbl, o) for c, k, lbl, o in bottom])
    return Layout(name, description, stations,
                  player_start=(_x(4), 350), robot_start=(_x(8), 350),
                  swap_time=swap_time)


def _reactive():
    """Separated workspaces connected by two one-item handoff counters."""
    human = [(50, C.Y_TOP, "crate_tomato", "Tomato", HUMAN),
             (142, C.Y_TOP, "crate_onion", "Onion", HUMAN),
             (234, C.Y_TOP, "crate_lettuce", "Lettuce", HUMAN),
             (50, C.Y_BOTTOM, "board", "Chop", HUMAN),
             (142, C.Y_BOTTOM, "board", "Chop", HUMAN),
             (326, C.Y_BOTTOM, "trash", "Trash", HUMAN)]
    robot = [(650, C.Y_TOP, "board", "Chop", ROBOT),
             (742, C.Y_TOP, "pot", "Pot", ROBOT),
             (834, C.Y_TOP, "plates", "Plates", ROBOT),
             (1018, C.Y_TOP, "serve", "Serve", ROBOT),
             (650, C.Y_BOTTOM, "counter", "Store", ROBOT),
             (742, C.Y_BOTTOM, "counter", "Assemble", ROBOT),
             (1018, C.Y_BOTTOM, "trash", "Trash", ROBOT)]
    handoff = [(518, 250, "counter", "Handoff", SHARED),
               (518, 400, "counter", "Handoff", SHARED)]
    return Layout("reactive", "Separate workspaces with two handoff counters",
                  human + robot + handoff, (300, 330), (800, 330),
                  walls=((518, 90, 64, 160), (518, 314, 64, 86),
                         (518, 464, 64, 131)))


LAYOUTS: dict[str, Layout] = {
    "reactive": _reactive(),
    "shared": Layout("shared", "Shared kitchen: human and robot use all stations",
                     [tuple(s) for s in C.STATIONS],
                     C.PLAYER_START, C.ROBOT_START),
    "scripted": Layout("scripted", "Original map (scripted robot)",
                       [tuple(s) for s in C.STATIONS],
                       C.PLAYER_START, C.ROBOT_START),
    "near": _collab("near", 7, 8, "Control: short lead time"),
    "far": _collab("far", 10, 11, "Long lead time"),
    "mixed": _collab("mixed", 7, 11, "Soup near, salad far"),
    "swap": _collab("swap", 7, 11, "Mixed, crates swap mid-game",
                    swap_time=C.SWAP_TIME),
}
LAYOUT_NAMES = list(LAYOUTS)


def get_layout(name: str) -> Layout:
    return LAYOUTS[name]
