# Project 1: Anticipatory Collaboration in an Overcooked-Inspired Kitchen

The code requires **Python 3.10+**. On Windows, use Python 3.11 for the existing
pygame requirement; pygame 2.6.1 has no Windows wheel for Python 3.14.

## Six-dish divided-kitchen experiment

### Standalone Windows executable

Double-click `dist/CookingAgents.exe` in the repository root. This single-file
Windows x64 build includes Python, libraries and music. With Logging ON, sessions
create `logs` beside the executable, independent of the working directory.
Keep the executable in a writable folder. See [BUILDING.md](BUILDING.md) for
rebuild instructions and verification details.

### Graphical startup in PyCharm

Open **`overcookedAI/launcher.py`**, right-click in the editor and choose
**Run 'launcher'**. No script arguments are needed. Use a Python 3.10+ interpreter
with this project's `requirements.txt` installed. Logs are saved in `logs` beside
the game files (or beside the executable in a packaged build), regardless of the
working directory. Do not set
`SDL_VIDEODRIVER=dummy` in the interactive run configuration.

Select Reactive, Anticipatory or Adaptive Anticipatory, enter your participant ID,
toggle logging below that field, then click **START GAME**. The launcher always
uses Divided Kitchen, seed 42 and 180 active seconds; these settings are not
editable in the menu. The right panel explains the task, ingredient preparation,
handoff counters and controls. Defaults are Reactive and logging enabled. **MAIN MENU** or
**Esc** returns from a running or finished game. Every new start and R restart
creates fresh robot state, including adaptive preferences. Closing the window exits.

After playing with all three robot types, use **Open questionnaire and upload logs**
below the menu panels. It opens the study form in your default browser. Complete
the questionnaire using the same Participant ID and upload the files from `logs`
beside the game. Uploading is manual; clicking the link does not send game data.

Music starts automatically during play and loops. Press **M** to turn it off/on;
your choice is retained between sessions while the application stays open.
Pausing with **P** also pauses music, and music stops on the end screen or when
returning to the menu. The bundled track is `assets/music/background.mp3`, loaded
relative to the game files. If audio is unavailable, gameplay continues silently.

Adaptive Anticipatory adds session-local, decaying handoff-style frequencies to
the existing anticipatory planner. It distinguishes individual ingredients,
prepared ingredients and completed dishes. Ingredient placements are provisional
until the robot actually picks them up; human withdrawals and unexplained
removals do not train these preferences. After repeated completed-sandwich
handoffs it prepares to receive the finished dish; recent ingredient handoffs can
reverse that expectation. Current visible completed dishes override predictions
for both anticipatory variants. Standard Anticipatory retains its existing action
prediction without this collaboration-preference model.

Shared Kitchen, No Robot and fixed/dynamic horizon robots remain available through
the existing CLI for compatibility. Adaptive Anticipatory's CLI identifier is
`adaptive_anticipatory` and requires Divided Kitchen. GUI logs use the entered
participant ID (default `P001`). CLI runs retain their configuration options.

`menu.py` contains recipe/schedule definitions; **`launcher.py` is the graphical
entry point**. `main.py` remains the existing CLI entry point for automated runs.

### Command-line startup

Run from this folder with Python 3.10+ and `requirements.txt` installed:

```powershell
python main.py --robot reactive --layout divided --seed 42 --participant P01 --condition reactive
python main.py --robot anticipatory --layout divided --seed 42 --participant P01 --condition anticipatory
python main.py --robot adaptive_anticipatory --layout divided --seed 42 --participant P01 --condition adaptive_anticipatory
```

Both conditions use the same layout, preparation rules and seeded arrivals. Sessions
last 180 active seconds; P pauses the game clock. Breakfast is 0–60 seconds, lunch
60–120, and dinner 120–180. New orders select the current category with probability
80%, each alternative with 10%, then either dish equally. Scheduled arrivals from
already finished meal categories are skipped. At 60 seconds breakfast orders are
cancelled immediately; at 120 seconds lunch orders are cancelled; dinner orders
are cleared at 180 seconds. The current yellow priority order at each boundary
is exempt from that cleanup, so it can still be completed. Its normal timer and
expiry penalty remain active. Orders for future meals may remain visible. These
meal-end cancellations have no score penalty and are logged as `order_cancelled`
with reason `meal_end`; ordinary timer expiry still incurs its usual penalty.

| Period | Dish | Ingredients | Preparation |
| --- | --- | --- | --- |
| Breakfast | Cheese Sandwich | Bread + Cheese | Assemble on a counter |
| Breakfast | Ham Sandwich | Bread + Ham | Assemble on a counter |
| Lunch | Tomato Soup | Tomato + Water | Chop tomato; cook 2 seconds; plate |
| Lunch | Chicken Soup | Chicken + Water | Cook 3 seconds; plate |
| Dinner | Chicken with Potatoes | Chicken + Potato | Chop potato; cook 4 seconds; plate |
| Dinner | Pasta with Tomatoes | Pasta + Tomato | Chop tomato; cook 5 seconds; plate |

