"""End-to-end divided kitchen collaboration and reactive-only decisions."""
import unittest

import pygame

import config as C
from game import GameState, Order, interaction_target
from navigation import Navigator, approach_point
from reactive_robot import ReactiveRobot

DT = 1 / 30


class ReactiveRobotTests(unittest.TestCase):
    def setUp(self):
        self.state = GameState(ReactiveRobot, seed=0, layout="divided", legacy_menu=True)
        self.state.orders = [Order("salad", 150)]
        self.state.order_timer = -1000
        self.robot = self.state.robot
        self.handoffs = [s for s in self.state.stations if s.owner == "shared"]

    def tick(self, frames=1):
        for _ in range(frames):
            before = self.robot.rect.copy()
            self.state.update(DT, (0, 0), False)
            self.assertTrue(pygame.Rect(*C.PLAY_AREA).contains(self.robot.rect))
            self.assertGreaterEqual(self.robot.rect.left, 582)
            self.assertFalse(self.robot.rect.colliderect(self.state.player.rect))
            self.assertFalse(any(self.robot.rect.colliderect(s.rect) for s in self.state.stations))
            self.assertFalse(any(self.robot.rect.colliderect(w) for w in self.state.walls))
            self.assertLessEqual(pygame.Vector2(before.center).distance_to(self.robot.rect.center),
                                 C.ROBOT_SPEED * DT + 1.5)

    def deliver(self, item, index=0):
        counter = self.handoffs[index]
        for _ in range(1200):
            if counter.held is None:
                break
            self.tick()
        self.assertIsNone(counter.held, self.robot.status)
        self.state.player.rect.topleft = (counter.rect.left - 42, counter.rect.y + 11)
        self.state.player.pos.update(self.state.player.rect.topleft)
        self.state.player.carrying = item
        self.assertIs(interaction_target(self.state.player, self.state.stations), counter)
        self.state.player_interact()
        self.assertEqual(counter.held, item)

    def finish(self, recipe, previous=0, frames=2100):
        for _ in range(frames):
            self.tick()
            if getattr(self.robot, "completed_" + recipe + "s") > previous:
                return
        self.fail(f"No {recipe} delivered: {self.robot.status}; carry={self.robot.carrying}; "
                  f"contents={[(s.kind, s.held, s.contents) for s in self.state.stations if s.held or s.contents]}")

    def test_raw_salad_from_both_handoffs(self):
        self.deliver("tomato", 0)
        self.deliver("lettuce", 1)
        self.finish("salad")
        self.assertGreater(self.state.score, 0)

    def test_human_collects_and_delivers_using_real_navigation_and_interactions(self):
        navigator = Navigator()
        for name, counter in zip(("tomato", "lettuce"), self.handoffs):
            crate = next(s for s in self.state.stations if s.kind == "crate_" + name)
            destinations = ((crate, approach_point(crate)),
                            (counter, pygame.Vector2(counter.rect.left - 26, counter.rect.centery)))
            for station, goal in destinations:
                for _ in range(600):
                    arrived = navigator.move_to(self.state.player, goal, self.state, DT)
                    self.tick()
                    self.assertLessEqual(self.state.player.rect.right, 518)
                    self.assertFalse(any(self.state.player.rect.colliderect(s.rect)
                                         for s in self.state.stations))
                    if arrived:
                        break
                else:
                    self.fail("Human could not reach " + station.label)
                self.assertIs(interaction_target(self.state.player, self.state.stations), station)
                self.state.player_interact()
        self.finish("salad")

    def test_raw_soup_is_chopped_cooked_plated_and_served(self):
        self.state.orders = [Order("soup", 150)]
        self.deliver("onion", 1)
        self.deliver("tomato", 0)
        self.finish("soup")
        pot = next(s for s in self.state.stations if s.kind == "pot")
        self.assertEqual(pot.contents, [])
        self.assertFalse(pot.ready)

    def test_chopped_and_mixed_preparation_for_both_recipes(self):
        for recipe, items in (("salad", ("chopped_lettuce", "tomato")),
                              ("soup", ("chopped_onion", "chopped_tomato"))):
            with self.subTest(recipe=recipe):
                self.setUp()
                self.state.orders = [Order(recipe, 150)]
                self.deliver(items[0], 0)
                self.deliver(items[1], 1)
                self.finish(recipe)

    def test_empty_kitchen_does_not_start_work_or_predict(self):
        before = self.robot.rect.copy()
        self.state.player.carrying = "tomato"
        self.tick(180)
        self.assertEqual(self.robot.rect, before)
        self.assertIsNone(self.robot.carrying)
        self.assertIn("Waiting for ingredients", self.robot.status)
        self.assertFalse(hasattr(self.robot, "model"))
        self.assertFalse(hasattr(self.robot, "intent"))
        revision = self.robot.diagnostic_revision
        self.tick(180)
        self.assertEqual(self.robot.diagnostic_revision, revision)

    def test_missing_ingredient_waits_then_resumes(self):
        self.deliver("tomato", 0)
        self.tick(600)
        self.assertEqual(self.robot.completed_salads, 0)
        self.assertIn("Waiting for ingredients", self.robot.status)
        before = self.robot.rect.copy()
        self.tick(60)
        self.assertEqual(before, self.robot.rect)
        self.deliver("lettuce", 1)
        self.finish("salad")

    def test_less_urgent_available_recipe_is_completed(self):
        self.state.orders = [Order("salad", 90), Order("soup", 150)]
        self.deliver("onion", 0)
        self.deliver("tomato", 1)
        self.finish("soup")
        self.assertEqual(self.robot.completed_salads, 0)

    def test_delayed_onion_keeps_prepared_tomato_available_for_soup(self):
        self.state.orders = [Order("salad", 100), Order("soup", 150)]
        self.deliver("tomato", 0)
        self.tick(450)
        self.assertFalse(any(s.held == "plated_tomato" for s in self.state.stations))
        self.deliver("onion", 1)
        self.finish("soup")

    def test_urgency_selects_available_ingredient(self):
        self.state.orders = [Order("salad", 150), Order("soup", 90)]
        self.deliver("lettuce", 0)
        self.deliver("onion", 1)
        self.tick()
        self.assertEqual(self.robot.task.recipe, "soup")
        self.assertEqual(self.robot.task.item, "onion")

    def test_consecutive_orders_continue_without_restart(self):
        self.state.orders = [Order("salad", 130), Order("soup", 150), Order("salad", 170)]
        self.deliver("tomato", 0)
        self.deliver("lettuce", 1)
        self.finish("salad")
        self.deliver("onion", 0)
        self.deliver("tomato", 1)
        self.finish("soup")
        self.deliver("chopped_lettuce", 0)
        self.deliver("chopped_tomato", 1)
        self.finish("salad", previous=1)
        self.assertEqual(self.robot.completed_salads, 2)

    def test_removed_delivery_cancels_task(self):
        self.deliver("tomato", 0)
        self.tick()
        self.assertEqual(self.robot.task.item, "tomato")
        self.handoffs[0].held = None
        before = self.robot.rect.copy()
        self.tick(60)
        self.assertIsNone(self.robot.task)
        self.assertEqual(before, self.robot.rect)

    def test_blocked_handoff_waits_and_recovers(self):
        self.deliver("tomato", 0)
        goal = self.robot._approach(self.handoffs[0])
        self.state.walls.append(pygame.Rect(goal.x - 22, goal.y - 22, 44, 44))
        before = self.robot.rect.copy()
        self.tick(120)
        self.assertEqual(before, self.robot.rect)
        self.state.walls.pop()
        self.deliver("lettuce", 1)
        self.finish("salad")

    def test_contact_with_right_wall_and_counter_can_escape(self):
        for position in ((1058, 300), (608, 131), (1058, 184), (1058, 468)):
            with self.subTest(position=position):
                self.setUp()
                self.robot.rect.topleft = position
                self.robot.pos.update(position)
                self.deliver("chopped_tomato", 0)
                self.deliver("chopped_lettuce", 1)
                self.finish("salad")

    def test_pause_and_restart_state(self):
        self.deliver("tomato", 0)
        self.robot.enabled = False
        before = self.robot.rect.copy()
        self.tick(60)
        self.assertEqual(before, self.robot.rect)
        self.robot.enabled = True
        self.deliver("lettuce", 1)
        self.finish("salad")
        restarted = GameState(ReactiveRobot, seed=0, layout="divided", legacy_menu=True)
        self.assertIsNone(restarted.robot.carrying)
        self.assertEqual(restarted.robot.completed_salads, 0)
        self.assertTrue(all(s.held is None for s in restarted.stations))

    def test_duplicate_delivery_does_not_create_storage_loop(self):
        self.deliver("tomato", 0)
        self.deliver("tomato", 1)
        self.tick(450)
        self.assertIn("Waiting for ingredients", self.robot.status)
        self.assertEqual(self.handoffs[1].held, "tomato")
        self.deliver("lettuce", 0)
        self.finish("salad")

    def test_expired_recipe_board_is_cleared_for_new_delivery(self):
        board = next(s for s in self.state.stations if s.owner == "robot" and s.kind == "board")
        board.held = "onion"
        self.deliver("tomato", 0)
        self.deliver("lettuce", 1)
        self.finish("salad")
        self.assertTrue(any(s.held == "chopped_onion" for s in self.state.stations))

    def test_human_waiting_at_handoff_does_not_reserve_robot_equipment(self):
        self.deliver("chopped_tomato", 0)
        self.deliver("chopped_lettuce", 1)
        # The human remains touching the left side of the last handoff.
        self.finish("salad")

    def test_ready_orders_use_urgency_and_changes_are_observed(self):
        self.state.orders = [Order("salad", 140), Order("soup", 100)]
        self.deliver("chopped_lettuce", 0)
        self.deliver("chopped_onion", 1)
        counter = next(s for s in self.state.stations if s.owner == "robot" and s.kind == "counter")
        counter.held = "chopped_tomato"
        self.tick()
        self.assertEqual(self.robot.recipe, "soup")
        self.state.orders[0].time_left = 70
        self.tick()
        self.assertEqual(self.robot.recipe, "salad")


if __name__ == "__main__":
    unittest.main()

