# Logging for the experiments (Person 4 report section)

## Meal-period experiment update — 16 October 2026

The default CLI now runs the reproducible six-recipe experiment described in
[EXPERIMENT.md](EXPERIMENT.md). Both conditions use the same divided layout.
The existing event/5 Hz position CSV and summary schema are retained. Event
rows add `meal_period`; period transitions emit `meal_period` events. Main-loop
snapshots now precede E-key interactions so human actions are captured.

Each completed/aborted trial also writes `<run>_orders.csv` with a row for every
precomputed order: condition, seed, layout, final score, scheduled and actual
appearance time/period, delay, completion time, duration and outcome. Stable
order IDs allow pairing by seed. Duration starts at actual appearance; TTL
starts there too. Blocked arrivals are queued FIFO without resampling. Recipes
are sampled according to their scheduled meal period, even when shown later.
`completed`, `expired` and `missed` are order outcomes. Aborted unfinished rows
have `censored=1` and `run_completed=0`; do not analyze them as full trials.

The future schedule remains engine-only and is written to the ledger at trial
end. No schedule, seed, RNG, engine callback or recorder is passed to a robot.
Run filenames now use microseconds to preserve quick restarts. Summary metrics
retain their calculations; `soups` includes tomato/potato soups, while sandwiches
and mains can be counted from the ledger rather than being labeled as soups.
No new functional-delay or concurrency aggregate is invented.

Examples (from this folder):

```powershell
python main.py --robot reactive --seed 42 --participant P01 --condition reactive
python main.py --robot anticipatory --seed 42 --participant P01 --condition anticipatory
```

The older report below describes the original logger. Its shared-kitchen and
salad/soup examples require `--legacy` under the updated CLI.

Status: 13 Oct 2026. This documents the logging added to `overcookedAI/` so
that every human-played trial is stored for later comparison. It is written to
be pasted into the report (methodology: data collection).

## What changed (minimal)

| File | Change |
| --- | --- |
| `logger.py` | Rewritten: `RunRecorder` infers events by comparing the game state before and after every update. |
| `main.py` | 3 new options (`--participant`, `--condition`, `--no-log`) and 4 hook calls around `state.update`. |
| `tests/test_logger.py` | New: 3 headless tests. The 53 existing tests still pass (56 in total). |

`game.py`, the robots and the rendering are **unchanged**, so logging cannot
alter robot behaviour.

## How to record a trial

```powershell
python main.py --robot anticipatory --participant P01 --condition fixed_h --seed 0
```

Play normally. At the end of the game (or on `R` / `Esc`) the files are
closed. Use `--condition` as a free label (for example `fixed_h`,
`dynamic_h`, `reactive`) and keep `--seed` identical between conditions so
the order schedule matches. `--no-log` disables logging for practice runs.

Output (folder `logs/`, ignored by git: copy or commit it explicitly):

* `logs/<participant>_<robot>_<layout>_<condition>_<time>.csv`: full event stream
* `logs/summary.csv`: one row per run, appended automatically

## Event log columns

| Column | Meaning |
| --- | --- |
| `run_id, participant, condition, robot, layout, recipe, seed` | Run metadata (on every row) |
| `score` | Score at that moment |
| `t` | Game seconds since start (pauses excluded); time left = 180 - t |
| `kind` | `event` or `pos` (position sample at 5 Hz) |
| `actor` | `human`, `robot` or `system` |
| `action` | `take`, `put`, `combine`, `chop`, `serve`, `trash`, `status`, `order_new`, `order_expired`, `pot_ready`, `crates_swapped`, `game_end` |
| `item` | Item concerned; for `status`, the robot's activity text; for `pos`, the carried item |
| `station` | `Label#index` of the station used |
| `order_id` | Order number (serve, order_new, order_expired) |
| `x, y` | Position in pixels (`pos` rows) |
| `anticipating` | Robot rows only: 1 if the robot acted on a guess made before the human showed the choice |
| `info` | `order_time_left=..` on serve; `completed`/`aborted` on `game_end` |

**Definition of "anticipating".** The anticipatory robot records where its
knowledge of the human's contribution comes from. `routine` (learned starter
frequency), `default` (initial tomato assumption) and `movement` (human
walking towards a crate) count as anticipating; `observed` (human already
carries the ingredient) and `delivered` count as reactive. This gives a
within-trial split of robot actions into anticipatory and reactive ones.

## Summary columns
`completed` (1 = full 180 s, 0 = aborted), `duration`, `score`,
`served_human`, `served_robot`, `salads`, `soups`, `expired`,
`first_serve_t`, `robot_actions`, `robot_anticipating_actions`.

## How the log answers the three research questions

1. **Score vs anticipation, where to draw the line.** Split robot actions by
   `anticipating` and by time left (`180 - t`, for example the last 30 s):
   compare serves and score gained per time window, and whether anticipatory
   prefetches near the end were still delivered before `game_end`
   (wasted effort = a robot `take`/`put` with `anticipating=1` and no later
   `serve` of that recipe).
2. **Dynamic vs fixed `h`.** Lead time = time between the robot placing an
   ingredient and the human's matching `put`/`take` on the shared station;
   waiting time = durations of robot `status` rows starting with "Waiting".
   Compare across `--condition` labels and layouts (`near`, `far`, `mixed`,
   `swap`; `crates_swapped` marks the routine change).
3. **Efficiency across scenarios.** Per run: serves per minute, mean order
   completion time (`order_new` to `serve`), expired orders, human and robot
   idle time from the 5 Hz positions, from `summary.csv` and the event stream.

## Robot decision diagnostics

Anticipatory and reactive games add `event` rows with `action=diagnostic`. The `info` column
contains JSON with the current or just attempted task (station label, rectangle,
action, item), decision text, navigation reason, route availability, the latest
planned waypoints, decision events and autonomous mode. `intentional_wait`
distinguishes expected resource/access waiting from a failed requested route.
Navigation reasons include `not_requested`, `moving`, `arrived`, `no_route` and
`collision_rejected`. Events identify invalidated tasks, replanning, contact
recovery, yielding, priority changes and cases with no valid action.

Rows are emitted when the task, decision, navigation outcome or autonomous mode
changes; unchanged waits and periodic identical replans produce no per-frame
diagnostic rows. `planned_path` is the latest plan at that transition, not a
per-frame trace. Diagnostics do not count as cooking actions in the summary.

To also print decision changes in the terminal:

```powershell
python main.py --robot anticipatory --seed 0 --debug-agent
```

CSV recording remains enabled by default. `--no-log` disables CSV writing;
`--debug-agent` can still print diagnostics independently.

Reactive diagnostics also include `unreachable_targets`. All reactive robot
actions have `anticipating=0`; the policy does not set a contribution forecast
or an autonomous takeover mode. Launch with
`python main.py --robot reactive --layout reactive --seed 0 --debug-agent`.

## Known limitations
* The logger observes state; it does not know the robot's internal "h" or
  prediction confidence. If fixed/dynamic `h` is added to the agent, log it in
  `info` (one line in `RunRecorder.after`).
* Actor attribution uses the robot's task target and the human's nearest
  station. In very crowded moments the station name can be off by one
  neighbour; the item and the time are exact.
* Only the anticipatory robot sets `contribution_source`; for other robots
  `anticipating` is 0.
* One human, so data is paired by seed and condition, not by participant
  population; see the experimental design (Person 3) for counterbalancing.
