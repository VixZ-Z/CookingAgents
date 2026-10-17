# Divided kitchen meal-period experiment

Implemented locally on 16 October 2026. The default CLI now runs the six-recipe
experiment. No commits, branches, pushes or remote changes are needed.

## Run paired conditions

From the `overcookedAI` folder, using a Python environment with `requirements.txt`:

```powershell
python main.py --robot reactive --seed 42 --participant P01 --condition reactive
python main.py --robot anticipatory --seed 42 --participant P01 --condition anticipatory
```

Both default to the existing `reactive` divided layout. You can specify
`--layout reactive` explicitly. Repeat with any integer seed, including 123 or
789. Seed 42 is the CLI default. `--debug-agent` prints decision transitions;
`--no-log` is for unrecorded practice. `--recipe tomato_soup`, for example,
restricts practice orders to one recipe and is not the mixed experiment.

WASD moves, E picks up/puts down/combines, B toggles the robot, P pauses, R
restarts, and Esc ends the trial. Restart uses the same seed and schedule but
clears inventory and robot learning. Paused wall-clock time is excluded.

## Recipes and preparation

Exactly six order types are generated:

| Period/category | Dish | Ingredients | Preparation |
| --- | --- | --- | --- |
| Breakfast | Cheese Sandwich | Bread + cheese | Combine on a counter, then combine with a plate |
| Breakfast | Ham Sandwich | Bread + ham | Combine on a counter, then combine with a plate |
| Lunch | Tomato Soup | Tomato + water | Put both in the cooker, cook for 5 game seconds, scoop with a plate |
| Lunch | Potato Soup | Potato + water | Same cooker sequence |
| Dinner | Chicken with Potatoes | Chicken + potato | Same cooker sequence |
| Dinner | Meat with Vegetables | Meat + vegetables | Same cooker sequence |

The human takes ingredients from the left-side dispensers and places them on
either purple handoff counter with E. Supply **both** required ingredients;
neither robot can cross the divider or fetch left-side ingredients. The robot
collects, assembles/cooks, plates and serves automatically. Chopping is not
required for these simplified recipes; chopped tomato is also accepted. The
leftover chopping boards remain usable work surfaces.

The existing pot is reused as a generic cooker for soups and mains, rather than
adding a grill or redesigning the kitchen. Bread/cheese and other ingredients
have distinct colors and short labels. Unplated sandwiches have a wooden
background; completed dishes have a white plate. Cooker contents, progress and
readiness are visible. Wrong hot-ingredient pairs are rejected.

## Geometry, capabilities and policy differences

The divider, starts, two shared handoffs, robot equipment and collision rules are
unchanged. Two obsolete experiment dispensers are repurposed and six missing
dispensers are added to that existing layout, identically in both conditions.
The historical geometry remains available in explicit legacy mode.

Both robots have identical speed, a 0.5-second startup delay, station access,
recipes, cooking times, scoring and simulation clock. They use the existing A*
navigator and its contact/buffer recovery. Handoffs are approached from the
robot side; left-wall dispensers are approached from the human aisle.

The reactive condition checks current deliveries, robot inventory, cooking
state and visible orders. Fully supplied recipes are preferred by deadline;
otherwise it processes useful partial deliveries. It does not inspect human
intent or learn preferences, fetch ingredients, or act on undisclosed orders.

The anticipatory condition retains its existing intent model and per-recipe
starter-frequency learning, including observed-choice overrides. It prioritizes
visible urgent orders and can prepare a plate and position at the inferred
handoff before delivery. The shared-kitchen complementary-fetch/takeover actions
cannot cross the divider and are therefore unavailable in this experiment.
Learning still resets on restart, and reported confidence is heuristic.

`meal_policy.py` shares only the new recipe logistics and execution adapter;
the two robot classes and their historical planners remain separate. This avoids
copying new six-recipe mechanics into both planners. Leftovers are stored rather
than silently discarded. An obsolete partial cooker batch can be retrieved, and
an obsolete finished batch can be plated/stored to free the cooker. These
capabilities are identical in both conditions.

## Meal periods and scheduling

| Elapsed active game time | Period | New-order category probabilities |
| --- | --- | --- |
| 0 <= t < 60 | BREAKFAST | 80% breakfast, 10% lunch, 10% dinner |
| 60 <= t < 120 | LUNCH | 10% breakfast, 80% lunch, 10% dinner |
| 120 <= t <= 180 | DINNER | 10% breakfast, 10% lunch, 80% dinner |

Within a category, its two recipes are equally likely. Thus the dominant
recipes have 40% probability each and the other four have 5% each. These are
probabilities, not per-session quotas. Existing orders survive period changes.

The engine generates the full schedule on initialization with a dedicated,
local `random.Random(seed)`. Its draws select recipes and the existing 65–90
second order lifetimes. No robot/animation/global-RNG draws affect it.
There are three initial orders at t=0, followed by one scheduled arrival every
15 seconds at t=15 through t=165: fourteen scheduled orders in total.

