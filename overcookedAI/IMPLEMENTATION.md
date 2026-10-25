# Ingredient returns (25 October 2026)

The human can press E at a supply to return its matching raw ingredient. Other
items remain in hand; supplies remain unlimited and robot restrictions are
unchanged. Returns are observable `put` actions, included in transition learning
and CSV logging, without score changes or handoff attribution. Both instruction
panels explain the control. All 235 source tests pass; the packaged check exercises
pickup and return at all eight supplies.

# Executable rebuilt with meal cleanup and two pots (25 October 2026)

`../dist/CookingAgents.exe` now includes the latest meal-end cancellation rules,
yellow-order preservation and both cooking pots. Its isolated self-check passed
all three robot sessions, actual second-pot meal completion without disturbing
the first batch, meal cleanup, bundled music and six session logs beside the EXE.
The latest source suite passed all 230 tests before this rebuild. The earlier
source-only notes below describe the state before this executable refresh.

# Second cooking pot (Python source only, 25 October 2026)

Added Cook 2 in the robot processing area at (926, 120), between Plates and Serve.
Both experiment layouts use two pots. All three menu robots can keep an unrelated
batch in the first pot and prepare the selected dish in the other. Compatible
started batches take precedence over empty pots, and a usable pot is preferred
over recovering unrelated ingredients. Separate ingredients of the same recipe
can be consolidated into a stable destination pot without alternating targets.
Legacy layouts are unchanged. The executable has not been rebuilt.

# Meal-end order cancellation (Python source only, 25 October 2026)

Breakfast orders are cancelled at 60 active seconds, lunch at 120 and dinner at
180. The yellow priority order is captured at each boundary and preserved on
subsequent frames; completing or normally expiring it does not promote another
old order into exemption. Its timer and expiry penalty are unchanged.
Removal happens before the robot acts on a frame crossing a boundary.
Future-meal orders remain available; later scheduled arrivals for finished meal
categories are consumed from the immutable schedule but not released. The same
schedule/filter is used for every robot. Legacy-menu fixtures are unaffected.
Meal-end removals have no score penalty and emit `order_cancelled` with
`info=meal_end`, distinct from timer expiry and serving. CSV columns are unchanged.
The existing executable has not been rebuilt and retains its earlier behavior.
Validation: all 225 tests pass; the executable's SHA-256 hash is unchanged.

# Standalone Windows build (25 October 2026)

The ready-to-run single-file build is `../dist/CookingAgents.exe` (Windows x64,
approximately 34 MB). Python, libraries and music are bundled. Frozen logging
uses the executable's directory, not the temporary extraction or working folder.
See `BUILDING.md` for reproduction and automated verification details.
All 219 source tests and the actual executable's isolated self-check passed.

# Gameplay music (25 October 2026)

The supplied MP3 is bundled in `assets/music/background.mp3`. `music.py` manages
looped session playback, M mute/unmute, P pause/resume and cleanup on game over,
menu return, exit or session exceptions. The mute preference survives R and new
sessions within the application; the menu is silent. Assets resolve relative to
the module, and unavailable audio does not block gameplay. Both instruction
panels list M. Tests use SDL's silent audio driver to decode the actual MP3 and
exercise playback controls and game-loop integration.
Validation: all 215 tests pass.

# Simplified launcher (25 October 2026)

The graphical menu exposes robot selection, Participant ID and Logging ON/OFF.
Divided Kitchen, seed 42 and a 180-second active session are fixed. The logging
toggle sits below Participant ID; the right panel contains a short task and
controls guide. CLI configuration remains available independently.
All six launcher tests pass, including real session startup, return to menu,
logging and fixed session settings. The updated menu was also rendered headlessly.

# Planner and handoff-test fixes (25 October 2026)

Anticipatory sandwich assembly now uses compatible ingredients on any accessible
robot/shared surface before waiting for a new handoff. When a selected cooked
recipe is fully supplied, an incompatible incomplete pot batch can be recovered
into available storage. Its ingredients remain available for the older order.
Predictions alone do not displace active batches, and ingredients are not fetched
for a blocked pot without a feasible cooking destination.

The two previously failing preference tests now confirm actual robot pickups
through game rules. Ingredient placements remain provisional; human withdrawals
and unexplained removals do not train the collaboration model. This preserves
the distinction between human assembly and ingredient delivery.

Validation: all 210 tests pass, including the seven previously failing cases.

The following sections record earlier implementation stages.

# Adaptive Anticipatory update

