# Changes made to CookingAgents

## Return raw ingredients to their supplies (25 October 2026)

- Pressing E at a matching supply while carrying its raw ingredient returns it
  and frees the human's hand. Other ingredients, chopped items and finished
  dishes are not accepted. Robot access restrictions remain unchanged.
- Returns emit successful human `put` events and CSV rows at the supply, without
  changing score or counting as trash/handoffs. Learned return transitions are
  feasible intent targets. Added the control to menu and in-game instructions.
- All 235 source tests pass, covering all ingredients, incorrect returns,
  robot restrictions, learned goals and logging. Packaged self-check now includes
  actual E-key pickup/return for all eight supplies.
- Rebuilt `dist/CookingAgents.exe`; the actual binary passed isolated checks for
  all eight returns, three robot modes, two-pot cooking, music and CSV output.

## Refresh standalone executable (25 October 2026)

- Rebuilt `dist/CookingAgents.exe` with the current Python source, including meal
  cleanup, preservation of the yellow priority order and the second cooking pot.
- Extended the packaged self-check to verify the meal boundary and complete a
  meal using the second pot while preserving an unrelated first-pot ingredient,
  for Reactive, Anticipatory and Adaptive Anticipatory.
- The actual EXE passed isolated checks without Python on PATH, including music,
  restart/menu return and six CSV recordings plus summary beside the executable.
  The latest source suite passed 230 tests. Participant logs were not modified.

## Second cooking pot (Python only, 25 October 2026)

- Added Cook 2 between Plates and Serve in the robot processing area. Both
  experiment kitchens now have two pots; legacy fixtures retain their layouts.
- Robots use another compatible pot before disturbing an unrelated batch and
  prefer a compatible started batch to an empty pot. Split ingredients can be
  consolidated into one stable batch without switching targets every frame.
- Added checks across Reactive, Anticipatory and Adaptive Anticipatory for
  alternate-pot cooking, preserved unrelated contents, batch consolidation and
  access to both pots. Single-pot recovery remains covered by a dedicated fixture.
- Python source only; the existing EXE has not been rebuilt.
- Validation: all 230 tests pass; checked rendering and both pot approaches.

## Preserve the current order at meal changes (Python only, 25 October 2026)

- Meal-end cleanup now preserves the exact yellow priority order selected at
  the boundary. Other orders from finished meals are cancelled as before.
- The exemption persists on later frames rather than being reassigned each
  update. The preserved order can be served or expire with its normal penalty.
- Added checks for stable exemption, ordinary expiry, successful boundary-frame
  serving and cancellation of non-priority orders. The EXE is not rebuilt.

## Remove orders when their meal ends (Python only, 25 October 2026)

- Cancel breakfast orders at 60 active seconds, lunch at 120 and dinner at 180,
  before the robot can act on them on a boundary-crossing update.
- Skip later arrivals from finished meal categories while preserving the seeded
  schedule and allowing future-meal orders. Legacy-menu behavior is unchanged.
- Meal-end cancellations do not incur missed-deadline penalties. CSV records
  `order_cancelled` with reason `meal_end`, separately from expiry or serving.
- Added checks for exact boundaries, large time steps, future/late arrivals,
  score handling, robot actions and CSV/summary classification.
- Validation: all 225 tests pass. The existing EXE's SHA-256 hash is unchanged.
- The executable was not rebuilt; this change applies to Python source only.

## Standalone Windows executable (25 October 2026)

- Built `dist/CookingAgents.exe`, a single Windows x64 executable containing
  Python, dependencies and music. Participants can run it without installing
  Python or packages. The existing frozen-output path creates logs beside it.
- Added `CookingAgents.spec`, pinned build requirements, `build_exe.ps1` and
  `BUILDING.md` so the binary can be rebuilt after source changes.
- Added an optional offline `--self-check` diagnostic for packaged verification.
  Normal startup still opens the menu. Tests use a separate copy so diagnostic
  logs do not mix with participant results.
