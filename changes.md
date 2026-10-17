# Changes made to CookingAgents

## Divided meal-period experiment (16 October 2026)

The default CLI now uses the existing divided `reactive` kitchen for both robot
conditions. Exactly six dishes are generated: cheese/ham sandwiches,
tomato/potato soup, chicken with potatoes, and meat with vegetables. Missing
dispensers are added to the existing map; the divider, handoffs, starts and
robot equipment are preserved. Both conditions share preparation, cooking,
movement, a 0.5-second startup delay, collision, scoring and duration rules.

Breakfast, lunch and dinner last exactly 60 active game seconds each. New
orders follow an 80/10/10 category distribution with equal within-category
selection. A dedicated seeded RNG precomputes all fourteen scheduled orders;
full queues retain pending arrivals FIFO, record delays and never resample.
Robot constructors and updates receive allowlisted current observations with
no future schedule, engine reference, seed, RNG or logging interface.

The existing anticipatory model learns starters for the new recipes and
recognizes human deliveries; it can prepare plates and preposition at inferred
handoffs. It cannot fetch across the divider or use the old shared-kitchen
takeover there. Reactive work depends only on current deliveries/inventory.
New recipe logistics are shared through a small compatibility module rather
than duplicating them across the old planners. Legacy algorithms and fixtures
are preserved, with historical CLI gameplay behind `--legacy`.

Added per-order CSV ledgers with timing, outcome and pairing metadata, meal
periods in event logs, and microsecond run IDs. Fixed snapshots to capture
actual human E-key interactions. Existing position/action metrics remain.
See `overcookedAI/EXPERIMENT.md` for recipes, commands, exact schedule/queue
semantics, files and limitations. All changes are local and uncommitted.

Verification: all 135 tests passed (113 existing unchanged plus 22 new), with
no failures or skips. Headless UI checks covered all meal periods and six dish
types. Human usability/efficacy trials have not been performed.

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

The latest code verification passed all **65 tests**. These cover complete salad
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
- Learning full human action sequences; the current model learns only the first
  ingredient choice.
- Fixed and dynamic `h`, representing the estimated time until the human next
  changes the shared counter. This should not be confused with the short
  projection of character movement.
- Experimental CSV logging, collaboration metrics, a routine-change protocol,
  the experiment, and the research report. The current tests do not replace an
  HRC experiment.
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
