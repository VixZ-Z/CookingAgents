"""Meal timing, actual recipes, seeded scheduling, visibility and navigation."""
from collections import Counter
from dataclasses import fields
import csv
import os
import random
import tempfile
import unittest

import pygame

import config as C
from anticipatory_robot import AnticipatoryRobot
from experiment import RobotObservation, ScheduledOrder, build_schedule, sample_recipe
from game import GameState, Player, interact
from navigation import Navigator, approach_point
from reactive_robot import ReactiveRobot
from recipes import MEAL_RECIPES, MEAL_KINDS, MEAL_INGREDIENTS, meal_period
from logger import RunRecorder

DT = 1 / 30
ROBOTS = (ReactiveRobot, AnticipatoryRobot)


def create(robot=ReactiveRobot, seed=42, recipe=None):
    return GameState(robot, seed=seed, layout="reactive", recipe=recipe, experiment=True)


def deliver(state, item, index):
    station = [s for s in state.stations if s.owner == "shared"][index]
    if station.held is not None:
        raise AssertionError("Handoff is occupied")
    state.player.rect.topleft = (station.rect.left - 42, station.rect.y + 11)
    state.player.pos.update(state.player.rect.topleft)
    state.player.carrying = item
    state.player_interact()
    if station.held != item:
        raise AssertionError("Delivery failed")