- Validation: all 219 source tests pass. The actual EXE passed isolated playback,
  three-robot startup, mute/pause/restart, menu return and CSV/summary checks with
  Python removed from PATH. Logs were created beside the copied executable,
  not in its unrelated working directory.

## Questionnaire link and stable log location (25 October 2026)

- Added a clickable questionnaire link below the menu panels and existing
  captions, with instructions to play all three robots and upload the log files.
  The form opens in the default browser; uploads remain manual.
- Default logs now go beside the source game files, or beside the executable in
  a frozen build, rather than depending on the current working directory.
  Explicit output folders and Logging OFF retain their existing behavior.
- All 26 launcher/logging/experiment checks pass, including link activation,
  browser failure handling and source/frozen output paths. Menu rendering checked.

## Gameplay music (25 October 2026)

- Added the supplied MP3 as `overcookedAI/assets/music/background.mp3` and a
  small music controller. The track loops during gameplay at 30% volume.
- M toggles music without affecting gameplay or recording; mute choice persists
  across restarts and sessions within the application. P also pauses/resumes audio.
  Music stops at game over, on returning to the menu, on quit and on session errors.
- Added the M shortcut to both the main-menu guide and in-game instructions.
  Missing audio devices or unavailable tracks do not prevent gameplay.
- Added real MP3 decoding/playback checks with SDL's silent driver, including
  working-directory independence, muting, pause, restart and session cleanup.
- Validation: all 215 tests pass.

## Simplified participant menu (25 October 2026)

- Removed layout, seed and duration controls from the graphical launcher.
  Sessions always use Divided Kitchen, seed 42 and 180 active seconds.
- Moved the Logging ON/OFF button below Participant ID. Robot selection and
  participant-ID editing remain available.
- Replaced the previous right-side settings with a short task and controls guide,
  including order urgency, ingredient collection, preparation and handoffs.
- Updated launcher checks for fixed settings, participant validation, logging and
  repeated sessions. All six launcher tests pass; rendering was checked headlessly.

## Planner recovery and confirmed-handoff tests (25 October 2026)

- Anticipatory sandwich assembly now checks every accessible robot/shared work
  surface for the complementary ingredient before waiting at a handoff counter.
  This fixes waiting for cheese or ham already available on Stage/Assemble.
- A fully supplied selected cooked recipe can reclaim the only accessible pot
  from an incompatible incomplete batch when storage is available. Recovered
  ingredients are stored for the older order rather than immediately reloaded
  or discarded. A forecast alone does not displace an active batch.
- Cooking ingredients are collected only when a compatible pot can accept the
  prepared item, preventing collection/staging loops and unnecessary pickups
  when the pot is blocked and storage is full.
- Updated the two adaptive-learning tests to confirm ingredient pickup through
  game-rule interactions. Merely placing an ingredient, withdrawing it, or
  removing it without an observable robot pickup does not train preferences.
- Added regression checks for unconfirmed handoffs, preservation of recovered
  chicken, forecast-only batch protection and blocked pots with full storage.
- Validation: all 210 tests pass, including the seven previously failing cases.

## Left-side potato and pasta supplies (25 October 2026)

- Moved Potato and Pasta into the left column below Chicken and above Prep in
  the experiment kitchens. Updated approach points for the three stacked supply
  crates so they are accessed from the open aisle on the right.
- Checked rendering, station reachability and human preparation of all six
  recipes. Full suite: 200 of 207 tests pass; the same seven failures also occur
  with the original layout/navigation, verified separately without changing files.

## Reactive fixed/dynamic h modes (16 October 2026)

- Added `--robot reactive_fixed_h` and `--robot reactive_dynamic_h`. Both use the
  existing separated `reactive` map, cooking policy, human transition model and
  initial order schedule. The ordinary `reactive` baseline stays observation-only.
- Added `human_horizon.py`: `h` estimates remaining game time until a human
  placement or pickup at a shared counter. Fixed h counts down after observed
  human actions; movement and repeated frames never restart it. The default is
  4 seconds, configurable with `--fixed-h`, and preserved on R.
