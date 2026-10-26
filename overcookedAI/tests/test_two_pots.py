"""Alternate cooking stations preserve unrelated batches and finish meals."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game import GameState, Order, interact
from reactive_robot import ReactiveRobot
from anticipatory_robot import AnticipatoryRobot
from anticipatory_robot.adaptive import AdaptiveAnticipatoryRobot
from menu_planner import plan


ROBOTS = (ReactiveRobot, AnticipatoryRobot, AdaptiveAnticipatoryRobot)


class TwoPotTests(unittest.TestCase):
    def test_wrong_first_pot_is_preserved_while_second_completes_the_order(self):
        for robot in ROBOTS:
            for layout in ("divided", "shared"):
                for old_order in (False, True):
                    with self.subTest(robot=robot.__name__, layout=layout, old_order=old_order):
                        state = GameState(robot, seed=42, layout=layout)
                        state._arrivals = ()
                        target = Order("pasta_tomatoes", 150)
                        state.orders = ([Order("chicken_soup", 140)] if old_order else []) + [target]
                        pots = [s for s in state.stations if s.kind == "pot"]
                        pots[0].contents = ["chicken"]
                        for counter, item in zip([s for s in state.stations if s.owner == "shared"],
                                                  ("pasta", "chopped_tomato")):
                            state.player.carrying = item
                            interact(state.player, counter, state)
                        state.player.carrying = "pasta"
                        for _ in range(1200):
                            state.update(1 / 30, (0, 0), False)
                            self.assertEqual(pots[0].contents, ["chicken"])
                            self.assertFalse(any(state.robot.rect.colliderect(s.rect) for s in state.stations))
                            if not any(o is target for o in state.orders):
                                break
                        self.assertGreater(state.score, 0, state.robot.status)
                        self.assertFalse(any(o is target for o in state.orders))

    def test_matching_started_batch_is_preferred_to_an_empty_pot(self):
        for robot in ROBOTS:
            with self.subTest(robot=robot.__name__):
                state = GameState(robot, seed=42, layout="divided")
                state.orders = [Order("pasta_tomatoes", 150)]
                pots = [s for s in state.stations if s.kind == "pot"]
                pots[1].contents = ["chopped_tomato"]
                state.robot.carrying = "pasta"
                task = plan(state.robot, state, anticipatory=robot is not ReactiveRobot)
                self.assertEqual(task.action, "put_pot")
                self.assertIs(task.station, pots[1])

    def test_ingredients_split_between_pots_are_consolidated_and_served(self):
        for robot in ROBOTS:
            with self.subTest(robot=robot.__name__):
                state = GameState(robot, seed=42, layout="divided")
                state._arrivals = ()
                state.orders = [Order("pasta_tomatoes", 150)]
                pots = [s for s in state.stations if s.kind == "pot"]
                pots[0].contents, pots[1].contents = ["pasta"], ["chopped_tomato"]
                for _ in range(1200):
                    state.update(1 / 30, (0, 0), False)
                    if state.score:
                        break
                self.assertGreater(state.score, 0, state.robot.status)


if __name__ == "__main__":
    unittest.main()
