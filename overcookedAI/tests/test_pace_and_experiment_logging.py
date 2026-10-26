"""Per-situation pace learning for dynamic h and the experiment-level log rows."""
import csv
import glob
import json
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

import config as C
from game import GameState, Order
from human_horizon import HandoffEstimate
from logger import RunRecorder, SUMMARY_FIELDS
from reactive_robot import ReactiveRobot, AnticipatoryDynamicHRobot
from test_horizon_modes import find, make_state, use

META = {"participant": "T01", "condition": "test", "robot": "anticipatory_dynamic_h",
        "recipe": "salad", "seed": 0}


def read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def wait(state, seconds, recorder=None):
    for _ in range(round(seconds * 30)):
        if recorder:
            recorder.before(state)
        state.update(1 / 30, (0, 0), False)
        if recorder:
            recorder.after(state, 1 / 30)


class PaceTests(unittest.TestCase):
    def pace_after(self, pause):
        state = make_state(AnticipatoryDynamicHRobot)
        state.robot.enabled = False
        use(state, find(state, "crate_tomato"))
        wait(state, pause)
        use(state, find(state, "board", "human"))
        state.update(1 / 30, (0, 0), False)
        return state.robot.horizon

    def test_slow_and_quick_humans_get_different_step_estimates(self):
        slow, quick = self.pace_after(4.0), self.pace_after(0.1)
        key = "put:board"
        self.assertEqual(slow.pace.snapshot()["handling"][key]["samples"], 1)
        self.assertGreater(slow.pace.handling_seconds(key), C.H_INTERACTION_SECONDS)
        self.assertLessEqual(quick.pace.handling_seconds(key), C.H_INTERACTION_SECONDS)
        estimate = HandoffEstimate(distance=0, steps=(key,))
        self.assertGreater(slow._eta_seconds(estimate), quick._eta_seconds(estimate))

    def test_unobserved_situations_keep_the_default_interaction_time(self):
        horizon = make_state(AnticipatoryDynamicHRobot).robot.horizon
        estimate = HandoffEstimate(distance=0, chopping=1.0, interactions=2,
                                   steps=("take:crate", "put:counter"))
        self.assertAlmostEqual(horizon._eta_seconds(estimate), 1.0 + 2 * C.H_INTERACTION_SECONDS)

    def test_pace_is_per_situation_and_ignores_long_pauses(self):
        horizon = make_state(AnticipatoryDynamicHRobot).robot.horizon
        horizon.pace.observe("take:crate", 3.0, 1.0)
        self.assertGreater(horizon.pace.handling_seconds("take:crate"), C.H_INTERACTION_SECONDS)
        self.assertEqual(horizon.pace.handling_seconds("put:counter"), C.H_INTERACTION_SECONDS)
        before = horizon.pace.revision
        horizon.pace.observe("put:counter", 60.0, 1.0)
        self.assertEqual(horizon.pace.revision, before)

    def test_slow_chopping_raises_the_chop_factor(self):
        horizon = make_state(AnticipatoryDynamicHRobot).robot.horizon
        horizon.pace.observe("chop:board", 3 * C.CHOP_TIME, 0.0)
        self.assertGreater(horizon.pace.chop_factor, 1.0)


class ExperimentLoggingTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def rows(self):
        return read(glob.glob(os.path.join(self.dir.name, "T01_*.csv"))[0])

    def test_run_config_and_summary_columns(self):
        state = make_state(AnticipatoryDynamicHRobot)
        rec = RunRecorder(META, self.dir.name)
        rec.start(state)
        wait(state, 0.5, rec)
        rec.finish(state, completed=False)
        config = json.loads(next(r for r in self.rows() if r["action"] == "run_config")["info"])
        self.assertEqual(config["parameters"]["FIXED_H_SECONDS"], C.FIXED_H_SECONDS)
        self.assertEqual(len(config["schedule_hash"]), 8)
        self.assertEqual(config["initial_orders"], [["salad", 150]])
        summary = read(os.path.join(self.dir.name, "summary.csv"))
        self.assertEqual(list(summary[0]), SUMMARY_FIELDS)

    def test_handoff_dwell_and_robot_arrival_are_paired(self):
        state = GameState(ReactiveRobot, seed=0, layout="divided", recipe="salad", legacy_menu=True)
        state.orders = [Order("salad", 150)]
        state.order_timer = -1000
        counters = [s for s in state.stations if s.owner == "shared"]
        rec = RunRecorder(dict(META, robot="reactive"), self.dir.name)
        rec.start(state)
        for name, counter in zip(("chopped_tomato", "chopped_lettuce"), counters):
            state.player.carrying = name
            rec.before(state)
            use(state, counter)
            state.update(1 / 30, (0, 0), False)
            rec.after(state, 1 / 30)
        wait(state, 15, rec)
        rec.finish(state, completed=False)
        handoffs = [json.loads(r["info"]) for r in self.rows() if r["action"] == "handoff"]
        self.assertGreaterEqual(len(handoffs), 1)
        for handoff in handoffs:
            self.assertGreater(handoff["dwell"], 0)
            self.assertAlmostEqual(handoff["robot_take_t"] - handoff["human_put_t"], handoff["dwell"], places=2)
        summary = read(os.path.join(self.dir.name, "summary.csv"))[0]
        self.assertEqual(int(summary["handoffs"]), len(handoffs))
        self.assertGreater(float(summary["human_distance_px"]), 0)
        self.assertGreater(float(summary["robot_wait_s"]), 0)

    def test_h_estimates_are_scored_against_the_real_handoff(self):
        state = make_state(AnticipatoryDynamicHRobot)
        state.robot.enabled = False
        state.player.carrying = "chopped_tomato"
        rec = RunRecorder(META, self.dir.name)
        rec.start(state)
        wait(state, 2.0, rec)
        target = state.robot.horizon.estimate.target
        self.assertIsNotNone(target)
        rec.before(state)
        use(state, target)
        state.update(1 / 30, (0, 0), False)
        rec.after(state, 1 / 30)
        rec.finish(state, completed=False)
        outcome = json.loads(next(r for r in self.rows() if r["action"] == "h_outcome")["info"])
        self.assertEqual(outcome["action"], "put")
        self.assertGreaterEqual(outcome["right_station"], 1)
        self.assertIsNotNone(outcome["mae"])
        summary = read(os.path.join(self.dir.name, "summary.csv"))[0]
        self.assertGreaterEqual(int(summary["h_samples"]), 1)

    def test_pace_rows_are_logged_when_estimates_change(self):
        state = make_state(AnticipatoryDynamicHRobot)
        state.robot.enabled = False
        rec = RunRecorder(META, self.dir.name)
        rec.start(state)
        for station in (find(state, "crate_tomato"), find(state, "board", "human")):
            rec.before(state)
            use(state, station)
            state.update(1 / 30, (0, 0), False)
            rec.after(state, 1 / 30)
            wait(state, 1.0, rec)
        rec.finish(state, completed=False)
        pace = [json.loads(r["info"]) for r in self.rows() if r["action"] == "pace"]
        self.assertTrue(pace)
        self.assertIn("handling", pace[-1])


class MainLoopLoggingTests(unittest.TestCase):
    def test_human_interaction_pressed_with_e_is_logged_by_the_real_loop(self):
        import sys
        from unittest.mock import patch
        from main import main

        def take_something(state):
            state.player.carrying = "tomato"

        events = [[pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e)],
                  [], [pygame.event.Event(pygame.QUIT)]]
        with tempfile.TemporaryDirectory() as folder:
            def recorder(meta, enabled=True):
                return RunRecorder(meta, folder, enabled)

            with patch.object(sys, "argv", ["main.py", "--robot", "none", "--layout", "divided",
                                            "--participant", "T01"]):
                with patch("main.View"), patch("main.RunRecorder", side_effect=recorder):
                    with patch("game.GameState.player_interact", take_something):
                        with patch("pygame.event.get", side_effect=events):
                            main()
            rows = read(glob.glob(os.path.join(folder, "T01_*.csv"))[0])
        human = [r for r in rows if r["actor"] == "human" and r["action"] == "take"]
        self.assertEqual([r["item"] for r in human], ["tomato"])


class GameTimeOptionTests(unittest.TestCase):
    def test_game_time_sets_the_clock_and_survives_restart(self):
        import contextlib
        import io
        import sys
        from unittest.mock import patch
        from main import main

        clocks = []
        events = [[pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r)],
                  [pygame.event.Event(pygame.QUIT)]]
        with patch.object(C, "GAME_TIME", C.GAME_TIME), patch.object(
                sys, "argv", ["main.py", "--robot", "none", "--no-log", "--game-time", "45"]):
            with patch("main.View"), patch("main.RunRecorder") as recorder:
                recorder.return_value.start.side_effect = lambda state: clocks.append(
                    (state.game_time, state.elapsed))
                with patch("pygame.event.get", side_effect=events):
                    main()
        self.assertEqual(clocks, [(45.0, 0.0), (45.0, 0.0)])

        for bad in ("0", "-5", "nan", "inf"):
            with patch.object(C, "GAME_TIME", C.GAME_TIME), patch.object(
                    sys, "argv", ["main.py", "--robot", "none", "--game-time", bad]):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    main()

    def test_game_ends_after_the_requested_time_and_is_logged(self):
        from unittest.mock import patch
        with patch.object(C, "GAME_TIME", 2):
            state = make_state(AnticipatoryDynamicHRobot)
            self.assertEqual(state.game_time, 2.0)
            with tempfile.TemporaryDirectory() as folder:
                rec = RunRecorder(META, folder)
                rec.start(state)
                wait(state, 2.5, rec)
                self.assertTrue(state.game_over)
                rec.finish(state, completed=True)
                rows = read(rec.path)
        config = json.loads(next(r for r in rows if r["action"] == "run_config")["info"])
        self.assertEqual(config["parameters"]["GAME_TIME"], 2)


if __name__ == "__main__":
    pygame.init()
    unittest.main()
