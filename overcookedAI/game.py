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


@dataclass
class Order:
    kind: str
    time_left: float

    @property
    def name(self) -> str:
        return self.kind.capitalize()


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
    result = COMBOS.get(frozenset((a, b)))
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
                   or actor.carrying.startswith("chopped_"))):
            station.held, actor.carrying = actor.carrying, None
            station.progress = 0
    elif station.kind == "pot":
        if (actor.carrying and can_go_in_pot(actor.carrying)
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
        if actor.carrying in ("salad", "soup"):
            order = next((o for o in state.orders
                          if o.kind == actor.carrying), None)
            if order is None:
                return              # keep the dish until a matching order
            state.orders.remove(order)
            state.score += C.SCORE_DELIVERY + max(0, int(order.time_left))
            actor.carrying = None


# ----------------------------------------------------------------------
# Game state
# ----------------------------------------------------------------------
class GameState:
    def __init__(self, robot_cls=None, seed: int | None = None,
                 layout: str = "scripted"):
        self.rng = random.Random(seed)
        self.layout = get_layout(layout)
        self.swapped = False
        self.stations = [
            Station(pygame.Rect(x, y, C.TILE, C.TILE), kind, label,
                    owner=(rest[0] if rest else None))
            for x, y, kind, label, *rest in self.layout.stations]
        self.player = Player(*self.layout.player_start)
        self.orders: list[Order] = []
        self.score = 0
        self.game_time = float(C.GAME_TIME)
        self.order_timer = 0.0
        self.game_over = False
        for _ in range(C.INITIAL_ORDERS):
            self.add_order()
        self.robot = robot_cls(self) if robot_cls else None

    def add_order(self):
        if len(self.orders) < C.MAX_ORDERS:
            self.orders.append(Order(self.rng.choice(C.ORDER_KINDS),
                                     self.rng.uniform(*C.ORDER_TTL)))

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
        target = interaction_target(self.player, self.stations)
        if not (target and handle_counter_combinations(self.player, target)):
            interact(self.player, target, self)

    def update(self, dt, move, chopping):
        """Advance the game by dt seconds. `move` = (dx, dy) input."""
        if self.game_over:
            return
        self.player.update(dt, move, [s.rect for s in self.stations])
        target = interaction_target(self.player, self.stations)
        if (chopping and target and target.kind == "board"
                and chop_name(target.held)):
            target.progress += dt
            if target.progress >= C.CHOP_TIME:
                target.held = chop_name(target.held)
                target.progress = 0
        for st in self.stations:
            if st.kind == "pot" and len(st.contents) == 2 and not st.ready:
                st.progress += dt
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
        if self.order_timer >= C.ORDER_INTERVAL:
            self.order_timer = 0
            self.add_order()
