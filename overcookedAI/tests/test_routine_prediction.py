"""Learn starter choices, prepare the next order, and recover from wrong forecasts."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import config as C
from anticipatory_robot import AnticipatoryRobot
from game import GameState, Order, interact
from navigation import approach_point


DT = 1 / 30


def place(actor, center):
    actor.rect.center = center
    actor.pos.update(actor.rect.topleft)


class RoutinePredictionTests(unittest.TestCase):
    def setUp(self):
        self.state = GameState(AnticipatoryRobot, seed=0, layout="shared")
        self.state.game_time -= C.ROBOT_START_DELAY
        self.state.order_timer = -1000
        place(self.state.player, (80, 350))

    def stations(self, kind):
        return [s for s in self.state.stations if s.kind == kind]

    def tick(self, seconds):
        for _ in range(round(seconds / DT)):
            self.state.update(DT, (0, 0), False)
            robot = self.state.robot
            self.assertFalse(robot.rect.colliderect(self.state.player.rect))
            self.assertFalse(any(robot.rect.colliderect(s.rect) for s in self.state.stations))

    def record_start(self, recipe, ingredient):
        """A separate order and a real crate pickup; observe without robot movement."""
        self.state.orders = [Order(recipe, 100)]
        human, model = self.state.player, self.state.robot.model
        human.carrying = None
        model.observe(self.state, DT)
        interact(human, self.stations("crate_" + ingredient)[0], self.state)
        model.observe(self.state, DT)
        human.carrying = None
        model.observe(self.state, DT)

    def prepared(self, ingredient):
        items = [s.held for s in self.state.stations] + [self.state.robot.carrying]
        items += [item for s in self.stations("pot") for item in s.contents]
        return any(item in items for item in ("chopped_" + ingredient, "plated_" + ingredient))

    def test_counts_one_start_per_order_not_frames_or_repeated_pickups(self):
        self.record_start("salad", "tomato")
        model = self.state.robot.model
        self.state.player.carrying = "tomato"
        for _ in range(100):
            model.observe(self.state, DT)
        for item in (None, "chopped_tomato", None, "lettuce"):
            self.state.player.carrying = item
            model.observe(self.state, DT)
        self.assertEqual(model.starter_counts["salad"], {"tomato": 1, "lettuce": 0})

    def test_movement_prediction_does_not_train_history(self):
        self.state.orders = [Order("soup", 100)]
        place(self.state.player, (72, 300))
        self.state.robot.update_ai(DT, self.state)
        place(self.state.player, (72, 292))
        self.state.robot.update_ai(DT, self.state)
        self.assertEqual(self.state.robot.task.item, "onion")
        self.assertIsNone(self.state.robot.model.predict_start("soup"))

    def test_inventory_and_robot_preparation_do_not_train_history(self):
        self.state.orders = [Order("salad", 100)]
        self.stations("counter")[0].held = "chopped_tomato"
        self.tick(20)
        self.assertIsNone(self.state.robot.model.predict_start("salad"))

    def test_each_recipe_has_its_own_history(self):
        self.record_start("salad", "lettuce")
        self.assertIsNone(self.state.robot.model.predict_start("soup"))
        self.record_start("soup", "tomato")
        model = self.state.robot.model
        self.assertEqual(model.predict_start("salad").ingredient, "lettuce")
        self.assertEqual(model.predict_start("soup").ingredient, "tomato")

    def test_cumulative_frequency_and_recent_tie_break_without_forgetting(self):
        for ingredient in ("tomato", "tomato", "lettuce"):
            self.record_start("salad", ingredient)
        prediction = self.state.robot.model.predict_start("salad")
        self.assertEqual((prediction.ingredient, prediction.matches, prediction.observations),
                         ("tomato", 2, 3))
        self.record_start("salad", "lettuce")
        prediction = self.state.robot.model.predict_start("salad")
        self.assertEqual((prediction.ingredient, prediction.matches, prediction.observations),
                         ("lettuce", 2, 4))

    def test_autonomous_preparation_stops_at_the_robot_contribution(self):
        for recipe, complement in (("salad", "lettuce"), ("soup", "onion")):
            with self.subTest(recipe=recipe):
                self.setUp()
                self.record_start(recipe, "tomato")
                self.state.orders = [Order(recipe, 100)]
                self.tick(25)
                self.assertTrue(self.prepared(complement))
                self.assertIsNone(self.state.player.carrying)
                self.assertEqual(self.state.robot.completed_salads, 0)
                self.assertEqual(self.state.robot.completed_soups, 0)
                self.assertEqual(self.state.robot.model.predict_start(recipe).observations, 1)
                self.assertFalse(any(s.held in ("tomato", "chopped_tomato", "plated_tomato")
                                     for s in self.state.stations))

    def test_after_real_robot_delivery_next_order_starts_while_human_is_idle(self):
        for recipe, complement in (("salad", "lettuce"), ("soup", "onion")):
            with self.subTest(recipe=recipe):
                self.setUp()
                self.state.orders = [Order(recipe, 90), Order(recipe, 120)]
                self.state.player.carrying = "tomato"
                self.tick(12)
                counter = next(s for s in self.stations("counter") if s.held is None)
                self.state.player.carrying = "chopped_tomato"
                place(self.state.player, approach_point(counter))
                self.state.player_interact()
                place(self.state.player, (80, 350))
                for _ in range(750):
                    self.tick(DT)
                    if self.state.robot.completed_salads + self.state.robot.completed_soups:
                        break
                self.assertEqual(len(self.state.orders), 1)
                self.assertIsNone(self.state.player.carrying)
                self.tick(15)
                self.assertTrue(self.prepared(complement), self.state.robot.status)
                self.assertEqual(self.state.robot.contribution_source, "routine")
                self.assertEqual(self.state.robot.completed_salads + self.state.robot.completed_soups, 1)

    def test_after_human_serving_robot_also_starts_the_next_order(self):
        self.record_start("soup", "tomato")
        self.state.orders = [Order("soup", 80), Order("soup", 100)]
        self.state.player.carrying = "soup"
        place(self.state.player, approach_point(self.stations("serve")[0]))
        self.state.player_interact()
        place(self.state.player, (80, 350))
        self.tick(DT)
        self.assertEqual(self.state.robot.task.item, "onion")
        self.assertEqual(self.state.robot.contribution_source, "routine")

    def test_wrong_forecast_is_cancelled_before_pickup(self):
        self.record_start("salad", "tomato")
        self.state.orders = [Order("salad", 100)]
        self.tick(DT)
        self.assertEqual(self.state.robot.task.item, "lettuce")
        self.state.player.carrying = "lettuce"
        self.tick(DT)
        self.assertEqual(self.state.robot.task.item, "tomato")
        self.assertIsNone(self.state.robot.routine_prediction)

    def test_wrong_forecast_after_pickup_is_stored_and_roles_switch(self):
        self.record_start("salad", "tomato")
        self.state.orders = [Order("salad", 100)]
        for _ in range(300):
            self.tick(DT)
            if self.state.robot.carrying == "lettuce":
                break
        self.assertEqual(self.state.robot.carrying, "lettuce")
        self.state.player.carrying = "lettuce"
        self.tick(15)
        self.assertTrue(any(s.held == "lettuce" for s in self.stations("counter")))
        self.assertTrue(self.prepared("tomato"), self.state.robot.status)
        self.assertEqual(self.state.robot.human_ingredient, "lettuce")
        self.assertEqual(self.state.robot.completed_salads, 0)
        counter = next(s for s in self.stations("counter") if s.held is None)
        self.state.player.carrying = "chopped_lettuce"
        place(self.state.player, approach_point(counter))
        self.state.player_interact()
        place(self.state.player, (80, 350))
        self.tick(15)
        self.assertEqual(self.state.robot.completed_salads, 1)

    def test_wrong_forecast_releases_robot_board_for_human_ingredient(self):
        self.record_start("salad", "tomato")
        self.state.orders = [Order("salad", 100)]
        for _ in range(300):
            self.tick(DT)
            if self.state.robot.own_board and self.state.robot.own_board.held == "lettuce":
                break
        board = self.state.robot.own_board
        self.assertIsNotNone(board)
        self.state.player.carrying = "lettuce"
        self.tick(12)
        self.assertNotEqual(board.held, "lettuce")
        self.assertTrue(any(s.held == "lettuce" for s in self.stations("counter")))
        self.assertTrue(self.prepared("tomato"))

    def test_priority_change_uses_the_new_recipes_history(self):
        self.record_start("salad", "lettuce")
        self.record_start("soup", "tomato")
        self.state.orders = [Order("salad", 30), Order("soup", 80)]
        self.tick(DT)
        self.assertEqual(self.state.robot.task.item, "tomato")
        self.state.orders.append(Order("soup", 20))
        self.tick(DT)
        self.assertEqual(self.state.robot.task.item, "onion")
        self.assertEqual(self.state.robot.routine_prediction.recipe, "soup")

    def test_order_switch_while_human_still_carries_item_is_not_another_sample(self):
        self.record_start("salad", "tomato")
        self.state.player.carrying = "tomato"
        model = self.state.robot.model
        model.observe(self.state, DT)
        self.state.orders = [Order("salad", 100)]
        model.observe(self.state, DT)
        self.assertEqual(model.predict_start("salad").observations, 1)

    def test_restart_starts_without_invented_history(self):
        self.record_start("salad", "tomato")
        restarted = GameState(AnticipatoryRobot, seed=0, layout="shared")
        self.assertIsNone(restarted.robot.model.predict_start("salad"))


if __name__ == "__main__":
    unittest.main()
