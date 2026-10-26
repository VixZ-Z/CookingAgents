# Project 2: Sense-Think-Act for an Elderly Home-Care Kitchen Robot

A toy simulation: a home robot supports an elderly person cooking in a
5x5 kitchen, only when needed. Pure Python (numpy + matplotlib), Python 3.10+.
Visual style matches Overcooked AI colours (pot, teal robot, blue person)
without pygame.

## Run
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py        # 60 steps, seed 0 -> log.csv + console trace
python visualize.py   # -> figure.png
python animate.py     # -> animation.gif (add --show for a live window,
                      #    --frame 34 for a single PNG frame)
python compare.py     # 100 seeds, 3 robot variants (optional)
```

## Scenario
Kitchen (row, col), row 0 on top:
```
Fridge(0,0)  .  Board(0,2)   .  Pot(0,4)
   .         .      .         .     .
   .         .      .         .     .
   R start   .      .         .     .
   .         .   Table(4,2)   .  Chair(4,4)
```
Hidden state: `Cooking`, `NeedsHelp`, `Resting` (driven by a hidden fatigue
level; at step 30 the person starts tiring ~3x faster).

## Sense-think-act
- **Sense** (`human.py`): noisy zone, reaching gesture, idle bucket, rare
  verbal cue, 15% dropout. Emission tables are in `config.py`.
- **Think** (`hmm.py`, `policy.py`): HMM forward filter -> belief; QMDP picks
  `argmax_a sum_s b(s) Q(s, a)`; a hard safety rule overrides Fetch near an
  active pot (the robot asks first).
- **Act** (`environment.py`, `robot.py`): `Wait`, `Keep distance`, `Ask`,
  `Fetch`, and `Chop` (2 steps each for Fetch and Chop). When the person
  sits down they leave an ingredient on the chopping board; the robot
  walks over and cuts it. Keep distance only steps away while closer than
  1 cell. Ask/Fetch approach until adjacent, then stop.
- **Adapt**: transition counts updated online with decay.

The animation labels the three phases explicitly so it is clear what the
robot sensed, how it interpreted the belief, and which action it took.

## Files and stable interfaces
| File | Interface |
|---|---|
| `human.py` | `human.step() -> (true_state, observation)` |
| `hmm.py` | `hmm.update(obs) -> belief` |
| `policy.py` | `policy.choose(belief, context) -> action` |
| `environment.py` | `env.apply(action) -> (reward, new_context)` |
| `robot.py` | the sense-think-act loop |
| `main.py` | `run_episode()`, CSV log |
| `theme.py` | Overcooked-like matplotlib palette |

Log columns: step, true_state, observation, belief (3), action, reward,
safety_fired, food_on_board.

## Style check
`pip install flake8` then `flake8 .`