- Dynamic h uses collision-aware route length, observed walking speed, remaining
  chopping and interaction estimates. Carried items, observed board work and
  sufficiently supported learned transitions identify a plausible handoff.
  Missing evidence or inaccessible handoffs produce `unknown`. Estimates are
  conditional on the human continuing the task; there is no forgetting.
- Added `reactive_robot/horizon.py`. Available cooking tasks take precedence.
  Otherwise an expected ingredient delivery can trigger either one plate fetched
  and stored in the robot workspace, or an approach to the predicted handoff.
  Candidate durations T use the local score `max(0, h-T) + 2*max(0, T-h)`.
  Supplies remain unavailable until actual delivery. Incoming plated or finished
  dishes do not trigger an extra plate, and a prefetched plate cannot cause
  premature salad assembly with only one ingredient.
- Both modes can finish raw/chopped salad and soup deliveries without fetching
  human-side ingredients or using the anticipatory agent's inactivity takeover.
  These timing-assisted extensions perform forecast-based preparation, while
  ordinary `reactive` remains the strict reactive control.
- Added live h/evidence to the UI, CLI validation, restart preservation and CSV
  `h_config`/`horizon` JSON diagnostics with parameter values and candidate costs.
  Early preparation uses `anticipating=1`; supplied cooking work remains 0.
  Diagnostic rows do not count as cooking actions.
- Added behavioural checks for countdowns, dynamic routes and chopping, observed
  speed, unknown evidence, cost-dependent choices, available-work priority,
  prefetched plates, moving-human deliveries, both recipes, CLI and logging.
- All **166 tests** pass, including the existing reactive, anticipatory, navigation
  and transition-learning checks.
- The 4-second default, 0.2-second interaction estimate and lateness weight 2 are
  pilot parameters requiring calibration. The cost is a local proxy, not measured
  human waiting or global expected-cost optimisation. Shared-kitchen anticipatory
  h integration and the controlled experiment remain future work.

Launch from `overcookedAI/`:

```powershell
python main.py --robot reactive_fixed_h --fixed-h 4 --seed 0
python main.py --robot reactive_dynamic_h --seed 0
```

## Human action transition learning (16 October 2026)

- Added `overcookedAI/human_transitions.py`, shared by the reactive and anticipatory
  agents. It learns `P(next action | previous action, recipe)` from cumulative
  counts over action, item and station-type symbols.
- Game rules now record successful human pickups, placements, completed chopping,
  pot additions, scooping, combinations, serving and discarding. Failed actions,
  idle frames and robot actions do not train the model. Multiple human actions
  between robot updates are consumed in order, without duplicate frame samples.
- Recipe histories are separate. Order identity, serving and priority-context
  interruptions prevent unrelated episodes from being joined. R clears the
  event stream and history for a fresh game.
- The anticipatory agent uses sufficiently supported, feasible learned next
  actions to infer the next human station and complementary ingredient. Defaults
  require two source-action observations and a most likely outcome of at least
  60%. Current physical evidence can override learned predictions.
- The reactive agent learns the same model for observation and comparison only;
  task selection remains based on currently delivered supplies and orders.
- Added learned forecasts to the UI and `human_transition` JSON updates to CSV
  logs. Forecast evaluation happens before incorporating the observed outcome.
  Transition rows do not count as robot cooking actions.
- Added 26 tests covering normalised probabilities, recipe and episode boundaries,
  prediction updates, no training from robot actions, real human routines,
  anticipatory policy use, reactive policy independence and logging.
- At that stage, all **139 tests** passed. Fixed/dynamic `h`, forgetting and expected decision-cost
  optimisation are outside this change. This is a first-order model, not a model
  conditioned on an entire action history.

## Working divided-kitchen reactive agent (13 October 2026)

