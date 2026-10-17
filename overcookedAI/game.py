"""Game logic: stations, orders, player, interactions, scoring.

No window/drawing here. pygame is only used for Rect/Vector2 maths, so this
module imports fine without a display. Drawing is in render.py.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

import pygame

import config as C
from layouts import get_layout
from experiment import RobotObservation, Score, build_schedule
from recipes import (MEAL_RECIPES, MEAL_INGREDIENTS, can_add_to_cooker,
                     cooked_recipe, combination, meal_period)

CRATE_MAP = {"crate_tomato": "tomato", "crate_onion": "onion",
             "crate_lettuce": "lettuce"}
CRATE_MAP.update({"crate_" + name: name for name in MEAL_INGREDIENTS})
CHOP_MAP = {"tomato": "chopped_tomato", "onion": "chopped_onion",
            "lettuce": "chopped_lettuce"}
COMBOS = {
    frozenset(("plate", "chopped_tomato")): "plated_tomato",
    frozenset(("plate", "chopped_lettuce")): "plated_lettuce",
    frozenset(("plated_tomato", "chopped_lettuce")): "salad",
    frozenset(("plated_lettuce", "chopped_tomato")): "salad",
}


@dataclass
class Order:
    kind: str
    time_left: float
    order_id: int | None = None
    scheduled_at: float | None = None
    appeared_at: float | None = None
    completed_at: float | None = None
    outcome: str = "active"

    @property
    def name(self) -> str:
        return MEAL_RECIPES[self.kind].name if self.kind in MEAL_RECIPES else self.kind.capitalize()


@dataclass
class Station:
    rect: pygame.Rect
    kind: str
    label: str
    held: str | None = None
    contents: list[str] = field(default_factory=list)
    progress: float = 0.0
    ready: bool = False
    owner: str | None = None     # None = anyone, "human", "robot", "shared"


class Player:
    """Free-moving agent (the human, and the base of the robot)."""

    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 42, 42)
        self.pos = pygame.Vector2(x, y)
        self.carrying: str | None = None

    def update(self, dt, move, obstacles):
        move = pygame.Vector2(move)
        if move.length_squared() > 0:
            move = move.normalize() * C.PLAYER_SPEED * dt

        self.pos.x += move.x
        self.rect.x = round(self.pos.x)
        for ob in obstacles:
            if self.rect.colliderect(ob):
                if move.x > 0:
                    self.rect.right = ob.left
                elif move.x < 0:
                    self.rect.left = ob.right
                self.pos.x = self.rect.x

        self.pos.y += move.y
        self.rect.y = round(self.pos.y)
        for ob in obstacles:
            if self.rect.colliderect(ob):
                if move.y > 0:
                    self.rect.bottom = ob.top
                elif move.y < 0:
                    self.rect.top = ob.bottom
                self.pos.y = self.rect.y

        self.rect.clamp_ip(pygame.Rect(*C.PLAY_AREA))
        self.pos.update(self.rect.x, self.rect.y)


# ----------------------------------------------------------------------
# Rules
# ----------------------------------------------------------------------
def chop_name(item):
    return CHOP_MAP.get(item)


def can_go_in_pot(item):
    return item in ("chopped_tomato", "chopped_onion")


def interaction_target(player, stations, who="human"):
    expanded = player.rect.inflate(50, 50)
    nearby = [s for s in stations
              if expanded.colliderect(s.rect)
              and s.owner in (None, "shared", who)]
    if not nearby:
        return None
    return min(nearby, key=lambda s: pygame.Vector2(player.rect.center)
               .distance_to(s.rect.center))


def handle_counter_combinations(actor, station):
    if station.kind not in ("counter", "board"):
        return False
    a, b = actor.carrying, station.held
    if a is None or b is None:
        return False
    result = COMBOS.get(frozenset((a, b))) or combination(a, b)
    if result:
        actor.carrying = result
        station.held = None
        return True
    return False


def interact(actor, station, state):
    """E key / robot action. `state` provides orders and score."""
    if station is None:
        return

    if station.kind == "trash":
        actor.carrying = None
    elif station.kind in CRATE_MAP:
        if actor.carrying is None:
            actor.carrying = CRATE_MAP[station.kind]
    elif station.kind == "plates":
        if actor.carrying is None:
            actor.carrying = "plate"
    elif station.kind == "counter":
        if actor.carrying is None and station.held is not None:
            actor.carrying, station.held = station.held, None
        elif actor.carrying is not None and station.held is None:
            station.held, actor.carrying = actor.carrying, None
    elif station.kind == "board":
        if actor.carrying is None and station.held is not None:
            actor.carrying, station.held = station.held, None
            station.progress = 0
        elif (actor.carrying is not None and station.held is None
              and (chop_name(actor.carrying)
                   or actor.carrying.startswith("chopped_")
                   or getattr(state, "experiment", False))):
            station.held, actor.carrying = actor.carrying, None
            station.progress = 0
    elif station.kind == "pot":
        if getattr(state, "experiment", False):
            if actor.carrying is None and not station.ready and len(station.contents) == 1:
                actor.carrying = station.contents.pop()
                station.progress = 0
            elif (actor.carrying and not station.ready
                    and can_add_to_cooker(actor.carrying, station.contents)):
                station.contents.append(actor.carrying)
                actor.carrying = None
                if len(station.contents) == 2:
                    station.progress = 0
            elif actor.carrying == "plate" and station.ready:
                dish = cooked_recipe(station.contents)
                if dish:
                    actor.carrying = dish
                    station.contents.clear()
                    station.progress, station.ready = 0, False
        elif (actor.carrying and can_go_in_pot(actor.carrying)
                and not station.ready and len(station.contents) < 2
                and actor.carrying not in station.contents):
            station.contents.append(actor.carrying)
            actor.carrying = None
            if len(station.contents) == 2:
                station.progress = 0
        elif actor.carrying == "plate" and station.ready:
            actor.carrying = "soup"
            station.contents.clear()
            station.progress = 0
            station.ready = False
    elif station.kind == "serve":
        if actor.carrying in ("salad", "soup") or actor.carrying in MEAL_RECIPES:
            order = min((o for o in state.orders
                         if o.kind == actor.carrying and o.time_left > 0),
                        key=lambda o: o.time_left, default=None)
            if order is None:
                return              # keep the dish until a matching order
            state.orders.remove(order)
            order.outcome, order.completed_at = "completed", state.elapsed
            state.score += C.SCORE_DELIVERY + max(0, int(order.time_left))
            actor.carrying = None


# ----------------------------------------------------------------------
# Game state
# ----------------------------------------------------------------------
class GameState:
    def __init__(self, robot_cls=None, seed: int | None = None,
                 layout: str = "scripted", recipe: str | None = None, experiment=False):
        self.experiment = experiment
        kinds = tuple(MEAL_RECIPES) if experiment else C.ORDER_KINDS
        if recipe is not None and recipe not in kinds:
            raise ValueError(f"Unknown recipe: {recipe}")
        if not experiment:
            self.rng = random.Random(seed)
        self.order_kinds = [recipe] if recipe else kinds
        self.layout = get_layout(layout, experiment=experiment)
        self.swapped = False
        self.walls = [pygame.Rect(*wall) for wall in self.layout.walls]
        self.stations = [
            Station(pygame.Rect(x, y, C.TILE, C.TILE), kind, label,
                    owner=(rest[0] if rest else None))
            for x, y, kind, label, *rest in self.layout.stations]
        self.player = Player(*self.layout.player_start)
        self.human_activity_revision = 0
        self.orders: list[Order] = []
        self._score = Score()
        self.game_time = float(C.GAME_TIME)
        self.order_timer = 0.0
        self.game_over = False
        self.robot = None
        if experiment:
            self._order_schedule = build_schedule(seed, recipe)
            self._experiment_orders = tuple(Order(entry.kind, entry.ttl, entry.order_id,
                                                   entry.scheduled_at, outcome="scheduled")
                                             for entry in self._order_schedule)
            self._schedule_index = 0
            self._pending_orders = []
            self._dispatch_orders()
            self.robot = robot_cls(self.robot_observation()) if robot_cls else None
            return
        # Mixed-mode teammate starts with both recipes visible, then random orders.
        initial_kinds = []
        if (recipe is None and robot_cls
                and getattr(robot_cls, "ensure_mixed_orders", False)):
            initial_kinds = list(self.order_kinds)
            self.rng.shuffle(initial_kinds)
        for index in range(C.INITIAL_ORDERS):
            self.add_order(initial_kinds[index] if index < len(initial_kinds) else None)
        self.robot = robot_cls(self) if robot_cls else None

    def add_order(self, kind=None):
        if self.experiment:
            raise RuntimeError("Experiment arrivals are determined by the engine schedule")
        if len(self.orders) < C.MAX_ORDERS:
            self.orders.append(Order(kind or self.rng.choice(self.order_kinds),
                                     self.rng.uniform(*C.ORDER_TTL)))

    @property
    def score(self):
        return self._score.value

    @score.setter
    def score(self, value):
        self._score.value = value

    @property
    def meal_period(self):
        return meal_period(self.elapsed)

    def robot_observation(self):
        """Allowlisted visible state; never pass the scheduler's GameState to robots."""
        return RobotObservation(self.layout, self.stations, self.walls, self.player,
                                self.robot, self.orders, self._score, self.game_time,
                                self.human_activity_revision)

    def _dispatch_orders(self):
        while (self._schedule_index < len(self._experiment_orders)
               and self._experiment_orders[self._schedule_index].scheduled_at <= self.elapsed + 1e-9):
            order = self._experiment_orders[self._schedule_index]
            order.outcome = "queued"
            self._pending_orders.append(order)
            self._schedule_index += 1
        while self._pending_orders and len(self.orders) < C.MAX_ORDERS:
            order = self._pending_orders.pop(0)
            order.appeared_at, order.outcome = self.elapsed, "active"
            self.orders.append(order)

    @property
    def priority_order(self):
        """Earliest deadline; list order breaks equal-deadline ties."""
        return min((o for o in self.orders if o.time_left > 0),
                   key=lambda o: o.time_left, default=None)

    @property
    def elapsed(self) -> float:
        return C.GAME_TIME - self.game_time

    def _maybe_swap_crates(self):
        """'swap' layout: onion and lettuce crates trade places at swap_time."""
        t = self.layout.swap_time
        if t is None or self.swapped or self.elapsed < t:
            return
        onion = next(s for s in self.stations if s.kind == "crate_onion")
        lettuce = next(s for s in self.stations if s.kind == "crate_lettuce")
        onion.rect.topleft, lettuce.rect.topleft = (lettuce.rect.topleft,
                                                    onion.rect.topleft)
        self.swapped = True

    def player_interact(self):
        if self.game_over:
            return
        self.human_activity_revision += 1
        target = interaction_target(self.player, self.stations)
        if not (target and handle_counter_combinations(self.player, target)):
            interact(self.player, target, self)

    def update(self, dt, move, chopping):
        """Advance the game by dt seconds. `move` = (dx, dy) input."""
        if self.game_over:
            return
        if self.experiment:
            self._update_experiment(dt, move, chopping)
            return
        self._update_actors(dt, move, chopping)
        self.game_time = max(0.0, self.game_time - dt)
        self.game_over = self.game_time <= 0
        self._maybe_swap_crates()
        for order in self.orders[:]:
            order.time_left -= dt
            if order.time_left <= 0:
                self.orders.remove(order)
                self.score = max(0, self.score - C.SCORE_EXPIRE_PENALTY)
        self.order_timer += dt
        if self.order_timer >= C.ORDER_INTERVAL:
            self.order_timer = 0
            self.add_order()

    def _update_actors(self, dt, move, chopping):
        if any(move):
            # Attempts to move count too, including movement blocked by an obstacle.
            self.human_activity_revision += 1
        obstacles = [s.rect for s in self.stations] + self.walls
        if self.robot and getattr(self.robot, "avoids_human", False):
            obstacles.append(self.robot.rect)
        self.player.update(dt, move, obstacles)
        target = interaction_target(self.player, self.stations)
        if (chopping and target and target.kind == "board"
                and chop_name(target.held)):
            self.human_activity_revision += 1
            target.progress += dt
            if target.progress >= C.CHOP_TIME:
                target.held = chop_name(target.held)
                target.progress = 0
        for st in self.stations:
            if st.kind == "pot" and len(st.contents) == 2 and not st.ready:
                st.progress += dt
                if ((cooked_recipe(st.contents) if self.experiment else
                     set(st.contents) == {"chopped_tomato", "chopped_onion"})
                        and st.progress >= C.POT_TIME):
                    st.ready = True
        if self.robot:
            self.robot.update_ai(dt, self.robot_observation() if self.experiment else self)

    def _update_experiment(self, dt, move, chopping):
        remaining = min(max(0.0, dt), self.game_time)
        # Split on public arrival/expiry/period boundaries and normal simulation
        # steps, so long headless updates cannot skip a scheduled appearance.
        while remaining > 1e-9:
            self._dispatch_orders()
            step = min(remaining, 0.05)
            if self._schedule_index < len(self._experiment_orders):
                until = self._experiment_orders[self._schedule_index].scheduled_at - self.elapsed
                if until > 1e-9:
                    step = min(step, until)
            for boundary in (60.0, 120.0, 180.0):
                if boundary - self.elapsed > 1e-9:
                    step = min(step, boundary - self.elapsed)
            if self.orders:
                step = min(step, max(1e-9, min(o.time_left for o in self.orders)))
            self.game_time = max(0.0, self.game_time - step)
            for boundary in (0.0, 60.0, 120.0, 180.0):
                if abs(self.game_time - boundary) < 1e-8:
                    self.game_time = boundary
            for order in self.orders[:]:
                order.time_left -= step
                if order.time_left <= 1e-9:
                    order.time_left, order.outcome = 0.0, "expired"
                    self.orders.remove(order)
                    self.score = max(0, self.score - C.SCORE_EXPIRE_PENALTY)
            self._dispatch_orders()
            self._update_actors(step, move, chopping)
            remaining -= step
        self.game_over = self.game_time <= 0
