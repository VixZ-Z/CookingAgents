"""Headless behavioural checks. Run from overcookedAI with unittest discovery."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

import config as C
from anticipatory_robot import AnticipatoryRobot
from anticipatory_robot.model import HumanIntentModel
from game import GameState, chop_name, interact
from navigation import Navigator, approach_point
from scripted_robot import ScriptedRobot


DT = 1 / 30


def place(actor, center):
    actor.rect.center = center
    actor.pos.update(actor.rect.topleft)


class AnticipatoryTests(unittest.TestCase):
    def setUp(self):
        self.state = GameState(AnticipatoryRobot, seed=0, layout="shared", recipe="salad")
        self.state.game_time -= C.ROBOT_START_DELAY

    def stations(self, kind):
        return [s for s in self.state.stations if s.kind == kind]

    def tick(self, seconds=1):
        for _ in range(round(seconds / DT)):
            self.state.update(DT, (0, 0), False)
            self.assertFalse(self.state.robot.rect.colliderect(self.state.player.rect))
            self.assertFalse(any(self.state.robot.rect.colliderect(s.rect) for s in self.state.stations))

    def test_idle_robot_prepares_complement_without_finishing_the_meal(self):
        self.tick(15)
        self.assertEqual(self.state.robot.human_ingredient, "tomato")
        self.assertTrue(any(s.held in ("chopped_lettuce", "plated_lettuce")
                            for s in self.state.stations))
        self.assertEqual(self.state.score, 0)
        self.assertIsNone(self.state.robot.model.predict_start("salad"))

    def test_predicts_chopping_before_human_reaches_board(self):
        self.state.player.carrying = "tomato"
        intent = HumanIntentModel().observe(self.state, DT)
        self.assertEqual(intent.action, "chop tomato")
        self.assertEqual(intent.goal.kind, "board")
        self.state.robot.update_ai(DT, self.state)
        self.assertEqual(self.state.robot.task.item, "lettuce")
        self.assertEqual(self.state.robot.task.action, "fetch")

    def test_does_not_duplicate_humans_ingredient(self):
        self.state.player.carrying = "lettuce"
        self.tick(4)
        self.assertNotEqual(self.state.robot.carrying, "lettuce")
        self.assertFalse(any(s.held == "lettuce" for s in self.state.stations))

    def test_navigation_detours_around_stationary_human(self):
        human, robot = self.state.player, self.state.robot
        place(robot, (800, 350))
        place(human, (550, 350))
        navigator = Navigator()
        reached = False
        for _ in range(900):
            reached = navigator.move_to(robot, (250, 350), self.state, DT)
            self.assertFalse(robot.rect.colliderect(human.rect))
            self.assertFalse(any(robot.rect.colliderect(s.rect) for s in self.state.stations))
            if reached:
                break
        self.assertTrue(reached)

    def test_human_cannot_walk_through_robot(self):
        place(self.state.player, (500, 350))
        place(self.state.robot, (550, 350))
        self.state.robot.enabled = False
        for _ in range(30):
            self.state.update(DT, (1, 0), False)
            self.assertFalse(self.state.player.rect.colliderect(self.state.robot.rect))

    def test_stolen_task_target_is_replanned(self):
        robot = self.state.robot
        self.state.player.carrying = "tomato"
        robot.update_ai(DT, self.state)
        self.state.player.carrying = "lettuce"
        robot.update_ai(DT, self.state)
        self.assertFalse(robot.task and robot.task.action == "fetch" and robot.task.item == "lettuce")

    def test_disabled_robot_does_not_move_or_interact(self):
        self.state.player.carrying = "tomato"
        robot = self.state.robot
        robot.enabled = False
        before = robot.rect.copy()
        self.tick(2)
        self.assertEqual(before, robot.rect)
        self.assertIsNone(robot.carrying)

    def test_robot_can_retreat_when_human_stops_against_it(self):
        place(self.state.player, (500, 350))
        place(self.state.robot, (542, 350))
        self.tick(DT)  # Inspect the escape step before it resumes its own task.
        self.assertGreater(self.state.robot.rect.centerx, 542)

    def test_already_delivered_ingredient_can_start_collaboration(self):
        place(self.state.player, (80, 350))
        self.stations("counter")[0].held = "chopped_tomato"
        self.tick(35)
        self.assertGreater(self.state.score, 0)

    def test_partial_salad_can_be_completed(self):
        place(self.state.player, (80, 350))
        self.stations("counter")[0].held = "plated_tomato"
        self.tick(35)
        self.assertGreater(self.state.score, 0)

    def test_complete_human_workflow_without_teleporting(self):
        state, human = self.state, self.state.player
        crate = self.stations("crate_tomato")[0]
        board = self.stations("board")[0]
        counter = self.stations("counter")[0]
        navigator = Navigator()
        steps = [(crate, "interact"), (board, "interact"), (board, "chop"),
                 (board, "interact"), (counter, "interact")]
        for _ in range(2400):
            if steps:
                target, action = steps[0]
                # The robot may prepare a partial salad before delivery. A human
                # delivering an ingredient chooses a counter that is still empty.
                if target.kind == "counter" and target.held is not None:
                    target = next(s for s in self.stations("counter") if s.held is None)
                    steps[0] = (target, action)
                if navigator.move_to(human, approach_point(target), state, DT):
                    if action == "chop":
                        # SPACE in the real game performs the same update below.
                        state.update(DT, (0, 0), True)
                        if not chop_name(target.held):
                            steps.pop(0)
                        continue
                    interact(human, target, state)
                    steps.pop(0)
            else:
                navigator.move_to(human, (80, 350), state, DT)
            state.update(DT, (0, 0), False)
            self.assertFalse(state.robot.rect.colliderect(human.rect))
            if state.score > 0:
                break
        self.assertFalse(steps, (steps, state.robot.status))
        self.assertGreater(state.score, 0, state.robot.status)

    def test_salad_after_early_preparation_and_human_delivery(self):
        self._complete_salad("tomato")

    def test_reverse_roles_complete_salad(self):
        self._complete_salad("lettuce")

    def test_next_salad_can_use_a_different_division_of_work(self):
        self._complete_salad("tomato")
        self._complete_salad("lettuce")

    def _complete_salad(self, ingredient):
        completed_before = self.state.robot.completed_salads
        # Human starts a raw ingredient and pauses: robot prepares the complement early.
        place(self.state.player, (80, 350))
        self.state.player.carrying = ingredient
        self.tick(12)
        complement = "lettuce" if ingredient == "tomato" else "tomato"
        prepared = [s.held for s in self.state.stations] + [self.state.robot.carrying]
        self.assertTrue(any(item in ("chopped_" + complement, "plated_" + complement)
                            for item in prepared), prepared)
        self.assertEqual(self.state.robot.completed_salads, completed_before)
        # Deliver the human contribution, then clear access to the counter.
        counter = next(s for s in self.stations("counter") if s.held is None)
        self.state.player.carrying = "chopped_" + ingredient
        place(self.state.player, approach_point(counter))
        self.state.player_interact()
        self.assertEqual(counter.held, "chopped_" + ingredient)
        place(self.state.player, (80, 350))
        # Stop at this delivery: the robot can now begin the following order.
        for _ in range(750):
            self.tick(DT)
            if self.state.robot.completed_salads > completed_before:
                break
        self.assertGreater(self.state.score, 0)
        self.assertEqual(self.state.robot.completed_salads, completed_before + 1)
        self.assertFalse(any(s.held in ("tomato", "lettuce") for s in self.state.stations))

    def test_original_scripted_robot_still_completes_orders(self):
        state = GameState(ScriptedRobot, seed=0)
        for _ in range(1800):
            state.update(DT, (0, 0), False)
        self.assertGreater(state.score, 0)


if __name__ == "__main__":
    unittest.main()
