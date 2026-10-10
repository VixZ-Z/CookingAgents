"""Collision-aware A* navigation in continuous pixel coordinates.

Edges are checked against obstacles inflated by the agent's body size.
"""
from __future__ import annotations

import heapq
import math

import pygame

import config as C


def approach_point(station):
    """Stand on the kitchen-aisle side, within interaction range."""
    y = station.rect.bottom + 26 if station.rect.centery < 350 else station.rect.top - 26
    return pygame.Vector2(station.rect.centerx, y)


class Navigator:
    GRID = 24
    REPLAN_SECONDS = 0.35

    def __init__(self):
        self.path = []
        self.goal = None
        self.timer = 0.0

    @staticmethod
    def make_space(actor, state, dt):
        """Escape a close human contact without crossing either body.

        Keyboard motion can bring the human inside our navigation buffer.
        A short, checked retreat keeps this from trapping the robot there.
        """
        human = state.player
        if actor is human or not actor.rect.inflate(12, 12).colliderect(human.rect):
            return False
        center = pygame.Vector2(actor.rect.center)
        away = center - pygame.Vector2(human.rect.center)
        if away.length_squared() == 0:
            return False
        away = away.normalize()
        directions = [away, pygame.Vector2(1, 0), pygame.Vector2(-1, 0),
                      pygame.Vector2(0, 1), pygame.Vector2(0, -1)]
        for direction in directions:
            if direction.dot(away) <= 0:
                continue
            position = actor.pos + direction * getattr(actor, "speed", C.ROBOT_SPEED) * dt
            candidate = actor.rect.copy()
            candidate.topleft = (round(position.x), round(position.y))
            swept = actor.rect.union(candidate)
            if (pygame.Rect(*C.PLAY_AREA).contains(candidate)
                    and not swept.colliderect(human.rect)
                    and not any(swept.colliderect(s.rect) for s in state.stations)):
                actor.pos.update(position)
                actor.rect.update(candidate)
                return True
        return False

    @staticmethod
    def _geometry(actor, state):
        area = pygame.Rect(*C.PLAY_AREA)
        bounds = pygame.Rect(area.x + actor.rect.width // 2,
                             area.y + actor.rect.height // 2,
                             area.width - actor.rect.width + 1,
                             area.height - actor.rect.height + 1)
        other = state.player if actor is not state.player else state.robot
        bodies = [s.rect for s in state.stations]
        if other:
            bodies.append(other.rect.inflate(8, 8))
        obstacles = [r.inflate(actor.rect.width + 2, actor.rect.height + 2)
                     for r in bodies]
        return bounds, obstacles

    @staticmethod
    def _clear(a, b, bounds, obstacles):
        if not bounds.collidepoint(a) or not bounds.collidepoint(b):
            return False
        return not any(r.collidepoint(a) or r.collidepoint(b)
                       or r.clipline(a, b) for r in obstacles)

    def _route(self, actor, goal, state, prediction):
        start = pygame.Vector2(actor.rect.center)
        bounds, obstacles = self._geometry(actor, state)
        if not bounds.collidepoint(goal) or any(r.collidepoint(goal) for r in obstacles):
            return []

        def risk(point):
            if prediction is None:
                return 0.0
            delta = pygame.Vector2(point).distance_to(prediction)
            return max(0.0, 75.0 - delta) * 0.8

        if self._clear(start, goal, bounds, obstacles) and risk(goal) == 0:
            if prediction is None or not pygame.Rect(
                    prediction[0] - 35, prediction[1] - 35, 70, 70).clipline(start, goal):
                return [goal]
        step = self.GRID
        nodes = {}
        for col, x in enumerate(range(bounds.left + 1, bounds.right - 1, step)):
            for row, y in enumerate(range(bounds.top + 1, bounds.bottom - 1, step)):
                point = (x, y)
                if not any(r.collidepoint(point) for r in obstacles):
                    nodes[col, row] = point
        sources = sorted(nodes, key=lambda n: start.distance_squared_to(nodes[n]))[:16]
        queue, costs, parents = [], {}, {}
        for node in sources:
            point = nodes[node]
            if self._clear(start, point, bounds, obstacles):
                costs[node] = start.distance_to(point)
                parents[node] = None
                heapq.heappush(queue, (costs[node] + goal.distance_to(point), node))
        while queue:
            _, node = heapq.heappop(queue)
            point = nodes[node]
            if goal.distance_to(point) <= step * 2 and self._clear(point, goal, bounds, obstacles):
                path = [goal]
                while node is not None:
                    path.append(pygame.Vector2(nodes[node]))
                    node = parents[node]
                return list(reversed(path))
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                           (1, 1), (1, -1), (-1, 1), (-1, -1)):
                nxt = (node[0] + dx, node[1] + dy)
                if nxt not in nodes or not self._clear(point, nodes[nxt], bounds, obstacles):
                    continue
                cost = costs[node] + step * math.hypot(dx, dy) + risk(nodes[nxt])
                if cost >= costs.get(nxt, float("inf")):
                    continue
                costs[nxt], parents[nxt] = cost, node
                heapq.heappush(queue, (cost + goal.distance_to(nodes[nxt]), nxt))
        return []

    def move_to(self, actor, goal, state, dt, prediction=None):
        """Move safely; return True only after reaching the requested point."""
        goal = pygame.Vector2(goal)
        center = actor.pos + pygame.Vector2(actor.rect.size) / 2
        if center.distance_to(goal) < 2:
            return True
        self.timer -= dt
        bounds, obstacles = self._geometry(actor, state)
        if (self.goal != goal or self.timer <= 0 or not self.path
                or not self._clear(center, self.path[0], bounds, obstacles)):
            self.path = self._route(actor, goal, state, prediction)
            self.goal = goal
            self.timer = self.REPLAN_SECONDS
        if not self.path:
            return False
        delta = self.path[0] - center
        distance = delta.length()
        speed = getattr(actor, "speed", C.ROBOT_SPEED)
        new_center = self.path[0] if distance <= speed * dt else center + delta * speed * dt / distance
        if not self._clear(center, new_center, bounds, obstacles):
            self.path = []
            return False
        actor.pos.update(new_center - pygame.Vector2(actor.rect.size) / 2)
        actor.rect.topleft = (round(actor.pos.x), round(actor.pos.y))
        if distance <= speed * dt:
            self.path.pop(0)
        return new_center.distance_to(goal) < 2
