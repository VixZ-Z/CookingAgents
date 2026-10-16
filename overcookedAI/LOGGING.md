# Logging for the experiments (Person 4 report section)

Updated: 16 Oct 2026. This documents the logging added to `overcookedAI/` so
that every human-played trial is stored for later comparison. It is written to
be pasted into the report (methodology: data collection).

## Original logging implementation (13 October 2026)

| File | Change |
| --- | --- |
| `logger.py` | Rewritten: `RunRecorder` infers events by comparing the game state before and after every update. |
| `main.py` | 3 new options (`--participant`, `--condition`, `--no-log`) and 4 hook calls around `state.update`. |
| `tests/test_logger.py` | New: 3 headless tests. The 53 existing tests still pass (56 in total). |

That initial logging change left game rules, robots and rendering unchanged.
Subsequent instrumentation and agent extensions are documented below.

## How to record a trial

```powershell
python main.py --robot reactive_fixed_h --fixed-h 4 --participant P01 --condition fixed_h --seed 0
python main.py --robot reactive_dynamic_h --participant P01 --condition dynamic_h --seed 0
python main.py --robot reactive --participant P01 --condition reactive --seed 0
```

Play normally. At the end of the game (or on `R` / `Esc`) the files are
closed. Use `--condition` as a free label (for example `fixed_h`,
`dynamic_h`, `reactive`); it does not select the robot policy. The three reactive
variants share a layout and initial order schedule for the same seed. Later order
creation can depend on play, so an identical seed does not guarantee identical
complete trial schedules. `--no-log` disables logging for practice runs.

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
| `action` | Cooking/world events, `status`, `diagnostic`, `human_transition`, `h_config`, `horizon`, `game_end` |
| `item` | Item concerned; for `status`, the robot's activity text; for `pos`, the carried item |
| `station` | `Label#index` of the station used |
| `order_id` | Order number (serve, order_new, order_expired) |
| `x, y` | Position in pixels (`pos` rows) |
| `anticipating` | Robot rows only: 1 for forecast-based contributions, including preparation before a predicted handoff |
| `info` | `order_time_left=..` on serve; `completed`/`aborted` on `game_end` |

**Definition of "anticipating".** The anticipatory robot records where its
knowledge of the human's contribution comes from. `routine` (learned starter
frequency), `default` (initial tomato assumption) and `movement` (human
walking towards a crate) count as anticipating; `observed` (human already
carries the ingredient) and `delivered` count as reactive. This gives a
within-trial split of robot actions into anticipatory and reactive ones. Learned
`transition` forecasts and `horizon` preparation also count as anticipating.
Horizon actions can anticipate the delivery timing of an already visible item.

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
2. **Dynamic vs fixed `h`.** Compare `reactive_fixed_h` and `reactive_dynamic_h`
   on the same `reactive` map. Use `horizon` rows to relate estimates and selected
   tasks to subsequent human handoff events. Estimate robot waiting from status
   intervals; the local cost's `handoff_lateness` is a prediction, not measured
   human waiting. Human waiting requires an explicit operational definition or
   annotation. Preview layouts (`near`, `far`, `mixed`, `swap`) do not select an
   implemented reactive policy; `crates_swapped` marks changes in swap layouts.
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

Reactive diagnostics also include `unreachable_targets`. Ordinary `--robot reactive`
actions have `anticipating=0`; that policy does not set a contribution forecast
or an autonomous takeover mode. Launch with
`python main.py --robot reactive --layout reactive --seed 0 --debug-agent`.

## Human action transition learning (16 October 2026)

Both agents emit `event` rows with `action=human_transition` when their shared
observational model changes, not on unchanged frames. The `info` JSON contains
`observations`, `transitions`, `recipe`, `source`, `next_action`, `probability`,
`samples`, `distribution`, `evaluated_predictions` and `correct_predictions`.
`source` and `next_action` contain the action, item and station type. A missing
forecast is represented by null; unknown rows do not get artificial probabilities.

These rows report learning updates, not robot cooking actions, and do not
increase `robot_actions` in the summary. Model training uses successful human
game-rule events even with `--no-log`; it does not depend on CSV event inference.
At serving, expiry or priority-context changes, the active prediction is cleared
while learned per-recipe counts remain available for subsequent orders.

Forecasts are evaluated against the next observed human action before that
outcome is added to the counts. The evaluation includes every available model
forecast, even low-support forecasts not used by the anticipatory policy.
Row probability is an observed conditional frequency. Empirical forecast
accuracy can be computed as `correct_predictions / evaluated_predictions` when
the denominator is nonzero.

The shared-kitchen anticipatory agent uses transition forecasts for planning, with minimum
support and probability thresholds and checks against current physical state.
Its `transition` contribution source is included in `anticipating=1`. The reactive
baseline's observational forecasts do not alter its policy or anticipation flags.
The fixed/dynamic-h extensions also use supported transitions to infer handoff
routes, while preserving the baseline's cooking policy for delivered supplies.
The earlier logging snapshot in this document predates this instrumentation.

## Fixed/dynamic h diagnostics (16 October 2026)

`reactive_fixed_h` and `reactive_dynamic_h` emit `action=h_config` once at run
start, including the actual numeric `--fixed-h` setting. Restarting begins a new
run with the same configured setting. `action=horizon` rows record estimates at
2 Hz, plus changes of target, action, item, evidence source, unknown state or
scheduling choice.

The `info` JSON includes `mode`, `remaining` (seconds, null if unknown),
`fixed_seconds`, `anchor_time`, `estimated_at`, `target` (station index), `action`,
`item`, `source`, `route_pixels`, `walking_speed`, `remaining_chopping`,
`interaction_seconds` and `lateness_weight`. Horizon rows also include
`scheduling`, with a `choice` and, when alternatives were evaluated, `candidates`.
Each candidate has `duration`, `robot_idle`, `handoff_lateness` and `cost`.
The score is `robot_idle + lateness_weight * handoff_lateness`, using the current
`h`. It is a local estimate, not a measured outcome or a full expected-cost model.

The `horizon` contribution source marks plate preparation, storing that prefetched
plate and approaching/waiting at a forecast handoff as anticipating. Actual
supplied cooking work has no forecast source. `h_config`, `horizon`, transition
and diagnostic rows do not increase `robot_actions` or
`robot_anticipating_actions`; those counters retain the cooking-action definition.
CSV columns and summary schema are unchanged.

## Known limitations
* Recorded `h` values and row frequencies are conditional estimates, not
  calibrated confidence or guaranteed arrival times. Freeze pilot parameters
  before collecting comparison trials.
* Actor attribution uses the robot's task target and the human's nearest
  station. In very crowded moments the station name can be off by one
  neighbour; the item and the time are exact.
* The shared-kitchen anticipatory robot and the two timing-assisted reactive
  variants set `contribution_source`; ordinary reactive/scripted actions remain 0.
* One human, so data is paired by seed and condition, not by participant
  population; see the experimental design (Person 3) for counterbalancing.
