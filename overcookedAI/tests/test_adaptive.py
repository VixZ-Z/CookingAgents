"""Adaptive handoff preferences and completed-dish prediction regressions."""
import csv
import tempfile
import unittest
import pygame
from game import GameState, Order, interact, handle_counter_combinations
from anticipatory_robot import AnticipatoryRobot
from anticipatory_robot.adaptive import AdaptiveAnticipatoryRobot
from reactive_robot import ReactiveRobot
from logger import RunRecorder
from menu_planner import plan
import launcher


class AdaptiveTests(unittest.TestCase):
    def state(self, cls=AdaptiveAnticipatoryRobot):
        state = GameState(cls, seed=42, layout='divided', recipe='cheese_sandwich')
        state.orders = [Order('cheese_sandwich', 150)]
        return state

    def handoff(self, state, item):
        counter = next(s for s in state.stations if s.owner == 'shared' and s.held is None)
        state.player.carrying = item
        interact(state.player, counter, state)
        return counter

    def completed_sandwich(self, state):
        tray = next(s for s in state.stations if s.kind == 'counter' and s.owner == 'human')
        for name in ('bread', 'cheese'):
            interact(state.player, next(s for s in state.stations if s.kind == 'crate_' + name), state)
            if not handle_counter_combinations(state.player, tray, state):
                interact(state.player, tray, state)
        self.assertEqual(state.player.carrying, 'cheese_sandwich')
        counter = next(s for s in state.stations if s.owner == 'shared' and s.held is None)
        interact(state.player, counter, state)

    def confirm_pickup(self, state, counter):
        """Confirm delivery through the game rules, independently of AI choices."""
        state.robot.preferences.update(state)
        self.assertIsNone(state.robot.carrying)
        expected = counter.held
        interact(state.robot, counter, state)
        self.assertEqual(state.robot.carrying, expected)
        state.robot.preferences.update(state)

    def test_repeated_complete_cheese_sandwich_and_behavior_reversal(self):
        state = self.state()
        for _ in range(6):
            state.orders = [Order('cheese_sandwich', 150)]
            self.completed_sandwich(state)
            before = state.score
            for _ in range(600):
                state.update(1/30, (0,0), False)
                if state.score > before:
                    break
            self.assertGreater(state.score, before, state.robot.status)
        state.orders = [Order('cheese_sandwich', 150)]
        state.player.carrying = 'bread'
        state.robot.intent = None
        forecast = plan(state.robot, state, True)
        self.assertEqual(forecast.item, 'cheese_sandwich')
        self.assertEqual(forecast.action, 'wait_for_handoff')
        for _ in range(8):
            counter = self.handoff(state, 'cheese')
            self.confirm_pickup(state, counter)
            # Clear the received test sample using the game rules.
            trash = next(s for s in state.stations if s.kind == 'trash' and s.owner == 'robot')
            interact(state.robot, trash, state)
        state.player.carrying = 'bread'
        self.assertEqual(state.robot.preferences.preferred('cheese_sandwich'), 'individual')
        self.assertEqual(plan(state.robot, state, True).item, 'bread')

    def test_completed_lower_priority_dish_overrides_obsolete_wait(self):
        for cls in (AnticipatoryRobot, AdaptiveAnticipatoryRobot):
            state = self.state(cls)
            state.orders = [Order('ham_sandwich', 100), Order('cheese_sandwich', 140)]
            state.player.carrying = 'bread'
            state.update(.6, (0,0), False)
            self.assertEqual(state.robot.task.action, 'wait_for_handoff')
            self.handoff(state, 'cheese_sandwich')
            for _ in range(600):
                state.update(1/30, (0,0), False)
                if state.score:
                    break
            self.assertGreater(state.score, 0, state.robot.status)
            self.assertTrue(any(o.kind == 'ham_sandwich' for o in state.orders))

    def test_visible_completed_human_task_cancels_ingredient_plan(self):
        for cls in (AnticipatoryRobot, AdaptiveAnticipatoryRobot):
            state = self.state(cls)
            state.player.carrying = 'bread'
            state.update(.6, (0, 0), False)
            tray = next(s for s in state.stations if s.kind == 'counter' and s.owner == 'human')
            state.player.carrying = None
            tray.held = 'cheese_sandwich'
            task = plan(state.robot, state, True)
            self.assertEqual(task.item, 'cheese_sandwich')
            self.assertEqual(task.action, 'wait_for_handoff')

    def test_partial_preferences_reset_and_schedule_fairness(self):
        state = GameState(AdaptiveAnticipatoryRobot, seed=42, layout='divided', recipe='tomato_soup')
        counter = self.handoff(state, 'chopped_tomato')
        state.robot.preferences.update(state)
        self.assertEqual(state.robot.preferences.counts, {})
        self.confirm_pickup(state, counter)
        self.assertEqual(state.robot.preferences.preferred('tomato_soup'), 'partial')
        fresh = self.state()
        self.assertEqual(fresh.robot.preferences.counts, {})
        self.assertFalse(hasattr(self.state(AnticipatoryRobot).robot, 'preferences'))
        schedules = [GameState(cls, seed=42, layout='divided')._arrivals
                     for cls in (ReactiveRobot, AnticipatoryRobot, AdaptiveAnticipatoryRobot)]
        self.assertTrue(all(schedule == schedules[0] for schedule in schedules))

    def test_withdrawn_or_unconfirmed_ingredients_do_not_train_preferences(self):
        for removal in ('human_pickup', 'unexplained_removal'):
            with self.subTest(removal=removal):
                state = self.state()
                counter = self.handoff(state, 'bread')
                state.robot.preferences.update(state)
                self.assertEqual(state.robot.preferences.counts, {})
                if removal == 'human_pickup':
                    interact(state.player, counter, state)
                else:
                    counter.held = None
                state.robot.preferences.update(state)
                self.assertEqual(state.robot.preferences.counts, {})
                self.assertEqual(state.robot.preferences.pending, {})

    def test_observable_only_and_separate_logging(self):
        state = self.state()
        class Observable:
            def __getattr__(self, name):
                if name.startswith('_') or name in ('rng', 'order_kinds'):
                    raise AssertionError(name)
                return getattr(state, name)
        self.handoff(state, 'cheese_sandwich')
        with tempfile.TemporaryDirectory() as folder:
            rec = RunRecorder(dict(participant='test',robot='adaptive_anticipatory',condition='test',recipe='cheese_sandwich',seed=42), folder)
            rec.start(state)
            rec.before(state)
            state.robot.update_ai(.6, Observable())
            rec.after(state, .6)
            rec.finish(state, False)
            with open(rec.path, encoding='utf-8') as stream:
                rows = list(csv.DictReader(stream))
            self.assertTrue(any(r['action'] == 'collaboration_pattern' for r in rows))

    def test_launcher_has_only_requested_choices(self):
        self.assertEqual([key for key, _ in launcher.ROBOTS],
                         ['reactive','anticipatory','adaptive_anticipatory'])
        self.assertEqual(launcher.LAYOUTS, (('divided','Divided Kitchen'),))


if __name__ == '__main__':
    unittest.main()
