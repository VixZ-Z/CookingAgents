"""Handoff timing, real scheduling effects, divided-kitchen safety, and logging."""
import contextlib
import csv
import io
import json
import math
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

import config as C
from game import GameState, Order
from human_transitions import ActionSymbol, HumanActionEvent
from logger import RunRecorder
from main import get_robot_class, main
from navigation import Navigator, approach_point
from reactive_robot import ReactiveRobot, AnticipatoryFixedHRobot, AnticipatoryDynamicHRobot


DT = 1 / 30


def place(actor, center):
    actor.rect.center = center
    actor.pos.update(actor.rect.topleft)


def make_state(robot=AnticipatoryFixedHRobot, recipe="salad", legacy_menu=True):
    state = GameState(robot, seed=0, layout="divided", recipe=recipe, legacy_menu=True)
    state.orders = [Order(recipe, 150)]
    state.order_timer = -1000
    return state


def find(state, kind, owner=None):
    return next(s for s in state.stations if s.kind == kind
                and (owner is None or s.owner == owner))


def use(state, station):
    goal = ((station.rect.left - 26, station.rect.centery)
            if station.owner == "shared" else approach_point(station))
    place(state.player, goal)
    state.player_interact()


def tick(state, seconds):
    for _ in range(round(seconds / DT)):
        before = state.robot.rect.copy()
        state.update(DT, (0, 0), False)
        assert state.robot.rect.left >= 582
        assert not state.robot.rect.colliderect(state.player.rect)
        assert not any(state.robot.rect.colliderect(s.rect) for s in state.stations)
        assert not any(state.robot.rect.colliderect(w) for w in state.walls)
        assert pygame.Vector2(before.center).distance_to(state.robot.rect.center) <= C.ROBOT_SPEED * DT + 1.5


