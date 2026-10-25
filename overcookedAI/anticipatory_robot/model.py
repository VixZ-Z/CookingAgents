"""Observable goal inference for the shared-kitchen pilot.

Rules use carried items, station contents and movement. Starter frequencies and
first-order action transitions are learned per recipe. No forgetting or timing
horizon; rule confidence is heuristic, learned confidence is row frequency.
"""
from __future__ import annotations

from dataclasses import dataclass

import pygame

import config as C
from game import COMBOS, Station, chop_name
from navigation import approach_point
from human_transitions import HumanTransitionModel


def ingredient_name(item):
    return next((name for name in dict.fromkeys(n for pair in C.ALL_RECIPE_INGREDIENTS.values() for n in pair)
                 if item in (name, "chopped_" + name, "plated_" + name)), None)


@dataclass(frozen=True)
class StarterPrediction:
    ingredient: str
    matches: int
    observations: int
    recipe: str

    @property
    def description(self):
        return (f"Expected start: {self.ingredient} "
                f"({self.matches}/{self.observations} {self.recipe} starts)")


@dataclass
class HumanIntent:
    goal: Station | None
    action: str
    ingredient: str | None
    confidence: float
    velocity: pygame.Vector2
    projected_position: pygame.Vector2
    source: str = "rules"
    samples: int = 0

    @property
    def description(self):
        destination = self.goal.label if self.goal else "unknown"
        if self.source == "transition":
            return (f"Human next: {self.action} -> {destination} "
                    f"({self.confidence:.0%}, n={self.samples}, learned)")
        return f"Human: {self.action} -> {destination} ({self.confidence:.0%})"


