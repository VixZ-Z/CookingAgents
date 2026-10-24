"""Real Pygame launcher/session transitions driven by deterministic input events."""
import csv
import os
import random
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import config as C
import launcher
import main
from game import GameState
from logger import RunRecorder
from render import View


def click(rect):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pygame.Rect(rect).center)


def escape():
    return pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode="", mod=0)


class LauncherTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((C.WIDTH, C.HEIGHT))
        self.menu = launcher.MainMenu()
        self.addCleanup(pygame.quit)

    def test_defaults_and_render_do_not_consume_randomness(self):
        before = random.getstate()
        menu = launcher.MainMenu()
        menu.draw(pygame.display.get_surface())
        options = menu.configuration()
        self.assertEqual((options.seed, options.game_time, options.robot), (42, 180, "reactive"))
        self.assertFalse(options.no_log)
        self.assertEqual(before, random.getstate())

    def test_all_robot_and_layout_buttons_and_validation(self):
        for robot, _ in launcher.ROBOTS:
            for layout, _ in launcher.LAYOUTS:
                self.menu.handle_event(click(self.menu.robot_buttons[robot]))
                self.menu.handle_event(click(self.menu.layout_buttons[layout]))
                self.assertEqual((self.menu.robot, self.menu.layout), (robot, layout))
                options = self.menu.configuration()
                valid = layout == "divided" or robot in ("none", "anticipatory", "reactive")
                self.assertEqual(options is not None, valid)
                if not valid:
                    self.assertIn("Divided Kitchen", self.menu.error)
                    with patch("launcher.run_game") as run:
                        self.assertEqual(launcher.launch_selected(self.menu), "menu")
                        run.assert_not_called()

    def test_edit_fields_and_toggle_logging(self):
        for field, value in (("seed", "-27"), ("duration", "90.5")):
            self.menu.handle_event(click(self.menu.fields[field]))
            for char in value:
                self.menu.handle_event(pygame.event.Event(pygame.KEYDOWN, key=ord(char), unicode=char, mod=0))
            self.assertEqual(getattr(self.menu, field), value)
        self.menu.handle_event(click(self.menu.logging_button))
        options = self.menu.configuration()
        self.assertEqual((options.seed, options.game_time, options.no_log), (-27, 90.5, True))
        for value in ("", "0", "-1", "nan", "inf"):
            self.menu.duration = value
            self.assertIsNone(self.menu.configuration())
        self.menu.duration = "180"
        self.menu.seed = "2.5"
        self.assertIsNone(self.menu.configuration())

    def test_every_supported_selection_launches_real_game(self):
        previous_duration = C.GAME_TIME
        states = []
        def create(*args, **kwargs):
            state = GameState(*args, **kwargs)
            states.append(state)
            return state
        for robot, _ in launcher.ROBOTS:
            for layout, _ in launcher.LAYOUTS:
                if main.configuration_error(robot, layout):
                    continue
                with self.subTest(robot=robot, layout=layout):
                    self.menu.robot, self.menu.layout = robot, layout
                    self.menu.logging_enabled = False
                    with patch("main.GameState", side_effect=create), patch("pygame.time.Clock") as clock:
                        clock.return_value.tick.return_value = 50
                        with patch("pygame.event.get", side_effect=[[], [escape()]]):
                            self.assertEqual(launcher.launch_selected(self.menu), "menu")
                    state = states[-1]
                    self.assertEqual(state.layout.name, layout)
                    cls = main.get_robot_class(robot)
                    self.assertEqual(type(state.robot) if state.robot else None, cls)
                    self.assertLess(state.game_time, 180)
                    self.assertEqual(C.GAME_TIME, previous_duration)
        self.assertTrue(all(s._arrivals == states[0]._arrivals for s in states))

    def test_two_completed_sessions_return_to_menu_with_separate_logs(self):
        self.menu.duration = ".05"
        states, starts, recorders = [], [], []
        def create(*args, **kwargs):
            state = GameState(*args, **kwargs)
            states.append(state)
            starts.append((state.score, state.game_time, len(state.human_actions)))
            return state
        previous_duration = C.GAME_TIME
        events = [[click(self.menu.start_button)], [], [escape()],
                  [click(self.menu.robot_buttons["anticipatory"]), click(self.menu.start_button)],
                  [], [click(View.MENU_BUTTON)], [click(self.menu.quit_button)]]
        with tempfile.TemporaryDirectory() as folder:
            def recorder(*args, **kwargs):
                obj = RunRecorder(*args, log_dir=folder, **kwargs)
                recorders.append(obj)
                return obj
            with patch("launcher.MainMenu", return_value=self.menu), patch("main.GameState", side_effect=create):
                with patch("main.RunRecorder", side_effect=recorder), patch("pygame.time.Clock") as clock:
                    clock.return_value.tick.return_value = 50
                    with patch("pygame.event.get", side_effect=events):
                        launcher.main()
            self.assertEqual(len(states), 2)
            self.assertEqual(starts, [(0, .05, 0), (0, .05, 0)])
            self.assertTrue(all(s.game_over for s in states))
            self.assertIsNot(states[0].robot, states[1].robot)
            self.assertEqual(states[0]._arrivals, states[1]._arrivals)
            self.assertNotEqual(recorders[0].path, recorders[1].path)
            self.assertTrue(all(r._file is None for r in recorders))
            with open(os.path.join(folder, "summary.csv"), encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([r["completed"] for r in rows], ["1", "1"])
            self.assertEqual([r["robot"] for r in rows], ["reactive", "anticipatory"])
        self.assertEqual(C.GAME_TIME, previous_duration)

    def test_window_close_quits_and_disabled_logging_creates_no_files(self):
        self.menu.logging_enabled = False
        with tempfile.TemporaryDirectory() as folder:
            def recorder(*args, **kwargs):
                return RunRecorder(*args, log_dir=folder, **kwargs)
            with patch("main.RunRecorder", side_effect=recorder):
                with patch("pygame.event.get", return_value=[pygame.event.Event(pygame.QUIT)]):
                    self.assertEqual(launcher.launch_selected(self.menu), "quit")
            self.assertEqual(os.listdir(folder), [])


if __name__ == "__main__":
    unittest.main()
