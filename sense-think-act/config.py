"""All parameters of the simulation, each with a short justification.

Every other module takes its numbers from here, so the whole model can be
read (and tuned) in one place. States, actions and zones are integer
indices so they can index the numpy tables directly.
"""
import numpy as np

# --------------------------------------------------------------------------
# Run settings
# --------------------------------------------------------------------------
SEED = 34                 # fixed seed: reproducible, and the demo run shows
#                           every action including the safety rule
N_STEPS = 60              # well above the 10 steps the assignment requires
ROUTINE_CHANGE_STEP = 30  # from here on the person tires much faster

# --------------------------------------------------------------------------
# Kitchen: 5x5 grid, cells are (row, col), row 0 on top
# --------------------------------------------------------------------------
GRID_SIZE = 5
ZONES = ["Fridge", "Pot", "Board", "Table", "Chair"]
FRIDGE, POT, BOARD, TABLE, CHAIR = range(len(ZONES))
LOCATIONS = {             # top row = work area, bottom row = rest area
    "Fridge": (0, 0),
    "Board": (0, 2),      # chopping board
    "Pot": (0, 4),        # stove with a pot
    "Table": (4, 2),
    "Chair": (4, 4),      # resting spot
}
ROBOT_START = (3, 0)      # starts away from the person: unobtrusive
PERSONAL_SPACE = 1        # cells; closer than this only to hand something over

# --------------------------------------------------------------------------
# Hidden human state and robot actions
# --------------------------------------------------------------------------
STATES = ["Cooking", "NeedsHelp", "Resting"]
COOKING, NEEDS_HELP, RESTING = range(len(STATES))
# Wait = stay idle at a polite distance (the robot backs off whenever it is
# inside the person's personal space).
ACTIONS = ["Wait", "Ask", "Fetch", "Chop"]
WAIT, ASK, FETCH, CHOP = range(len(ACTIONS))
# Multi-step actions (all others take one step). The robot commits to them
# until they finish: this is the "intention" of the BDI model.
DURATION = {FETCH: 2, CHOP: 3}

# --------------------------------------------------------------------------
# True human dynamics (human.py only: the robot never sees these)
# --------------------------------------------------------------------------
# Row "from Cooking" of the transition matrix grows with hidden fatigue f:
#   P(-> NeedsHelp) = 0.05 + 0.35 f,  P(-> Resting) = 0.10 + 0.40 f
# A tired person struggles (heavy pot, high shelf) much more often.
T_COOKING_FRESH = np.array([0.85, 0.05, 0.10])
FATIGUE_TO_HELP = 0.35
FATIGUE_TO_REST = 0.40
T_NEEDS_HELP = np.array([0.05, 0.80, 0.15])  # stuck until helped
T_RESTING = np.array([0.15, 0.02, 0.83])     # breaks last ~6 steps

FATIGUE_GAIN = 0.04        # per cooking step before the routine change
FATIGUE_GAIN_AFTER = 0.20  # after it: a bad day, tired within ~5 steps
FATIGUE_RECOVERY = 0.05    # per resting step: rest helps, but slowly
FATIGUE_RELIEF = 0.25      # a finished Fetch or Chop takes work off them

# Where the person stands in each state: P(zone | state)
ZONE_PROBS = np.array([
    # Fridge  Pot  Board  Table  Chair
    [0.15, 0.35, 0.45, 0.05, 0.00],  # Cooking: mostly board and pot
    [0.25, 0.50, 0.20, 0.05, 0.00],  # NeedsHelp: often stuck at the pot
    [0.00, 0.00, 0.00, 0.10, 0.90],  # Resting: sitting down
])
ZONE_MOVE_PROB = 0.30      # chance to walk elsewhere within the same state

# Kitchen objects the person uses. The robot observes them directly.
POT_ON_PROB = 0.5          # per cooking step, an off pot gets switched on
POT_OFF_PROB = 0.15        # per step, an on pot is finished / switched off
NEW_INGREDIENT_PROB = 0.3  # per cooking step, a new ingredient on the board
SELF_CHOP_PROB = 0.3       # per cooking step, the person finishes it

# --------------------------------------------------------------------------
# SENSE: noisy observation model, P(signal | state)
# --------------------------------------------------------------------------
P_DROPOUT = 0.15          # all person sensors fail ~1 step in 7 (occlusion)
POS_ERR = 0.10            # position tracker reports a wrong zone 10% of time
# P(observed zone | state): the true zone distribution blurred by POS_ERR.
EMIT_ZONE = (1 - POS_ERR) * ZONE_PROBS + POS_ERR * (1 - ZONE_PROBS) / 4
# Reaching gesture: the camera misses 30% of real reaches (0.70) and
# rarely fires by mistake while cooking (0.10) or resting (0.05).
EMIT_GESTURE = np.array([0.10, 0.70, 0.05])
# Long idle time: typical of resting, common when stuck, rare when cooking.
EMIT_IDLE = np.array([0.15, 0.50, 0.90])
# Verbal "could you...": rare (0.08) but almost never a false alarm.
EMIT_VERBAL = np.array([0.002, 0.08, 0.002])

# --------------------------------------------------------------------------
# THINK 1: the robot's HMM (deliberately not identical to the truth)
# --------------------------------------------------------------------------
# The robot assumes a "fresh" person (fatigue 0). The real person tires,
# so this prior is wrong later in the day: the HMM has to adapt.
T_PRIOR = np.array([T_COOKING_FRESH, T_NEEDS_HELP, T_RESTING])
INITIAL_BELIEF = np.array([0.80, 0.10, 0.10])  # day starts with cooking
PRIOR_STRENGTH = 10.0     # the prior weighs as much as ~10 observed steps
DECAY = 0.95              # forget old evidence (memory of ~20 steps), fast
#                           enough to track the routine change at step 30

# --------------------------------------------------------------------------
# THINK 2: MDP rewards R[state, action]
# --------------------------------------------------------------------------
#                Wait   Ask  Fetch  Chop
REWARD = np.array([
    [0.0,  -1.0, -5.0, -3.0],   # Cooking: leave them be (autonomy)
    [-4.0,  1.0,  6.0, -1.0],   # NeedsHelp: ignoring them is bad
    [0.0,  -1.5, -5.0,  5.0],   # Resting: do not disturb, but finish chopping
])
# Ask is cheap when wrong, Fetch is expensive: with an unsure belief the
# robot asks, with a confident belief it fetches straight away.
# Ask in NeedsHelp is only +1 because asking alone does not solve the
# problem; with a higher value the MDP learns to keep the person waiting.
GAMMA = 0.9               # help now matters more than help later
T_AFTER_FETCH = np.array([0.90, 0.02, 0.08])  # Fetch solves NeedsHelp

# --------------------------------------------------------------------------
# Safety rule (a hard constraint outside the learned policy)
# --------------------------------------------------------------------------
SAFETY_RULE = True        # set False to see what happens without it
POT_PENALTY = -20.0       # world penalty: autonomous Fetch next to a hot pot
