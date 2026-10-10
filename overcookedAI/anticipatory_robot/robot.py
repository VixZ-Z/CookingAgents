"""Shared-kitchen teammate: anticipate complementary work for the earliest deadline.

Observable goals override learned starter frequencies. No full action-sequence
learning, forgetting or h yet.
"""
from __future__ import annotations

from dataclasses import dataclass

import pygame

import config as C
from game import COMBOS, Station, chop_name, handle_counter_combinations, interact
from navigation import Navigator, approach_point
from robot_base import RobotBase
from .model import HumanIntentModel, ingredient_name


@dataclass
class Task:
    station: Station
    action: str
    item: str | None
    label: str
    recipe: str | None


class AnticipatoryRobot(RobotBase):
    avoids_human = True
    ensure_mixed_orders = True
    speed = C.ROBOT_SPEED

    def __init__(self, state):
        if state.layout.name not in ("shared", "scripted"):
            raise ValueError("Anticipatory prototype needs a shared kitchen")
        super().__init__(*state.layout.robot_start)
        self.model = HumanIntentModel()
        self.navigator = Navigator()
        self.intent = None
        self.task = None
        self.own_board = None
        self.reassigned_board = None
        self.human_ingredient = None
        self.priority_order = state.priority_order
        self.contribution_source = None
        self.routine_prediction = None
        self.stow_for_reassignment = False
        self.status = f"Starting in {C.ROBOT_START_DELAY:.1f}s"
        self.completed_salads = 0
        self.completed_soups = 0

    @property
    def recipe(self):
        return self.priority_order.kind if self.priority_order else None

    @property
    def ingredients(self):
        return C.RECIPE_INGREDIENTS.get(self.recipe, ())

    def _near_human(self, station, state):
        distance = pygame.Vector2(state.player.rect.center).distance_to(approach_point(station))
        return distance < 72

    def _choose_station(self, stations, state):
        candidates = [s for s in stations if s.owner in (None, "shared", "robot")
                      and not self._near_human(s, state)
                      and not (self.intent and s is self.intent.goal)]
        return min(candidates, key=lambda s: pygame.Vector2(self.rect.center).distance_to(
            approach_point(s))) if candidates else None

    def _pick(self, station, action, item, label):
        return Task(station, action, item, label, self.recipe) if station else None

    @staticmethod
    def _surfaces(state):
        return [s for s in state.stations if s.kind in ("counter", "board")]

    def _inventory(self, state):
        items = [s.held for s in self._surfaces(state)]
        items += [state.player.carrying, self.carrying]
        if self.recipe == "soup":
            items += [item for s in state.stations if s.kind == "pot" for item in s.contents]
        return items

    def _observe_contribution(self, state):
        carried = ingredient_name(state.player.carrying)
        ingredient = carried if carried in self.ingredients else None
        source = "observed"
        if ingredient is None and self.contribution_source != "observed":
            ingredient = self.intent.ingredient if self.intent else None
            source = "movement"
        if ingredient in self.ingredients:
            if ingredient != self.human_ingredient:
                # Human behaviour overrides the forecast, including a task in flight.
                self.task = None
                if self.carrying and ingredient_name(self.carrying) == ingredient:
                    self.stow_for_reassignment = True
                if self.own_board and ingredient_name(self.own_board.held) == ingredient:
                    self.reassigned_board = self.own_board
                    self.own_board = None
            self.human_ingredient = ingredient
            self.contribution_source = source
            self.routine_prediction = None
        if self.human_ingredient not in self.ingredients:
            self.human_ingredient = None
        if self.human_ingredient is None:
            self.routine_prediction = self.model.predict_start(self.recipe)
            if self.routine_prediction:
                self.human_ingredient = self.routine_prediction.ingredient
                self.contribution_source = "routine"
                return
            items = self._inventory(state)
            for name in self.ingredients:
                if any(item in items for item in (name, "chopped_" + name, "plated_" + name)):
                    self.human_ingredient = name
                    self.contribution_source = "delivered"
                    break
            if self.human_ingredient is None and self.ingredients:
                # Bootstrap the shared recipe ingredient without inventing observations.
                self.human_ingredient = "tomato"
                self.contribution_source = "default"

    @property
    def cooperation_description(self):
        if self.contribution_source == "routine" and self.routine_prediction:
            return self.routine_prediction.description
        if self.contribution_source == "default":
            return "Expected start: tomato (initial assumption)"
        return self.intent.description if self.intent else "Learning your first ingredient"

    def _store(self, state):
        station = self._choose_station(
            [s for s in self._surfaces(state) if s.kind == "counter" and s.held is None], state)
        return self._pick(station, "put", self.carrying,
                          "Leaving " + self.carrying + " on a counter")

    def _soup_pot(self, item, state):
        pots = [s for s in state.stations if s.kind == "pot" and not s.ready
                and len(s.contents) < 2 and item not in s.contents
                and set(s.contents) <= {"chopped_tomato", "chopped_onion"}]
        # Wait for access to a partial pot instead of splitting one soup across two pots.
        partial = [s for s in pots if s.contents]
        return self._choose_station(partial or pots, state)

    def _carried_task(self, state):
        item = self.carrying
        if item in ("salad", "soup"):
            if any(o.kind == item and o.time_left > 0 for o in state.orders):
                target = self._choose_station([s for s in state.stations if s.kind == "serve"], state)
                return self._pick(target, "serve", item, "Serving our " + item)
            return self._store(state)
        if self.stow_for_reassignment:
            return self._store(state)
        if item in self.ingredients:
            target = self._choose_station(
                [s for s in self._surfaces(state) if s.kind == "board" and s.held is None], state)
            return self._pick(target, "put", item, "Preparing " + item) if target else self._store(state)
        if self.recipe == "soup":
            if item in ("chopped_tomato", "chopped_onion"):
                pot = self._soup_pot(item, state)
                if pot:
                    return self._pick(pot, "put_pot", item, "Adding " + item[8:] + " to soup")
            elif item == "plate":
                pots = [s for s in state.stations if s.kind == "pot"
                        and set(s.contents) == {"chopped_tomato", "chopped_onion"}]
                target = self._choose_station(pots, state)
                if target:
                    return self._pick(target, "scoop", item, "Plating our soup")
            return self._store(state)
        if self.recipe == "salad":
            matches = [s for s in self._surfaces(state) if s.held
                       and frozenset((item, s.held)) in COMBOS]
            target = self._choose_station(matches, state)
            if target:
                return self._pick(target, "combine", target.held, "Assembling our salad")
        return self._store(state)

    def _plate_task(self, state, soup=False):
        inventory = self._inventory(state)
        plate_items = ("plate",) if soup else ("plate", "plated_tomato", "plated_lettuce")
        if state.player.carrying in plate_items:
            return None
        target = self._choose_station([s for s in self._surfaces(state) if s.held == "plate"], state)
        if target:
            return self._pick(target, "take", "plate", "Collecting a plate")
        if not any(item in plate_items for item in inventory):
            target = self._choose_station([s for s in state.stations if s.kind == "plates"], state)
            return self._pick(target, "fetch", "plate", "Fetching a plate for " + self.recipe)
        return None

    def _prepare_complement(self, state):
        if self.human_ingredient is None:
            return None
        other = next(name for name in self.ingredients if name != self.human_ingredient)
        inventory = self._inventory(state)
        human_items = (self.human_ingredient, "chopped_" + self.human_ingredient,
                       "plated_" + self.human_ingredient)
        approaching = (self.intent and self.intent.action == "approach"
                       and self.intent.ingredient == self.human_ingredient)
        if (self.contribution_source not in ("routine", "default") and not approaching
                and not any(item in human_items for item in inventory)):
            return None
        raw = self._choose_station(
            [s for s in self._surfaces(state) if s.held == other], state)
        if raw:
            action = "chop" if raw.kind == "board" else "take"
            return self._pick(raw, action, other, "Preparing existing " + other)
        if any(item in inventory for item in (other, "chopped_" + other, "plated_" + other)):
            return None
        board = self._choose_station(
            [s for s in self._surfaces(state) if s.kind == "board" and s.held is None], state)
        if board:
            target = self._choose_station([s for s in state.stations if s.kind == "crate_" + other], state)
            label = (f"Expecting your {self.human_ingredient}: prepare {other}"
                     if self.contribution_source in ("routine", "default")
                     else "Anticipating " + self.recipe + ": prepare " + other)
            return self._pick(target, "fetch", other, label)
        return None

    def _salad_task(self, state):
        surfaces = self._surfaces(state)
        held = [s.held for s in surfaces]
        for name, other in (("tomato", "lettuce"), ("lettuce", "tomato")):
            if "chopped_" + other in held:
                target = self._choose_station([s for s in surfaces if s.held == "plated_" + name], state)
                if target:
                    return self._pick(target, "take", target.held, "Finishing our salad")
        ready = any(item in ("chopped_tomato", "chopped_lettuce") for item in self._inventory(state))
        if ready:
            task = self._plate_task(state)
            if task:
                return task
        return self._prepare_complement(state)

    def _soup_task(self, state):
        full_pots = [s for s in state.stations if s.kind == "pot"
                     and set(s.contents) == {"chopped_tomato", "chopped_onion"}]
        if full_pots:
            return self._plate_task(state, soup=True)
        for item in ("chopped_tomato", "chopped_onion"):
            target = self._choose_station([s for s in self._surfaces(state) if s.held == item], state)
            if target and self._soup_pot(item, state):
                return self._pick(target, "take", item, "Collecting " + item[8:] + " for soup")
        return self._prepare_complement(state)

    def _plan(self, state):
        if self.carrying:
            return self._carried_task(state)
        if self.reassigned_board:
            board = self.reassigned_board
            if board.held and (ingredient_name(board.held) == self.human_ingredient
                               or ingredient_name(board.held) not in self.ingredients):
                target = self._choose_station([board], state)
                return self._pick(target, "take_for_reassignment", board.held,
                                  "Clearing my board after your change of plan")
            self.reassigned_board = None
        if self.recipe is None:
            return None
        # Hand over the finished dish if the human is already serving this recipe.
        if state.player.carrying == self.recipe:
            return None
        if self.own_board:
            item = self.own_board.held
            if item in self.ingredients:
                target = self._choose_station([self.own_board], state)
                return self._pick(target, "chop", item, "Chopping " + item)
            if item in tuple("chopped_" + name for name in self.ingredients):
                return self._pick(self.own_board, "take", item, "Collecting chopped ingredient")
            self.own_board = None
        target = self._choose_station([s for s in self._surfaces(state) if s.held == self.recipe], state)
        if target:
            return self._pick(target, "take", self.recipe, "Collecting our " + self.recipe)
        return self._soup_task(state) if self.recipe == "soup" else self._salad_task(state)

    def _valid(self, task, state):
        st = task.station
        if st.owner not in (None, "shared", "robot"):
            return False
        if task.action != "serve" and task.recipe != self.recipe:
            return False
        if task.action == "fetch":
            if self.carrying is not None or self.recipe is None:
                return False
            items = self._inventory(state)
            if task.item != "plate":
                return (task.item in self.ingredients and task.item != self.human_ingredient
                        and not any(item in items for item in (
                            task.item, "chopped_" + task.item, "plated_" + task.item)))
            unavailable = ("plate",) if self.recipe == "soup" else (
                "plate", "plated_tomato", "plated_lettuce", "salad")
            return not any(item in unavailable for item in items)
        if task.action in ("take", "take_for_reassignment"):
            return self.carrying is None and st.held == task.item
        if task.action == "put":
            return self.carrying == task.item and st.held is None
        if task.action == "put_pot":
            return (self.carrying == task.item and not st.ready and len(st.contents) < 2
                    and task.item not in st.contents)
        if task.action == "scoop":
            return (self.carrying == "plate"
                    and set(st.contents) == {"chopped_tomato", "chopped_onion"})
        if task.action == "combine":
            return st.held == task.item and frozenset((self.carrying, st.held)) in COMBOS
        if task.action == "chop":
            return self.carrying is None and st.held == task.item and chop_name(st.held) is not None
        return self.carrying == task.item and any(
            o.kind == task.item and o.time_left > 0 for o in state.orders)

    def _yield(self, state, dt):
        if not self.intent:
            return
        center = pygame.Vector2(self.rect.center)
        projected = self.intent.projected_position
        goal = self.intent.goal
        reserving_access = (goal is not None
                            and center.distance_to(approach_point(goal)) < 90)
        if reserving_access:
            # A blocked human can be stationary. Clear their station approach too.
            direction = approach_point(goal) - pygame.Vector2(state.player.rect.center)
            if direction.length_squared() == 0:
                direction = center - pygame.Vector2(state.player.rect.center)
        else:
            if self.intent.velocity.length() < 20 or center.distance_to(projected) > 90:
                return
            direction = self.intent.velocity
        if direction.length_squared() == 0:
            return
        heading = direction.normalize()
        side = pygame.Vector2(-heading.y, heading.x)
        bounds, obstacles = self.navigator._geometry(self, state)
        for goal in (center + side * 85, center - side * 85):
            if self.navigator._clear(center, goal, bounds, obstacles):
                self.navigator.move_to(self, goal, state, dt, projected)
                self.status = "Making room for you"
                return

    def update_ai(self, dt, state):
        previous_order = self.priority_order
        self.priority_order = state.priority_order
        if previous_order is not self.priority_order:
            # Reset roles for every new order, including another order of the same recipe.
            # Prepared ingredients remain available; history survives order changes.
            self.task = None
            self.human_ingredient = None
            self.contribution_source = None
            self.routine_prediction = None
        self.intent = self.model.observe(state, dt)
        if not self.enabled:
            return
        self._observe_contribution(state)
        # Game time excludes pause; only a new game/restart applies this delay.
        if state.elapsed + dt < C.ROBOT_START_DELAY - 1e-9:
            self.status = f"Starting in {C.ROBOT_START_DELAY - state.elapsed - dt:.2f}s"
            return
        if self.navigator.make_space(self, state, dt):
            self.status = "Making room for you"
            return
        if self.task and not self._valid(self.task, state):
            self.task = None
        if self.task is None:
            self.task = self._plan(state)
        if self.task is None:
            names = " or ".join(self.ingredients)
            if self.contribution_source in ("routine", "default"):
                self.status = "Waiting for your " + self.human_ingredient + " or station access"
            else:
                self.status = "Priority " + self.recipe + ": waiting for " + names if self.recipe else "Waiting for orders"
            self._yield(state, dt)
            return
        task, st = self.task, self.task.station
        self.status = task.label
        if self._near_human(st, state) or st is self.intent.goal:
            self.status = "Giving you access to " + st.label
            self._yield(state, dt)
            return
        projected = self.intent.projected_position if self.intent.velocity.length() > 20 else None
        if not self.navigator.move_to(self, approach_point(st), state, dt, projected):
            if not self.navigator.path:
                self.status = "Waiting for a clear path to " + st.label
            return
        if not self.rect.inflate(50, 50).colliderect(st.rect):
            return
        if task.action == "chop":
            st.progress += dt
            if st.progress < C.CHOP_TIME:
                return
            st.held, st.progress = chop_name(st.held), 0
            self.own_board = st
        else:
            if task.action == "scoop" and not st.ready:
                self.status = "Waiting for soup to finish cooking"
                return
            before = (self.carrying, st.held, tuple(st.contents), state.score)
            if task.action == "combine":
                handle_counter_combinations(self, st)
            else:
                interact(self, st, state)
            if before == (self.carrying, st.held, tuple(st.contents), state.score):
                self.task = None
                return
            if task.action == "put" and st.kind == "board":
                self.own_board = st
            if task.action == "put" and st.kind == "counter":
                self.stow_for_reassignment = False
            if task.action == "take" and st is self.own_board:
                self.own_board = None
            if task.action == "take_for_reassignment":
                self.stow_for_reassignment = True
                self.reassigned_board = None
            if task.action == "serve":
                if task.item == "soup":
                    self.completed_soups += 1
                else:
                    self.completed_salads += 1
                self.human_ingredient = None
        self.task = None
