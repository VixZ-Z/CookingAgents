"""Inactivity detection, autonomous order completion, and return to cooperation."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from anticipatory_robot import AnticipatoryRobot
from game import GameState, Order
from navigation import approach_point


DT = 1 / 30


def place(actor, center):
    actor.rect.center = center
    actor.pos.update(actor.rect.topleft)


class InactivityTests(unittest.TestCase):
    def setUp(self):
        self.state = GameState(AnticipatoryRobot, seed=0, layout="shared")
        self.state.orders = [Order("salad", 90)]
        self.state.order_timer = -1000
        place(self.state.player, (80, 350))
        self.state.update(DT, (0, 0), False)  # Arrival is the last human activity.

    def stations(self, kind):
        return [s for s in self.state.stations if s.kind == kind]

    def tick(self, seconds, human_active=False):
        for step in range(round(seconds / DT)):
            move = (1 if (step // 15) % 2 == 0 else -1, 0) if human_active else (0, 0)
            self.state.update(DT, move, False)
            robot = self.state.robot
            self.assertFalse(robot.rect.colliderect(self.state.player.rect))
            self.assertFalse(any(robot.rect.colliderect(s.rect) for s in self.state.stations))

    def wait_for_delivery(self, recipe, limit=45):
        previous = getattr(self.state.robot, "completed_" + recipe + "s")
        for _ in range(round(limit / DT)):
            self.tick(DT)
            if getattr(self.state.robot, "completed_" + recipe + "s") > previous:
                return
        self.fail("Order not completed: " + self.state.robot.status)

    def test_takeover_at_five_seconds_not_before(self):
        self.tick(4.9)
        self.state.update(0.09, (0, 0), False)
        self.assertFalse(self.state.robot.autonomous)
        self.assertAlmostEqual(self.state.robot.human_idle_seconds, 4.99)
        self.state.update(0.01, (0, 0), False)
        self.assertTrue(self.state.robot.autonomous)
        self.assertAlmostEqual(self.state.robot.human_idle_seconds, 5)
        self.assertIn("Human idle", self.state.robot.cooperation_description)

    def test_movement_resets_the_timeout(self):
        self.tick(4.8)
        self.state.update(DT, (1, 0), False)
        self.assertEqual(self.state.robot.human_idle_seconds, 0)
        self.tick(4.8)
        self.assertFalse(self.state.robot.autonomous)
        self.tick(0.3)
        self.assertTrue(self.state.robot.autonomous)

    def test_interaction_without_movement_restores_cooperation(self):
        self.tick(6)
        self.assertTrue(self.state.robot.autonomous)
        position = self.state.player.rect.copy()
        self.state.player_interact()
        self.tick(DT)
        self.assertEqual(position, self.state.player.rect)
        self.assertEqual(self.state.robot.human_idle_seconds, 0)
        self.assertFalse(self.state.robot.autonomous)

    def test_chopping_is_activity_even_when_standing_still(self):
        board = self.stations("board")[0]
        board.held = "tomato"
        place(self.state.player, approach_point(board))
        self.state.robot.enabled = False
        self.tick(DT)
        self.tick(4.9)
        position = self.state.player.rect.copy()
        self.state.update(DT, (0, 0), True)
        self.assertEqual(self.state.player.rect, position)
        self.assertGreater(board.progress, 0)
        self.assertEqual(self.state.robot.human_idle_seconds, 0)
        self.assertFalse(self.state.robot.autonomous)

    def test_blocked_movement_input_still_counts_as_activity(self):
        place(self.state.player, (21, 350))
        self.tick(DT)
        self.tick(4.9)
        position = self.state.player.rect.copy()
        self.state.update(DT, (-1, 0), False)
        self.assertEqual(self.state.player.rect, position)
        self.assertFalse(self.state.robot.autonomous)
        self.assertEqual(self.state.robot.human_idle_seconds, 0)

    def test_robot_finishes_both_recipes_with_a_stationary_human(self):
        for recipe in ("salad", "soup"):
            with self.subTest(recipe=recipe):
                self.setUp()
                self.state.orders = [Order(recipe, 90)]
                self.wait_for_delivery(recipe)
                self.assertGreater(self.state.score, 0)
                self.assertEqual(self.state.orders, [])
                self.assertTrue(self.state.robot.autonomous)
                self.assertIsNone(self.state.robot.model.predict_start(recipe))

    def test_idle_human_carried_ingredient_does_not_block_autonomous_work(self):
        self.state.orders = [Order("soup", 90)]
        self.state.player.carrying = "tomato"
        self.wait_for_delivery("soup")
        self.assertEqual(self.state.player.carrying, "tomato")
        self.assertEqual(self.state.robot.completed_soups, 1)
        self.assertEqual(self.state.robot.model.predict_start("soup").observations, 1)

    def test_idle_human_holding_plate_does_not_block_soup(self):
        self.state.orders = [Order("soup", 90)]
        self.state.player.carrying = "plate"
        self.wait_for_delivery("soup")
        self.assertEqual(self.state.player.carrying, "plate")

    def test_resumed_human_choice_overrides_a_takeover_task(self):
        self.state.orders = [Order("soup", 90)]
        self.state.player.carrying = "tomato"
        for _ in range(450):
            self.tick(DT)
            if self.state.robot.autonomous and self.state.robot.carrying == "tomato":
                break
        self.assertTrue(self.state.robot.autonomous)
        self.assertEqual(self.state.robot.carrying, "tomato")
        self.state.update(DT, (1, 0), False)
        self.assertFalse(self.state.robot.autonomous)
        self.assertEqual(self.state.robot.human_ingredient, "tomato")
        self.assertTrue(self.state.robot.stow_for_reassignment)
        self.assertEqual(self.state.robot.task.action, "put")
        self.assertEqual(self.state.robot.task.station.kind, "counter")

    def test_urgent_order_first_then_next_order_without_human_input(self):
        soup, salad = Order("soup", 90), Order("salad", 30)
        self.state.orders = [soup, salad]
        self.wait_for_delivery("salad")
        self.assertEqual(self.state.robot.completed_soups, 0)
        self.assertEqual(len(self.state.orders), 1)
        self.assertIs(self.state.orders[0], soup)
        self.wait_for_delivery("soup")
        self.assertEqual(self.state.orders, [])

    def test_partial_pots_are_not_mistaken_for_one_complete_batch(self):
        self.state.orders = [Order("soup", 90)]
        first, second = self.stations("pot")
        first.contents = ["chopped_onion"]
        second.contents = ["chopped_tomato"]
        self.wait_for_delivery("soup")
        self.assertEqual(self.state.robot.completed_soups, 1)
        self.assertTrue(any(pot.contents for pot in (first, second)))

    def test_no_orders_does_not_create_unnecessary_work(self):
        self.state.orders.clear()
        self.tick(6)
        self.assertTrue(self.state.robot.autonomous)
        self.assertIsNone(self.state.robot.task)
        self.assertIsNone(self.state.robot.carrying)
        self.assertTrue(all(s.held is None for s in self.state.stations))


if __name__ == "__main__":
    unittest.main()
