"""Constants and layout for Kitchen Chaos (no pygame imports here).

Requires Python 3.10+.
"""
WIDTH, HEIGHT = 1100, 720
FPS = 60
TILE = 64
GAME_TIME = 180

PLAYER_SPEED = 230
ROBOT_SPEED = 205
ROBOT_START_DELAY = 0.5                 # seconds of game time, once per game
HUMAN_IDLE_TIMEOUT = 5.0                # seconds before the robot takes over missing work
TRANSITION_MIN_SAMPLES = 2              # policy evidence threshold, not a fabricated prior
TRANSITION_MIN_PROBABILITY = 0.6
FIXED_H_SECONDS = 4.0                   # pilot parameter; freeze it within an experiment
H_INTERACTION_SECONDS = 0.2             # scheduling estimate for an E interaction
H_HANDOFF_LATENESS_WEIGHT = 2.0         # local scheduling cost, seconds per second late
PLAYER_START = (WIDTH // 2 - 20, HEIGHT // 2)
ROBOT_START = (580, 350)
PLAY_AREA = (0, 90, WIDTH, 505)          # x, y, w, h the agents may walk in

# Collaborative layouts (near / far / mixed / swap)
COLLAB_ROBOT_SPEED = 120                 # slower than the scripted robot; tune
SWAP_TIME = 90                           # seconds, crate swap in "swap" layout

CHOP_TIME = 0.2
POT_TIME = 0.5

INITIAL_ORDERS = 3
MAX_ORDERS = 4
ORDER_TTL = (65, 90)                     # seconds, random range
ORDER_INTERVAL = 10
SCORE_DELIVERY = 100
SCORE_EXPIRE_PENALTY = 20

# Station layout: (x, y, kind, label). The robot reserves the 2nd board,
# 2nd pot and 2nd counter (in this list order) as its own equipment.
Y_TOP, Y_BOTTOM = 120, 510
STATIONS = [
    (40, Y_TOP, "crate_tomato", "Tomato"),
    (120, Y_TOP, "crate_onion", "Onion"),
    (200, Y_TOP, "crate_lettuce", "Lettuce"),
    (320, Y_TOP, "board", "Chop"),
    (400, Y_TOP, "board", "Chop"),
    (520, Y_TOP, "counter", "Counter"),
    (600, Y_TOP, "counter", "Counter"),
    (720, Y_TOP, "pot", "Pot"),
    (800, Y_TOP, "pot", "Pot"),
    (920, Y_TOP, "serve", "Serve"),
    (140, Y_BOTTOM, "counter", "Counter"),
    (260, Y_BOTTOM, "counter", "Counter"),
    (420, Y_BOTTOM, "plates", "Plates"),
    (540, Y_BOTTOM, "counter", "Counter"),
    (660, Y_BOTTOM, "counter", "Counter"),
    (820, Y_BOTTOM, "counter", "Counter"),
    (960, Y_BOTTOM, "trash", "Trash"),
]
ROBOT_OWNED_INDEX = 1                    # index among boards / pots / counters

from menu import RECIPES
RECIPE_INGREDIENTS = {key: r.ingredients for key, r in RECIPES.items()}
INGREDIENTS = {key: " + ".join(n.title() for n in r.ingredients)
               for key, r in RECIPES.items()}
ORDER_KINDS = list(RECIPES)
# Historical metadata is confined to archive/regression support, not playable options.
ALL_RECIPE_INGREDIENTS = {"salad": ("tomato", "lettuce"), "soup": ("tomato", "onion"),
                          **RECIPE_INGREDIENTS}
