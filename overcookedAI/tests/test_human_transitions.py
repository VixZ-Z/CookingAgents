"""Transition arithmetic, exact human events, policy use, and passive baseline learning."""
import csv
import json
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import config as C
from anticipatory_robot import AnticipatoryRobot
from game import GameState, Order, interact
from human_transitions import ActionSymbol, HumanActionEvent, HumanTransitionModel
from logger import RunRecorder
from navigation import approach_point
from reactive_robot import ReactiveRobot
from robot_tasks import Task, execute_task


DT = 1 / 30
TAKE_TOMATO = ActionSymbol("take", "tomato", "crate_tomato")
PUT_BOARD = ActionSymbol("put", "tomato", "board")
PUT_COUNTER = ActionSymbol("put", "tomato", "counter")
TAKE_LETTUCE = ActionSymbol("take", "lettuce", "crate_lettuce")
SERVE = ActionSymbol("serve", "salad", "serve")


def event(symbol, order, recipe="salad"):
    return HumanActionEvent(symbol, recipe, order, 0.0, 0)


def train_pair(model, source, target, recipe="salad", repeats=1):
    for _ in range(repeats):
        order = object()
        model.observe(event(source, order, recipe))
        model.observe(event(target, order, recipe))


def place(actor, center):
    actor.rect.center = center
    actor.pos.update(actor.rect.topleft)


def station(state, kind, owner=None):
    return next(s for s in state.stations if s.kind == kind
                and (owner is None or s.owner == owner))


def use(state, target):
    goal = approach_point(target)
    if state.layout.name == "divided" and target.owner == "shared":
        goal = (target.rect.left - 26, target.rect.centery)
    place(state.player, goal)
    state.player_interact()


class TransitionArithmeticTests(unittest.TestCase):
    def test_unknown_rows_have_no_fabricated_forecast(self):
        model = HumanTransitionModel()
        self.assertEqual(model.distribution("salad", TAKE_TOMATO), {})
        self.assertIsNone(model.predict("salad", TAKE_TOMATO))

    def test_conditional_probabilities_normalise_to_one(self):
        model = HumanTransitionModel()
        train_pair(model, TAKE_TOMATO, PUT_BOARD, repeats=3)
        train_pair(model, TAKE_TOMATO, PUT_COUNTER)
        row = model.distribution("salad", TAKE_TOMATO)
        self.assertEqual(row, {PUT_BOARD: 0.75, PUT_COUNTER: 0.25})
        self.assertEqual(sum(row.values()), 1)
        prediction = model.predict("salad", TAKE_TOMATO)
        self.assertEqual((prediction.target, prediction.probability, prediction.samples),
                         (PUT_BOARD, 0.75, 4))

    def test_recipes_are_learned_separately(self):
        model = HumanTransitionModel()
        train_pair(model, TAKE_TOMATO, PUT_BOARD, recipe="salad")
        train_pair(model, TAKE_TOMATO, PUT_COUNTER, recipe="soup")
        self.assertEqual(model.predict("salad", TAKE_TOMATO).target, PUT_BOARD)
        self.assertEqual(model.predict("soup", TAKE_TOMATO).target, PUT_COUNTER)

    def test_equal_orders_do_not_create_cross_order_transitions(self):
        model = HumanTransitionModel()
        first, second = Order("salad", 30), Order("salad", 30)
        self.assertEqual(first, second)
        model.observe(event(TAKE_TOMATO, first))
        model.observe(event(PUT_BOARD, second))
        self.assertEqual(model.transition_count, 0)

    def test_serve_is_a_terminal_action(self):
        model, order = HumanTransitionModel(), object()
        model.observe(event(PUT_COUNTER, order))
        model.observe(event(SERVE, order))
        self.assertIsNone(model.prediction)
        model.observe(event(TAKE_TOMATO, order))
        self.assertEqual(model.transition_count, 1)
        self.assertEqual(model.distribution("salad", SERVE), {})

    def test_ties_use_latest_observed_outcome_without_forgetting(self):
        model = HumanTransitionModel()
        train_pair(model, TAKE_TOMATO, PUT_BOARD, repeats=2)
        train_pair(model, TAKE_TOMATO, PUT_COUNTER, repeats=2)
        prediction = model.predict("salad", TAKE_TOMATO)
        self.assertEqual((prediction.target, prediction.samples), (PUT_COUNTER, 4))
        self.assertEqual(model.counts[("salad", TAKE_TOMATO)][PUT_BOARD], 2)

    def test_prediction_is_evaluated_before_learning_the_outcome(self):
        model = HumanTransitionModel()
        train_pair(model, TAKE_TOMATO, PUT_BOARD)
        self.assertEqual(model.evaluated_predictions, 0)
        train_pair(model, TAKE_TOMATO, PUT_COUNTER)
        self.assertEqual((model.evaluated_predictions, model.correct_predictions), (1, 0))
        train_pair(model, TAKE_TOMATO, PUT_COUNTER)
        self.assertEqual((model.evaluated_predictions, model.correct_predictions), (2, 1))
        self.assertAlmostEqual(model.predict("salad", TAKE_TOMATO).probability, 2 / 3)

    def test_real_repeated_actions_are_not_collapsed(self):
        model, order = HumanTransitionModel(), object()
        chop = ActionSymbol("chop", "chopped_tomato", "board")
        model.observe(event(chop, order))
        model.observe(event(chop, order))
        self.assertEqual(model.distribution("salad", chop), {chop: 1.0})

    def test_context_invalidation_preserves_history_and_breaks_the_chain(self):
        state = GameState(None, seed=0, layout="shared", recipe="salad", legacy_menu=True)
        order = state.priority_order
        model = HumanTransitionModel()
        train_pair(model, TAKE_TOMATO, PUT_BOARD)
        state.human_actions.append(event(TAKE_TOMATO, order))
        model.update(state)
        self.assertIsNotNone(model.prediction)
        state.orders = [Order("salad", 20)]
        model.update(state)
        self.assertIsNone(model.prediction)
        state.orders = [order]
        state.human_actions.append(event(PUT_COUNTER, order))
        model.update(state)
        self.assertEqual(model.transition_count, 1)


