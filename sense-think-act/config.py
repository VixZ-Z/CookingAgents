"""All parameters of the simulation, each with a short justification.

Tune things here only: the other modules contain no magic numbers.
Array conventions: states and actions are integer indices (see below).
"""
import numpy as np

# --------------------------------------------------------------------------
# Run settings
# --------------------------------------------------------------------------
SEED = 0                  # fixed seed so every run is reproducible
N_STEPS = 60              # > 50 steps as the assignment asks
ROUTINE_CHANGE_STEP = 30  # mid-run change: person starts tiring sooner

# --------------------------------------------------------------------------
# Kitchen: 5x5 grid, positions are (row, col)
# --------------------------------------------------------------------------
GRID_SIZE = 5
ZONES = ["Fridge", "Pot", "Board", "Table", "Chair"]
LOCATIONS = {             # top row = work area, bottom row = rest area
    "Fridge": (0, 0),
    "Board": (0, 2),      # chopping board (Overcooked-style)
    "Pot": (0, 4),        # cook surface (Overcooked-style pot)
    "Table": (4, 2),
    "Chair": (4, 4),      # resting spot
}
POT_CELL = LOCATIONS["Pot"]
BOARD_CELL = LOCATIONS["Board"]
ROBOT_START = (3, 0)      # far from the person: the robot starts unobtrusive
NEAR_POT_DIST = 1         # "adjacent" = Chebyshev distance <= 1
# Keep distance only backs away while closer than this; 1 cell is enough
# comfort space (do not flee to the far corner).
KEEP_DISTANCE_CELLS = 1

# --------------------------------------------------------------------------
# Hidden human state and actions
# --------------------------------------------------------------------------
STATES = ["Cooking", "NeedsHelp", "Resting"]
COOKING, NEEDS_HELP, RESTING = 0, 1, 2
ACTIONS = ["Wait", "Keep distance", "Ask", "Fetch", "Chop"]
WAIT, KEEP_DISTANCE, ASK, FETCH, CHOP = 0, 1, 2, 3, 4
FETCH_STEPS = 2           # fetching takes 2 steps: the robot must commit
CHOP_STEPS = 4            # cutting takes long enough to see the robot work

# --------------------------------------------------------------------------
# True human dynamics (used by human.py only; the robot never sees these)
# --------------------------------------------------------------------------
# Cooking -> NeedsHelp / Resting grows linearly with hidden fatigue in [0, 1]
# Fresh cook still sometimes sits down and leaves the board for the robot.
T_BASE_COOKING = np.array([0.78, 0.06, 0.16])
FATIGUE_TO_HELP = 0.12    # at fatigue 1, P(Cooking->NeedsHelp) = 0.18
FATIGUE_TO_REST = 0.36    # at fatigue 1, P(Cooking->Resting) = 0.52
# Rows for NeedsHelp and Resting do not depend on fatigue.
# NeedsHelp persists until helped (0.80), may give up and sit down (0.15).
T_NEEDS_HELP = np.array([0.05, 0.80, 0.15])
# While food is still on the board the person stays seated.
# 0.01 floor so the HMM never sees a hard zero.
T_RESTING = np.array([0.08, 0.01, 0.91])
# Once the robot has chopped it, they get back up sooner.
T_RESTING_DONE = np.array([0.45, 0.05, 0.50])
# Chance per cooking step to leave an ingredient on the empty board.
LEAVE_FOOD_PROB = 0.28

FATIGUE_GAIN = 0.08       # tires after ~12 cooking steps, then often rests
FATIGUE_GAIN_AFTER = 0.16  # after the routine change: tires twice as fast
FATIGUE_RECOVERY = 0.08   # rest restores fatigue slowly (longer breaks)
FATIGUE_RELIEF = 0.25     # finished chop or fetch makes them less tired

