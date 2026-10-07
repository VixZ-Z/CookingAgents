"""Central configuration for Project 1 (no pygame imports here!).

Everything that defines an experiment condition lives in this file so that
the headless simulator, the pygame wrapper and the analysis scripts agree.
Requires Python 3.10+.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Time
# --------------------------------------------------------------------------
TICK_HZ = 20                  # fixed simulation step: 20 ticks per second
DT = 1.0 / TICK_HZ
GAME_TIME = 180.0             # seconds per trial
POSITION_LOG_HZ = 5           # positions are logged every TICK_HZ/5 ticks

# --------------------------------------------------------------------------
# Layout (grid units, NOT pixels; render.py converts to pixels)
# --------------------------------------------------------------------------
GRID_W, GRID_H = 14, 7

# station id -> (kind, (col, row)). Ingredient crates are configurable so the
# "swap crate locations" routine change can be applied via LAYOUT_B.
LAYOUT_A: dict[str, tuple[str, tuple[int, int]]] = {
    "crate_tomato":  ("crate_tomato",  (0, 0)),
    "crate_onion":   ("crate_onion",   (2, 0)),
    "crate_lettuce": ("crate_lettuce", (4, 0)),
    "board_h":       ("board",         (6, 0)),    # human's chopping board
    "board_r":       ("board",         (8, 0)),    # robot's chopping board
    "shared":        ("counter",       (7, 3)),    # hand-over point
    "pot":           ("pot",           (11, 0)),
    "plates":        ("plates",        (5, 6)),
    "serve":         ("serve",         (13, 0)),
    "trash":         ("trash",         (13, 6)),
}

# Crate swap used by the "layout" routine change (tomato <-> lettuce).
LAYOUT_B = {
    **LAYOUT_A,
    "crate_tomato":  ("crate_tomato",  LAYOUT_A["crate_lettuce"][1]),
    "crate_lettuce": ("crate_lettuce", LAYOUT_A["crate_tomato"][1]),
}

# --------------------------------------------------------------------------
# Recipes and the human/robot task split (INTERDEPENDENCE, gate G2)
#
# Neither agent can finish a dish alone:
#   human : fetches + chops TOMATO, drops it on the shared counter
#   robot : fetches + chops ONION/LETTUCE, fetches plates, runs the pot, serves
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Recipe:
    name: str
    human_part: tuple[str, ...]     # ingredients only the human handles
    robot_part: tuple[str, ...]     # ingredients only the robot handles
    cook_time: float = 0.0          # pot time (0 = no cooking)


RECIPES: dict[str, Recipe] = {
    "salad": Recipe("salad", human_part=("tomato",), robot_part=("lettuce",)),
    "soup":  Recipe("soup",  human_part=("tomato",), robot_part=("onion",),
                    cook_time=5.0),
}
CHOP_TIME = 1.5

# --------------------------------------------------------------------------
# Orders
# --------------------------------------------------------------------------
ORDER_TTL = (65.0, 90.0)       # lifetime range (s)
ORDER_INTERVAL = 15.0          # new order every N seconds
MAX_ORDERS = 4
SCORE_DELIVERY = 100
SCORE_EXPIRE_PENALTY = 20

# Fixed schedules per condition => identical difficulty for every run.
# Each entry is the dish kind of the k-th order.
ORDER_SCHEDULES: dict[str, list[str]] = {
    "salad_first": ["salad", "salad", "soup", "salad", "soup", "soup",
                    "salad", "soup", "salad", "soup", "salad", "soup"],
    "soup_first":  ["soup", "soup", "salad", "soup", "salad", "salad",
                    "soup", "salad", "soup", "salad", "soup", "salad"],
}

# --------------------------------------------------------------------------
# Experiment conditions
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Condition:
    name: str
    agent: str                      # "reactive" | "anticipatory"
    forgetting: str = "none"        # "none" | "fixed" | "dynamic"
    h: int | None = None            # window size for fixed forgetting
    routine_before: str = "salad_first"
    routine_after: str = "soup_first"
    change_time: float = 90.0       # routine change at T (s); None => no change


CONDITIONS: dict[str, Condition] = {
    "reactive":       Condition("reactive", "reactive"),
    "antic_fixed_h":  Condition("antic_fixed_h", "anticipatory", "fixed", h=30),
    "antic_dynamic_h": Condition("antic_dynamic_h", "anticipatory", "dynamic"),
}

DEFAULT_SEEDS = list(range(100))   # simulated runs: seeds 0..99
LOG_DIR = "logs"
