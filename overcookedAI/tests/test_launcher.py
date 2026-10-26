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

    def test_all_robot_buttons_use_the_fixed_session_settings(self):
        for robot, _ in launcher.ROBOTS:
            self.menu.handle_event(click(self.menu.robot_buttons[robot]))
            self.assertEqual(self.menu.robot, robot)
            options = self.menu.configuration()
            self.assertEqual((options.seed, options.game_time), (42, 180))
            self.assertEqual(launcher.FIXED_LAYOUT, "divided")

    def test_edit_fields_and_toggle_logging(self):
        self.assertEqual(set(self.menu.fields), {"participant"})
        self.menu.handle_event(click(self.menu.fields["participant"]))
        for char in "P02_trial-1":
            self.menu.handle_event(pygame.event.Event(pygame.KEYDOWN, key=ord(char), unicode=char, mod=0))
        self.assertEqual(self.menu.participant, "P02_trial-1")
        self.assertGreater(self.menu.logging_button.top, self.menu.fields["participant"].bottom)
        self.menu.handle_event(click(self.menu.logging_button))
        options = self.menu.configuration()
        self.assertEqual((options.seed, options.game_time, options.no_log), (42, 180, True))
        self.assertEqual(options.participant, "P02_trial-1")
        for value in ("", "bad id", "ą", "x" * 25):
            self.menu.participant = value
            self.assertIsNone(self.menu.configuration())

    def test_questionnaire_link_opens_browser_without_starting_a_session(self):
        with patch("launcher.webbrowser.open", return_value=True) as browser:
            self.assertIsNone(self.menu.handle_event(click(self.menu.form_link)))
            browser.assert_called_once_with(launcher.FORM_URL, new=2)
        self.assertGreater(self.menu.form_link.top, 606)
        self.assertLessEqual(self.menu.form_link.bottom, C.HEIGHT)
        self.assertFalse(self.menu.form_link.colliderect(self.menu.start_button))

    def test_questionnaire_browser_failure_keeps_menu_usable(self):
        with patch("launcher.webbrowser.open", return_value=False):
            self.menu.handle_event(click(self.menu.form_link))
        self.assertIn("browser", self.menu.error)
        self.assertEqual(self.menu.handle_event(click(self.menu.start_button)), "start")

    def test_every_supported_selection_launches_real_game(self):
        previous_duration = C.GAME_TIME
        states = []
        def create(*args, **kwargs):
            state = GameState(*args, **kwargs)
            states.append(state)
            return state
        for robot, _ in launcher.ROBOTS:
            for layout in (launcher.FIXED_LAYOUT,):
                if main.configuration_error(robot, layout):
                    continue
                with self.subTest(robot=robot, layout=layout):
                    self.menu.robot = robot
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
        states, starts, recorders = [], [], []
        def create(*args, **kwargs):
            state = GameState(*args, **kwargs)
            states.append(state)
            starts.append((state.score, state.game_time, len(state.human_actions)))
            # Reach the end screen quickly without exposing a duration setting.
            state.game_time = .05
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
            self.assertEqual(starts, [(0, 180, 0), (0, 180, 0)])
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
