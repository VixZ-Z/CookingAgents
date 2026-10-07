"""Constants and layout for Kitchen Chaos (no pygame imports here).

Requires Python 3.10+.
"""
WIDTH, HEIGHT = 1100, 720
FPS = 60
TILE = 64
GAME_TIME = 180

PLAYER_SPEED = 230
ROBOT_SPEED = 205
PLAYER_START = (WIDTH // 2 - 20, HEIGHT // 2)
ROBOT_START = (580, 350)
PLAY_AREA = (0, 90, WIDTH, 505)          # x, y, w, h the agents may walk in

# Collaborative layouts (near / far / mixed / swap)
COLLAB_ROBOT_SPEED = 120                 # slower than the scripted robot; tune
SWAP_TIME = 90                           # seconds, crate swap in "swap" layout

CHOP_TIME = 1.5
POT_TIME = 5.0

INITIAL_ORDERS = 3
MAX_ORDERS = 4
ORDER_TTL = (65, 90)                     # seconds, random range
ORDER_INTERVAL = 15
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

INGREDIENTS = {"salad": "Tomato + Lettuce", "soup": "Tomato + Onion"}
ORDER_KINDS = ["salad", "soup"]