class HumanEventTests(unittest.TestCase):
    def setUp(self):
        self.state = GameState(None, seed=0, layout="shared", recipe="salad", legacy_menu=True)

    def workflow(self, state):
        use(state, station(state, "crate_tomato"))
        board = station(state, "board", "human" if state.layout.name == "divided" else None)
        use(state, board)
        for _ in range(round(C.CHOP_TIME / DT) + 2):
            state.update(DT, (0, 0), True)
        use(state, board)
        counter = station(state, "counter", "shared" if state.layout.name == "divided" else None)
        use(state, counter)
        return counter

    def test_full_workflow_records_each_completed_action_once(self):
        self.workflow(self.state)
        symbols = [e.symbol for e in self.state.human_actions]
        self.assertEqual(symbols, [TAKE_TOMATO, PUT_BOARD,
                                  ActionSymbol("chop", "chopped_tomato", "board"),
                                  ActionSymbol("take", "chopped_tomato", "board"),
                                  ActionSymbol("put", "chopped_tomato", "counter")])
        self.assertTrue(all(e.recipe == "salad" for e in self.state.human_actions))
        self.assertEqual(sorted(e.time for e in self.state.human_actions),
                         [e.time for e in self.state.human_actions])

    def test_failed_interactions_and_idle_frames_add_no_events(self):
        empty = station(self.state, "counter")
        use(self.state, empty)
        for _ in range(100):
            self.state.update(DT, (0, 0), False)
        self.assertEqual(self.state.human_actions, [])

    def test_soup_pot_and_serving_actions(self):
        self.state.orders = [Order("soup", 90)]
        pot = station(self.state, "pot")
        for item in ("chopped_tomato", "chopped_onion"):
            self.state.player.carrying = item
            use(self.state, pot)
        self.state.update(C.POT_TIME, (0, 0), False)
        use(self.state, station(self.state, "plates"))
        use(self.state, pot)
        use(self.state, station(self.state, "serve"))
        self.assertEqual([e.symbol.action for e in self.state.human_actions],
                         ["add_to_pot", "add_to_pot", "take", "scoop", "serve"])
        self.assertTrue(all(e.recipe == "soup" for e in self.state.human_actions))

    def test_combinations_and_trash_are_observed(self):
        counters = [s for s in self.state.stations if s.kind == "counter"]
        self.state.player.carrying = "plate"
        counters[0].held, counters[1].held = "chopped_tomato", "chopped_lettuce"
        use(self.state, counters[0])
        use(self.state, counters[1])
        use(self.state, station(self.state, "trash"))
        self.assertEqual([e.symbol for e in self.state.human_actions],
                         [ActionSymbol("combine", "plated_tomato", "counter"),
                          ActionSymbol("combine", "salad", "counter"),
                          ActionSymbol("trash", "salad", "trash")])

    def test_serving_uses_the_matched_order_context(self):
        urgent, served = Order("salad", 30), Order("soup", 90)
        self.state.orders = [urgent, served]
        self.state.player.carrying = "soup"
        use(self.state, station(self.state, "serve"))
        self.assertIs(self.state.human_actions[-1].order, served)
        self.assertEqual(self.state.human_actions[-1].recipe, "soup")

    def test_both_agents_learn_identical_real_human_workflows(self):
        counts = []
        for robot, layout in ((AnticipatoryRobot, "shared"), (ReactiveRobot, "divided")):
            state = GameState(robot, seed=0, layout=layout, recipe="salad", legacy_menu=True)
            state.robot.enabled = False
            self.workflow(state)
            state.update(DT, (0, 0), False)
            model = state.robot.transition_model
            self.assertEqual(model.transition_count, 4)
            self.assertEqual(model.cursor, 5)
            revision = model.revision
            for _ in range(50):
                state.update(DT, (0, 0), False)
            self.assertEqual(model.transition_count, 4)
            self.assertEqual(model.revision, revision)
            counts.append(model.counts)
        self.assertEqual(counts[0], counts[1])

    def test_robot_interactions_and_chopping_never_train_the_model(self):
        for robot, layout in ((AnticipatoryRobot, "shared"), (ReactiveRobot, "divided")):
            state = GameState(robot, seed=0, layout=layout, recipe="salad", legacy_menu=True)
            state.robot.enabled = False
            interact(state.robot, station(state, "crate_tomato"), state)
            board = station(state, "board", "robot" if layout == "divided" else None)
            interact(state.robot, board, state)
            task = Task(board, "chop", "tomato", "Chopping tomato", "salad")
            execute_task(state.robot, task, state, C.CHOP_TIME)
            state.update(DT, (0, 0), False)
            self.assertEqual(state.human_actions, [])
            self.assertEqual(state.robot.transition_model.transition_count, 0)

    def test_two_real_routines_create_a_live_forecast_in_both_agents(self):
        for robot, layout in ((AnticipatoryRobot, "shared"), (ReactiveRobot, "divided")):
            with self.subTest(robot=robot.__name__):
                state = GameState(robot, seed=0, layout=layout, recipe="salad", legacy_menu=True)
                state.robot.enabled = False
                crate = station(state, "crate_tomato")
                counter = station(state, "counter", "shared" if layout == "divided" else None)
                trash = station(state, "trash", "robot" if layout == "divided" else None)
                for _ in range(2):
                    use(state, crate)
                    state.update(DT, (0, 0), False)
                    use(state, counter)
                    state.update(DT, (0, 0), False)
                    # Clear the delivered ingredient without producing human actions.
                    interact(state.robot, counter, state)
                    interact(state.robot, trash, state)
                use(state, crate)
                state.update(DT, (0, 0), False)
                prediction = state.robot.transition_model.prediction
                self.assertEqual(prediction.target, PUT_COUNTER)
                self.assertEqual((prediction.samples, prediction.probability), (2, 1))
                if layout == "shared":
                    self.assertEqual(state.robot.intent.source, "transition")
                    self.assertEqual(state.robot.intent.goal.kind, "counter")


class TransitionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.state = GameState(AnticipatoryRobot, seed=0, layout="shared", recipe="salad", legacy_menu=True)
        self.state.game_time -= C.ROBOT_START_DELAY

    def test_learned_destination_overrides_rule_destination(self):
        model = self.state.robot.transition_model
        train_pair(model, TAKE_TOMATO, PUT_COUNTER, repeats=2)
        use(self.state, station(self.state, "crate_tomato"))
        self.state.update(DT, (0, 0), False)
        intent = self.state.robot.intent
        self.assertEqual((intent.source, intent.goal.kind), ("transition", "counter"))
        self.assertEqual((intent.confidence, intent.samples), (1, 2))

    def test_insufficient_or_ambiguous_history_uses_rules(self):
        for outcomes in ((PUT_COUNTER,), (PUT_COUNTER, PUT_BOARD)):
            with self.subTest(outcomes=outcomes):
                self.setUp()
                for target in outcomes:
                    train_pair(self.state.robot.transition_model, TAKE_TOMATO, target)
                use(self.state, station(self.state, "crate_tomato"))
                self.state.update(DT, (0, 0), False)
                self.assertEqual(self.state.robot.intent.source, "rules")
                self.assertEqual(self.state.robot.intent.goal.kind, "board")

    def test_infeasible_forecast_falls_back_to_current_state(self):
        train_pair(self.state.robot.transition_model, TAKE_TOMATO, PUT_COUNTER, repeats=2)
        for target in self.state.stations:
            if target.kind == "counter":
                target.held = "plate"
        use(self.state, station(self.state, "crate_tomato"))
        self.state.update(DT, (0, 0), False)
        self.assertEqual(self.state.robot.intent.source, "rules")
        self.assertEqual(self.state.robot.intent.goal.kind, "board")

    def test_predicted_next_ingredient_changes_the_division_of_work(self):
        train_pair(self.state.robot.transition_model, PUT_COUNTER, TAKE_LETTUCE, repeats=2)
        use(self.state, station(self.state, "crate_tomato"))
        self.state.update(DT, (0, 0), False)
        self.assertEqual(self.state.robot.human_ingredient, "tomato")
        use(self.state, station(self.state, "counter"))
        self.state.update(DT, (0, 0), False)
        self.assertEqual(self.state.robot.intent.source, "transition")
        self.assertEqual(self.state.robot.intent.goal.kind, "crate_lettuce")
        self.assertEqual(self.state.robot.human_ingredient, "lettuce")
        self.assertEqual(self.state.robot.contribution_source, "transition")

    def test_actual_choice_invalidates_the_old_forecast(self):
        train_pair(self.state.robot.transition_model, TAKE_TOMATO, PUT_COUNTER, repeats=2)
        use(self.state, station(self.state, "crate_tomato"))
        self.state.update(DT, (0, 0), False)
        use(self.state, station(self.state, "trash"))
        use(self.state, station(self.state, "crate_lettuce"))
        self.state.update(DT, (0, 0), False)
        self.assertEqual(self.state.robot.intent.source, "rules")
        self.assertEqual(self.state.robot.human_ingredient, "lettuce")
        self.assertEqual(self.state.robot.task.item, "tomato")

    def test_new_movement_away_from_the_forecast_uses_current_evidence(self):
        train_pair(self.state.robot.transition_model, PUT_COUNTER, TAKE_LETTUCE, repeats=2)
        use(self.state, station(self.state, "crate_tomato"))
        self.state.update(DT, (0, 0), False)
        use(self.state, station(self.state, "counter"))
        self.state.update(DT, (0, 0), False)
        self.assertEqual(self.state.robot.intent.source, "transition")
        self.state.update(DT, (1, 0), False)
        self.assertEqual(self.state.robot.intent.source, "rules")

    def test_reactive_planning_ignores_an_available_transition_forecast(self):
        state = GameState(ReactiveRobot, seed=0, layout="divided", recipe="salad", legacy_menu=True)
        handoffs = [s for s in state.stations if s.owner == "shared"]
        handoffs[0].held, handoffs[1].held = "chopped_tomato", "chopped_lettuce"
        before = state.robot._plan(state)
        model = state.robot.transition_model
        train_pair(model, TAKE_TOMATO, PUT_COUNTER, repeats=2)
        model.observe(event(TAKE_TOMATO, state.priority_order))
        state.update(DT, (0, 0), False)
        after = state.robot.task
        self.assertIsNotNone(model.prediction)
        self.assertEqual((after.action, after.item, after.station, after.recipe),
                         (before.action, before.item, before.station, before.recipe))
        self.assertFalse(hasattr(state.robot, "contribution_source"))

    def test_restart_clears_observations_and_transition_history(self):
        train_pair(self.state.robot.transition_model, TAKE_TOMATO, PUT_COUNTER)
        restarted = GameState(AnticipatoryRobot, seed=0, layout="shared")
        self.assertEqual(restarted.human_actions, [])
        self.assertEqual(restarted.robot.transition_model.transition_count, 0)