class ScheduleTests(unittest.TestCase):
    def test_engine_passes_only_observations_at_construction_and_update(self):
        class Probe:
            def __init__(self, observation):
                if not isinstance(observation, RobotObservation):
                    raise AssertionError("Engine leaked at robot construction")
                self.observation = observation
                self.calls = 0

            def update_ai(self, dt, observation):
                if not isinstance(observation, RobotObservation):
                    raise AssertionError("Engine leaked at robot update")
                self.observation = observation
                self.calls += 1

        state = create(Probe)
        state.update(1, (0, 0), False)
        self.assertGreater(state.robot.calls, 0)
        self.assertEqual(len(state.robot.observation.orders), C.INITIAL_ORDERS)

    def test_scheduling_is_independent_of_update_cadence(self):
        small, large = create(robot=None), create(robot=None)
        for _ in range(180):
            small.update(1, (0, 0), False)
        large.update(180, (0, 0), False)
        self.assertEqual(small._order_schedule, large._order_schedule)
        for a, b in zip(small._experiment_orders, large._experiment_orders):
            self.assertEqual(a.outcome, b.outcome)
            if a.appeared_at is not None:
                self.assertAlmostEqual(a.appeared_at, b.appeared_at, places=6)
            else:
                self.assertIsNone(b.appeared_at)

    def test_period_boundaries_and_end(self):
        for time, expected in ((0, "breakfast"), (59.999, "breakfast"), (60, "lunch"),
                               (119.999, "lunch"), (120, "dinner"), (180, "dinner")):
            self.assertEqual(meal_period(time), expected)
        state = create(robot=None)
        state.update(60, (0, 0), False)
        self.assertAlmostEqual(state.elapsed, 60)
        self.assertEqual(state.meal_period, "lunch")
        before = state.elapsed
        state.update(0, (0, 0), False)
        self.assertEqual(state.elapsed, before)
        state.update(60, (0, 0), False)
        self.assertEqual(state.meal_period, "dinner")
        state.update(75, (0, 0), False)
        self.assertEqual(state.elapsed, 180)
        self.assertTrue(state.game_over)

    def test_distribution_per_category_and_per_recipe(self):
        for time in (0, 60, 120):
            rng = random.Random(123)
            counts = Counter(sample_recipe(rng, time) for _ in range(30000))
            category_counts = Counter()
            for kind, count in counts.items():
                category_counts[MEAL_RECIPES[kind].category] += count
                expected = 0.4 if MEAL_RECIPES[kind].category == meal_period(time) else 0.05
                self.assertAlmostEqual(count / 30000, expected, delta=0.012)
            for category, count in category_counts.items():
                self.assertAlmostEqual(count / 30000, 0.8 if category == meal_period(time) else 0.1,
                                       delta=0.015)
            self.assertEqual(set(counts), set(MEAL_KINDS))

    def test_reproducible_across_conditions_and_robot_randomness(self):
        for seed in (42, 123, 789):
            reactive, anticipatory = create(seed=seed), create(AnticipatoryRobot, seed=seed)
            self.assertEqual(reactive._order_schedule, anticipatory._order_schedule)
            self.assertEqual(reactive._order_schedule, build_schedule(seed))
            random.seed(seed + 100)
            for _ in range(100):
                random.random()
            self.assertEqual(reactive._order_schedule, build_schedule(seed))
            self.assertNotEqual(reactive._order_schedule, build_schedule(seed + 1))
            self.assertEqual([s.scheduled_at for s in reactive._order_schedule],
                             [0, 0, 0] + list(range(15, 180, 15)))

    def test_full_queue_delays_preserve_schedule_and_ids(self):
        state = create(robot=None)
        schedule = state._order_schedule
        state.update(35, (0, 0), False)
        self.assertEqual(len(state.orders), C.MAX_ORDERS)
        delayed = state._experiment_orders[4]
        self.assertEqual(delayed.scheduled_at, 30)
        self.assertIsNone(delayed.appeared_at)
        self.assertEqual(delayed.outcome, "queued")
        player = Player(0, 0)
        player.carrying = state.orders[0].kind
        interact(player, next(s for s in state.stations if s.kind == "serve"), state)
        state.update(0.05, (0, 0), False)
        self.assertAlmostEqual(delayed.appeared_at, 35)
        self.assertEqual(state._order_schedule, schedule)
        self.assertIs(state.orders[-1], delayed)
        self.assertEqual(delayed.order_id, 5)

    def test_period_change_keeps_visible_orders_valid(self):
        state = create(robot=None, recipe="cheese_sandwich")
        order = state.orders[0]
        for visible in state.orders:
            visible.time_left = 160
        order.time_left = 150
        state.update(60, (0, 0), False)
        self.assertTrue(any(order is o for o in state.orders))
        player = Player(0, 0)
        for _ in range(len(state.orders)):
            player.carrying = "cheese_sandwich"
            interact(player, next(s for s in state.stations if s.kind == "serve"), state)
            if order.outcome == "completed":
                break
        self.assertEqual(order.outcome, "completed")
        self.assertAlmostEqual(order.completed_at, 60)

    def test_observations_contain_no_engine_future_seed_or_rng(self):
        for robot in ROBOTS:
            state = create(robot)
            state.update(0.6, (0, 0), False)
            observation = state.robot_observation()
            self.assertIsInstance(observation, RobotObservation)
            for name in ("_order_schedule", "_experiment_orders", "_pending_orders", "rng", "seed",
                         "_seed", "add_order", "_dispatch_orders", "__dict__"):
                self.assertFalse(hasattr(observation, name), name)
            self.assertEqual(len(observation.orders), C.INITIAL_ORDERS)
            self.assertTrue(all(o.appeared_at <= observation.elapsed for o in observation.orders))
            pending, seen = [observation], set()
            while pending:
                obj = pending.pop()
                if id(obj) in seen:
                    continue
                seen.add(id(obj))
                self.assertNotIsInstance(obj, (GameState, random.Random, ScheduledOrder))
                if isinstance(obj, dict):
                    pending.extend(obj.values())
                elif isinstance(obj, (list, tuple, set)):
                    pending.extend(obj)
                elif isinstance(obj, RobotObservation):
                    pending.extend(getattr(obj, f.name) for f in fields(obj))
                elif hasattr(obj, "__dict__") and not isinstance(obj, type):
                    pending.extend(vars(obj).values())