class HorizonEstimateTests(unittest.TestCase):
    def test_fixed_h_counts_down_and_does_not_reset_on_movement(self):
        state = make_state()
        state.robot.enabled = False
        use(state, find(state, "crate_tomato"))
        state.update(0.1, (0, 0), False)
        self.assertAlmostEqual(state.robot.horizon.remaining, 3.9)
        anchor = state.robot.horizon.anchor_time
        for _ in range(10):
            state.update(0.1, (1, 0), False)
        self.assertAlmostEqual(state.robot.horizon.remaining, 2.9)
        self.assertEqual(state.robot.horizon.anchor_time, anchor)

    def test_new_completed_action_restarts_fixed_h_once(self):
        state = make_state()
        state.robot.enabled = False
        use(state, find(state, "crate_tomato"))
        tick(state, 1)
        use(state, find(state, "board", "human"))
        state.update(0.1, (0, 0), False)
        self.assertAlmostEqual(state.robot.horizon.remaining, 3.9)
        state.update(0.1, (0, 0), False)
        self.assertAlmostEqual(state.robot.horizon.remaining, 3.8)

    def test_expired_estimate_does_not_repeat_or_generate_phantom_supplies(self):
        state = make_state()
        use(state, find(state, "crate_tomato"))
        tick(state, 7)
        self.assertEqual(state.robot.horizon.remaining, 0)
        self.assertEqual(state.robot.horizon.anchor_time, 0)
        self.assertFalse(any(s.held for s in state.stations if s.owner == "shared"))
        self.assertIsNone(state.robot.task)
        self.assertEqual(state.score, 0)

    def test_no_evidence_means_unknown_in_both_modes(self):
        for robot in (AnticipatoryFixedHRobot, AnticipatoryDynamicHRobot):
            state = make_state(robot)
            before = state.robot.rect.copy()
            tick(state, 1)
            self.assertIsNone(state.robot.horizon.remaining)
            self.assertIsNone(state.robot.task)
            self.assertEqual(state.robot.rect, before)

    def test_dynamic_h_changes_with_distance(self):
        state = make_state(AnticipatoryDynamicHRobot)
        state.robot.enabled = False
        state.player.carrying = "chopped_tomato"
        place(state.player, (400, 350))
        state.update(0.3, (0, 0), False)
        near = state.robot.horizon.remaining
        place(state.player, (70, 350))
        state.update(0.3, (0, 0), False)
        self.assertGreater(state.robot.horizon.remaining, near)

    def test_dynamic_h_learns_observed_walking_speed(self):
        estimates = []
        for speed in (115, 230):
            state = make_state(AnticipatoryDynamicHRobot)
            state.robot.enabled = False
            state.player.carrying = "tomato"
            state.update(DT, (0, 0), False)
            with patch.object(C, "PLAYER_SPEED", speed):
                for _ in range(3):
                    state.update(0.1, (1, 0), False)
            # Integer body positions quantise the effective speed at 0.1 s steps.
            self.assertAlmostEqual(state.robot.horizon.speed, speed, delta=6)
            estimates.append(state.robot.horizon.remaining)
        self.assertGreater(estimates[0], estimates[1])

    def test_dynamic_h_tracks_stationary_human_chopping_progress(self):
        state = make_state(AnticipatoryDynamicHRobot)
        state.robot.enabled = False
        use(state, find(state, "crate_tomato"))
        use(state, find(state, "board", "human"))
        state.update(DT, (0, 0), False)
        before = state.robot.horizon.remaining
        position = state.player.rect.copy()
        state.robot.horizon.REFRESH_SECONDS = C.CHOP_TIME / 10
        state.robot.horizon._refresh_at = 0
        state.update(C.CHOP_TIME * .4, (0, 0), True)
        state.update(C.CHOP_TIME * .4, (0, 0), True)
        self.assertEqual(position, state.player.rect)
        self.assertAlmostEqual(state.robot.horizon.estimate.chopping, C.CHOP_TIME * .2)
        self.assertLess(state.robot.horizon.remaining, before)

    def test_blocked_handoffs_produce_unknown_not_a_straight_line_eta(self):
        state = make_state(AnticipatoryDynamicHRobot)
        state.player.carrying = "tomato"
        for s in state.stations:
            if s.owner == "shared":
                goal = state.robot.horizon.human_approach(s)
                state.walls.append(pygame.Rect(goal.x - 22, goal.y - 22, 44, 44))
        state.update(DT, (0, 0), False)
        self.assertIsNone(state.robot.horizon.remaining)
        self.assertIsNone(state.robot.task)

    def test_dynamic_route_accounts_for_a_detour(self):
        state = make_state(AnticipatoryDynamicHRobot)
        state.robot.enabled = False
        state.player.carrying = "tomato"
        state.update(0.3, (0, 0), False)
        direct = state.robot.horizon.remaining
        state.walls.append(pygame.Rect(380, 200, 20, 200))
        state.update(0.3, (0, 0), False)
        self.assertIsNotNone(state.robot.horizon.remaining)
        self.assertGreater(state.robot.horizon.remaining, direct)

    def test_learned_board_route_includes_chopping_and_interactions(self):
        state = make_state(AnticipatoryDynamicHRobot)
        model = state.robot.transition_model
        source = ActionSymbol("take", "tomato", "crate_tomato")
        target = ActionSymbol("put", "tomato", "board")
        for _ in range(2):
            order = object()
            model.observe(HumanActionEvent(source, "salad", order, 0, 0))
            model.observe(HumanActionEvent(target, "salad", order, 0, 0))
        use(state, find(state, "crate_tomato"))
        state.update(DT, (0, 0), False)
        estimate = state.robot.horizon.estimate
        self.assertEqual(estimate.source, "learned_board_route")
        self.assertEqual(estimate.chopping, C.CHOP_TIME)
        self.assertEqual(estimate.interactions, 3)
        self.assertGreater(state.robot.horizon.remaining, C.CHOP_TIME)

    def test_fixed_h_validation(self):
        horizon = make_state().robot.horizon
        for value in (0, -1, math.inf, math.nan):
            with self.assertRaises(ValueError):
                horizon.fixed_seconds = value

    def test_h_can_describe_a_human_pickup_from_the_shared_counter(self):
        state = make_state(AnticipatoryDynamicHRobot)
        counter = find(state, "counter", "shared")
        counter.held = "plate"
        model = state.robot.transition_model
        source = ActionSymbol("put", "chopped_tomato", "counter")
        target = ActionSymbol("take", "plate", "counter")
        for _ in range(2):
            order = object()
            model.observe(HumanActionEvent(source, "salad", order, 0, 0))
            model.observe(HumanActionEvent(target, "salad", order, 0, 0))
        model.observe(HumanActionEvent(source, "salad", state.priority_order, 0, 0))
        state.update(DT, (0, 0), False)
        self.assertEqual(state.robot.horizon.estimate.action, "take")
        self.assertIs(state.robot.horizon.estimate.target, counter)
        self.assertGreater(state.robot.horizon.remaining, 0)


