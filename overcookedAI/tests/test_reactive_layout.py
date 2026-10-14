"""Physical separation and usable two-sided deliveries in the reactive map."""
import unittest

import pygame

import config as C
from game import GameState, Player, interact, interaction_target
from navigation import Navigator


class ReactiveLayoutTests(unittest.TestCase):
    def setUp(self):
        self.state = GameState(seed=0, layout="reactive")

    def test_divider_blocks_crossing_at_every_height(self):
        obstacles = self.state.walls + [s.rect for s in self.state.stations]
        area = pygame.Rect(*C.PLAY_AREA)
        for y in range(area.top, area.bottom - 41):
            for x, direction in ((470, 1), (588, -1)):
                actor = Player(x, y)
                for _ in range(20):
                    actor.update(0.05, (direction, 0), obstacles)
                if direction == 1:
                    self.assertLessEqual(actor.rect.right, 518)
                else:
                    self.assertGreaterEqual(actor.rect.left, 582)

    def test_both_counters_allow_delivery_from_opposite_sides(self):
        for counter in (s for s in self.state.stations if s.owner == "shared"):
            human = Player(counter.rect.left - 42, counter.rect.y + 11)
            robot = Player(counter.rect.right, counter.rect.y + 11)
            self.assertIs(interaction_target(human, self.state.stations), counter)
            self.assertIs(interaction_target(robot, self.state.stations, "robot"), counter)
            human.carrying = "chopped_tomato"
            interact(human, counter, self.state)
            interact(robot, counter, self.state)
            self.assertEqual(robot.carrying, "chopped_tomato")
            self.assertIsNone(counter.held)

    def test_navigation_cannot_cross_but_reaches_robot_handoff(self):
        actor = Player(*self.state.layout.robot_start)
        nav = Navigator()
        self.assertEqual(nav._route(actor, self.state.player.rect.center, self.state, None), [])
        for counter in (s for s in self.state.stations if s.owner == "shared"):
            goal = (counter.rect.right + 26, counter.rect.centery)
            self.assertTrue(nav._route(actor, goal, self.state, None))

    def test_stations_have_correct_access_and_recipes_are_available(self):
        crates = [s for s in self.state.stations if s.kind.startswith("crate_")]
        self.assertEqual({s.kind for s in crates},
                         {"crate_tomato", "crate_onion", "crate_lettuce"})
        self.assertTrue(all(s.owner == "human" for s in crates))
        for kind in ("board", "pot", "plates", "counter", "serve", "trash"):
            self.assertTrue(any(s.kind == kind and s.owner == "robot"
                                for s in self.state.stations))


if __name__ == "__main__":
    unittest.main()
