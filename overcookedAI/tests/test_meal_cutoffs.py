"""Meal deadlines cancel old orders without treating them as missed deliveries."""
import csv
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import config as C
from game import GameState, Order
from logger import RunRecorder
from menu import RECIPES
from menu_planner import approach
from reactive_robot import ReactiveRobot


def state_with_all_recipes():
    state = GameState(seed=42, layout="divided")
    state._arrivals = ()
    state.orders = [Order(kind, 300) for kind in RECIPES]
    return state


class MealCutoffTests(unittest.TestCase):
    def test_exact_boundaries_cancel_only_finished_categories_without_penalty(self):
        state = state_with_all_recipes()
        original = list(state.orders)
        protected = state.priority_order
        state.score = 100
        for boundary, category, expected_count in ((60, "BREAKFAST", 5), (120, "LUNCH", 3), (180, "DINNER", 1)):
            state.game_time = C.GAME_TIME - (boundary - .01)
            before = list(state.orders)
            state.update(.005, (0, 0), False)
            self.assertEqual(state.orders, before)
            state.update(.005, (0, 0), False)
            self.assertEqual(len(state.orders), expected_count)
            self.assertFalse(any(o is not protected and RECIPES[o.kind].category == category for o in state.orders))
            self.assertTrue(all(o.cancel_reason == "meal_end" for o in original
                                if o is not protected and RECIPES[o.kind].category == category))
            self.assertTrue(any(o is protected for o in state.orders))
            self.assertIsNone(protected.cancel_reason)
            self.assertEqual(state.score, 100)

    def test_future_meals_remain_available_and_expired_categories_do_not_return(self):
        state = GameState(seed=42, layout="divided")
        state.orders = []
        state._arrivals = ((0, "tomato_soup", 200), (60, "cheese_sandwich", 200),
                           (120, "chicken_soup", 200), (120, "pasta_tomatoes", 200))
        state._arrival_cursor = 0
        state.update(.01, (0, 0), False)
        self.assertEqual([o.kind for o in state.orders], ["tomato_soup"])
        state.update(59.99, (0, 0), False)
        self.assertEqual([o.kind for o in state.orders], ["tomato_soup"])
        state.update(60, (0, 0), False)
        self.assertEqual([o.kind for o in state.orders], ["tomato_soup", "pasta_tomatoes"])
        self.assertEqual(state._arrival_cursor, len(state._arrivals))

    def test_large_step_cancels_multiple_finished_meals(self):
        state = state_with_all_recipes()
        protected = state.priority_order
        state.update(120, (0, 0), False)
        self.assertEqual({RECIPES[o.kind].category for o in state.orders if o is not protected}, {"DINNER"})

    def test_normal_order_expiry_still_applies_its_penalty(self):
        state = state_with_all_recipes()
        order = Order("cheese_sandwich", .01)
        state.orders = [order]
        state.score = 100
        state.update(.02, (0, 0), False)
        self.assertEqual(state.orders, [])
        self.assertIsNone(order.cancel_reason)
        self.assertEqual(state.score, 100 - C.SCORE_EXPIRE_PENALTY)

    def test_robot_cannot_serve_a_cancelled_meal_on_the_boundary_frame(self):
        state = GameState(ReactiveRobot, seed=42, layout="divided")
        state._arrivals = ()
        state.orders = [Order("tomato_soup", 50), Order("cheese_sandwich", 100)]
        serve = next(s for s in state.stations if s.kind == "serve")
        state.robot.rect.center = approach(serve, state)
        state.robot.pos.update(state.robot.rect.topleft)
        state.robot.carrying = "cheese_sandwich"
        state.game_time = C.GAME_TIME - 59.99
        state.update(.01, (0, 0), False)
        self.assertEqual([o.kind for o in state.orders], ["tomato_soup"])
        self.assertEqual(state.score, 0)

    def test_protected_order_survives_later_frames_and_expires_normally(self):
        state = state_with_all_recipes()
        protected = Order("cheese_sandwich", .1)
        removed = Order("ham_sandwich", 100)
        state.orders = [removed, protected]
        state.game_time = C.GAME_TIME - 59.99
        state.score = 100
        state.update(.01, (0, 0), False)
        self.assertEqual(state.orders, [protected])
        state.update(.01, (0, 0), False)
        self.assertEqual(state.orders, [protected])
        state.update(.1, (0, 0), False)
        self.assertEqual(state.orders, [])
        self.assertIsNone(protected.cancel_reason)
        self.assertEqual(removed.cancel_reason, "meal_end")
        self.assertEqual(state.score, 100 - C.SCORE_EXPIRE_PENALTY)

    def test_robot_can_finish_the_protected_order_after_the_boundary(self):
        state = GameState(ReactiveRobot, seed=42, layout="divided")
        state._arrivals = ()
        state.orders = [Order("cheese_sandwich", 100)]
        serve = next(s for s in state.stations if s.kind == "serve")
        state.robot.rect.center = approach(serve, state)
        state.robot.pos.update(state.robot.rect.topleft)
        state.robot.carrying = "cheese_sandwich"
        state.game_time = C.GAME_TIME - 59.99
        state.update(.01, (0, 0), False)
        self.assertEqual(state.orders, [])
        self.assertGreater(state.score, 0)

    def test_cancellation_is_logged_separately_from_expiry_and_serving(self):
        state = state_with_all_recipes()
        state.game_time = C.GAME_TIME - 59.99
        with tempfile.TemporaryDirectory() as folder:
            recorder = RunRecorder(dict(participant="test", robot="none", condition="cutoff", seed=42), folder)
            recorder.start(state)
            recorder.before(state)
            state.update(.01, (0, 0), False)
            recorder.after(state, .01)
            recorder.finish(state, completed=False)
            with open(recorder.path, newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            cancelled = [row for row in rows if row["action"] == "order_cancelled"]
            self.assertEqual(len(cancelled), 1)
            self.assertTrue(all(row["info"] == "meal_end" and float(row["t"]) == 60 for row in cancelled))
            self.assertFalse(any(row["action"] in ("serve", "order_expired") for row in rows))
            with open(os.path.join(folder, "summary.csv"), newline="", encoding="utf-8") as stream:
                summary = next(csv.DictReader(stream))
            self.assertEqual((summary["expired"], summary["served_human"], summary["served_robot"]), ("0", "0", "0"))


if __name__ == "__main__":
    unittest.main()
