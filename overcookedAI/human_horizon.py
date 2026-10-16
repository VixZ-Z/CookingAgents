"""Estimate seconds until the next human change to a shared counter.

Fixed h counts down from observed action boundaries, never from each frame.
Dynamic h uses collision-aware travel, observed walking speed and chopping.
These are conditional estimates, not a guarantee that a stationary human resumes.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass

import pygame

import config as C
from game import Player, chop_name
from navigation import Navigator, approach_point


def path_distance(actor, goal, state, start=None):
    """Read-only route length, optionally from a hypothetical future position."""
    if start is not None:
        proxy = Player(start[0] - actor.rect.width / 2, start[1] - actor.rect.height / 2)
        proxy.pos.update(start[0] - actor.rect.width / 2, start[1] - actor.rect.height / 2)
        world = copy.copy(state)
        if actor is state.player:
            world.player = proxy
        else:
            world.robot = proxy
        return path_distance(proxy, goal, world)
    navigator = Navigator()
    center = actor.pos + pygame.Vector2(actor.rect.size) / 2
    bounds, obstacles = navigator._geometry(actor, state)
    if navigator._clear(center, goal, bounds, obstacles):
        return center.distance_to(goal)
    route = navigator._route(actor, pygame.Vector2(goal), state, None)
    if not route:
        return math.inf
    distance = 0.0
    for point in route:
        distance += center.distance_to(point)
        center = pygame.Vector2(point)
    return distance


def situation(action, station_kind):
    """Coarse situation key for pace learning, e.g. ``take:crate`` or ``put:counter``."""
    kind = "crate" if station_kind.startswith("crate_") else station_kind
    return f"{action}:{kind}"


class PaceModel:
    """Per-situation estimate of how long this human takes at a station.

    The handling time of a step is the time between two completed human actions
    minus the walking time between their stations. Estimates are running means
    shrunk towards the default interaction time, so a step with no observations
    behaves exactly like the original constant. Chopping is learned as a factor
    on the game's chop time. Nothing persists beyond one game.
    """
    PRIOR_WEIGHT = 1.0
    MAX_INTERVAL = 15.0     # longer gaps are pauses, not pace
    MAX_HANDLING = 10.0

    def __init__(self):
        self.handling = {}          # situation -> [sum seconds, samples]
        self.chop = [0.0, 0]        # [sum of observed/nominal chop time, samples]
        self.revision = 0

    def handling_seconds(self, key):
        total, n = self.handling.get(key, (0.0, 0))
        return (self.PRIOR_WEIGHT * C.H_INTERACTION_SECONDS + total) / (self.PRIOR_WEIGHT + n)

    @property
    def chop_factor(self):
        total, n = self.chop
        return (self.PRIOR_WEIGHT + total) / (self.PRIOR_WEIGHT + n)

    def observe(self, key, interval, walking):
        if not 0 < interval <= self.MAX_INTERVAL:
            return
        if key == "chop:board":
            self.chop[0] += min(max(interval / C.CHOP_TIME, 0.5), 10.0)
            self.chop[1] += 1
        else:
            handling = max(0.0, interval - walking)
            if handling > self.MAX_HANDLING:
                return
            entry = self.handling.setdefault(key, [0.0, 0])
            entry[0] += handling
            entry[1] += 1
        self.revision += 1

    def snapshot(self):
        steps = {key: dict(seconds=round(self.handling_seconds(key), 3), samples=n)
                 for key, (_, n) in sorted(self.handling.items())}
        return dict(handling=steps, chop_factor=round(self.chop_factor, 3),
                    chop_samples=self.chop[1], default_handling=C.H_INTERACTION_SECONDS)


@dataclass
class HandoffEstimate:
    target: object | None = None
    action: str | None = None
    item: str | None = None
    distance: float = 0.0
    chopping: float = 0.0
    interactions: int = 1
    source: str = "unknown"
    steps: tuple = ()


class HumanHorizon:
    REFRESH_SECONDS = 0.25

    def __init__(self, state, mode, fixed_seconds=C.FIXED_H_SECONDS):
        if mode not in ("fixed", "dynamic"):
            raise ValueError("h mode must be fixed or dynamic")
        self.mode = mode
        self.fixed_seconds = fixed_seconds
        self.anchor_time = state.elapsed
        self.remaining = None
        self.estimate = HandoffEstimate()
        self.speed = float(C.PLAYER_SPEED)
        self.walking_distance = self.walking_time = 0.0
        self.previous_position = pygame.Vector2(state.player.rect.center)
        self.previous_time = state.elapsed
        self.previous_item = state.player.carrying
        self.cursor = 0
        self._refresh_at = -math.inf
        self._signature = None
        self._eta = 0.0
        self._estimate_time = state.elapsed
        self.pace = PaceModel()
        self._last_event = None

    @property
    def fixed_seconds(self):
        return self._fixed_seconds

    @fixed_seconds.setter
    def fixed_seconds(self, value):
        if not math.isfinite(value) or value <= 0:
            raise ValueError("fixed h must be a finite positive number of seconds")
        self._fixed_seconds = float(value)

    @staticmethod
    def human_approach(station):
        if station.owner == "shared" and station.kind == "counter":
            return pygame.Vector2(station.rect.left - 26, station.rect.centery)
        return approach_point(station)

    def _hint(self, state, transitions):
        human = state.player
        counters = [s for s in state.stations if s.kind == "counter" and s.owner == "shared"]
        prediction = transitions.prediction
        learned = (prediction is not None and prediction.samples >= C.TRANSITION_MIN_SAMPLES
                   and prediction.probability >= C.TRANSITION_MIN_PROBABILITY)
        target = prediction.target if learned else None
        waypoints = []
        item = human.carrying
        action, chopping, interactions, source = "put", 0.0, 1, "carried_item"
        steps = ("put:counter",)

        if item is None and target and target.action == "take" and target.station_kind == "counter":
            choices = [s for s in counters if s.held == target.item]
            return self._destination(state, choices, "take", target.item, [], 0.0, 1,
                                     "learned_counter_pickup", ("take:counter",))
        if item is None:
            boards = [s for s in state.stations if s.kind == "board" and s.owner == "human"
                      and s.held and (chop_name(s.held) or s.held.startswith("chopped_"))]
            last = state.human_actions[-1] if state.human_actions else None
            relevant = [s for s in boards if
                        pygame.Vector2(human.rect.center).distance_to(approach_point(s)) < 85
                        or (last and last.symbol.station_kind == "board"
                            and 0 <= last.station_index < len(state.stations)
                            and state.stations[last.station_index] is s)]
            if relevant:
                board = min(relevant, key=lambda s: pygame.Vector2(human.rect.center).distance_to(
                    approach_point(s)))
                item = chop_name(board.held) or board.held
                chopping = max(0.0, C.CHOP_TIME - board.progress) if chop_name(board.held) else 0.0
                interactions, source = 2, "observed_board"
                steps = ("take:board", "put:counter")
                waypoints = [approach_point(board)]
            elif target and target.action == "take" and target.station_kind.startswith("crate_"):
                crates = [s for s in state.stations if s.owner == "human"
                          and s.kind == target.station_kind]
                if not crates:
                    return HandoffEstimate()
                item, interactions, source = target.item, 2, "learned_crate_pickup"
                steps = ("take:crate", "put:counter")
                waypoints = [approach_point(crates[0])]
            else:
                return HandoffEstimate()
        elif chop_name(item) and target and target.action == "put" and target.station_kind == "board":
            boards = [s for s in state.stations if s.owner == "human"
                      and s.kind == "board" and s.held is None]
            if not boards:
                return HandoffEstimate()
            board = min(boards, key=lambda s: pygame.Vector2(human.rect.center).distance_to(
                approach_point(s)))
            waypoints = [approach_point(board)]
            item, chopping, interactions, source = chop_name(item), C.CHOP_TIME, 3, "learned_board_route"
            steps = ("put:board", "take:board", "put:counter")
        return self._destination(state, [s for s in counters if s.held is None], action,
                                 item, waypoints, chopping, interactions, source, steps)

    def _destination(self, state, counters, action, item, waypoints, chopping, interactions, source,
                     steps=()):
        start = pygame.Vector2(state.player.rect.center)
        prefix = 0.0
        for point in waypoints:
            prefix += path_distance(state.player, point, state, start=start)
            start = point
        choices = [(prefix + path_distance(state.player, self.human_approach(s), state, start=start), s)
                   for s in counters]
        choices = [choice for choice in choices if math.isfinite(choice[0])]
        if not choices:
            return HandoffEstimate()
        distance, station = min(choices, key=lambda pair: pair[0])
        return HandoffEstimate(station, action, item, distance, chopping, interactions, source, steps)

    def _learn_pace(self, state, events):
        """Update per-situation handling times from newly completed human actions."""
        for event in events:
            previous, self._last_event = self._last_event, event
            if previous is None:
                continue
            stations = state.stations
            if not (0 <= previous.station_index < len(stations)
                    and 0 <= event.station_index < len(stations)):
                continue
            walking = path_distance(state.player, self.human_approach(stations[event.station_index]),
                                    state, start=self.human_approach(stations[previous.station_index]))
            if not math.isfinite(walking):
                continue
            key = situation(event.symbol.action, event.symbol.station_kind)
            self.pace.observe(key, event.time - previous.time, walking / self.speed)

    def _eta_seconds(self, estimate):
        est = estimate
        if est.steps:
            handling = sum(self.pace.handling_seconds(key) for key in est.steps)
        else:
            handling = est.interactions * C.H_INTERACTION_SECONDS
        return est.distance / self.speed + est.chopping * self.pace.chop_factor + handling

    def update(self, state, dt, transitions):
        now = state.elapsed + dt
        position = pygame.Vector2(state.player.rect.center)
        elapsed = now - self.previous_time
        displacement = position.distance_to(self.previous_position)
        if elapsed > 0 and 20 < displacement / elapsed <= C.PLAYER_SPEED * 1.25:
            self.walking_distance += displacement
            self.walking_time += elapsed
            self.speed = self.walking_distance / self.walking_time
        fresh = state.human_actions[self.cursor:]
        self._learn_pace(state, fresh)
        if fresh:
            self.anchor_time = fresh[-1].time
        elif state.player.carrying != self.previous_item:
            self.anchor_time = now
        item_changed = state.player.carrying != self.previous_item
        self.cursor = len(state.human_actions)
        self.previous_item = state.player.carrying
        self.previous_position, self.previous_time = position, now
        prediction = transitions.prediction
        signature = (tuple((tuple(s.rect), s.held) for s in state.stations),
                     tuple(tuple(w) for w in state.walls),
                     prediction.target if prediction else None)
        if fresh or item_changed or now >= self._refresh_at or signature != self._signature:
            self.estimate = self._hint(state, transitions)
            self._estimate_time, self._signature = now, signature
            self._refresh_at = now + self.REFRESH_SECONDS
            self._eta = self._eta_seconds(self.estimate)
        if self.estimate.target is None:
            self.remaining = None
        elif self.mode == "fixed":
            self.remaining = max(0.0, self.fixed_seconds - (now - self.anchor_time))
        else:
            self.remaining = max(0.0, self._eta - (now - self._estimate_time))

    def snapshot(self, state):
        target = self.estimate.target
        return dict(mode=self.mode, remaining=self.remaining,
                    fixed_seconds=self.fixed_seconds if self.mode == "fixed" else None,
                    anchor_time=self.anchor_time, estimated_at=self._estimate_time,
                    target=next((i for i, s in enumerate(state.stations) if s is target), None),
                    action=self.estimate.action, item=self.estimate.item, source=self.estimate.source,
                    route_pixels=self.estimate.distance, walking_speed=self.speed,
                    remaining_chopping=self.estimate.chopping,
                    interaction_seconds=C.H_INTERACTION_SECONDS,
                    lateness_weight=C.H_HANDOFF_LATENESS_WEIGHT)
