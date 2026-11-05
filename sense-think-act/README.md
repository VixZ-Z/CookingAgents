# Project 2: Sense-Think-Act for an Elderly Home-Care Kitchen Robot

A toy simulation of a home robot that supports an elderly person cooking in
a 5x5 kitchen, and only steps in when it is needed. Pure Python (numpy +
matplotlib), Python 3.10+.

## Run
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py        # 60 steps -> console trace + log.csv
python visualize.py   # -> figure.png (belief, kitchen, reward)
python animate.py     # -> animation.gif (--show: live window,
                      #    --frame 41: one PNG frame)
python compare.py     # 4 robot variants over 100 seeds
```

## Scenario
Kitchen cells are (row, col), row 0 on top:
```
Fridge(0,0)  .  Board(0,2)   .  Pot(0,4)
   .         .      .         .     .
   .         .      .         .     .
   R start   .      .         .     .
   .         .   Table(4,2)   .  Chair(4,4)
```
The person is in one of three hidden states, `Cooking`, `NeedsHelp` or
`Resting`. A hidden fatigue level makes NeedsHelp and Resting more likely,
and from step 30 the person tires much faster (routine change). While
cooking they switch the pot on and put ingredients on the board; when they
sit down, any unfinished ingredient stays on the board.

## The loop (`main.py`)
```python
human.step()                         # the hidden world moves on
obs = human.observe()                # SENSE: noisy person signals
context = env.sense(obs)             # SENSE: pot, board, own task
action = robot.think(obs, context)   # THINK: HMM belief -> QMDP
reward = env.apply(action)           # ACT: move, ask, fetch, chop
```

- **Sense** (`human.observe`, `Environment.sense`): zone (10% wrong),
  reaching gesture, long idle time, rare verbal cue, 15% total dropout.
  The smart stove and the board camera are reliable; they show objects,
  not the person's intent.
- **Think** (`hmm.py`, `policy.py`, `robot.py`): an HMM forward filter
  gives the belief; QMDP picks `argmax_a sum_s b(s) Q(s, a)` with `Q` from
  value iteration. The transition matrix is re-estimated online
  (adaptation). Fetch and Chop take several steps and are finished before
  a new decision (BDI intention).
- **Act** (`environment.py`): `Wait` (back off out of personal space),
  `Ask` (approach to one cell, the person answers), `Fetch` (2 steps:
  fridge, then hand-over), `Chop` (3 steps at the board).
- **Safety rule**: no autonomous Fetch while the pot is on and the person
  is (or may be, during a dropout) at the pot: the robot asks first.

## Files
| File | Role |
|---|---|
| `config.py` | every parameter, with a one-line justification |
| `human.py` | hidden person model and noisy observations (SENSE) |
| `hmm.py` | belief update and online adaptation (THINK 1) |
| `policy.py` | MDP value iteration, QMDP, safety rule (THINK 2) |
| `robot.py` | BDI agent: belief + intention -> action |
| `environment.py` | robot sensors, movement, action effects, reward (ACT) |
| `main.py` | the sense-think-act loop and the log |
| `compare.py` | rules vs static HMM vs adaptive HMM vs no safety rule |
| `visualize.py`, `animate.py`, `theme.py` | figures and animation |

`log.csv` has one row per step: true state, fatigue, observation, belief
(3 columns), action, whether it continues an earlier action, whether the
person had confirmed, safety rule fired, unsafe fetch, reward, pot and
board state.

## Style check
`pip install flake8` then `flake8 .`
