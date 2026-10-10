# Changes made to CookingAgents

Status as of 10 October 2026. This document describes the features added while
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
even while the human stands still. It leaves the predicted human contribution
to the human, while making use of ingredients already delivered to the kitchen.

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

The latest code verification passed all **53 tests**. These cover complete salad
and soup preparation, a moving human, changes in priority and division of work,
incorrect forecasts, collisions, startup after 0.5 seconds, and restart.
Program startup, rendering without a window, and the original scripted robot's
behaviour were also checked.

```powershell
# From the overcookedAI folder:
python -B -m unittest discover -s tests -v
```

## 9. Remaining work

- A complete reactive agent for comparison in the same kitchen with the same
  movement rules; `reactive_robot/` currently remains a stub.
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