The graphical launcher now offers only Divided Kitchen and three robots: Reactive,
Anticipatory and Adaptive Anticipatory. The divided map and recipe/timing rules
are unchanged. Shared Kitchen and historical horizon modes remain internally
available and retain their CLI options.

New `anticipatory_robot/adaptive.py` subclasses the existing anticipatory robot.
It observes successful human puts on handoff counters, classifies them as
individual, partially prepared (chopped), or complete, and maintains per-recipe
counts with 0.75 decay per observation and symmetric unit priors. The most probable
style selects the expected delivery. This is session-local; no persistence or
randomness is added. Ambiguous ingredient-to-recipe observations are skipped.
Current completed dishes override learned expectations. Both anticipatory variants
replan every update, recognize completed work on human trays/in human hands, and
prioritize completed handoffs over obsolete ingredient waits. Navigation, task
execution and cooking rules are reused.

Modified files for this update: `launcher.py`, `main.py`, `menu_planner.py`,
`anticipatory_robot/adaptive.py` (new), `logger.py`, `analyze.py`,
`tests/test_menu.py`, `tests/test_adaptive.py` (new), `README.md`, `LOGGING.md`,
`IMPLEMENTATION.md`. Adaptation diagnostics use separate `collaboration_pattern`
rows with JSON payloads; existing CSV columns and metric formulas are unchanged.

Validation: **207 tests passed** in 28.272 seconds; Python compilation and CLI
help also passed. Repeated complete cheese sandwich and behavior
reversal regression, current-observation overrides, per-session reset, all six
recipes and human handoffs, seeded schedule equality and hidden-information guard.
The existing launcher tests run all three choices through the real game loop.
Separate 30-run synthetic validation at `.test-tmp/adaptive-validation-18d78529/`
includes all six recipes across the three main robots plus both horizon variants.
All five chart types and summary CSV generated. Synthetic runs end after the first
serve and are not experimental performance evidence. GUI tests are headless;
PyCharm itself was not manually operated.

Launch from the project root: `python overcookedAI/launcher.py`. For PyCharm, run
`overcookedAI/launcher.py` without arguments. CLI adaptive example:
`python overcookedAI/main.py --robot adaptive_anticipatory --layout divided --seed 42`.
No Git operations or uploads occurred; previous participant results are untouched.

---

The following report records the preceding refinement; its launcher choices are
superseded by the update above.

# CookingAgents implementation and local verification

## Current behavior

The active menu contains exactly six two-ingredient recipes: Cheese Sandwich,
Ham Sandwich, Tomato Soup, Chicken Soup, Chicken with Potatoes, and Pasta with
Tomatoes. Tomato and potato use the existing chopping action. Sandwiches assemble
on counters; soups and mains cook and require a plate. Cooking times remain 2, 3,
4 and 5 seconds for the four cooked menu slots, identical across robot conditions.
Obsolete recipes are disabled in the normal game, CLI and launcher. Historical
salad/soup code and geometry remain available only to explicit `legacy_menu=True`
regression fixtures.

Both kitchens have eight unique, human-owned ingredient crates. Robots cannot
collect ingredients from any crate. Divided Kitchen separates human supplies and
preparation from robot processing, assembly, cooking and serving, linked by two
purple handoff counters. Shared Kitchen uses the same supplies in an open
workspace; processing stations are available to both actors. Each now has two pots,
one plate supply, one serving station, and one board for each preparation role.
Shared Kitchen has one trash station; divided zones each need accessible trash.

Reactive uses delivered supply and current orders. Anticipatory retains the
existing observable movement/intention model, predicts compatible current
recipes, stages equipment and approaches handoffs before delivery. It can process
a delivered complementary ingredient before the other arrives. Changed intentions
trigger replanning and recovery of incompatible pot contents; existing inventory
prevents repeated speculative equipment staging. No robot reads future orders.

The default session lasts 180 active seconds. Meal boundaries remain exactly 60
and 120 seconds; sampling is 80/10/10 by category and 50/50 within each category.
A dedicated seeded generator creates three initial orders and one every 15 seconds
through 165. Backlog and robot behavior cannot alter scheduled exposure. Pausing
freezes active time. Meal-end cancellation supersedes the previous behavior of
retaining old meal orders, as described in the source-only update above.

Ingredient colors and abbreviations are consistent on crates, items and pots;
processing stations have distinct colors and handoffs remain purple.

## Files changed in the refinement

- `menu.py`, `config.py`: current recipes, ingredient sets and active registries.
- `layouts.py`, `game.py`: unique supplies, ownership, reachable workstations,
  robot crate restriction and explicit historical-mode separation.
- `menu_planner.py`: supplied-ingredient planning, predictive equipment/handoff
  readiness, shared-workspace access and changed-intention pot recovery.