Implemented `ReactiveRobot` for `--layout reactive` without altering the map.
The human supplies raw or chopped ingredients through either shared counter.
The robot collects, chops, assembles salads, cooks soup, plates and serves using
its own equipment. It continues across orders and responds to changing urgency,
withdrawn deliveries, duplicates and blocked approaches. Fully supplied recipes
are prioritized by deadline; otherwise it prepares available ingredients for
the earliest actionable recipe. A lone tomato is not plated before the salad
ingredients are available, so it remains usable for soup if onion arrives.

No human intent recognition, starter learning, predicted movement or autonomous
ingredient fetching is used. The existing collision-aware navigator is reused,
with right-side approaches to the handoff counters. Task execution is shared
with the anticipatory agent through `robot_tasks.py`; anticipatory planning
remains separate. Tasks, targets and routes appear on screen. Existing CSV
diagnostics and `--debug-agent` support the reactive robot, whose logged actions
always have `anticipating=0`.

Launch from `overcookedAI/`:
`python main.py --robot reactive --layout reactive --seed 0`.

## Unexpected stopping and decision diagnostics (13 October 2026)

Fixed a moving-human replan loop that repeatedly consumed the zero-length start
waypoint without advancing. Route starts now use the continuous agent position;
zero-length waypoints are consumed before movement, and a moving human does not
invalidate a still-clear route every frame. Safety-buffer fallback considers the
continuous position as well as the visible body. Fractional contact bookkeeping
is aligned to the unchanged body only when needed to leave a valid contact.

Station selection now checks reachability with cached route checks. Unreachable
stored ingredients no longer suppress reachable preparation. A retained task
with no navigation progress is reconsidered after 0.7 seconds, human reservations
allow selecting other work, and blocked owned/reassignment boards no longer
short-circuit the rest of the planner. An inaccessible empty soup pot can be
reselected; started batches remain together. Removed stations invalidate tasks.

Added transition-based JSON diagnostics to the existing CSV event log and
optional terminal diagnostics via `--debug-agent`. Regression tests cover moving
humans, subpixel counter contact, unreachable targets and inventory, alternative
tasks, invalidation, resumption, and distinguishing intentional waits from failed
routes. Existing collision, recovery, learning and collaboration tests remain.

## Navigation contact recovery (13 October 2026)

Fixed anticipatory-agent deadlocks at walls, furniture and human contact.
The padded navigation geometry previously rejected valid starts at obstacle
edges, sideways recovery was excluded, and the regular grid could miss narrow
escape lanes. Navigation now falls back to full-body collision geometry when
the start is inside the comfort buffer, permits edge sliding, and includes the
current position's row and column in A*. Rounded movement is checked against
physical obstacles before applying it. The robot never teleports or crosses
furniture or the human.

Sideways contact recovery is allowed. Failed routes are retried every 0.35 seconds
or immediately when obstacle geometry changes. No progress for 0.7 seconds is
reported as a blocked path; the current task remains available for resumption
and normal task validation continues. Truly trapped robots wait safely.
Ten new regression tests cover corners, each counter edge, human pressure,
temporary blockage, bounded retries and task completion after escape.

## Separated reactive map (13 October 2026)

Added `--layout reactive` with physically separated human and robot workspaces
and two shared one-item handoff counters. All ingredient crates are on the human
side; the robot side supports chopping delivered raw ingredients, assembling
salads, cooking soup, plating and serving. Walls participate in player collision
and A* navigation and are shown in the renderer. Preview with
`python main.py --robot none --layout reactive --seed 0 --no-log` from
`overcookedAI/`. The reactive policy was implemented subsequently as described above.

Status as of 13 October 2026. This document describes the features added while
developing the human–robot collaboration prototype in `overcookedAI/`.

## 1. Shared kitchen and anticipatory agent

- Implemented a working `AnticipatoryRobot`, replacing the previous stub.
- Added the `shared` layout, which uses the existing kitchen geometry and makes
  the equipment accessible to both teammates.
- The `--robot anticipatory` mode selects this shared kitchen by default.
- The robot performs tasks that complement the human's work: fetching and
  chopping the second ingredient, preparing a plate, finishing and serving dishes.