Use E to collect, deposit, assemble, plate and serve; hold SPACE at a board to chop.
To return a raw ingredient, approach its matching supply and press E again
(for example, return tomato to Tomato). Other ingredients, chopped items and
finished dishes are not accepted by that supply. Returns free your hands without
changing the score and are logged as `put` at the supply, not as trash or handoffs.
Deliver ingredients through either purple handoff counter. There is exactly one
human-owned supply per ingredient in both kitchens. Robots cannot collect from
crates. The human can chop tomato/potato before delivery, or deliver them raw for
the robot to process. Divided Kitchen separates human preparation from robot
processing, cooking, assembly and serving. Shared Kitchen keeps the workspace
open and allows the human to use the processing stations too.

Reactive processes current delivered supply without predicting human intentions.
Anticipatory uses visible carried items, movement and the existing intention model
to predict a recipe, stage a plate, approach the likely handoff and process a
supplied complementary ingredient before the full recipe has arrived. It replans
when the human changes direction or recipes, limits duplicate staging and recovers
incompatible pot contents. Neither robot reads future orders.

Ingredient colors and short labels are consistent across crates, carried items,
counters and pot contents. Processing stations use separate colors; handoffs are
purple. Each layout has two pots, one plate supply and one serving station, plus separate
human preparation and robot processing boards.

Robots prefer a compatible started batch and can use the other pot when one
contains an unrelated ingredient. An accessible compatible pot takes precedence
over clearing the unrelated batch. Ingredients split across two compatible pots
can be consolidated into one batch. The current executable includes both pots
and meal-end cleanup with preservation of the yellow priority order.

There are three orders at time zero and one every 15 active seconds through 165.
Arrivals are generated before play with their own seeded random generator. The
previous four-order cap does not apply to this schedule: skipping arrivals when
busy would change experimental exposure. The robot planners never read the
schedule. Use the same seed in paired conditions; do not mix recipe filters or
game-time overrides between trials. `--recipe cheese_sandwich` and the other recipe
IDs in `menu.py` are available for isolated practice.

All changes are local. See `IMPLEMENTATION.md` for verification results, changed
files and commands for the bundled Python runtime on this computer.

## Archived prototype behavior

The sections below describe the historical salad/tomato-onion prototype, not the
active six-recipe game. Obsolete recipe CLI filters are disabled. Historical
regression fixtures explicitly use `GameState(..., legacy_menu=True)` to preserve
old mechanics and geometry; this is not a launcher option. Normal sessions use
the six recipes above. The `scripted` CLI robot name now uses delivered-supply
reactive execution for the active menu.

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

### Learning transitions between human actions

Both agents use `human_transitions.py` to learn a first-order model from completed
human actions: taking, putting, finishing chopping, adding to a pot, scooping,
combining, serving and discarding. Each symbol includes the action, item and
station type. Game rules emit successful actions exactly once, independently of
CSV logging. Idle frames, failed interactions and robot actions add no samples.

For each recipe the model estimates
`P(next action | previous action, recipe)` from transition counts. Unknown rows
have no forecast. Ties favour the latest observed outcome. Transitions never
cross order boundaries, serving, or a detected priority-context interruption.
History accumulates for one game and resets with R; there is no forgetting.

The anticipatory agent can use a learned next action to choose the human's next
station and prepare complementary work before the human's next ingredient
pickup. By default a row needs at least two observations and a most likely
outcome of at least 60% (`TRANSITION_MIN_SAMPLES` and
`TRANSITION_MIN_PROBABILITY`). Incompatible carried items, unavailable targets,
or subsequent movement away from the forecast cause a fallback to current-state
rules. A new completed action starts a new forecast rather than treating the
movement that led to that action as evidence against the next goal.

The reactive agent learns and displays the same forecasts for observation only.
Its task selection does not use them, preserving a reactive baseline. The screen
labels its forecast `Observe only`; the anticipatory intent panel labels learned
goals with their row frequency and sample count. These frequencies are not
calibrated prediction accuracy.

Repeat a routine such as taking tomato, putting it on a board, chopping, taking
the chopped tomato and delivering it to a counter across at least two orders.
When that source action recurs, the learned destination can replace the rule
guess. Both modes use the existing launch commands; no additional flag is needed.
CSV `human_transition` rows record forecasts, row distributions, sample counts,
and prediction outcomes scored before the new observation updates the model.

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
python main.py --robot anticipatory --recipe salad --seed 0
python main.py --robot anticipatory --recipe soup --seed 0
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
Rule confidence percentages are heuristic scores; learned intent percentages
are conditional transition frequencies, not measured prediction accuracy.

This prototype combines rule-based goal inference with learned starter frequencies
and first-order human action transitions. Higher-order sequence models, forgetting,
and integration of `h` into the shared-kitchen anticipatory policy remain future
work. The separated-kitchen timing variants below implement fixed/dynamic `h`
and a local scheduling cost. CSV logging is enabled by default. A controlled
policy comparison should use the same kitchen and movement rules for both agents.

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
### Divided kitchen (reactive baseline)

