"""Initial assumption and one 0.5-second delay, independent of human input."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from anticipatory_robot import AnticipatoryRobot
from game import GameState, Order


class StartupTests(unittest.TestCase):
    def test_stationary_human_robot_starts_at_half_second_for_both_recipes(self):
        for recipe, complement in (("salad", "lettuce"), ("soup", "onion")):
            with self.subTest(recipe=recipe, legacy_menu=True):
                state = GameState(AnticipatoryRobot, seed=0, layout="shared", recipe=recipe, legacy_menu=True)
                before = state.robot.rect.copy()
                state.update(0.49, (0, 0), False)
                self.assertEqual(state.robot.rect, before)
                self.assertIsNone(state.robot.task)
                state.update(0.01, (0, 0), False)
                self.assertNotEqual(state.robot.rect, before)
                self.assertEqual(state.robot.task.action, "fetch")
                self.assertEqual(state.robot.task.item, complement)
                self.assertIsNone(state.player.carrying)
                self.assertEqual(state.robot.contribution_source, "default")
                self.assertIsNone(state.robot.model.predict_start(recipe))

    def test_human_choice_during_delay_overrides_initial_assumption(self):
        state = GameState(AnticipatoryRobot, seed=0, layout="shared", recipe="soup", legacy_menu=True)
        before = state.robot.rect.copy()
        state.player.carrying = "onion"
        state.update(0.49, (0, 0), False)
        self.assertEqual(state.robot.rect, before)
        state.update(0.01, (0, 0), False)
        self.assertEqual(state.robot.task.item, "tomato")
        self.assertEqual(state.robot.contribution_source, "observed")

    def test_new_priority_does_not_repeat_the_startup_delay(self):
        state = GameState(AnticipatoryRobot, seed=0, layout="shared", legacy_menu=True)
        state.orders = [Order("salad", 30), Order("soup", 80)]
        for _ in range(30):
            state.update(1 / 60, (0, 0), False)
        self.assertEqual(state.robot.task.item, "lettuce")
        state.orders.append(Order("soup", 10))
        state.update(1 / 60, (0, 0), False)
        self.assertEqual(state.robot.task.item, "onion")
        self.assertNotIn("Starting", state.robot.status)

    def test_default_and_idle_takeover_do_not_learn_from_robot_actions(self):
        for recipe in ("salad", "soup"):
            with self.subTest(recipe=recipe, legacy_menu=True):
                state = GameState(AnticipatoryRobot, seed=0, layout="shared", recipe=recipe, legacy_menu=True)
                for _ in range(1350):
                    state.update(1 / 30, (0, 0), False)
                    self.assertFalse(state.robot.rect.colliderect(state.player.rect))
                    self.assertFalse(any(state.robot.rect.colliderect(s.rect)
                                         for s in state.stations))
                    if state.robot.completed_salads + state.robot.completed_soups:
                        break
                self.assertEqual(state.robot.completed_salads + state.robot.completed_soups, 1)
                self.assertGreater(state.score, 0)
                self.assertIsNone(state.robot.model.predict_start(recipe))

    def test_no_orders_means_no_ingredient_fetch(self):
        state = GameState(AnticipatoryRobot, seed=0, layout="shared", legacy_menu=True)
        state.orders.clear()
        state.update(0.5, (0, 0), False)
        self.assertIsNone(state.robot.task)
        self.assertIsNone(state.robot.human_ingredient)

    def test_restart_reapplies_the_delay_and_initial_assumption(self):
        state = GameState(AnticipatoryRobot, seed=0, layout="shared", recipe="soup", legacy_menu=True)
        state.update(0.5, (0, 0), False)
        self.assertEqual(state.robot.task.item, "onion")
        restarted = GameState(AnticipatoryRobot, seed=0, layout="shared", recipe="soup", legacy_menu=True)
        before = restarted.robot.rect.copy()
        restarted.update(0.49, (0, 0), False)
        self.assertEqual(restarted.robot.rect, before)
        self.assertIsNone(restarted.robot.task)
        restarted.update(0.01, (0, 0), False)
        self.assertEqual(restarted.robot.task.item, "onion")


if __name__ == "__main__":
    unittest.main()

