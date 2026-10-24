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
from human_transitions import ActionSymbol, HumanActionEvent
from menu import RECIPES, prepared, cooked_recipe, order_schedule, period_at

CRATE_MAP = {"crate_tomato": "tomato", "crate_onion": "onion",
             "crate_lettuce": "lettuce"}
CHOP_MAP = {"tomato": "chopped_tomato", "onion": "chopped_onion",
            "lettuce": "chopped_lettuce"}
COMBOS = {
    frozenset(("plate", "chopped_tomato")): "plated_tomato",
    frozenset(("plate", "chopped_lettuce")): "plated_lettuce",
    frozenset(("plated_tomato", "chopped_lettuce")): "salad",
    frozenset(("plated_lettuce", "chopped_tomato")): "salad",
}
CRATE_MAP.update({"crate_" + name: name for r in RECIPES.values() for name in r.ingredients})
CHOP_MAP.update({name: prepared(name) for r in RECIPES.values() for name in r.ingredients
                 if prepared(name) != name})
COMBOS.update({frozenset(r.ingredients): key for key, r in RECIPES.items() if not r.cook_seconds})


@dataclass
class Order:
    kind: str
    time_left: float
    scheduled_at: float | None = None

    @property
    def name(self) -> str:
        return RECIPES[self.kind].name if self.kind in RECIPES else self.kind.capitalize()


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
    return item in ("chopped_tomato", "chopped_onion") or any(
        r.cook_seconds and item in map(prepared, r.ingredients) for r in RECIPES.values())


def compatible_pot(contents, item):
    batch = set(contents) | {item}
    return (batch <= {"chopped_tomato", "chopped_onion"} or any(
        r.cook_seconds and batch <= set(map(prepared, r.ingredients)) for r in RECIPES.values()))


def interaction_target(player, stations, who="human"):
    expanded = player.rect.inflate(50, 50)
    nearby = [s for s in stations
              if expanded.colliderect(s.rect)
              and s.owner in (None, "shared", who)]
    if not nearby:
        return None
    return min(nearby, key=lambda s: pygame.Vector2(player.rect.center)
               .distance_to(s.rect.center))


def handle_counter_combinations(actor, station, state=None):
    if station.kind not in ("counter", "board"):
        return False
    a, b = actor.carrying, station.held
    if a is None or b is None:
        return False
    result = COMBOS.get(frozenset((a, b)))
    if result:
        if state is not None and not state.legacy_menu and result not in RECIPES:
            return False
        actor.carrying = result
        station.held = None
        if state is not None and actor is state.player:
            state.record_human_action("combine", result, station)
        return True
    return False


def interact(actor, station, state):
    """E key / robot action. `state` provides orders and score."""
    if station is None:
        return

    before_item = actor.carrying
    context = state.priority_order

    if station.kind == "trash":
        actor.carrying = None
    elif station.kind in CRATE_MAP:
        if not state.legacy_menu and actor is not state.player:
            return  # All ingredient supplies belong to the human in current experiments.
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
                   or actor.carrying.startswith("chopped_"))):
            station.held, actor.carrying = actor.carrying, None
            station.progress = 0
    elif station.kind == "pot":
        if (actor.carrying and can_go_in_pot(actor.carrying)
                and not station.ready and len(station.contents) < 2
                and compatible_pot(station.contents, actor.carrying)
                and actor.carrying not in station.contents):
            station.contents.append(actor.carrying)
            actor.carrying = None
            if len(station.contents) == 2:
                station.progress = 0
        elif actor.carrying == "plate" and station.ready:
            actor.carrying = cooked_recipe(station.contents) or "soup"
            station.contents.clear()
            station.progress = 0
            station.ready = False
        elif actor.carrying is None and station.contents and not station.ready:
            actor.carrying = station.contents.pop()
            station.progress = 0
    elif station.kind == "serve":
        if actor.carrying in (C.ALL_RECIPE_INGREDIENTS if state.legacy_menu else C.ORDER_KINDS):
            order = min((o for o in state.orders
                         if o.kind == actor.carrying and o.time_left > 0),
                        key=lambda o: o.time_left, default=None)
            if order is None:
                return              # keep the dish until a matching order
            context = order
            state.orders.remove(order)
            state.score += C.SCORE_DELIVERY + max(0, int(order.time_left))
            actor.carrying = None

    if actor is state.player and before_item != actor.carrying:
        if station.kind == "serve":
            action, item = "serve", before_item
        elif station.kind == "trash":
            action, item = "trash", before_item
        elif station.kind == "pot":
            action = "take_from_pot" if before_item is None else ("scoop" if before_item == "plate" else "add_to_pot")
            item = actor.carrying if action in ("scoop", "take_from_pot") else before_item
        else:
            action = "take" if before_item is None else "put"
            item = actor.carrying if action == "take" else before_item
        state.record_human_action(action, item, station, order=context)