# Where the person stands in each state (true zone distribution)
ZONE_PROBS = np.array([
    [0.15, 0.30, 0.50, 0.05, 0.00],  # Cooking: board and pot
    [0.25, 0.20, 0.50, 0.05, 0.00],  # NeedsHelp: stuck at board/fridge
    [0.00, 0.00, 0.00, 0.10, 0.90],  # Resting: on the chair
])
ZONE_MOVE_PROB = 0.30     # chance of walking elsewhere while state is kept

# --------------------------------------------------------------------------
# SENSE: noisy observation model (emission probabilities, per state)
# --------------------------------------------------------------------------
P_DROPOUT = 0.15          # sensor fails ~1 step in 7 (occlusion, Wi-Fi)

POS_ERR = 0.10            # position tracker reports a wrong zone 10% of time
# P(observed zone | state): correct with 0.9, else uniform over other 4.
EMIT_POS = (1 - POS_ERR) * ZONE_PROBS + POS_ERR * (1 - ZONE_PROBS) / 4

# P(reaching gesture detected | state): camera misses 30% of real reaches
# (0.70) and rarely fires by mistake while cooking (0.10) or resting (0.05).
EMIT_GESTURE = np.array([0.10, 0.70, 0.05])

# P(idle time "high" | state): standing still is typical of resting,
# common when stuck, and rare while actively cooking.
EMIT_IDLE = np.array([0.15, 0.50, 0.90])

# P(verbal cue "could you..." | state): rare (0.08) but nearly never a
# false alarm (0.002), so it is highly reliable evidence for NeedsHelp.
EMIT_VERBAL = np.array([0.002, 0.08, 0.002])

# --------------------------------------------------------------------------
# THINK 1: HMM (the robot's model, deliberately not identical to the truth)
# --------------------------------------------------------------------------
# Average transition matrix assuming mid fatigue (0.5): the robot does not
# know the hidden fatigue, so it starts from this "typical person" model.
T_PRIOR = np.array([
    [0.62, 0.12, 0.26],   # expects more rest than a tireless cook
    T_NEEDS_HELP,
    T_RESTING,
])
INITIAL_BELIEF = np.array([0.80, 0.10, 0.10])  # person starts by cooking
PRIOR_STRENGTH = 20.0     # prior is worth ~20 observed transitions per row
DECAY = 0.95              # forgetting: memory of ~20 steps, fast enough to
#                           track a change at step 30 in a 60-step run

# --------------------------------------------------------------------------
# THINK 2: reward  [Wait, Keep, Ask, Fetch, Chop]
# --------------------------------------------------------------------------
# Cooking: give a little space, do not nag with Ask.
# NeedsHelp: Fetch (or Ask if the pot is unsafe) is the right help.
# Resting: Chop is the useful job — they left food on the board.
# Chop while they are still cooking is a small intrusion unless the
# board camera shows food (see FOOD_CHOP_BONUS in the policy).
_REWARD = np.array([
    [0.0, 0.3, -3.0, -6.0, -1.0],
    [-2.0, -2.0, 2.0, 8.0, 6.0],
    [0.0, 0.2, -3.0, -4.0, 9.0],
])
ACTION_COST = 0.1         # small cost for every action except Wait
REWARD = _REWARD.copy()
REWARD[:, 1:] -= ACTION_COST
POT_PENALTY = -20.0       # very negative: fetching near an active pot
# Added on top of Q when the board still holds an ingredient, so the
# robot cuts it instead of hovering or asking.
FOOD_CHOP_BONUS = 3.0
# World reward for starting a chop while an ingredient is actually there.
# Higher than the MDP's "chop during cooking" penalty: the board is visible.
CHOP_HELP_REWARD = 6.0
GAMMA = 0.9               # discount: help now matters more than later
# Fetch fixes a NeedsHelp person almost always (0.90); the MDP uses this.
T_FETCH_FROM_NEEDS_HELP = np.array([0.90, 0.02, 0.08])
# After a finished chop the person often gets up and cooks again.
T_CHOP_FROM_RESTING = np.array([0.55, 0.05, 0.40])

# --------------------------------------------------------------------------
# Safety rule (outside the learned policy)
# --------------------------------------------------------------------------
SAFETY_RULE = True        # set False to see why the rule matters