class TransitionLoggingTests(unittest.TestCase):
    def test_both_models_log_updates_once_without_counting_them_as_robot_actions(self):
        for robot, layout in ((AnticipatoryRobot, "shared"), (ReactiveRobot, "divided")):
            with self.subTest(robot=robot.__name__), tempfile.TemporaryDirectory() as folder:
                state = GameState(robot, seed=0, layout=layout, recipe="salad", legacy_menu=True)
                state.robot.enabled = False
                rec = RunRecorder(dict(participant="T", robot=layout, condition="test",
                                       recipe="salad", seed=0), folder)
                rec.start(state)
                use(state, station(state, "crate_tomato"))
                for _ in range(30):
                    rec.before(state)
                    state.update(DT, (0, 0), False)
                    rec.after(state, DT)
                use(state, station(state, "board", "human" if layout == "divided" else None))
                for _ in range(30):
                    rec.before(state)
                    state.update(DT, (0, 0), False)
                    rec.after(state, DT)
                rec.finish(state, completed=False)
                with open(rec.path, encoding="utf-8", newline="") as file:
                    rows = list(csv.DictReader(file))
                updates = [json.loads(row["info"]) for row in rows if row["action"] == "human_transition"]
                self.assertEqual(len(updates), 2)
                self.assertEqual([row["transitions"] for row in updates], [0, 1])
                with open(os.path.join(folder, "summary.csv"), encoding="utf-8", newline="") as file:
                    self.assertEqual(next(csv.DictReader(file))["robot_actions"], "0")