class HumanIntentModel:
    def __init__(self):
        self.previous_position = None
        self.previous_item = None
        self.starter_counts = {recipe: dict.fromkeys(ingredients, 0)
                               for recipe, ingredients in C.ALL_RECIPE_INGREDIENTS.items()}
        self.last_starter = {}
        # Keep order references: equal recipes/deadlines are still distinct trials.
        self.observed_orders = []
        self.transitions = HumanTransitionModel()

    def _transition_goals(self, state, available):
        prediction = self.transitions.prediction
        if (prediction is None or prediction.samples < C.TRANSITION_MIN_SAMPLES
                or prediction.probability < C.TRANSITION_MIN_PROBABILITY):
            return []
        target, carried = prediction.target, state.player.carrying
        candidates = [s for s in available if s.kind == target.station_kind]

        def feasible(station):
            if target.action == "take" and carried is None:
                return (station.kind == "crate_" + target.item
                        or (station.kind == "plates" and target.item == "plate")
                        or (station.kind in ("board", "counter") and station.held == target.item))
            if target.action == "put" and carried == target.item:
                if station.kind == "crate_" + carried:
                    return True
                return station.held is None and (
                    station.kind == "counter" or (station.kind == "board"
                    and (chop_name(carried) or carried.startswith("chopped_"))))
            if target.action == "chop":
                return (carried is None and station.kind == "board"
                        and chop_name(station.held) == target.item)
            if target.action == "add_to_pot":
                return (carried == target.item and station.kind == "pot" and not station.ready
                        and len(station.contents) < 2 and carried not in station.contents)
            if target.action == "scoop":
                return (carried == "plate" and station.kind == "pot"
                        and set(station.contents) == {"chopped_tomato", "chopped_onion"})
            if target.action == "combine":
                return (station.kind in ("board", "counter") and carried and station.held
                        and COMBOS.get(frozenset((carried, station.held))) == target.item)
            if target.action == "serve":
                return (carried == target.item and station.kind == "serve"
                        and any(o.kind == carried and o.time_left > 0 for o in state.orders))
            if target.action == "trash":
                return carried == target.item and station.kind == "trash"
            return False

        return [s for s in candidates if feasible(s)]

    def _learn_start(self, state, ingredient):
        order = state.priority_order
        if (order is None or ingredient not in C.ALL_RECIPE_INGREDIENTS[order.kind]
                or ingredient == ingredient_name(self.previous_item)
                or any(seen is order for seen in self.observed_orders)):
            return
        self.starter_counts[order.kind][ingredient] += 1
        self.last_starter[order.kind] = ingredient
        self.observed_orders.append(order)

    def predict_start(self, recipe):
        counts = self.starter_counts.get(recipe, {})
        total = sum(counts.values())
        if not total:
            return None
        # Cumulative frequencies, with the most recent observed start breaking ties.
        ingredient = max(counts, key=lambda name: (
            counts[name], name == self.last_starter[recipe]))
        return StarterPrediction(ingredient, counts[ingredient], total, recipe)

    def observe(self, state, dt):
        previous_cursor = self.transitions.cursor
        self.transitions.update(state)
        fresh_action = self.transitions.cursor != previous_cursor
        human = state.player
        position = pygame.Vector2(human.rect.center)
        velocity = pygame.Vector2()
        if self.previous_position is not None and dt > 0:
            velocity = (position - self.previous_position) / dt
        self.previous_position = position
        if velocity.length() > C.PLAYER_SPEED:
            velocity.scale_to_length(C.PLAYER_SPEED)
        item = human.carrying
        ingredient = ingredient_name(item)
        # A sensed pickup counts once, not every frame, chop or later pickup.
        # Movement predictions and the robot's own items never train this model.
        self._learn_start(state, ingredient)
        self.previous_item = item
        candidates, action, confidence = [], "waiting", 0.0
        available = [s for s in state.stations if s.owner in (None, "human", "shared")]
        priority = state.priority_order
        recipe = priority.kind if priority else None
        if chop_name(item):
            candidates = [s for s in available if s.kind == "board" and s.held is None]
            action, confidence = "chop " + item, 0.85
        elif item in C.ORDER_KINDS:
            candidates = [s for s in available if s.kind == "serve"]
            action, confidence = "serve", 0.95
        elif item and item.startswith("chopped_"):
            if recipe == "soup" and item in ("chopped_tomato", "chopped_onion"):
                candidates = [s for s in available if s.kind == "pot" and not s.ready
                              and len(s.contents) < 2 and item not in s.contents]
                partial = [s for s in candidates if s.contents]
                candidates = partial or candidates
                action = "add " + item[8:] + " to soup"
            else:
                candidates = [s for s in available if s.kind == "counter" and s.held is None]
                action = "deliver " + item[8:]
            confidence = 0.75
        elif item in ("plate", "plated_tomato", "plated_lettuce"):
            if item == "plate" and recipe == "soup":
                candidates = [s for s in available if s.kind == "pot" and len(s.contents) == 2]
                action, confidence = "plate soup", 0.85
            else:
                candidates = [s for s in available if s.kind in ("board", "counter")
                              and s.held and frozenset((item, s.held)) in COMBOS]
                action, confidence = "assemble salad", 0.7
        elif ingredient:
            candidates = [s for s in available if s.kind == "counter" and s.held is None]
            action, confidence = "deliver " + ingredient, 0.75
        elif item is None:
            nearby = [s for s in available if s.kind == "board" and chop_name(s.held)
                      and position.distance_to(approach_point(s)) < 85]
            if nearby:
                candidates, action, confidence = nearby, "chop", 0.9
            elif velocity.length() > 20:
                candidates = [s for s in available if s.kind.startswith("crate_")
                              or s.held is not None]
                action, confidence = "approach", 0.4
        heading = velocity.normalize() if velocity.length() > 20 else pygame.Vector2()

        def score(station):
            delta = approach_point(station) - position
            alignment = delta.normalize().dot(heading) if delta.length() else 0
            return delta.length() - 75 * alignment

        goal = min(candidates, key=score) if candidates else None
        source, samples = "rules", 0
        learned_goals = self._transition_goals(state, available)
        if learned_goals:
            learned_goal = min(learned_goals, key=score)
            delta = approach_point(learned_goal) - position
            # Current motion away from a forecast is stronger evidence than history.
            if not (not fresh_action and heading.length_squared() and delta.length_squared()
                    and heading.dot(delta.normalize()) < -0.3):
                prediction = self.transitions.prediction
                goal = learned_goal
                action = prediction.target.description
                confidence, samples = prediction.probability, prediction.samples
                ingredient = ingredient_name(prediction.target.item) or ingredient
                source = "transition"
        if action == "chop" and goal:
            ingredient = goal.held
        if action == "approach" and goal and goal.kind.startswith("crate_"):
            delta = approach_point(goal) - position
            if delta.length() and delta.normalize().dot(heading) > 0.5:
                ingredient = goal.kind[6:]
        projected = position + velocity * 0.5
        if goal and velocity.length() > 20:
            delta = approach_point(goal) - position
            if delta.length() < velocity.length() * 0.5:
                projected = approach_point(goal)
        return HumanIntent(goal, action, ingredient, confidence if goal else 0.0,
                           velocity, projected, source, samples)