Capacity remains four active orders. A scheduled arrival that finds a full
queue waits FIFO; it is never replaced or resampled. Its lifetime starts when
it actually appears. Completion speed can consequently change actual appearance
times and visibility, but **not** IDs, scheduled times, recipes or lifetimes.
This distinction is logged and is an expected queue effect in paired trials.
Simulation steps split at arrival, expiry and period boundaries. The session
ends at 180 active seconds, including when a headless update overshoots it.

## Future-order isolation

The schedule and not-yet-visible orders are stored only on the engine's
`GameState`. Both experiment robot constructors and update methods receive
`RobotObservation`, an explicit allowlist of current layout/stations, player,
robot, active orders, score and game time. It has no engine pointer, callback,
seed, RNG, pending queue, future order collection or logging interface.
Active orders may reveal their own past scheduled/appearance times only.

The score container and active gameplay objects are shared so existing game
interactions can still work, without an engine reference hidden in a callback.
Tests inspect the reachable observation object graph and verify the actual
constructor/update inputs. This is an application data boundary, not a security
sandbox against malicious Python introspection or manually rewritten agents.
The legacy API is explicitly outside this experiment boundary.

## Experiment outputs

Existing event/position CSVs and `summary.csv` remain. Event rows add
`meal_period`, and transitions emit `meal_period` events. Human E-key actions
are now included in the before/after snapshot; previously the main loop took
its snapshot after processing E, losing those real UI interactions.

On finish/restart/exit, each experiment also writes `<run>_orders.csv`, one row
per scheduled order, with robot condition, seed, layout, final score, recipe,
order ID, scheduled period/time, actual appearance period/time, queue delay,
completion time, completion duration and outcome. Outcomes are `completed`,
`expired` or `missed` (not completed by session end, including queued arrivals).
Blank times mean the order never appeared/finished. Completion duration is
`completed_at - appeared_at`; queue delay is recorded separately.

Aborted trials have `run_completed=0`; unfinished rows have `censored=1` and
must not be treated as full-duration failures. Logging is engine-side, and
future schedule rows are written only at trial end. Robots never receive them.
Run filenames include microseconds to avoid overwriting fast restarts.

Existing 5 Hz position sampling, action counts, anticipating flags and summary
schema are retained. The `soups` summary counter includes the two new soups;
new sandwiches/mains are counted from the order ledger, not misclassified as
soups. This project does not yet compute a separate functional-delay/concurrent
activity aggregate; existing event/position data remain available for analysis.

## Verification and limitations

Run from this folder:

```powershell
python -B -m unittest discover -s tests -v
```

Focused experiment tests verify exact period boundaries, all six dishes with
both robots, the 80/10/10 distribution over 30,000 samples per period, paired
seeds 42/123/789, update-cadence independence, FIFO delays, future isolation,
station access, legal contact escapes, missing ingredients, learning/resumption,
obsolete batches and complete 180-second logs. CLI tests cover both default
conditions, pause timing and actual E-key event recording. The original 113
tests remain unchanged.

Tests and rendering checks are headless. They do not replace a human usability
pilot or establish a performance advantage for either policy. Finite storage,
missing deliveries or physically blocked stations may require waiting; robots
do not teleport, walk through obstacles or discard food automatically. The
simplified mains use the same pot/cooker timer rather than separate meat and
potato cooking models. No forgetting factor, dynamic h or medical mechanics are
introduced.

Verified on 16 October 2026 with Python 3.12 / Pygame 2.6.1: **135 tests passed**
(all 113 existing tests unchanged, plus 22 new tests). No tests failed or were
skipped. Rendered all three meal-period HUDs and all six dish representations;
CLI startup/rendering, pause handling and E-key logging passed. Manual play by
a human participant and experimental efficacy remain unverified.

## Compatibility and changed files

Historical gameplay is retained explicitly:

```powershell
python main.py --legacy --robot scripted --seed 42
python main.py --legacy --robot anticipatory --layout shared --seed 42
python main.py --legacy --robot reactive --layout reactive --recipe salad --seed 42
```

For programmatic legacy fixtures `GameState(...)` retains its historical default;
the new path is `GameState(..., layout="reactive", experiment=True)`. The CLI
always opts into the new experiment unless `--legacy` is specified.

New files: `recipes.py`, `experiment.py`, `meal_policy.py`,
`tests/test_experiment.py`, `tests/test_experiment_cli.py`, and this document.

Modified files: `config.py`, `game.py`, `layouts.py`, `navigation.py`,
`reactive_robot/robot.py`, `anticipatory_robot/robot.py`,
`anticipatory_robot/model.py`, `main.py`, `render.py`, `logger.py`, `README.md`,
`LOGGING.md`, the root `README.md`, root `changes.md`, and root `.gitignore`
(to ignore repository-local test scratch files).