- `anticipatory_robot/model.py`, `anticipatory_robot/robot.py`: current-menu
  integration and retained historical recipe recognition.
- `reactive_robot/robot.py`, `reactive_robot/horizon.py`: shared support and
  historical metadata compatibility. Fixed/dynamic horizon policies remain.
- `scripted_robot/robot.py`: the normal scripted CLI name uses delivered-supply
  reactive execution; explicit historical fixtures retain the old scripted robot.
- `main.py`, `render.py`: valid shared reactive launches, sensible CLI default,
  ingredient/station visuals and accurate human-supply guidance.
- `logger.py`: Chicken Soup included in the existing soup count. Metrics, units
  and CSV columns remain unchanged; existing results are not overwritten.
- `tests/test_menu.py`, `tests/test_launcher.py`: current recipes, both layouts,
  real human pickup/handoff paths, proactive behavior, recovery, launcher support.
- Historical fixtures in `test_divided_layout.py`, `test_human_transitions.py`,
  `test_inactivity.py`, `test_logger.py`, `test_reactive_robot.py`,
  `test_routine_prediction.py`, `test_soup_priority.py`, `test_startup.py`,
  `test_horizon_modes.py`: explicit legacy mode and historical metadata references.
- `README.md`, `LOGGING.md`, `IMPLEMENTATION.md`: current usage and verification.

The previously implemented `launcher.py`, schedule infrastructure, navigation and
chart pipeline were reused. No replacement game loop or menu logic was introduced.

## Verification

- Full unittest suite: 201 tests passed (latest run recorded below).
- All six recipes completed by Reactive and Anticipatory in both kitchens,
  including actual human navigation, crate pickup and handoff interactions.
- All six recipes completed by the human alone in Shared Kitchen.
- Unique crates, robot supply restriction, reachable workstations, divided bounds,
  prediction before delivery, one-time plate staging, changed plans, expired and
  incompatible pot recovery tested.
- Historical layouts and behaviors remain covered by explicit legacy fixtures;
  active recipes also run on the anticipatory shared/scripted layout options.
- Distribution: 100,000 samples per period; each recipe within 0.6 percentage points
  of its expected 40% or 5%. Same-seed schedules, backlog independence, exact meal
  boundaries and pause handling tested. An observable-state proxy rejects private
  schedule/RNG access during anticipatory updates.
- Pygame launcher tests render the actual UI, select every supported configuration,
  run real game loops, complete two sessions, return through Esc/menu button,
  verify fresh state and distinct logs, and check logging disabled and window quit.
- Separate integration: 36 synthetic runs in
  `.test-tmp/refined-validation-f95c89b5/` cover every recipe with both principal
  robots on both maps and both horizon variants on divided. Each records a serve
  event and ends after the first dish. All five existing charts and summary CSV
  generated successfully with `--include-aborted`. These short synthetic runs are
  functionality checks, not evidence of experimental performance differences.
- Both updated maps were rendered and visually inspected in
  `.test-tmp/refined-divided.png` and `.test-tmp/refined-shared.png`.

No known failing checks remain. GUI tests use SDL's dummy driver and injected
input; a manual PyCharm play session was not performed. Fixed/Dynamic Handoff
remain divided-only. No Robot on Divided Kitchen is a preview because the human
cannot access robot-side cooking/serving; choose Shared Kitchen for solo play.

## Launch and test commands

From the repository root with the project requirements installed:

```powershell
python overcookedAI/launcher.py
python overcookedAI/main.py --robot reactive --layout divided --seed 42
python overcookedAI/main.py --robot anticipatory --layout divided --seed 42
```

Use `--layout shared` for either principal robot on Shared Kitchen. In PyCharm,
open `overcookedAI/launcher.py` and choose Run, with no script arguments. Set its
working directory to `overcookedAI` for consistent log location. Do not set a dummy
SDL driver for interactive play. `menu.py` is recipe metadata, not an entry point.

Verified restricted-environment test commands from the repository root:

```powershell
$python = 'C:\Users\antek\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:PYTHONPATH = "$PWD\.test-deps;$PWD\overcookedAI"
$env:TEMP = "$PWD\.test-tmp"
$env:TMP = $env:TEMP
$env:SDL_VIDEODRIVER = 'dummy'
$env:SDL_AUDIODRIVER = 'dummy'
& $python -m unittest discover -s overcookedAI/tests -q
& $python -m compileall -q overcookedAI
```

All modifications and verification outputs remain local and uncommitted. No Git
operations, uploads, publishing or overwrites of participant results occurred.
