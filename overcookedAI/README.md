# Project 1: Anticipatory Collaboration in an Overcooked-Inspired Kitchen

The code requires **Python 3.10+**. On Windows, use Python 3.11 for the existing
pygame requirement; pygame 2.6.1 has no Windows wheel for Python 3.14.

## Current experiment: divided kitchen and three meal periods

```powershell
python main.py --robot reactive --seed 42
python main.py --robot anticipatory --seed 42
```

Both conditions use the same existing divided kitchen, six simple recipes,
180 seconds of active gameplay and an identical precomputed schedule per seed.
Breakfast/lunch/dinner each last 60 seconds with 80/10/10 category probabilities.
The robot observations contain current orders only, without the engine schedule,
seed or RNG. See [EXPERIMENT.md](EXPERIMENT.md) for recipes, exact commands,
queue-delay rules, logs, verification and compatibility notes.

The historical sections below describe the preserved salad/soup game and
require `--legacy`. They are not the new six-recipe experiment.

## Historical prototype: shared kitchen, salads and soups

```powershell
# From this folder, activate the environment created with Python 3.11:
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py --legacy --robot anticipatory --seed 0
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
While you remain active, it prepares its contribution and leaves the predicted
human ingredient to you.

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

### Taking over after 5 seconds of human inactivity

After 5 seconds without human activity, the robot stops relying on the predicted
human contribution and completes the most urgent order itself. It uses existing
ingredients, fetches and prepares missing ones, plates and serves the dish, then
continues with the next priority order if you remain inactive. The bottom panel
shows `Human idle` and the time since your last activity.

Movement, attempted movement against an obstacle, E interactions, and actual
chopping count as activity. Observed position and carried-item changes also reset
the timer. Standing still while chopping is therefore not considered inactivity.
The timer uses game time, so pausing does not advance it. The timeout is configured
by `HUMAN_IDLE_TIMEOUT` in `config.py`.

When you resume activity, the robot immediately returns to cooperative planning
and adjusts to your carried ingredient. It still avoids your body and occupied
stations. Ingredients held by an inactive human are not available to the robot;
it can fetch its own portion rather than waiting indefinitely for delivery.
In autonomous soup preparation it keeps one pot's batch separate from other pots.
Robot-only work does not add observations to the learned human starter history.

To isolate one recipe during testing:

```powershell
python main.py --legacy --robot anticipatory --recipe salad --seed 0
python main.py --legacy --robot anticipatory --recipe soup --seed 0
```

The robot infers your likely next station from the carried item, station contents
and movement direction. It can start the complementary ingredient while you
approach a crate, before pickup. While you handle one ingredient it prepares the
other, fetches a plate, assembles and serves the dish. It avoids occupied stations,
routes around your body, and gives way at close contact. It does not prepare a
complete meal from scratch while you remain active: it leaves the predicted human
contribution to you, while using delivered ingredients to finish dishes. After
the inactivity timeout, it can complete the whole meal itself.

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
human choice, priority changes, and restarting the game. Inactivity checks cover
the exact timeout, movement and interaction resets, stationary chopping,
autonomous completion of both recipes, consecutive orders, separate pot batches,
and returning to collaboration.

## Overview
### Separated reactive kitchen

Run the reactive robot in the divided kitchen:

```powershell
python main.py --legacy --robot reactive --layout reactive --seed 0
```

A solid divider runs across the entire playable height. Two purple handoff
counters interrupt the wall, each holding one item and reachable from both
sides. The human has all three ingredient crates, two boards and a trash bin.
The robot side has a board for raw deliveries, a pot, plates, two work counters,
a serving station and a trash bin. The human can deliver raw or chopped
ingredients; salad requires tomato and lettuce, soup requires tomato and onion.
Neither agent can walk into the other workspace.

Collect tomato and lettuce for salad, or tomato and onion for soup. Use E to
leave each raw or chopped ingredient on either empty purple handoff counter.
The robot collects and chops raw deliveries, assembles salads or cooks soup,
fetches a plate and serves. It continues across orders without restarting.
You may remain beside a handoff: each teammate uses their own side.

Orders with all required ingredients currently available take precedence, with
the earliest deadline breaking ties. Otherwise, the robot prepares available
ingredients for the earliest actionable order. It leaves duplicates for later
orders and does not plate a lone salad ingredient, keeping chopped tomato
available for either recipe until the second ingredient arrives. Missing
ingredients or access cause waiting or selection of another available task.
Leftovers from expired orders can be cleared off the board and stored to make
room for new raw deliveries; they are not discarded automatically.

The policy uses current orders, station contents and carried robot items only.
It never fetches ingredients from the human side, infers human intent, learns
preferences or takes over after human inactivity. The human's body is used only
for collision avoidance. `--robot reactive` defaults to this map; other layouts
are rejected. Add `--recipe salad` or `--recipe soup` to restrict orders.
Use `--robot none --layout reactive --no-log` to preview the map without a robot.

The interface shows the task, target, recipe and route. Transition diagnostics
are included in the normal CSV logs; add `--debug-agent` for console diagnostics
(see `LOGGING.md`). B toggles the robot and R starts a fresh game.

Comparing this separated kitchen with anticipatory mode in the shared kitchen
changes both layout and policy; a controlled policy comparison needs the same
layout for both agents.

A human and an autonomous robot cook together in a custom Pygame kitchen.
The shared-kitchen prototype above is the current development focus. Older
separate-station maps remain available as previews for a possible later study.

## Research question
Current direction: does anticipating a human teammate's goals improve task
coordination and reduce blocking in a shared kitchen? Forgetting and changing
routines remain possible later extensions, outside the first prototype.

## Structure
```
main.py             experiment entry point / main loop (--legacy for old modes)
recipes.py          six experiment recipes and simple preparation rules
experiment.py       seeded engine schedule and restricted robot observations
meal_policy.py      shared new-recipe compatibility for both robot architectures
config.py           constants and the original station layout (pixels)
layouts.py          selectable layouts: scripted, shared, reactive, near, far, mixed, swap
game.py             game logic: stations, orders, player, rules, scoring
render.py           all pygame drawing
robot_base.py       common robot interface
scripted_robot/     original robot (works, scripted layout only)
reactive_robot/     divided-kitchen robot using delivered items and current orders
robot_tasks.py      shared task description and game-rule execution
anticipatory_robot/ goal inference, learned starter frequencies, cooperative planner
navigation.py       body-aware A* paths, movement projection costs, contact recovery
tests/              headless behavioural checks
logger.py           CSV events, positions, decision diagnostics and run summaries
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
python main.py --legacy --robot scripted          # original scripted robot
python main.py --legacy --robot none --layout far # preview an old layout
```
Layouts: `scripted | shared | reactive | near | far | mixed | swap`.
Controls: WASD move, E interact, hold SPACE chop, B robot on/off, P pause,
R restart, ESC quit.
