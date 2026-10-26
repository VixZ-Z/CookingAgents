"""Planning deadlocks, moving-human replans, and transition diagnostics."""
import json
import unittest

import pygame

from anticipatory_robot import AnticipatoryRobot
from anticipatory_robot.robot import Task
from game import GameState, Order
from navigation import approach_point

DT = 1 / 60


def place(actor, position):
    actor.rect.topleft = position
    actor.pos.update(position)


class UnexpectedStoppingTests(unittest.TestCase):
    def setUp(self):
        self.state = GameState(AnticipatoryRobot, seed=0, layout="shared", recipe="salad", legacy_menu=True)
        self.state.game_time -= 1
        self.state.orders = [Order("salad", 90)]
        self.robot = self.state.robot
        self.robot.priority_order = self.state.priority_order
        place(self.state.player, (50, 350))

    def tick(self, frames):
        for _ in range(frames):
            self.state.human_activity_revision += 1
            self.state.update(DT, (0, 0), False)
            self.assertFalse(self.robot.rect.colliderect(self.state.player.rect))
            self.assertFalse(any(self.robot.rect.colliderect(s.rect) for s in self.state.stations))
            self.assertFalse(any(self.robot.rect.colliderect(w) for w in self.state.walls))

    def boards(self):
        return [s for s in self.state.stations if s.kind == "board"]

    def block_approach(self, station):
        goal = approach_point(station)
        self.state.walls.append(pygame.Rect(goal.x - 22, goal.y - 22, 44, 44))

    def test_moving_human_does_not_repeatedly_consume_start_waypoint(self):
        self.state.stations = []
        place(self.robot, (100, 300))
        place(self.state.player, (400, 300))
        goal = pygame.Vector2(650, 321)
        for frame in range(180):
            place(self.state.player, (400, 300 + frame % 15))
            self.robot.navigator.move_to(self.robot, goal, self.state, DT,
                                         self.state.player.rect.center)
            self.assertFalse(self.robot.rect.colliderect(self.state.player.rect))
        self.assertGreater(self.robot.rect.x, 400)

    def test_unreachable_board_uses_available_alternative(self):
        first, second = self.boards()
        self.block_approach(first)
        self.robot.carrying = "lettuce"
        self.tick(1)
        self.assertIs(self.robot.task.station, second)
        for _ in range(180):
            self.tick(1)
            if second.held:
                break
        self.assertIsNotNone(second.held)

    def test_retained_task_reconsiders_newly_unreachable_target(self):
        first, second = self.boards()
        self.robot.carrying = "lettuce"
        self.robot.task = Task(first, "put", "lettuce", "Preparing lettuce", "salad")
        self.block_approach(first)
        self.tick(60)
        self.assertIs(self.robot.task.station, second)

    def test_reserved_own_board_does_not_prevent_other_useful_work(self):
        board = self.boards()[0]
        board.held = "lettuce"
        self.robot.own_board = board
        counter = next(s for s in self.state.stations if s.kind == "counter")
        counter.held = "chopped_tomato"
        place(self.state.player, (board.rect.centerx - 21, board.rect.bottom + 5))
        self.tick(1)
        self.assertIsNotNone(self.robot.task)
        self.assertEqual(self.robot.task.item, "plate")

    def test_inaccessible_inventory_does_not_suppress_preparation(self):
        board = self.boards()[0]
        board.held = "chopped_lettuce"
        self.block_approach(board)
        self.robot.priority_order = self.state.priority_order
        self.robot.autonomous = True
        self.robot.human_ingredient = "tomato"
        task = self.robot._autonomous_task(self.state)
        self.assertIsNotNone(task)
        self.assertEqual(task.action, "fetch")

    def test_blocked_first_ingredient_does_not_prevent_preparing_second(self):
        self.robot.priority_order = self.state.priority_order
        self.robot.autonomous = True
        tomato = next(s for s in self.state.stations if s.kind == "crate_tomato")
        self.block_approach(tomato)
        task = self.robot._autonomous_task(self.state)
        self.assertIsNotNone(task)
        self.assertEqual(task.item, "lettuce")

    def test_empty_unreachable_soup_pot_is_reselected(self):
        self.state.orders = [Order("soup", 90)]
        self.robot.priority_order = self.state.priority_order
        self.robot.autonomous = True
        pots = [s for s in self.state.stations if s.kind == "pot"]
        self.robot.autonomous_pot = pots[0]
        self.block_approach(pots[0])
        self.assertIs(self.robot._autonomous_soup_pot(self.state), pots[1])

    def test_removed_station_invalidates_task(self):
        board = self.boards()[0]
        self.robot.carrying = "lettuce"
        task = Task(board, "put", "lettuce", "Preparing lettuce", "salad")
        self.robot.task = task
        self.state.stations.remove(board)
        self.tick(1)
        self.assertIsNot(self.robot.task, task)
        self.assertIn("task_invalidated", self.robot.diagnostic["events"])

    def test_fractional_position_at_counter_does_not_disable_all_tasks(self):
        counter = next(s for s in self.state.stations if s.kind == "counter")
        place(self.robot, (counter.rect.x - 42, counter.rect.y + 10))
        self.robot.pos.x += 0.4
        self.robot.carrying = "lettuce"
        before = self.robot.rect.copy()
        self.tick(60)
        self.assertNotEqual(self.robot.rect, before)
        self.assertTrue(self.robot.task or self.robot.carrying is None)

    def test_intentional_wait_logs_once_then_reports_resumption(self):
        self.state.orders = []
        self.state.order_timer = -1000
        self.tick(1)
        revision = self.robot.diagnostic_revision
        self.tick(120)
        self.assertEqual(self.robot.diagnostic_revision, revision)
        self.assertTrue(self.robot.diagnostic["intentional_wait"])
        self.assertIn("no_valid_action", self.robot.diagnostic["events"])
        json.dumps(self.robot.diagnostic)
        self.state.orders = [Order("salad", 90)]
        self.tick(1)
        self.assertGreater(self.robot.diagnostic_revision, revision)
        self.assertIsNotNone(self.robot.diagnostic["task"])

    def test_failed_route_diagnostic_distinguishes_unintended_inactivity(self):
        serve = next(s for s in self.state.stations if s.kind == "serve")
        self.robot.carrying = "salad"
        self.robot.task = Task(serve, "serve", "salad", "Serving our salad", "salad")
        self.block_approach(serve)
        self.tick(1)
        self.assertEqual(self.robot.diagnostic["navigation"], "no_route")
        self.assertFalse(self.robot.diagnostic["intentional_wait"])
        self.assertFalse(self.robot.diagnostic["route_exists"])
        self.assertIsNotNone(self.robot.diagnostic["task"])
        for _ in range(44):
            self.tick(1)
            if "unreachable_task_reconsidered" in self.robot.diagnostic["events"]:
                break
        self.assertIsNone(self.robot.task)
        self.assertIn("unreachable_task_reconsidered", self.robot.diagnostic["events"])
        self.state.walls = []
        self.tick(240)
        self.assertGreater(self.state.score, 0)


if __name__ == "__main__":
    unittest.main()
