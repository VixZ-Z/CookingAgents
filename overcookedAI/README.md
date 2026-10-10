# Project 1: Anticipatory Collaboration in an Overcooked-Inspired Kitchen

The code requires **Python 3.10+**. On Windows, use Python 3.11 for the existing
pygame requirement; pygame 2.6.1 has no Windows wheel for Python 3.14.

## Current prototype: shared kitchen, salads and soups

```powershell
# From this folder, activate the environment created with Python 3.11:
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py --robot anticipatory --seed 0
```

This selects `shared` (the original kitchen geometry, all equipment accessible
to both teammates) and mixed salad/soup orders. Both recipes appear in the initial
orders. The active order with the least remaining time has priority and is shown
first with a yellow border and an asterisk. To try the collaboration:

The robot starts after **0.5 seconds of game time**, even if you do not move.
With no history it assumes you will prepare tomato and starts lettuce for salad
or onion for soup, according to the most urgent order. This initial assumption is
shown on screen and does not count as a learned observation. The delay happens
once per game, including after R; later order changes do not repeat it.

1. Check the priority order. Pick up a tomato with E at the Tomato crate
   (or start with lettuce for salad, onion for soup).
2. Put it on an empty chopping board with E; hold SPACE to chop.
3. Take the chopped ingredient with E and leave it on an empty counter with E.
4. Move away from that counter so the robot can finish and serve the dish.
   For soup you can also put the chopped ingredient straight into the pot that
   contains the robot's complementary ingredient.

If you start tomato, the robot prepares lettuce when salad is most urgent, or
onion when soup is most urgent. For soup it loads the two chopped ingredients into
one pot, waits for cooking, fetches a plate, scoops and serves. It rechecks priority
every frame: an unfinished task is replanned when the priority recipe changes,
and a carried ingredient for the previous recipe is stored for later use. A
finished dish already in its hands is served if a matching order remains.

### Starting the next order before the human moves

The robot learns the first observed human ingredient for each priority order,
separately for salad and soup. At the next order it predicts your most frequent
starter and begins preparing the other ingredient without waiting for movement.
For example, after seeing you start soup with tomato, it can prepare onion for
the next soup while you stand still. One observation is enough for this pilot.
It prepares its contribution and leaves the predicted human ingredient to you.

With no history for a recipe it uses the initial tomato assumption.
Your actual carried ingredient overrides both history and movement guesses. If
you choose the ingredient the robot was preparing, it changes roles, stores its
extra portion and frees its board before preparing the complementary ingredient.
Already prepared ingredients remain available for later use.

Only the first observed ingredient pickup per order adds a history sample.
Standing still, chopping, picking the same ingredient up again, movement guesses,
and the robot's own preparations do not add repeated samples. Frequencies are
cumulative, with the latest observed choice breaking ties; there is no forgetting.
History lives for one game and resets with R. The bottom panel shows the forecast,
for example `Expected start: tomato (2/3 soup starts)`. This ratio describes the
observed choices, not validated prediction accuracy.

To isolate one recipe during testing:

```powershell
python main.py --robot anticipatory --recipe salad --seed 0
python main.py --robot anticipatory --recipe soup --seed 0
```

The robot infers your likely next station from the carried item, station contents
and movement direction. It can start the complementary ingredient while you
approach a crate, before pickup. While you handle one ingredient it prepares the
other, fetches a plate, assembles and serves the dish. It avoids occupied stations,
routes around your body, and gives way at close contact. It does not prepare a
complete meal from scratch on its own: it leaves the predicted human contribution
to you, while using ingredients already delivered to finish dishes.

The screen shows the inferred human goal (blue outline), the robot's task target
(turquoise outline), its route, and a blue circle for the short movement
projection. The bottom panel explains the current robot task and human intent.
Confidence percentages are heuristic scores, not measured prediction accuracy.

This prototype combines rule-based goal inference with learned starter frequencies.
Learning full action sequences, forgetting,
fixed/dynamic `h` and experimental CSV logging are not yet
implemented for this agent. The future reactive comparison should use the same
shared kitchen and movement rules.

### Behavioural checks

```powershell
python -B -m unittest discover -s tests -v
```

Checks cover mixed orders, earliest-deadline selection, priority changes, early
complementary preparation, both ingredient roles, completed salads and soups,
moving human workflows, collision avoidance, access recovery, cooking, serving,
and the original scripted robot. Additional checks cover learning once per order,
autonomous preparation after human/robot delivery, separate recipe histories,
wrong forecasts, storing extra ingredients and freeing boards. They run without
a window. Startup checks cover the 0.5-second delay, a stationary human, an early
human choice, priority changes, and restarting the game.

## Overview
A human and an autonomous robot cook together in a custom Pygame kitchen.
The shared-kitchen prototype above is the current development focus. Older
separate-station maps remain available as previews for a possible later study.

## Research question
Current direction: does anticipating a human teammate's goals improve task
coordination and reduce blocking in a shared kitchen? Forgetting and changing
routines remain possible later extensions, outside the first prototype.

## Structure
```
main.py             entry point / main loop (--robot, --layout, --seed)
config.py           constants and the original station layout (pixels)
layouts.py          selectable layouts: scripted, shared, near, far, mixed, swap
game.py             game logic: stations, orders, player, rules, scoring
render.py           all pygame drawing
robot_base.py       common robot interface
scripted_robot/     original robot (works, scripted layout only)
reactive_robot/     baseline robot (stub)
anticipatory_robot/ goal inference, learned starter frequencies, cooperative planner
navigation.py       body-aware A* paths, movement projection costs, contact recovery
tests/              headless behavioural checks
logger.py           event/position logger (not wired in yet)
run_sim.py, run_participant.py   stubs for later phases
```

## Phases
0. Design: task split, approval from instructor
1. Foundation: `config.py`, `logger.py`, structure
2. Headless `game.py` with fixed timestep and seeding
3. Agent interface + discrete human action symbols
4. Scripted human, routine change, reactive + anticipatory agents, `run_sim.py`
5. Participant wrapper, pilot, freeze conditions, data collection
6. Analysis and paper

## Run
```
pip install -r requirements.txt
python main.py                                   # scripted robot
python main.py --robot none --layout far         # preview a layout
```
Layouts: `scripted | shared | near | far | mixed | swap`.
Controls: WASD move, E interact, hold SPACE chop, B robot on/off, P pause,
R restart, ESC quit.
