"""Returning raw ingredients to their matching supplies through real E actions."""
import csv
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from anticipatory_robot import AnticipatoryRobot
from game import GameState, Order, interact
from logger import RunRecorder
from navigation import approach_point
from reactive_robot import ReactiveRobot


def use(state, station):
    state.player.rect.center = approach_point(station)
    state.player.pos.update(state.player.rect.topleft)
    state.player_interact()


class IngredientReturnTests(unittest.TestCase):
    def test_all_raw_ingredients_can_be_taken_returned_and_taken_again(self):
        for layout in ("divided", "shared"):
            state = GameState(seed=42, layout=layout)
            score, orders = state.score, list(state.orders)
            for crate in [s for s in state.stations if s.kind.startswith("crate_")]:
                with self.subTest(layout=layout, crate=crate.kind):
                    ingredient = crate.kind.removeprefix("crate_")
                    use(state, crate)
                    self.assertEqual(state.player.carrying, ingredient)
                    use(state, crate)
                    self.assertIsNone(state.player.carrying)
                    self.assertEqual(state.human_actions[-1].symbol.action, "put")
                    self.assertEqual(state.human_actions[-1].symbol.station_kind, crate.kind)
                    use(state, crate)
                    self.assertEqual(state.player.carrying, ingredient)
                    use(state, crate)
            self.assertEqual(state.score, score)
            self.assertEqual(state.orders, orders)

    def test_wrong_or_prepared_items_are_not_lost_at_a_supply(self):
        state = GameState(seed=42, layout="divided")
        crate = next(s for s in state.stations if s.kind == "crate_tomato")
        for item in ("potato", "chopped_tomato", "plate", "tomato_soup", "cheese_sandwich"):
            with self.subTest(item=item):
                state.player.carrying = item
                before = len(state.human_actions)
                use(state, crate)
                self.assertEqual(state.player.carrying, item)
                self.assertEqual(len(state.human_actions), before)

    def test_robot_access_to_human_supplies_remains_blocked(self):
        state = GameState(ReactiveRobot, seed=42, layout="divided")
        crate = next(s for s in state.stations if s.kind == "crate_tomato")
        for carrying in (None, "tomato"):
            state.robot.carrying = carrying
            interact(state.robot, crate, state)
            self.assertEqual(state.robot.carrying, carrying)
        self.assertEqual(state.human_actions, [])

    def test_learned_return_to_supply_is_a_feasible_human_goal(self):
        state = GameState(AnticipatoryRobot, seed=42, layout="divided")
        state.orders = [Order("tomato_soup", 150)]
        crate = next(s for s in state.stations if s.kind == "crate_tomato")
        for _ in range(2):
            use(state, crate)
            state.robot.model.observe(state, .1)
            use(state, crate)
            state.robot.model.observe(state, .1)
        use(state, crate)
        intent = state.robot.model.observe(state, .1)
        self.assertEqual(intent.source, "transition")
        self.assertIs(intent.goal, crate)
        self.assertEqual(state.robot.transition_model.prediction.target.action, "put")

    def test_return_is_logged_as_put_and_does_not_count_as_a_handoff(self):
        state = GameState(seed=42, layout="divided")
        crate = next(s for s in state.stations if s.kind == "crate_tomato")
        with tempfile.TemporaryDirectory() as folder:
            recorder = RunRecorder(dict(participant="test", robot="none", condition="returns", seed=42), folder)
            recorder.start(state)
            for _ in range(2):
                recorder.before(state)
                use(state, crate)
                state.update(.01, (0, 0), False)
                recorder.after(state, .01)
            recorder.finish(state, completed=False)
            with open(recorder.path, newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            actions = [r for r in rows if r["actor"] == "human" and r["kind"] == "event"]
            self.assertEqual([r["action"] for r in actions], ["take", "put"])
            self.assertTrue(all(r["item"] == "tomato" and r["station"].startswith("Tomato#") for r in actions))
            self.assertFalse(any(r["action"] in ("trash", "handoff") for r in rows))


if __name__ == "__main__":
    unittest.main()