class MealRecipeTests(unittest.TestCase):
    def assert_safe(self, state):
        robot = state.robot
        self.assertGreaterEqual(robot.rect.left, 582)
        self.assertTrue(pygame.Rect(*C.PLAY_AREA).contains(robot.rect))
        self.assertFalse(robot.rect.colliderect(state.player.rect))
        self.assertFalse(any(robot.rect.colliderect(s.rect) for s in state.stations))
        self.assertFalse(any(robot.rect.colliderect(w) for w in state.walls))

    def finish(self, state, recipe, limit=1800):
        for _ in range(limit):
            state.update(DT, (0, 0), False)
            self.assert_safe(state)
            if state.robot.completed_meals[recipe]:
                return
        self.fail(f"{type(state.robot).__name__} failed {recipe}: {state.robot.status}, "
                  f"carry={state.robot.carrying}, "
                  f"stations={[(s.kind, s.held, s.contents) for s in state.stations if s.held or s.contents]}")

    def test_all_six_recipes_are_prepared_and_scored_by_both_robots(self):
        self.assertEqual(len(MEAL_KINDS), 6)
        for robot in ROBOTS:
            for recipe, definition in MEAL_RECIPES.items():
                with self.subTest(robot=robot.__name__, recipe=recipe):
                    state = create(robot, recipe=recipe)
                    self.assertTrue(all(o.kind == recipe for o in state.orders))
                    deliver(state, definition.ingredients[0], 0)
                    deliver(state, definition.ingredients[1], 1)
                    self.finish(state, recipe)
                    self.assertGreaterEqual(state.score, C.SCORE_DELIVERY)
                    completed = [o for o in state._experiment_orders if o.outcome == "completed"]
                    self.assertEqual(len(completed), 1)
                    self.assertEqual(completed[0].kind, recipe)
                    if definition.cooked:
                        self.assertGreaterEqual(completed[0].completed_at, C.POT_TIME)

    def test_same_geometry_and_access_to_all_ingredients_and_required_stations(self):
        a, b = create(), create(AnticipatoryRobot)
        self.assertEqual(a.layout, b.layout)
        self.assertEqual(a.walls, b.walls)
        self.assertEqual({s.kind[6:] for s in a.stations if s.kind.startswith("crate_")}, set(MEAL_INGREDIENTS))
        for state in (a, b):
            for station in state.stations:
                if station.owner in ("robot", "shared"):
                    goal = state.robot.meal_policy.approach(station)
                    self.assertTrue(state.robot.navigator._route(state.robot, goal, state.robot_observation(), None),
                                    (type(state.robot).__name__, station.label))
            navigator = Navigator()
            for station in (s for s in state.stations if s.owner == "human"):
                self.assertTrue(navigator._route(state.player, approach_point(station), state.robot_observation(), None),
                                station.label)

    def test_human_walks_to_dispensers_and_handoffs_for_a_complete_main_course(self):
        for robot in ROBOTS:
            with self.subTest(robot=robot.__name__):
                state = create(robot, recipe="chicken_potatoes")
                navigator = Navigator()
                handoffs = [s for s in state.stations if s.owner == "shared"]
                for name, counter in zip(("chicken", "potato"), handoffs):
                    crate = next(s for s in state.stations if s.kind == "crate_" + name)
                    goals = ((crate, approach_point(crate)),
                             (counter, pygame.Vector2(counter.rect.left - 26, counter.rect.centery)))
                    for station, goal in goals:
                        for _ in range(600):
                            arrived = navigator.move_to(state.player, goal, state.robot_observation(), DT)
                            state.update(DT, (0, 0), False)
                            self.assert_safe(state)
                            self.assertLessEqual(state.player.rect.right, 518)
                            self.assertFalse(any(state.player.rect.colliderect(s.rect) for s in state.stations))
                            if arrived:
                                break
                        else:
                            self.fail("Human could not reach " + station.label)
                        state.player_interact()
                self.finish(state, "chicken_potatoes")

    def test_both_robots_escape_legal_wall_and_counter_contacts(self):
        for robot in ROBOTS:
            for position in ((1058, 184), (1058, 468), (608, 131), (582, 330)):
                with self.subTest(robot=robot.__name__, position=position):
                    state = create(robot, recipe="ham_sandwich")
                    state.robot.rect.topleft = position
                    state.robot.pos.update(position)
                    deliver(state, "bread", 0)
                    deliver(state, "ham", 1)
                    self.finish(state, "ham_sandwich")

    def test_only_anticipatory_robot_prepares_before_a_delivery(self):
        reactive, anticipatory = create(recipe="cheese_sandwich"), create(AnticipatoryRobot, recipe="cheese_sandwich")
        before = reactive.robot.rect.copy()
        for _ in range(180):
            reactive.update(DT, (0, 0), False)
            anticipatory.update(DT, (0, 0), False)
        self.assertEqual(reactive.robot.rect, before)
        self.assertNotEqual(anticipatory.robot.rect, before)
        self.assertFalse(hasattr(reactive.robot, "model"))
        self.assertIsNone(anticipatory.robot.model.predict_start("cheese_sandwich"))

    def test_missing_second_ingredient_and_learning_then_resumption(self):
        for robot in ROBOTS:
            with self.subTest(robot=robot.__name__):
                state = create(robot, recipe="cheese_sandwich")
                state.player.carrying = "cheese"
                state.update(DT, (0, 0), False)  # Observe the actual pickup before delivery.
                deliver(state, "cheese", 0)
                for _ in range(180):
                    state.update(DT, (0, 0), False)
                self.assertEqual(state.robot.completed_meals["cheese_sandwich"], 0)
                if robot is AnticipatoryRobot:
                    prediction = state.robot.model.predict_start("cheese_sandwich")
                    self.assertEqual(prediction.ingredient, "cheese")
                    self.assertEqual(prediction.observations, 1)
                deliver(state, "bread", 1)
                self.finish(state, "cheese_sandwich")

    def test_second_order_and_expired_cooker_batch_do_not_deadlock(self):
        for robot in ROBOTS:
            with self.subTest(robot=robot.__name__):
                state = create(robot, recipe="cheese_sandwich")
                cooker = next(s for s in state.stations if s.kind == "pot")
                cooker.contents = ["meat"]
                deliver(state, "bread", 0)
                deliver(state, "cheese", 1)
                self.finish(state, "cheese_sandwich")
                # Change only currently visible orders, as an experimenter/test
                # fixture, to exercise removal of a now-obsolete partial batch.
                state.orders[0].kind = "tomato_soup"
                state.orders[0].time_left = 60
                deliver(state, "tomato", 0)
                deliver(state, "water", 1)
                self.finish(state, "tomato_soup")

    def test_expired_finished_batch_is_stored_to_free_cooker(self):
        for robot in ROBOTS:
            with self.subTest(robot=robot.__name__):
                state = create(robot, recipe="tomato_soup")
                cooker = next(s for s in state.stations if s.kind == "pot")
                cooker.contents, cooker.ready = ["meat", "vegetables"], True
                deliver(state, "water", 0)
                deliver(state, "tomato", 1)
                self.finish(state, "tomato_soup")
                self.assertTrue(any(s.held == "meat_vegetables" for s in state.stations))

    def test_temporarily_blocked_handoff_is_retried_when_clear(self):
        for robot in ROBOTS:
            with self.subTest(robot=robot.__name__):
                state = create(robot, recipe="ham_sandwich")
                deliver(state, "bread", 0)
                deliver(state, "ham", 1)
                handoffs = [s for s in state.stations if s.owner == "shared"]
                blockers = [pygame.Rect(s.rect.right, s.rect.y, 50, 64) for s in handoffs]
                state.walls.extend(blockers)
                for _ in range(60):
                    state.update(DT, (0, 0), False)
                    self.assert_safe(state)
                self.assertEqual(state.robot.completed_meals["ham_sandwich"], 0)
                del state.walls[-2:]
                self.finish(state, "ham_sandwich")