class HorizonPolicyTests(unittest.TestCase):
    def test_fixed_and_dynamic_modes_can_choose_different_actions_for_the_same_world(self):
        actions = []
        for robot in (AnticipatoryFixedHRobot, AnticipatoryDynamicHRobot):
            state = make_state(robot)
            state.player.carrying = "tomato"
            state.update(DT, (0, 0), False)
            actions.append(state.robot.task.action)
        self.assertEqual(actions, ["fetch", "wait_for_handoff"])

    def test_h_changes_the_action_and_logged_costs_explain_the_choice(self):
        for seconds, action in ((0.5, "wait_for_handoff"), (10, "fetch")):
            with self.subTest(h=seconds):
                state = make_state()
                state.robot.horizon.fixed_seconds = seconds
                state.player.carrying = "tomato"
                state.update(DT, (0, 0), False)
                self.assertEqual(state.robot.task.action, action)
                candidates = state.robot.scheduling["candidates"]
                selected = state.robot.scheduling["choice"]
                self.assertEqual(candidates[selected]["cost"], min(c["cost"] for c in candidates.values()))
                self.assertTrue(all(c["robot_idle"] >= 0 and c["handoff_lateness"] >= 0
                                    for c in candidates.values()))
                self.assertEqual(state.robot.contribution_source, "horizon")

    def test_plain_reactive_baseline_does_not_prepare_from_human_carried_items(self):
        state = make_state(ReactiveRobot)
        state.player.carrying = "tomato"
        tick(state, 1)
        self.assertIsNone(state.robot.task)
        self.assertFalse(hasattr(state.robot, "horizon"))

    def test_available_cooking_work_precedes_horizon_preparation(self):
        for robot in (AnticipatoryFixedHRobot, AnticipatoryDynamicHRobot):
            state = make_state(robot)
            handoffs = [s for s in state.stations if s.owner == "shared"]
            handoffs[0].held, handoffs[1].held = "chopped_tomato", "chopped_lettuce"
            state.player.carrying = "tomato"
            state.update(DT, (0, 0), False)
            self.assertEqual(state.robot.task.action, "take")
            self.assertEqual(state.robot.scheduling["choice"], "available_work")

    def test_prefetch_stages_one_plate_without_committing_a_lone_ingredient(self):
        state = make_state()
        state.robot.horizon.fixed_seconds = 10
        find(state, "counter", "robot").held = "chopped_tomato"
        state.player.carrying = "lettuce"
        tick(state, 5)
        items = [s.held for s in state.stations] + [state.robot.carrying]
        self.assertEqual(items.count("plate"), 1)
        self.assertIn("chopped_tomato", items)
        self.assertNotIn("plated_tomato", items)
        self.assertEqual(state.robot.completed_salads, 0)

    def test_arrived_rendezvous_waits_without_interacting_or_reporting_soup(self):
        state = make_state()
        state.robot.horizon.fixed_seconds = 10
        find(state, "counter", "robot").held = "plate"
        state.player.carrying = "tomato"
        tick(state, 2)
        self.assertEqual(state.robot.task.action, "wait_for_handoff")
        self.assertIn("Waiting near predicted handoff", state.robot.status)
        self.assertIsNone(state.robot.carrying)
        self.assertFalse(any(s.held for s in state.stations if s.owner == "shared"))

    def test_ready_other_recipe_can_use_the_prefetched_plate(self):
        state = make_state()
        state.orders = [Order("salad", 30), Order("soup", 90)]
        find(state, "pot", "robot").contents = ["chopped_tomato", "chopped_onion"]
        state.robot.carrying = "plate"
        state.robot._prefetching = True
        state.player.carrying = "lettuce"
        state.update(DT, (0, 0), False)
        self.assertEqual(state.robot.task.action, "scoop")
        self.assertEqual(state.robot.task.recipe, "soup")

    def test_incoming_finished_dish_does_not_trigger_an_extra_plate(self):
        state = make_state()
        state.robot.horizon.fixed_seconds = 10
        state.player.carrying = "salad"
        state.update(DT, (0, 0), False)
        self.assertEqual(state.robot.task.action, "wait_for_handoff")
        self.assertNotIn("prepare_plate", state.robot.scheduling["candidates"])

    def test_both_variants_complete_raw_and_chopped_orders_after_waiting(self):
        for robot in (AnticipatoryFixedHRobot, AnticipatoryDynamicHRobot):
            for recipe in ("salad", "soup"):
                for chopped in (False, True):
                    with self.subTest(robot=robot.__name__, recipe=recipe, chopped=chopped):
                        state = make_state(robot, recipe)
                        state.player.carrying = "tomato"
                        tick(state, 6)
                        for name, counter in zip(C.ALL_RECIPE_INGREDIENTS[recipe],
                                                 [s for s in state.stations if s.owner == "shared"]):
                            state.player.carrying = ("chopped_" if chopped else "") + name
                            use(state, counter)
                        for _ in range(1200):
                            tick(state, DT)
                            if state.score:
                                break
                        self.assertGreater(state.score, 0, state.robot.status)
                        self.assertEqual(state.robot.completed_salads + state.robot.completed_soups, 1)

    def test_all_three_reactive_variants_share_layout_and_initial_order_schedule(self):
        states = [GameState(cls, seed=2, layout="divided") for cls in
                  (ReactiveRobot, AnticipatoryFixedHRobot, AnticipatoryDynamicHRobot)]
        schedules = [[(o.kind, o.time_left) for o in state.orders] for state in states]
        self.assertEqual(schedules[0], schedules[1])
        self.assertEqual(schedules[1], schedules[2])
        from menu import RECIPES
        self.assertTrue({o.kind for o in states[1].orders} <= set(RECIPES))

    def test_moving_human_collects_and_delivers_while_timing_policy_runs(self):
        for robot in (AnticipatoryFixedHRobot, AnticipatoryDynamicHRobot):
            with self.subTest(robot=robot.__name__):
                state = make_state(robot)
                navigator = Navigator()
                handoffs = [s for s in state.stations if s.owner == "shared"]
                for name, counter in zip(("tomato", "lettuce"), handoffs):
                    crate = find(state, "crate_" + name)
                    for target, goal in ((crate, approach_point(crate)),
                                         (counter, (counter.rect.left - 26, counter.rect.centery))):
                        for _ in range(600):
                            arrived = navigator.move_to(state.player, goal, state, DT)
                            tick(state, DT)
                            self.assertLessEqual(state.player.rect.right, 518)
                            if arrived:
                                break
                        else:
                            self.fail("Human could not reach " + target.label)
                        state.player_interact()
                for _ in range(900):
                    tick(state, DT)
                    if state.score:
                        break
                self.assertGreater(state.score, 0, state.robot.status)


