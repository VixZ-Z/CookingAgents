"""All simulation parameters in one place.

States, actions and zones are integer indices into the numpy tables.
"""
import numpy as np

# Run settings
SEED = 34                 # demo seed, shows every action incl. the safety rule
N_STEPS = 60
ROUTINE_CHANGE_STEP = 30  # the person starts tiring faster here

# Kitchen: 5x5 grid, cells are (row, col), row 0 on top
GRID_SIZE = 5
ZONES = ["Fridge", "Pot", "Board", "Table", "Chair"]
FRIDGE, POT, BOARD, TABLE, CHAIR = range(len(ZONES))
LOCATIONS = {             # top row = work area, bottom row = rest area
    "Fridge": (0, 0),
    "Board": (0, 2),
    "Pot": (0, 4),
    "Table": (4, 2),
    "Chair": (4, 4),
}
ROBOT_START = (3, 0)
PERSONAL_SPACE = 1        # cells

# States and actions
STATES = ["Cooking", "NeedsHelp", "Resting"]
COOKING, NEEDS_HELP, RESTING = range(len(STATES))
ACTIONS = ["Wait", "Ask", "Fetch", "Chop"]
WAIT, ASK, FETCH, CHOP = range(len(ACTIONS))
DURATION = {FETCH: 2, CHOP: 3}  # multi-step actions, the rest take 1 step

# True human dynamics (only human.py uses these)
# From Cooking: P(NeedsHelp) = 0.05 + 0.35 f, P(Resting) = 0.10 + 0.40 f
T_COOKING_FRESH = np.array([0.85, 0.05, 0.10])
FATIGUE_TO_HELP = 0.35
FATIGUE_TO_REST = 0.40
T_NEEDS_HELP = np.array([0.05, 0.80, 0.15])  # stuck until helped
T_RESTING = np.array([0.15, 0.02, 0.83])     # breaks last ~6 steps

FATIGUE_GAIN = 0.04        # per cooking step
FATIGUE_GAIN_AFTER = 0.20  # per cooking step after the routine change
FATIGUE_RECOVERY = 0.05    # per resting step
FATIGUE_RELIEF = 0.25      # when the robot finishes a Fetch or Chop

# P(zone | state)
ZONE_PROBS = np.array([
    # Fridge  Pot  Board  Table  Chair
    [0.15, 0.35, 0.45, 0.05, 0.00],  # Cooking
    [0.25, 0.50, 0.20, 0.05, 0.00],  # NeedsHelp: often stuck at the pot
    [0.00, 0.00, 0.00, 0.10, 0.90],  # Resting
])
ZONE_MOVE_PROB = 0.30      # chance to move within the same state

# Kitchen objects (observed directly by the robot)
POT_ON_PROB = 0.5
POT_OFF_PROB = 0.15
NEW_INGREDIENT_PROB = 0.3
SELF_CHOP_PROB = 0.3

# Sensor model P(signal | state)
P_DROPOUT = 0.15          # no person observation at all (occlusion)
POS_ERR = 0.10            # wrong zone reported
EMIT_ZONE = (1 - POS_ERR) * ZONE_PROBS + POS_ERR * (1 - ZONE_PROBS) / 4
EMIT_GESTURE = np.array([0.10, 0.70, 0.05])  # misses 30% of real reaches
EMIT_IDLE = np.array([0.15, 0.50, 0.90])
EMIT_VERBAL = np.array([0.002, 0.08, 0.002])  # rare, almost no false alarms

# Robot's HMM. It assumes a rested person, so the prior is wrong later on
# and has to adapt.
T_PRIOR = np.array([T_COOKING_FRESH, T_NEEDS_HELP, T_RESTING])
INITIAL_BELIEF = np.array([0.80, 0.10, 0.10])
PRIOR_STRENGTH = 10.0     # prior counts as ~10 observed steps
DECAY = 0.95              # memory of ~20 steps

# MDP rewards R[state, action]
#                Wait   Ask  Fetch  Chop
REWARD = np.array([
    [0.0,  -1.0, -5.0, -3.0],   # Cooking: leave them be
    [-4.0,  1.0,  6.0, -1.0],   # NeedsHelp: ignoring them is bad
    [0.0,  -1.5, -5.0,  5.0],   # Resting: don't disturb, but chop
])
# Ask is cheap when wrong and Fetch expensive, so an unsure robot asks.
# Ask in NeedsHelp stays low, otherwise the MDP prefers asking forever.
GAMMA = 0.9
T_AFTER_FETCH = np.array([0.90, 0.02, 0.08])  # Fetch solves NeedsHelp

# Safety rule (hard constraint outside the QMDP policy)
SAFETY_RULE = True
POT_PENALTY = -20.0       # autonomous Fetch next to a hot pot
