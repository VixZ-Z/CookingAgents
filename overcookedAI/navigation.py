"""Collision-aware A* navigation in continuous pixel coordinates.

Edges are checked against obstacles inflated by the agent's body size.
"""
from __future__ import annotations

import heapq

import pygame

import config as C


def approach_point(station):
    """Stand on the kitchen-aisle side, within interaction range."""
    if station.rect.x == 0 and station.kind.startswith("crate_"):
        return pygame.Vector2(station.rect.right + 26, station.rect.centery)
    y = station.rect.bottom + 26 if station.rect.centery < 350 else station.rect.top - 26
    return pygame.Vector2(station.rect.centerx, y)


class Navigator:
    GRID = 24
    REPLAN_SECONDS = 0.35
    STUCK_SECONDS = 0.7

    def __init__(self):
        self.path = []
        self.goal = None
        self.timer = 0.0
        self.geometry_key = None
        self.stuck_seconds = 0.0
        self.reason = "not_requested"
        self.planned_path = []

    @property
    def stuck(self):
        """No navigation progress across multiple scheduled replans."""
        return self.stuck_seconds >= self.STUCK_SECONDS

    @staticmethod
    def make_space(actor, state, dt):
        """Escape a close human contact without crossing either body.

        Keyboard motion can bring the human inside our navigation buffer.
        A short, checked retreat or sideways slide keeps this from trapping
        the robot there. No legal step means wait for the human to move.
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
            if direction.dot(away) < -1e-9:
                continue
            position = actor.pos + direction * getattr(actor, "speed", C.ROBOT_SPEED) * dt
            candidate = actor.rect.copy()
            candidate.topleft = (round(position.x), round(position.y))
            swept = actor.rect.union(candidate)
            if (pygame.Rect(*C.PLAY_AREA).contains(candidate)
                    and not swept.colliderect(human.rect)
                    and not any(swept.colliderect(rect)
                                for rect in [s.rect for s in state.stations] + state.walls)):
                actor.pos.update(position)
                actor.rect.update(candidate)
                return True
        return False

    @staticmethod
    def _geometry(actor, state, clearance=True):
        area = pygame.Rect(*C.PLAY_AREA)
        bounds = pygame.Rect(area.x + actor.rect.width // 2,
                             area.y + actor.rect.height // 2,
                             area.width - actor.rect.width + 1,
                             area.height - actor.rect.height + 1)
        other = state.player if actor is not state.player else state.robot
        bodies = [s.rect for s in state.stations] + state.walls
        if other:
            bodies.append(other.rect.inflate(8, 8) if clearance else other.rect)
        margin = 2 if clearance else 0
        obstacles = [r.inflate(actor.rect.width + margin, actor.rect.height + margin)
                     for r in bodies]
        # A collision-free body may touch furniture or lie inside the human's
        # comfort buffer. It must still be able to leave that position.
        center = actor.pos + pygame.Vector2(actor.rect.size) / 2
        if clearance and not Navigator._clear(center, center, bounds, obstacles):
            return Navigator._geometry(actor, state, clearance=False)
        return bounds, obstacles

    @staticmethod
    def _clear(a, b, bounds, obstacles):
        if not bounds.collidepoint(a) or not bounds.collidepoint(b):
            return False
        # Floating-point segment clipping against open rectangle interiors.
        # Touching an edge is legal; entering it is a physical collision.
        for rect in obstacles:
            low, high = 0.0, 1.0
            for index, left, right in ((0, rect.left, rect.right),
                                       (1, rect.top, rect.bottom)):
                delta = b[index] - a[index]
                if abs(delta) < 1e-12:
                    if not left < a[index] < right:
                        break
                else:
                    enter, leave = sorted(((left - a[index]) / delta,
                                           (right - a[index]) / delta))
                    low, high = max(low, enter), min(high, leave)
                    if low >= high:
                        break
            else:
                if low < high:
                    return False
        return True

    def _route(self, actor, goal, state, prediction):
        start = actor.pos + pygame.Vector2(actor.rect.size) / 2
        bounds, obstacles = self._geometry(actor, state)
        # Rounding can leave the continuous position fractionally inside an
        # obstacle while the actual body only touches it. Plan from that body.
        if (not self._clear(start, start, bounds, obstacles)
                and self._clear(actor.rect.center, actor.rect.center, bounds, obstacles)):
            start = pygame.Vector2(actor.rect.center)
        if not self._clear(goal, goal, bounds, obstacles):
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
        # Include the current axes: a body touching a wall/counter can slide
        # along its edge even when no regular grid column fits beside it.
        xs = sorted(set(range(bounds.left + 1, bounds.right - 1, step)) | {start.x})
        ys = sorted(set(range(bounds.top + 1, bounds.bottom - 1, step)) | {start.y})
        for col, x in enumerate(xs):
            for row, y in enumerate(ys):
                point = (x, y)
                if self._clear(point, point, bounds, obstacles):
                    nodes[col, row] = point
        sources = sorted(nodes, key=lambda n: start.distance_squared_to(nodes[n]))
        queue, costs, parents = [], {}, {}
        for node in sources:
            point = nodes[node]
            if self._clear(start, point, bounds, obstacles):
                costs[node] = start.distance_to(point)
                parents[node] = None
                heapq.heappush(queue, (costs[node] + goal.distance_to(point), node))
                # Keep several visible connections, even if the nearest grid
                # points are hidden by furniture at the start of a narrow aisle.
                if len(costs) >= 16:
                    break
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
                cost = costs[node] + pygame.Vector2(point).distance_to(nodes[nxt]) + risk(nodes[nxt])
                if cost >= costs.get(nxt, float("inf")):
                    continue
                costs[nxt], parents[nxt] = cost, node
                heapq.heappush(queue, (cost + goal.distance_to(nodes[nxt]), nxt))
        return []

    def move_to(self, actor, goal, state, dt, prediction=None):
        """Move safely; return True only after reaching the requested point."""
        goal = pygame.Vector2(goal)
        center = actor.pos + pygame.Vector2(actor.rect.size) / 2
        physical_bounds, physical_obstacles = self._geometry(actor, state, clearance=False)
        if (not self._clear(center, center, physical_bounds, physical_obstacles)
                and self._clear(actor.rect.center, actor.rect.center, physical_bounds, physical_obstacles)):
            # Align only the subpixel bookkeeping; the rendered body stays put.
            actor.pos.update(actor.rect.topleft)
            center = pygame.Vector2(actor.rect.center)
        if center.distance_to(goal) < 2:
            self.stuck_seconds = 0.0
            self.reason = "arrived"
            self.path = []
            return True
        self.timer -= dt
        bounds, obstacles = self._geometry(actor, state)
        geometry_key = (tuple(bounds), tuple(tuple(r) for r in obstacles))
        if (self.goal != goal or self.timer <= 0
                or (not self.path and geometry_key != self.geometry_key)
                or (self.path and not self._clear(center, self.path[0], bounds, obstacles))):
            if self.goal != goal:
                self.stuck_seconds = 0.0
            self.path = self._route(actor, goal, state, prediction)
            self.planned_path = [tuple(p) for p in self.path]
            self.goal = goal
            self.timer = self.REPLAN_SECONDS
            self.geometry_key = geometry_key
        # A* can include the start as its first waypoint. Consume it in this
        # update: changing human geometry must not make every frame a zero step.
        while self.path and center.distance_to(self.path[0]) < 1e-6:
            self.path.pop(0)
        if not self.path:
            self.stuck_seconds += dt
            self.reason = "no_route"
            return False
        delta = self.path[0] - center
        distance = delta.length()
        speed = getattr(actor, "speed", C.ROBOT_SPEED)
        new_center = self.path[0] if distance <= speed * dt else center + delta * speed * dt / distance
        rounded_center = pygame.Vector2(round(new_center.x - actor.rect.width / 2),
                                        round(new_center.y - actor.rect.height / 2))
        rounded_center += pygame.Vector2(actor.rect.size) / 2
        physical_bounds, physical_obstacles = self._geometry(actor, state, clearance=False)
        if (not self._clear(center, new_center, bounds, obstacles)
                or not self._clear(actor.rect.center, rounded_center,
                                   physical_bounds, physical_obstacles)):
            self.path = []
            self.stuck_seconds += dt
            self.reason = "collision_rejected"
            return False
        actor.pos.update(new_center - pygame.Vector2(actor.rect.size) / 2)
        actor.rect.topleft = (round(actor.pos.x), round(actor.pos.y))
        self.stuck_seconds = 0.0
        self.reason = "moving"
        if distance <= speed * dt:
            self.path.pop(0)
        return new_center.distance_to(goal) < 2