class HorizonInterfaceTests(unittest.TestCase):
    def test_cli_mode_lookup(self):
        self.assertIs(get_robot_class("anticipatory_fixed_h"), AnticipatoryFixedHRobot)
        self.assertIs(get_robot_class("anticipatory_dynamic_h"), AnticipatoryDynamicHRobot)

    def test_cli_restart_preserves_the_requested_fixed_h(self):
        values = []
        events = [[pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r)],
                  [pygame.event.Event(pygame.QUIT)]]
        with patch.object(sys, "argv", ["main.py", "--robot", "anticipatory_fixed_h", "--fixed-h", "7.5"]):
            with patch("main.View"), patch("main.RunRecorder") as recorder:
                recorder.return_value.start.side_effect = lambda state: values.append(
                    state.robot.horizon.fixed_seconds)
                with patch("pygame.event.get", side_effect=events):
                    main()
        self.assertEqual(values, [7.5, 7.5])

    def test_cli_rejects_invalid_fixed_h_and_incompatible_modes_before_opening_window(self):
        cases = [("anticipatory_fixed_h", value) for value in ("0", "-2", "nan", "inf")]
        cases.append(("anticipatory_dynamic_h", "4"))
        for robot, value in cases:
            with self.subTest(robot=robot, value=value):
                with patch.object(sys, "argv", ["main.py", "--robot", robot, "--fixed-h", value]):
                    with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                        main()
                    self.assertEqual(error.exception.code, 2)

    def test_horizon_logging_records_real_parameter_and_costs_without_changing_schema(self):
        with tempfile.TemporaryDirectory() as folder:
            state = make_state()
            state.robot.horizon.fixed_seconds = 10
            recorder = RunRecorder(dict(participant="T", robot="anticipatory_fixed_h", recipe="salad",
                                        seed=0, condition="test"), folder)
            recorder.start(state)
            state.player.carrying = "tomato"
            for _ in range(30):
                recorder.before(state)
                state.update(DT, (0, 0), False)
                recorder.after(state, DT)
            recorder.finish(state, completed=False)
            with open(recorder.path, newline="", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))
            config = next(json.loads(r["info"]) for r in rows if r["action"] == "h_config")
            self.assertEqual(config["fixed_seconds"], 10)
            horizons = [json.loads(r["info"]) for r in rows if r["action"] == "horizon"]
            self.assertTrue(any("candidates" in row["scheduling"] for row in horizons))
            self.assertLess(len(horizons), 10)
            self.assertTrue(all(r["anticipating"] == "1" for r in rows if r["action"] == "horizon"))


if __name__ == "__main__":
    unittest.main()