Run the reactive robot in the divided kitchen:

```powershell
python main.py --robot reactive --layout divided --seed 0
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
It never fetches ingredients from the human side or takes over after human
inactivity. A separate observational transition model learns human action patterns
but its forecasts do not affect policy decisions. The human's body is used only
for collision avoidance. `--robot reactive` defaults to this map; other layouts
are rejected. Add `--recipe salad` or `--recipe soup` to restrict orders.
Use `--robot none --layout divided --no-log` to preview the map without a robot.

The interface shows the task, target, recipe and route. Transition diagnostics
are included in the normal CSV logs; add `--debug-agent` for console diagnostics
(see `LOGGING.md`). B toggles the robot and R starts a fresh game.

Comparing this separated kitchen with anticipatory mode in the shared kitchen
changes both layout and policy; a controlled policy comparison needs the same
layout for both agents.

### Anticipatory robots with fixed and dynamic h

Run these commands from `overcookedAI/` in the activated environment:

```powershell
python main.py --robot reactive --seed 0
python main.py --robot anticipatory_fixed_h --fixed-h 4 --seed 0
python main.py --robot anticipatory_dynamic_h --seed 0
```

All three use the same `divided` layout and initial order schedule for
the same seed. The ordinary `reactive` mode remains the observation-only control.
The two new modes extend its cooking policy with preparation before an expected
handoff. They never fetch ingredients from the human workspace or take over after
human inactivity. Once supplies are available, productive cooking work takes
precedence over speculative preparation.

`h` is the estimated remaining game time until the human next changes a shared
counter, through a placement or pickup. It is separate from the shared-kitchen
agent's five-second inactivity timeout.

- **Fixed h:** starts at 4 seconds by default and counts down after a completed
  human action. Movement alone does not restart it. `--fixed-h` accepts a finite,
  positive number of seconds, only with `anticipatory_fixed_h`; R preserves that
  setting. After expiry the value stays zero until another observed action.
- **Dynamic h:** estimates collision-aware walking distance divided by observed
  walking speed, plus remaining chopping and interaction time. Those times adapt to
  the player's pace within one game, per situation (`take:crate`, `put:board`,
  `take:board`, `put:counter`, ...): each completed human action gives a handling
  time (gap since the previous action minus the walking time between the two
  stations), and chopping gives a factor on the nominal chop time. Estimates start
  at the 0.2 s default, shrink towards observed means, and reset with R; nothing is
  stored between games. It
  refreshes as the human moves or changes preparation stage. Supported transition
  predictions can identify an upcoming crate pickup, board visit or counter
  pickup; current carried items and observed board work also provide evidence.
- Without evidence for an accessible handoff, both modes display `unknown` and
  wait. These estimates assume the human continues the inferred task. A pause
  freezes game time; an inactive human does not trigger autonomous cooking.

For an expected ingredient delivery, the robot chooses between approaching the
handoff and fetching one plate, storing it on its own counter, then approaching
the handoff. It avoids fetching another plate for an incoming plated ingredient
or finished dish. For each candidate duration `T`, the local score is
`max(0, h - T) + 2 * max(0, T - h)`: estimated robot idle time plus a weighted
handoff lateness penalty. The lowest score wins; ties favour approaching the
handoff. Forecast counter pickups are tracked but do not trigger this delivery
preparation policy. Predicted supplies never become usable before actual delivery.

The 4-second default, 0.2-second interaction estimate and lateness weight 2 are
pilot parameters in `config.py`, requiring calibration before an experiment.
This score is a local scheduling proxy, not measured human waiting or an optimal
cost over all future tasks. Walking speed uses cumulative movement observations;
there is no forgetting. The bottom panel shows the current `h` and evidence source.
CSV `h_config` and `horizon` rows record parameters, estimates and candidate costs
(see `LOGGING.md`). Prefetching and approaching a forecast handoff count as
anticipatory actions; supplied cooking work remains reactive.

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
layouts.py          selectable layouts: scripted, shared, divided, near, far, mixed, swap
game.py             game logic: stations, orders, player, rules, scoring
render.py           all pygame drawing
robot_base.py       common robot interface
scripted_robot/     original robot (works, scripted layout only)
reactive_robot/     delivered-items baseline and fixed/dynamic-h scheduling variants
robot_tasks.py      shared task description and game-rule execution
anticipatory_robot/ goal inference, learned starter frequencies, cooperative planner
human_transitions.py shared human action events and first-order transition learning
human_horizon.py    fixed countdown and dynamic human handoff-time estimates
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
python main.py                                   # scripted robot
python main.py --robot none --layout far         # preview a layout
```
Layouts: `scripted | shared | divided | near | far | mixed | swap`.
Controls: WASD move, E interact, hold SPACE chop, B robot on/off, P pause, M music on/off,
R restart, ESC quit.
