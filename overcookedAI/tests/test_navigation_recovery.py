"""Recovery from legal tight-contact positions without crossing any body."""
import unittest
from unittest.mock import patch

import pygame

import config as C
from anticipatory_robot import AnticipatoryRobot
from game import GameState, Player, Station
from navigation import Navigator

DT = 1 / 60


def place(actor, position):
    actor.rect.topleft = position
    actor.pos.update(position)


class NavigationRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.state = GameState(AnticipatoryRobot, seed=0, layout="shared", recipe="salad", legacy_menu=True)
        self.robot = self.state.robot
        self.nav = self.robot.navigator
        place(self.state.player, (800, 400))

    def assert_safe_step(self, before):
        self.assertLessEqual(pygame.Vector2(before.center).distance_to(self.robot.rect.center),
                             C.ROBOT_SPEED * DT + 1.5)
        self.assertTrue(pygame.Rect(*C.PLAY_AREA).contains(self.robot.rect))
        self.assertFalse(self.robot.rect.colliderect(self.state.player.rect))
        for obstacle in [s.rect for s in self.state.stations] + self.state.walls:
            self.assertFalse(self.robot.rect.colliderect(obstacle))

    def follow(self, goal, frames=600):
        positions = []
        for _ in range(frames):
            before = self.robot.rect.copy()
            arrived = self.nav.move_to(self.robot, goal, self.state, DT)
            self.assert_safe_step(before)
            positions.append(self.robot.rect.center)
            if arrived:
                return positions
        self.fail(f"Robot did not reach {goal}; ended at {self.robot.rect.center}")

    def test_all_play_area_corners_escape(self):
        self.state.stations = []
        for position in ((0, 90), (1058, 90), (0, 553), (1058, 553)):
            with self.subTest(position=position):
                place(self.robot, position)
                self.follow((550, 350))

    def test_touching_each_side_of_counter_can_escape(self):
        self.state.stations = [Station(pygame.Rect(400, 300, 64, 64), "counter", "Counter")]
        for position in ((358, 311), (464, 311), (411, 258), (411, 364)):
            with self.subTest(position=position):
                place(self.robot, position)
                self.follow((600, 450))

    def test_furniture_corner_contact_rejoins_route(self):
        self.state.stations = [Station(pygame.Rect(400, 300, 64, 64), "counter", "Counter")]
        place(self.robot, (358, 258))
        self.follow((550, 350))

    def test_human_pins_robot_to_wall_sideways_escape(self):
        self.state.stations = []
        place(self.robot, (0, 300))
        place(self.state.player, (42, 300))
        before = self.robot.rect.copy()
        self.assertTrue(self.nav.make_space(self.robot, self.state, DT))
        self.assert_safe_step(before)
        self.assertNotEqual(self.robot.rect.y, before.y)
        self.follow((250, 200))

    def test_human_pins_robot_to_counter_sideways_escape(self):
        self.state.stations = [Station(pygame.Rect(400, 300, 64, 64), "counter", "Counter")]
        place(self.robot, (358, 311))
        place(self.state.player, (316, 311))
        before = self.robot.rect.copy()
        self.assertTrue(self.nav.make_space(self.robot, self.state, DT))
        self.assert_safe_step(before)
        self.follow((550, 450))

    def test_human_comfort_buffer_does_not_disable_pathfinding(self):
        self.state.stations = []
        place(self.robot, (300, 300))
        place(self.state.player, (342, 300))
        self.follow((200, 200))

    def test_trapped_robot_waits_then_resumes_when_human_moves(self):
        self.state.stations = []
        self.state.walls = [pygame.Rect(0, 132, 100, 64)]
        place(self.robot, (0, 90))
        place(self.state.player, (42, 90))
        before = self.robot.rect.copy()
        with patch.object(self.nav, "_route", wraps=self.nav._route) as route:
            for _ in range(180):
                self.assertFalse(self.nav.make_space(self.robot, self.state, DT))
                self.assertFalse(self.nav.move_to(self.robot, (250, 250), self.state, DT))
                self.assertEqual(self.robot.rect, before)
            self.assertLessEqual(route.call_count, 10)
        self.assertGreater(self.nav.stuck_seconds, 2)
        self.assertTrue(self.nav.stuck)
        place(self.state.player, (800, 400))
        self.follow((250, 250))
        self.assertEqual(self.nav.stuck_seconds, 0)

    def test_temporarily_blocked_goal_is_retried_immediately_after_clearance(self):
        self.state.stations = []
        place(self.robot, (300, 300))
        place(self.state.player, (500, 300))
        goal = self.state.player.rect.center
        for _ in range(60):
            self.assertFalse(self.nav.move_to(self.robot, goal, self.state, DT))
        place(self.state.player, (800, 400))
        self.follow(goal)

    def test_corner_pressure_escapes_without_oscillation_then_finishes_task(self):
        # A counter above and the play-area edge to the right leave only a
        # downward exit, which the human temporarily blocks.
        self.state.stations.append(
            Station(pygame.Rect(1058, 200, 42, 64), "counter", "Corner"))
        place(self.robot, (1058, 264))
        place(self.state.player, (1058, 306))
        self.robot.carrying = "salad"
        self.state.game_time -= 1
        before = self.robot.rect.copy()
        # Left is an escape route: sideways movement must succeed under pressure.
        for _ in range(120):
            previous = self.robot.rect.copy()
            self.state.update(DT, (0, -1), False)
            self.assert_safe_step(previous)
        self.assertLess(self.robot.rect.x, before.x - 42)
        place(self.state.player, (80, 350))
        for _ in range(1200):
            previous = self.robot.rect.copy()
            self.state.human_activity_revision += 1
            self.state.update(DT, (0, 0), False)
            self.assert_safe_step(previous)
            if self.state.score:
                break
        self.assertGreater(self.state.score, 0)

    def test_anticipatory_robot_finishes_original_carried_dish_after_escape(self):
        place(self.robot, (1058, 300))
        place(self.state.player, (1016, 300))
        self.robot.carrying = "salad"
        self.state.game_time -= 1
        for frame in range(1800):
            before = self.robot.rect.copy()
            self.state.human_activity_revision += 1
            self.state.update(DT, (0, 0), False)
            self.assert_safe_step(before)
            if frame == 60:
                place(self.state.player, (80, 350))
            if self.state.score:
                break
        self.assertGreater(self.state.score, 0)
        self.assertEqual(self.robot.completed_salads, 1)


if __name__ == "__main__":
    unittest.main()
