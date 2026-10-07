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
ZONES = ["Fridge", "Stove", "Counter", "Table", "Chair"]
LOCATIONS = {             # top row = work area, bottom row = rest area
    "Fridge": (0, 0),
    "Counter": (0, 2),
    "Stove": (0, 4),
    "Table": (4, 2),
    "Chair": (4, 4),      # resting spot
}
STOVE_CELL = LOCATIONS["Stove"]
ROBOT_START = (3, 0)      # far from the person: the robot starts unobtrusive
NEAR_STOVE_DIST = 1       # "adjacent" = Chebyshev distance <= 1

# --------------------------------------------------------------------------
# Hidden human state and actions
# --------------------------------------------------------------------------
STATES = ["Cooking", "NeedsHelp", "Resting"]
COOKING, NEEDS_HELP, RESTING = 0, 1, 2
ACTIONS = ["Wait", "Keep distance", "Ask", "Fetch"]
WAIT, KEEP_DISTANCE, ASK, FETCH = 0, 1, 2, 3
FETCH_STEPS = 2           # fetching takes 2 steps: the robot must commit

# --------------------------------------------------------------------------
# True human dynamics (used by human.py only; the robot never sees these)
# --------------------------------------------------------------------------
# Cooking -> NeedsHelp / Resting grows linearly with hidden fatigue in [0, 1]
T_BASE_COOKING = np.array([0.92, 0.04, 0.04])  # fatigue 0: rarely changes
FATIGUE_TO_HELP = 0.20    # at fatigue 1, P(Cooking->NeedsHelp) = 0.24
FATIGUE_TO_REST = 0.20    # at fatigue 1, P(Cooking->Resting) = 0.24
# Rows for NeedsHelp and Resting do not depend on fatigue.
# NeedsHelp persists until helped (0.80), may give up and sit down (0.15).
T_NEEDS_HELP = np.array([0.05, 0.80, 0.15])
# Resting: sits ~5 steps; 0.01 floor so the HMM never sees a hard zero.
T_RESTING = np.array([0.20, 0.01, 0.79])

FATIGUE_GAIN = 0.04       # per Cooking step: tires after ~25 active steps
FATIGUE_GAIN_AFTER = 0.12  # after the routine change: tires ~3x faster
FATIGUE_RECOVERY = 0.15   # per Resting step: rest restores fatigue quickly
FATIGUE_RELIEF = 0.20     # being helped makes the person feel less tired

# Where the person stands in each state (true zone distribution)
ZONE_PROBS = np.array([
    [0.25, 0.40, 0.30, 0.05, 0.00],  # Cooking: work area, mostly stove
    [0.40, 0.20, 0.40, 0.00, 0.00],  # NeedsHelp: stuck at fridge/counter
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
    [0.72, 0.14, 0.14],
    T_NEEDS_HELP,
    T_RESTING,
])
INITIAL_BELIEF = np.array([0.80, 0.10, 0.10])  # person starts by cooking
PRIOR_STRENGTH = 20.0     # prior is worth ~20 observed transitions per row
DECAY = 0.95              # forgetting: memory of ~20 steps, fast enough to
#                           track a change at step 30 in a 60-step run

# --------------------------------------------------------------------------
# THINK 2: reward (rows = states, columns = actions)  [Wait, Keep, Ask, Fetch]
# --------------------------------------------------------------------------
_REWARD = np.array([
    [0.0, 0.0, -3.0, -6.0],    # Cooking: any approach is an intrusion
    [-2.0, -2.0, 3.0, 10.0],   # NeedsHelp: waiting hurts, Fetch is best
    [0.0, 1.0, -3.0, -5.0],    # Resting: keeping distance = comfort
])
ACTION_COST = 0.1         # small cost for every action except Wait
REWARD = _REWARD.copy()
REWARD[:, 1:] -= ACTION_COST
STOVE_PENALTY = -20.0     # very negative: acting near an active stove
GAMMA = 0.9               # discount: help now matters more than later
# Fetch fixes a NeedsHelp person almost always (0.90); the MDP uses this.
T_FETCH_FROM_NEEDS_HELP = np.array([0.90, 0.02, 0.08])

# --------------------------------------------------------------------------
# Safety rule (outside the learned policy)
# --------------------------------------------------------------------------
SAFETY_RULE = True        # set False to see why the rule matters