- Ingredient roles can be reversed: the human can start with tomato, lettuce,
  or onion, depending on the recipe.

## 2. Recognising the human's current intent

The robot estimates the human's next station and action from the carried item,
station contents, and movement direction. It can start preparing the complementary
ingredient while the human approaches a crate, before pickup.

A short movement projection was also added to help the robot avoid the human.
Current goal recognition uses rules; the displayed confidence percentages are
heuristic values rather than measured model accuracy.

## 3. Salads, soups, and order priority

- Anticipatory mode supports both recipes. The initial order list guarantees
  that salad and soup are present; subsequent orders are generated randomly.
- Extended robot collaboration to soup: chopped tomato and onion go into one
  pot, the robot waits for cooking, scoops the soup onto a plate, and serves it.
  This uses the game's existing pot and cooking mechanics.
- The human can deliver a chopped ingredient to a counter or directly to a pot
  containing the complementary ingredient.
- The active order with the least remaining time has priority. List order breaks
  ties, and expired orders are ignored.
- The robot continuously checks priority and changes its plan when the most
  urgent recipe changes. It stores carried ingredients that are not currently
  needed.
- Serving a dish fulfils the most urgent matching order. A finished dish already
  carried by the robot can also be served when the other recipe has higher
  priority.

Example: when the human starts with tomato, the robot prepares lettuce for the
most urgent salad or onion for the most urgent soup.

## 4. Learning starter choices and beginning subsequent orders

Added a simple frequency model for the human's first observed ingredient,
separately for salad and soup. One observation is recorded per order. Additional
frames, chopping, and repeated pickups within the same order do not increase
the counts. Movement predictions and the robot's own actions do not train this
model.

The robot predicts the most frequent starter ingredient, using the most recently
observed choice to break ties. Once an order is completed, regardless of who
served the dish, it can start preparing its part of the next most urgent order
even while the human stands still. While the human remains active, it leaves the
predicted human contribution to them and uses ingredients already delivered to
the kitchen. After the inactivity timeout described below, it can complete the
whole order itself.

The ingredient actually carried by the human overrides the forecast. After an
incorrect prediction, the robot changes the division of work, stores its extra
portion, and clears its chopping board if necessary before preparing the other
ingredient.

History is cumulative, without a forgetting factor. It lasts for one game and
resets when the game is restarted with `R`.

## 5. Autonomous start after 0.5 seconds

- The robot starts working after 0.5 seconds of game time, without waiting for
  the human's first movement. Pausing does not advance this countdown.
- With no history, it assumes the human will prepare tomato and starts lettuce
  or onion according to the most urgent order.
- The initial assumption is shown on screen and is not recorded as an observation
  of human behaviour.
- The human's choice during the countdown can change the robot's first plan.
- The delay applies at launch and restart, but does not repeat for subsequent
  orders. It is configured by `ROBOT_START_DELAY` in `config.py`.

## 6. Navigation and station access

- Added A* navigation that accounts for character dimensions, stations, and
  the human.
- The robot avoids the human and can account for projected human movement when
  choosing a route.
- In anticipatory mode, the human also cannot walk through the robot.
- The robot avoids stations occupied by the human or inferred to be the human's
  destination.
- Added yielding, movement recovery after close contact, and clearing station
  approaches even for a stationary human.
- Tasks are replanned when station contents change or an item the robot was
  approaching is taken.

## 7. On-screen information and running the game

Orders are sorted by remaining time. The most urgent order has a yellow border
and an asterisk. Added blue highlighting for the human's goal, turquoise
highlighting for the robot's goal and route, and a visualisation of projected
human movement.

The bottom panel shows the robot's task, the human's current intent or predicted
starter ingredient, and the priority order. A label such as `2/3 soup starts`
describes the observed choice frequency, not prediction accuracy.

Updated the README files and added an option to restrict orders to one recipe.
Run these commands from `overcookedAI/` with the virtual environment activated:

```powershell
python main.py --robot anticipatory --seed 0
python main.py --robot anticipatory --recipe salad --seed 0
python main.py --robot anticipatory --recipe soup --seed 0
```

## 8. Files and verification

| File or folder | Changes |
| --- | --- |
| `overcookedAI/anticipatory_robot/model.py` | Intent recognition and starter-ingredient history. |
| `overcookedAI/anticipatory_robot/robot.py` | Cooperative planning, priorities, and autonomous preparation. |
| `overcookedAI/navigation.py` | New navigation and yielding behaviour. |
| `overcookedAI/game.py` | Order priority, an initial list containing both recipes, and collisions with the robot. |
| `overcookedAI/config.py` | Recipe ingredients and startup delay. |
| `overcookedAI/layouts.py` | Shared kitchen layout. |
| `overcookedAI/main.py` | Agent startup, layout selection, and recipe selection. |
| `overcookedAI/render.py` | Goals, routes, forecasts, and priority highlighting. |
| `overcookedAI/tests/` | Behavioural tests that run without opening a window. |
| `README.md`, `overcookedAI/README.md` | Documentation of the structure, setup, and current features. |

At that stage, code verification passed all **65 tests**. These cover complete salad
and soup preparation, a moving human, changes in priority and division of work,
incorrect forecasts, collisions, startup after 0.5 seconds, and restart. Additional
checks cover the 5-second inactivity threshold, activity resets, autonomous order
completion, consecutive orders, separate pot batches, and returning to cooperation.
Program startup, rendering without a window, and the original scripted robot's
behaviour were also checked.

```powershell
# From the overcookedAI folder:
python -B -m unittest discover -s tests -v
```

## 9. Remaining work

- A controlled comparison using the same kitchen layout for both policies;
  the reactive robot currently uses the divided kitchen and the anticipatory
  robot uses the shared kitchen.
- Higher-order human sequence models; the current agent learns starter choices
  and first-order transitions, as described in the 16 October update above.
- Integration of fixed/dynamic `h` with the shared-kitchen anticipatory agent.
  The separated reactive variants above already estimate time until a human
  changes the shared counter; this differs from short movement projection.
- Calibration of timing/cost parameters, collaboration metrics, a routine-change
  protocol, the experiment, and the research report. CSV recording is implemented;
  the current tests do not replace an HRC experiment.
- Refining and describing the healthcare scenario, such as helping an older
  adult or a person with limited mobility prepare meals. This currently
  motivates the project rather than introducing separate medical game mechanics.

The forgetting factor has intentionally been left out for now. Collaboration
between two bots and separate work areas remain optional extensions. The
`sense-think-act/` project was not modified as part of the changes described here.

## 10. Autonomous takeover after human inactivity (13 October 2026)

- Added `HUMAN_IDLE_TIMEOUT = 5.0` in `overcookedAI/config.py`.
- The robot tracks game time since the last human activity. Movement attempts,
  E interactions, and actual chopping register activity in `GameState`; observed
  position and carried-item changes also reset the robot's timer.
- After 5 seconds of inactivity, the robot completes the most urgent pending
  order, including work previously reserved for the human, then moves on to the
  next order if the human remains inactive.
- Existing ingredients are reused. Items held by an inactive human are excluded
  from the robot's available inventory, so it can fetch its own missing portion.
- Soup preparation focuses on one pot at a time, preventing ingredients split
  across different pots from being mistaken for one complete batch.
- Inferred human destinations no longer reserve stations during takeover.
  Physical collision avoidance and access checks remain in effect.
- Resumed human activity immediately restores cooperative planning. A conflicting
  robot ingredient can be stored and its board cleared as the roles change.
- The bottom panel displays `Human idle`, the inactivity duration, and the current
  recipe. The original 0.5-second startup delay still applies.
- Inactivity uses game time: pausing does not advance the timer. Autonomous work
  does not train the human starter-choice model.
- Added `overcookedAI/tests/test_inactivity.py` with 12 behavioural tests and
  adjusted earlier cooperative tests to simulate an active human where appropriate.
