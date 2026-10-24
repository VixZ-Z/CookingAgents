# Logging for the experiments (Person 4 report section)

## Six-dish menu extension (24 October 2026)

CSV column names, time units, scoring and metric formulas are unchanged. Recipe
IDs are stored in the existing `item` field of `order_new`, `serve` and
`order_expired` events. `meal_period` events put BREAKFAST, LUNCH or DINNER in
`item`; they use active seconds in `t`. Scheduled order arrivals retain their
nominal active-time timestamp. `run_config.schedule_hash` identifies the complete
seeded menu schedule; the logger alone reads it, never the robot planners.

The `salads` summary remains a salad count; `soups` includes the legacy soup and
Tomato Soup and Chicken Soup (and historical Potato Soup records). Sandwiches and mains contribute to the unchanged total served
counts and are identifiable individually in event rows. The existing anticipation
source classification is retained. The chart program also labels the
`anticipatory` condition explicitly.

Run filenames include a random suffix and are created exclusively, preventing
same-second restarts from overwriting results. Existing experiment files are not
rewritten. Runtime Git inspection is disabled; the existing commit metadata field
is left empty. Test logs and chart validation are kept separately under
`.test-tmp/menu-validation-*` at the repository root.

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
python main.py --robot anticipatory_fixed_h --fixed-h 4 --participant P01 --condition fixed_h --seed 0
python main.py --robot anticipatory_dynamic_h --participant P01 --condition dynamic_h --seed 0
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
2. **Dynamic vs fixed `h`.** Compare `anticipatory_fixed_h` and `anticipatory_dynamic_h`
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
`python main.py --robot reactive --layout divided --seed 0 --debug-agent`.

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

`anticipatory_fixed_h` and `anticipatory_dynamic_h` emit `action=h_config` once at run
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

## Experiment measures (16 October 2026)

The layout `reactive` is now `divided` and the timing robots are
`anticipatory_fixed_h` / `anticipatory_dynamic_h` (`reactive` is the baseline).
New event rows (all on the divided kitchen unless noted):

* `run_config` (once): git `commit`, key `parameters` (speeds, chop/pot time, fixed h,
  h interaction time and lateness weight, transition thresholds, order timing),
  `fixed_h_used`, `initial_orders` and a `schedule_hash` to confirm two runs had the
  same starting orders.
* `handoff` (robot `take` of an item the human put on a shared counter): `dwell`
  (human put to robot take, seconds), `robot_arrival_minus_put` (negative = the robot
  was already at the counter when the item arrived, positive = the human's item was
  waiting for the robot) and `robot_ready` (1 when arrival was not after the put).
* `h_outcome` (h robots; at each human put/take on a shared counter): the estimates
  made in the last 15 s are compared with the real time to that event. `estimates` is
  how many there were, `right_station` how many named the station actually used,
  `mae` and `bias` are the error in seconds (estimate minus actual) over those, and
  `last_source` is the evidence behind the latest estimate.
* `pace` (dynamic h; whenever a new step has been observed): per-situation handling
  time (`seconds`, `samples`), the chop factor and the default used before any
  observation.

New `summary.csv` columns: `handoffs`, `dwell_mean`, `robot_arrival_mean`,
`robot_late_share`, `h_samples`, `h_mae`, `h_bias`, `human_distance_px`,
`human_still_s` (time moving below 5 px/s, so it includes chopping in place) and
`robot_wait_s` (time with no robot task). If an older `summary.csv` has a different
header it is renamed to `summary_old_<run id>.csv` and a new file is started.

Analysis notes: use `dwell_mean`, `robot_late_share` and `h_mae` as the main measures
of coordination and timing quality, per participant and condition; score and serves
per minute also depend on player skill. `h_mae` only covers estimates that named the
right station, so also report `right_station / estimates` from the `h_outcome` rows.
`pace` rows are written for both h robots, but only dynamic h uses them; fixed h
ignores the observed pace, so its h error should grow when the player's pace differs
from the fixed value.

## When files are written, and report figures

The game length defaults to 180 s and can be set at launch with `--game-time SECONDS`
(for example `python main.py --robot reactive --game-time 120`). It is recorded as
`GAME_TIME` in the `run_config` row, and R restarts with the same length. Order
lifetimes (65-90 s) and timing constants are not scaled, so use the same length for
all conditions you compare. Elsewhere in this file "180" means the default.

`logs/<run>.csv` is created when the game starts and rows are written during play.
The run is closed, and its row added to `logs/summary.csv`, in these cases:

* the 180 s clock reaches zero: `game_end` with `completed` (summary `completed=1`);
* R (restart) mid-game, or ESC / closing the window: `game_end` with `aborted`
  (summary `completed=0`).

Each run is closed once, so pressing R or ESC after the game has ended adds nothing.
If the program is killed or crashes, the run is not closed: the file may be missing
its last rows, has no `game_end` row, and gets no summary row.

Figures and a table for the report:

```powershell
pip install -r requirements-analysis.txt
python analyze.py                # logs/ -> figures/
python analyze.py --include-aborted
```

Games are grouped by robot (the `condition` label is ignored). By default only
completed games are used (add `--include-aborted` for the rest); all participants
are included. It writes:

| File | Question it answers |
| --- | --- |
| `fig1_team_performance.png` | Final score, orders per minute and order-to-serve time per robot |
| `fig2_handoff_timing.png` | Robot arrival at the counter minus human placement, per handoff, and % of handoffs where the robot was ready |
| `fig3_h_accuracy.png` | Fixed vs dynamic h: predicted vs actual time to the next human handoff action, and the error per estimate |
| `fig4_idle_time.png` | Robot time with no task and human time standing still |
| `fig5_score_over_time.png` | Mean score curve per robot (band = range across games) |
| `summary_by_robot.csv` | Mean and SD of every measure per robot (also printed as a Markdown table) |

`fig3` pairs each `horizon` estimate with the human's next put/take on a handoff
counter, using estimates made up to 15 s before it and naming the counter used.

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

## Adaptive collaboration diagnostics

The `adaptive_anticipatory` condition uses the same metric formulas and columns.
`collaboration_pattern` event rows contain per-recipe probabilities in JSON `info`,
separate from experimental metrics. Existing diagnostic rows record changed plans.
Preferences reset on new sessions/restarts. Chart labels include Adaptive
Anticipatory; historical horizon conditions are unchanged.
