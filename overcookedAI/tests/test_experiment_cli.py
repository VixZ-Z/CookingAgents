"""Actual CLI condition selection, pause timing, and E-key event recording."""
import csv
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import main
from game import GameState
from logger import RunRecorder


class Clock:
    def tick(self, fps):
        return 50


class ExperimentCLITests(unittest.TestCase):
    def run_cli(self, robot, events, prepare=None, folder=None):
        states = []

        def make_state(*args, **kwargs):
            state = GameState(*args, **kwargs)
            if prepare:
                prepare(state)
            states.append(state)
            return state

        def recorder(meta, enabled=True):
            return RunRecorder(meta, folder, enabled=enabled)

        args = ["main.py", "--robot", robot, "--seed", "42"]
        if folder is None:
            args.append("--no-log")
        with patch.object(sys, "argv", args), patch("main.GameState", side_effect=make_state), \
                patch("pygame.event.get", side_effect=events), patch("pygame.time.Clock", return_value=Clock()):
            if folder is None:
                main.main()
            else:
                with patch("main.RunRecorder", side_effect=recorder):
                    main.main()
        return states

    def test_both_cli_conditions_default_to_same_divided_experiment(self):
        quit_event = pygame.event.Event(pygame.QUIT)
        states = [self.run_cli(robot, [[], [quit_event]])[0] for robot in ("reactive", "anticipatory")]
        self.assertTrue(all(s.experiment and s.layout.name == "reactive" for s in states))
        self.assertEqual(states[0].layout, states[1].layout)
        self.assertEqual(states[0]._order_schedule, states[1]._order_schedule)

    def test_pause_does_not_advance_game_time(self):
        pause = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p)
        quit_event = pygame.event.Event(pygame.QUIT)
        state = self.run_cli("reactive", [[pause], [], [], [pause], [quit_event]])[0]
        self.assertAlmostEqual(state.elapsed, 0.05)

    def test_human_e_key_is_included_in_existing_interaction_log(self):
        def prepare(state):
            counter = next(s for s in state.stations if s.owner == "shared")
            state.player.rect.topleft = (counter.rect.left - 42, counter.rect.y + 11)
            state.player.pos.update(state.player.rect.topleft)
            state.player.carrying = "bread"

        interact = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e)
        quit_event = pygame.event.Event(pygame.QUIT)
        with tempfile.TemporaryDirectory() as folder:
            self.run_cli("reactive", [[interact], [quit_event]], prepare=prepare, folder=folder)
            paths = [os.path.join(folder, p) for p in os.listdir(folder)
                     if p != "summary.csv" and not p.endswith("_orders.csv")]
            with open(paths[0], newline="", encoding="utf-8") as file:
                events = list(csv.DictReader(file))
            self.assertTrue(any(e["actor"] == "human" and e["action"] == "put" and e["item"] == "bread"
                                for e in events))


if __name__ == "__main__":
    unittest.main()
