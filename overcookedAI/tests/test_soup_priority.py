"""Mixed recipes, earliest-deadline decisions and complete soup teamwork."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import config as C
from anticipatory_robot import AnticipatoryRobot
from anticipatory_robot.model import HumanIntentModel
from game import GameState, Order, interact
from navigation import Navigator, approach_point


DT = 1 / 30


def place(actor, center):
    actor.rect.center = center
    actor.pos.update(actor.rect.topleft)


class SoupPriorityTests(unittest.TestCase):
    def setUp(self):
        self.state = GameState(AnticipatoryRobot, seed=0, layout="shared", recipe="soup")
        self.state.game_time -= C.ROBOT_START_DELAY
        place(self.state.player, (80, 350))

    def stations(self, kind):
        return [s for s in self.state.stations if s.kind == kind]

    def tick(self, seconds):
        for _ in range(round(seconds / DT)):
            self.state.update(DT, (0, 0), False)
            robot = self.state.robot
            self.assertFalse(robot.rect.colliderect(self.state.player.rect))
            self.assertFalse(any(robot.rect.colliderect(s.rect) for s in self.state.stations))

    def test_default_mixed_mode_starts_with_both_recipes(self):
        for seed in range(10):
            state = GameState(AnticipatoryRobot, seed=seed, layout="shared")
            self.assertEqual({o.kind for o in state.orders}, {"salad", "soup"})

    def test_tomato_means_lettuce_when_salad_is_more_urgent(self):
        self.state.orders = [Order("soup", 80), Order("salad", 30)]
        self.state.player.carrying = "tomato"
        self.state.robot.update_ai(DT, self.state)
        self.assertEqual(self.state.robot.recipe, "salad")
        self.assertEqual(self.state.robot.task.item, "lettuce")

    def test_tomato_means_onion_when_soup_is_more_urgent(self):
        self.state.orders = [Order("salad", 80), Order("soup", 30)]
        self.state.player.carrying = "tomato"
        self.state.robot.update_ai(DT, self.state)
        self.assertEqual(self.state.robot.recipe, "soup")
        self.assertEqual(self.state.robot.task.item, "onion")

    def test_can_anticipate_approach_to_tomato_before_pickup(self):
        place(self.state.player, (72, 300))
        self.state.robot.update_ai(DT, self.state)
        place(self.state.player, (72, 292))
        self.state.robot.update_ai(DT, self.state)
        self.assertEqual(self.state.robot.intent.ingredient, "tomato")
        self.assertEqual(self.state.robot.task.item, "onion")

    def test_new_urgent_recipe_cancels_pending_fetch(self):
        self.state.orders = [Order("salad", 60), Order("soup", 80)]
        self.state.player.carrying = "tomato"
        robot = self.state.robot
        robot.update_ai(DT, self.state)
        self.assertEqual(robot.task.item, "lettuce")
        self.state.orders.append(Order("soup", 20))
        robot.update_ai(DT, self.state)
        self.assertEqual(robot.task.item, "onion")

    def test_expired_recipe_no_longer_sets_priority(self):
        self.state.orders = [Order("salad", 50), Order("soup", -1)]
        self.state.player.carrying = "tomato"
        self.state.robot.update_ai(DT, self.state)
        self.assertEqual(self.state.robot.task.item, "lettuce")

    def test_same_deadline_keeps_list_order(self):
        first = Order("salad", 30)
        self.state.orders = [first, Order("soup", 30)]
        self.assertIs(self.state.priority_order, first)

    def test_priority_change_preserves_carried_old_ingredient(self):
        self.state.robot.carrying = "lettuce"
        self.state.player.carrying = "tomato"
        self.tick(15)
        self.assertTrue(any(s.held == "lettuce" for s in self.state.stations))
        self.assertTrue(any("chopped_onion" in s.contents for s in self.stations("pot")))

    def test_soup_after_early_preparation_and_counter_delivery(self):
        self.complete_soup("tomato")

    def test_soup_with_reverse_ingredient_roles(self):
        self.complete_soup("onion")

    def test_served_soup_hands_priority_to_salad(self):
        self.state.orders = [Order("soup", 60), Order("salad", 100)]
        self.state.order_timer = -1000  # Keep this scenario's two deadlines fixed.
        self.complete_soup("tomato")
        self.assertEqual(self.state.priority_order.kind, "salad")
        self.state.player.carrying = "lettuce"
        self.tick(12)
        counter = next(s for s in self.stations("counter") if s.held is None)
        self.state.player.carrying = "chopped_lettuce"
        place(self.state.player, approach_point(counter))
        self.state.player_interact()
        place(self.state.player, (80, 350))
        self.tick(25)
        self.assertEqual(self.state.robot.completed_soups, 1)
        self.assertEqual(self.state.robot.completed_salads, 1)
        self.assertEqual(self.state.orders, [])

    def test_human_can_deliver_straight_to_partial_pot(self):
        self.state.player.carrying = "tomato"
        self.tick(12)
        pot = next(s for s in self.stations("pot") if "chopped_onion" in s.contents)
        self.state.player.carrying = "chopped_tomato"
        place(self.state.player, approach_point(pot))
        self.state.player_interact()
        self.assertEqual(set(pot.contents), {"chopped_tomato", "chopped_onion"})
        place(self.state.player, (80, 350))
        self.tick(20)
        self.assertEqual(self.state.robot.completed_soups, 1)

    def test_existing_partial_pot_can_start_collaboration(self):
        self.stations("pot")[0].contents = ["chopped_tomato"]
        self.tick(35)
        self.assertEqual(self.state.robot.completed_soups, 1)

    def test_plate_waits_for_cooking_before_scooping(self):
        pot = self.stations("pot")[0]
        pot.contents = ["chopped_tomato", "chopped_onion"]
        self.state.robot.carrying = "plate"
        place(self.state.robot, approach_point(pot))
        self.tick(1)
        self.assertEqual(self.state.robot.carrying, "plate")
        self.assertEqual(self.state.robot.completed_soups, 0)
        self.tick(12)
        self.assertEqual(self.state.robot.completed_soups, 1)
        self.assertEqual(pot.contents, [])

    def test_chopped_tomato_goal_follows_priority_recipe(self):
        self.state.player.carrying = "chopped_tomato"
        intent = HumanIntentModel().observe(self.state, DT)
        self.assertEqual(intent.goal.kind, "pot")
        self.state.orders = [Order("salad", 30)]
        intent = HumanIntentModel().observe(self.state, DT)
        self.assertEqual(intent.goal.kind, "counter")

    def test_stationary_human_keeps_access_to_reserved_counter(self):
        self.state.orders = [Order("salad", 60)]
        robot = self.state.robot
        robot.priority_order = self.state.priority_order
        counter = self.stations("counter")[0]
        robot.carrying = "chopped_lettuce"
        robot.task = robot._pick(counter, "put", robot.carrying, "Store ingredient")
        place(robot, (526, 210))
        place(self.state.player, (352, 210))
        self.state.player.carrying = "chopped_tomato"
        self.tick(2)
        navigator = Navigator()
        bounds, obstacles = navigator._geometry(self.state.player, self.state)
        self.assertTrue(navigator._clear(approach_point(counter), approach_point(counter),
                                         bounds, obstacles))

    def test_complete_moving_human_soup_workflow(self):
        for delivery_kind in ("counter", "pot"):
            with self.subTest(delivery_kind=delivery_kind):
                self.setUp()
                state, human = self.state, self.state.player
                crate = self.stations("crate_tomato")[0]
                board = self.stations("board")[0]
                delivery = self.stations(delivery_kind)[0]
                navigator = Navigator()
                steps = [(crate, "interact"), (board, "interact"), (board, "chop"),
                         (board, "interact"), (delivery, "interact")]
                for _ in range(1800):
                    if steps:
                        target, action = steps[0]
                        if navigator.move_to(human, approach_point(target), state, DT):
                            if action == "chop":
                                state.update(DT, (0, 0), True)
                                if target.held == "chopped_tomato":
                                    steps.pop(0)
                                continue
                            interact(human, target, state)
                            steps.pop(0)
                    else:
                        navigator.move_to(human, (80, 350), state, DT)
                    state.update(DT, (0, 0), False)
                    self.assertFalse(state.robot.rect.colliderect(human.rect))
                    self.assertFalse(any(state.robot.rect.colliderect(s.rect)
                                         for s in state.stations))
                    if state.robot.completed_soups:
                        break
                self.assertFalse(steps, state.robot.status)
                self.assertEqual(state.robot.completed_soups, 1, state.robot.status)

    def test_serving_consumes_most_urgent_matching_order(self):
        slow, urgent = Order("soup", 80), Order("soup", 30)
        self.state.orders = [slow, urgent]
        self.state.robot.carrying = "soup"
        interact(self.state.robot, self.stations("serve")[0], self.state)
        self.assertEqual(len(self.state.orders), 1)
        self.assertIs(self.state.orders[0], slow)
        self.assertEqual(self.state.score, 130)

    def complete_soup(self, ingredient):
        complement = "onion" if ingredient == "tomato" else "tomato"
        self.state.player.carrying = ingredient
        self.tick(12)
        self.assertTrue(any("chopped_" + complement in s.contents for s in self.stations("pot")))
        self.assertEqual(self.state.robot.completed_soups, 0)
        counter = next(s for s in self.stations("counter") if s.held is None)
        self.state.player.carrying = "chopped_" + ingredient
        place(self.state.player, approach_point(counter))
        self.state.player_interact()
        place(self.state.player, (80, 350))
        self.tick(25)
        self.assertEqual(self.state.robot.completed_soups, 1)
        self.assertGreater(self.state.score, 0)


if __name__ == "__main__":
    unittest.main()