# ----------------------------------------------------------------------
# Game state
# ----------------------------------------------------------------------
class GameState:
    def __init__(self, robot_cls=None, seed: int | None = None,
                 layout: str = "scripted", recipe: str | None = None,
                 legacy_menu: bool = False):
        allowed = C.ALL_RECIPE_INGREDIENTS if legacy_menu else C.ORDER_KINDS
        if recipe is not None and recipe not in allowed:
            raise ValueError(f"Unknown recipe: {recipe}")
        self.rng = random.Random(seed)
        legacy = legacy_menu
        self.legacy_menu = legacy_menu
        self.order_kinds = [recipe] if recipe else (["salad", "soup"] if legacy else list(RECIPES))
        self.dynamic_menu = recipe in RECIPES or (recipe is None and not legacy)
        self.layout = get_layout(layout, legacy=legacy)
        self.swapped = False
        self.walls = [pygame.Rect(*wall) for wall in self.layout.walls]
        self.stations = [
            Station(pygame.Rect(x, y, C.TILE, C.TILE), kind, label,
                    owner=(rest[0] if rest else None))
            for x, y, kind, label, *rest in self.layout.stations]
        self.player = Player(*self.layout.player_start)
        self.human_activity_revision = 0
        self.human_actions = []
        self.orders: list[Order] = []
        self.score = 0
        self.game_time = float(C.GAME_TIME)
        self.order_timer = 0.0
        self.game_over = False
        # Mixed-mode teammate starts with both recipes visible, then random orders.
        initial_kinds = []
        if (not self.dynamic_menu and recipe is None and robot_cls
                and getattr(robot_cls, "ensure_mixed_orders", False)):
            initial_kinds = list(self.order_kinds)
            self.rng.shuffle(initial_kinds)
        self._arrivals = order_schedule(seed, C.GAME_TIME, C.INITIAL_ORDERS,
                                        C.ORDER_INTERVAL, C.ORDER_TTL, recipe) if self.dynamic_menu else ()
        self._arrival_cursor = 0
        if self.dynamic_menu:
            self._release_orders()
        else:
            for index in range(C.INITIAL_ORDERS):
                self.add_order(initial_kinds[index] if index < len(initial_kinds) else None)
        self.robot = robot_cls(self) if robot_cls else None

    def add_order(self, kind=None):
        if len(self.orders) < C.MAX_ORDERS:
            self.orders.append(Order(kind or self.rng.choice(self.order_kinds),
                                     self.rng.uniform(*C.ORDER_TTL)))

    def _release_orders(self):
        # Never gate scheduled arrivals on backlog: performance must not change exposure.
        while self._arrival_cursor < len(self._arrivals):
            when, kind, ttl = self._arrivals[self._arrival_cursor]
            if when > self.elapsed + 1e-9:
                break
            self.orders.append(Order(kind, ttl - (self.elapsed - when), when))
            self._arrival_cursor += 1

    @property
    def meal_period(self):
        return period_at(self.elapsed)

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
        self.human_activity_revision += 1
        target = interaction_target(self.player, self.stations)
        if not (target and handle_counter_combinations(self.player, target, self)):
            interact(self.player, target, self)

    def record_human_action(self, action, item, station, order=None, time=None):
        """Record successful human actions only, independently of CSV logging."""
        order = order if order is not None else self.priority_order
        index = next(i for i, candidate in enumerate(self.stations) if candidate is station)
        self.human_actions.append(HumanActionEvent(
            ActionSymbol(action, item, station.kind), order.kind if order else None,
            order, self.elapsed if time is None else time, index))

    def update(self, dt, move, chopping):
        """Advance the game by dt seconds. `move` = (dx, dy) input."""
        if self.game_over:
            return
        dt = min(max(0.0, dt), self.game_time)
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
                self.record_human_action("chop", target.held, target, time=self.elapsed + dt)
        for st in self.stations:
            if st.kind == "pot" and len(st.contents) == 2 and not st.ready:
                st.progress += dt
                recipe = cooked_recipe(st.contents)
                if recipe and st.progress >= RECIPES[recipe].cook_seconds:
                    st.ready = True
                if (set(st.contents) == {"chopped_tomato", "chopped_onion"}
                        and st.progress >= C.POT_TIME):
                    st.ready = True
        if self.robot:
            self.robot.update_ai(dt, self)
        self.game_time = max(0.0, self.game_time - dt)
        self.game_over = self.game_time <= 0
        self._maybe_swap_crates()
        for order in self.orders[:]:
            order.time_left -= dt
            if order.time_left <= 0:
                self.orders.remove(order)
                self.score = max(0, self.score - C.SCORE_EXPIRE_PENALTY)
        self.order_timer += dt
        if self.dynamic_menu:
            self._release_orders()
        elif self.order_timer >= C.ORDER_INTERVAL:
            self.order_timer = 0
            self.add_order()