class ExperimentLoggingTests(unittest.TestCase):
    def read(self, path):
        with open(path, newline="", encoding="utf-8") as file:
            return list(csv.DictReader(file))

    def record(self, robot, folder, recipe=None):
        state = create(robot, recipe=recipe)
        recorder = RunRecorder({"participant": "T", "condition": robot.__name__,
                                "robot": "reactive" if robot is ReactiveRobot else "anticipatory",
                                "seed": 42, "recipe": recipe or "meal_periods"}, folder)
        recorder.start(state)
        return state, recorder

    def test_completed_order_ledger_and_interaction_logs(self):
        for robot in ROBOTS:
            with self.subTest(robot=robot.__name__), tempfile.TemporaryDirectory() as folder:
                state, recorder = self.record(robot, folder, "cheese_sandwich")
                state.player.carrying = "bread"
                recorder.before(state)
                deliver(state, "bread", 0)
                recorder.after(state, 0)
                state.player.carrying = "cheese"
                recorder.before(state)
                deliver(state, "cheese", 1)
                recorder.after(state, 0)
                for _ in range(1200):
                    recorder.before(state)
                    state.update(DT, (0, 0), False)
                    recorder.after(state, DT)
                    if state.score:
                        break
                recorder.finish(state, completed=False)
                ledger = self.read(os.path.splitext(recorder.path)[0] + "_orders.csv")
                events = self.read(recorder.path)
                self.assertEqual(len(ledger), len(state._order_schedule))
                completed = [row for row in ledger if row["outcome"] == "completed"]
                self.assertEqual(len(completed), 1)
                row = completed[0]
                self.assertEqual(row["seed"], "42")
                self.assertEqual(row["meal_period"], "breakfast")
                self.assertEqual(row["layout"], "reactive")
                self.assertAlmostEqual(float(row["completion_duration"]), float(row["completed_at"]) - float(row["appeared_at"]), places=5)
                self.assertTrue(any(e["actor"] == "human" and e["action"] == "put" for e in events))
                self.assertTrue(any(e["actor"] == "robot" and e["action"] == "serve" for e in events))
                self.assertTrue(all(e["meal_period"] == "breakfast" for e in events))
                self.assertTrue(any(r["censored"] == "1" for r in ledger))

    def test_full_trials_log_identical_schedules_delays_expiries_and_misses(self):
        ledgers = []
        for robot in ROBOTS:
            with tempfile.TemporaryDirectory() as folder:
                state, recorder = self.record(robot, folder)
                for _ in range(5400):
                    recorder.before(state)
                    state.update(DT, (0, 0), False)
                    recorder.after(state, DT)
                recorder.finish(state, completed=state.game_over)
                ledger = self.read(os.path.splitext(recorder.path)[0] + "_orders.csv")
                ledgers.append([(r["order_id"], r["order_kind"], r["scheduled_at"]) for r in ledger])
                self.assertTrue(all(r["run_duration"] == "180.0" for r in ledger))
                self.assertTrue(all(r["run_completed"] == "1" for r in ledger))
                self.assertTrue(any(r["outcome"] == "expired" for r in ledger))
                self.assertTrue(any(r["outcome"] == "missed" for r in ledger))
                self.assertTrue(any(r["delay"] and float(r["delay"]) > 0 for r in ledger))
                events = self.read(recorder.path)
                self.assertEqual([e["item"] for e in events if e["action"] == "meal_period"], ["lunch", "dinner"])
        self.assertEqual(ledgers[0], ledgers[1])


if __name__ == "__main__":
    unittest.main()
