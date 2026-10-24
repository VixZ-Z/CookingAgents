"""Divided-kitchen collaborator using orders and delivered items only.

Transition forecasts are learned for observation only, never used by the policy.
No intent-based planning, ingredient fetching or autonomous takeover.
The human's body is considered only by collision-aware navigation.
"""
import json
import logging

import pygame

import config as C
from game import COMBOS
from navigation import Navigator, approach_point
from robot_base import RobotBase
from robot_tasks import Task, execute_task
from human_transitions import HumanTransitionModel


class ReactiveRobot(RobotBase):
    avoids_human = True
    ensure_mixed_orders = True
    speed = C.ROBOT_SPEED

    def __init__(self, state):
        if state.layout.name not in ("divided", "shared", "scripted"):
            raise ValueError("Reactive robot requires a divided or shared workspace")
        super().__init__(*state.layout.robot_start)
        self.navigator = Navigator()
        self.transition_model = HumanTransitionModel()
        self.task = None
        self.recipe = None
        self.status = "Waiting for delivered ingredients"
        self.completed_salads = self.completed_soups = 0
        self.diagnostic = {}
        self.diagnostic_revision = 0
        self._diagnostic_key = None
        self._route_cache_key = None
        self._route_cache = {}
        self._blocked_targets = set()

    @staticmethod
    def _approach(station):
        if station.owner == "shared":
            return pygame.Vector2(station.rect.right + 26, station.rect.centery)
        return approach_point(station)

    def _reachable(self, station, state):
        bounds, obstacles = self.navigator._geometry(self, state)
        key = (tuple(self.pos), tuple(bounds), tuple(tuple(r) for r in obstacles))
        if key != self._route_cache_key:
            self._route_cache_key, self._route_cache = key, {}
        goal = self._approach(station)
        target = tuple(goal)
        if target not in self._route_cache:
            center = self.pos + pygame.Vector2(self.rect.size) / 2
            self._route_cache[target] = (self.navigator._clear(center, goal, bounds, obstacles)
                                        or bool(self.navigator._route(self, goal, state, None)))
        return self._route_cache[target]

    def _choose(self, stations, state):
        candidates = sorted((s for s in stations if s.owner in ("robot", "shared")),
                            key=lambda s: pygame.Vector2(self.rect.center).distance_to(self._approach(s)))
        for station in candidates:
            if self._reachable(station, state):
                return station
            self._blocked_targets.add((station.label, tuple(station.rect)))
        return None

    @staticmethod
    def _surfaces(state, own=False):
        owners = ("robot",) if own else ("robot", "shared")
        return [s for s in state.stations if s.kind in ("board", "counter") and s.owner in owners]

    def _task(self, stations, action, item, label, recipe, state):
        station = self._choose(stations, state)
        return Task(station, action, item, label, recipe) if station else None

    def _store(self, item, recipe, state):
        return self._task([s for s in self._surfaces(state, own=True)
                           if s.kind == "counter" and s.held is None],
                          "put", item, "Storing " + item, recipe, state)

    def _pot(self, item, state):
        pots = [s for s in state.stations if s.owner == "robot" and s.kind == "pot"
                and not s.ready and len(s.contents) < 2 and item not in s.contents]
        return self._choose([s for s in pots if s.contents] or pots, state)

    def _carried_task(self, item, recipe, state):
        own = self._surfaces(state, own=True)
        if item in C.ALL_RECIPE_INGREDIENTS:
            if any(o.kind == item and o.time_left > 0 for o in state.orders):
                return self._task([s for s in state.stations if s.kind == "serve"],
                                  "serve", item, "Serving " + item, item, state)
            return self._store(item, recipe, state)
        if recipe is None:
            return self._store(item, recipe, state)
        if item in C.ALL_RECIPE_INGREDIENTS[recipe]:
            return self._task([s for s in own if s.kind == "board" and s.held is None],
                              "put", item, "Preparing " + item, recipe, state) or self._store(item, recipe, state)
        if recipe == "soup":
            if item in ("chopped_tomato", "chopped_onion"):
                pot = self._pot(item, state)
                if pot:
                    return Task(pot, "put_pot", item, "Adding " + item[8:] + " to soup", recipe)
            if item == "plate":
                return self._task([s for s in state.stations if s.kind == "pot"
                                   and set(s.contents) == {"chopped_tomato", "chopped_onion"}],
                                  "scoop", item, "Plating soup", recipe, state) or self._store(item, recipe, state)
        else:
            task = self._task([s for s in self._surfaces(state) if s.held
                               and frozenset((item, s.held)) in COMBOS],
                              "combine", None, "Assembling salad", recipe, state)
            if task:
                task.item = task.station.held
                return task
        return self._store(item, recipe, state)

    def _plate(self, recipe, state):
        return self._task([s for s in self._surfaces(state) if s.held == "plate"],
                          "take", "plate", "Collecting plate", recipe, state) or self._task(
                              [s for s in state.stations if s.kind == "plates"],
                              "fetch", "plate", "Fetching plate for " + recipe, recipe, state)

    def _recipe_task(self, recipe, state):
        surfaces = self._surfaces(state)
        own = self._surfaces(state, own=True)
        task = self._task([s for s in surfaces if s.held == recipe],
                          "take", recipe, "Collecting finished " + recipe, recipe, state)
        if task:
            return task
        if recipe == "soup":
            full = self._choose([s for s in state.stations if s.kind == "pot"
                                 and set(s.contents) == {"chopped_tomato", "chopped_onion"}], state)
            if full:
                return self._plate(recipe, state)
        else:
            for item, other in (("plated_tomato", "chopped_lettuce"),
                                ("plated_lettuce", "chopped_tomato")):
                if self._choose([s for s in surfaces if s.held == other], state):
                    task = self._task([s for s in surfaces if s.held == item],
                                      "take", item, "Finishing salad", recipe, state)
                    if task:
                        return task
            if (self._recipe_ready(recipe, state)
                    and self._choose([s for s in own if s.held in ("chopped_tomato", "chopped_lettuce")], state)):
                if not any(s.held in ("plated_tomato", "plated_lettuce") for s in own):
                    return self._plate(recipe, state)
        for name in C.ALL_RECIPE_INGREDIENTS[recipe]:
            chopped = "chopped_" + name
            if recipe == "soup" and self._pot(chopped, state) is None:
                continue
            task = self._task([s for s in own if s.kind == "board" and s.held == name],
                              "chop", name, "Chopping " + name, recipe, state)
            if task:
                return task
            for item in (chopped, name):
                destination = self._carried_task(item, recipe, state)
                if destination is None:
                    continue
                if item == name and destination.station.kind != "board":
                    continue
                sources = [s for s in surfaces if s.held == item]
                if any(s.held in (name, chopped, "plated_" + name) for s in own):
                    sources = [s for s in sources if s.owner == "robot"]
                # Do not shuffle a stored ingredient between counters.
                if destination.action == "put" and destination.station.kind == "counter":
                    sources = [s for s in sources if s.owner == "shared" or s.kind == "board"]
                task = self._task(sources, "take", item, "Collecting " + item, recipe, state)
                if task:
                    return task
        return None

    def _recipe_ready(self, recipe, state):
        """Whether the currently observed supply can complete this recipe."""
        items = [s.held for s in self._surfaces(state) if s.held and self._reachable(s, state)]
        items.append(self.carrying)
        if recipe in items:
            return True
        if recipe == "soup":
            items += [item for s in state.stations if s.kind == "pot" and s.owner == "robot"
                      and self._reachable(s, state) for item in s.contents]
        return all(any(item in items for item in (name, "chopped_" + name)
                       + (("plated_" + name,) if recipe == "salad" else ()))
                   for name in C.ALL_RECIPE_INGREDIENTS[recipe])

    def _plan(self, state):
        from menu import RECIPES
        if not state.legacy_menu:
            from menu_planner import plan
            return plan(self, state)
        readiness = {kind: self._recipe_ready(kind, state) for kind in C.ALL_RECIPE_INGREDIENTS}
        orders = sorted((o for o in state.orders if o.time_left > 0),
                        key=lambda o: (not readiness[o.kind], o.time_left))
        if self.carrying:
            for order in orders:
                if (self.carrying in (order.kind, "plate")
                        or any(self.carrying in (name, "chopped_" + name, "plated_" + name)
                               for name in C.ALL_RECIPE_INGREDIENTS[order.kind])):
                    task = self._carried_task(self.carrying, order.kind, state)
                    if task and (task.action != "put" or task.station.kind == "board"):
                        return task
            return self._store(self.carrying, orders[0].kind if orders else None, state)
        seen = set()
        for order in orders:
            if order.kind not in seen:
                seen.add(order.kind)
                task = self._recipe_task(order.kind, state)
                if task:
                    return task
        # An expired/reprioritized order can leave its ingredient on our only
        # board. Clear that observed obstruction before processing new deliveries.
        requested = {name for kind in seen for name in C.ALL_RECIPE_INGREDIENTS[kind]}
        if orders and any(s.owner == "shared" and s.held in requested for s in self._surfaces(state)):
            for board in self._surfaces(state, own=True):
                if board.kind != "board" or board.held is None:
                    continue
                if board.held in ("tomato", "lettuce", "onion"):
                    return self._task([board], "chop", board.held, "Clearing board: chop " + board.held,
                                      orders[0].kind, state)
                if self._store(board.held, orders[0].kind, state):
                    return self._task([board], "take", board.held, "Clearing board for delivered ingredients",
                                      orders[0].kind, state)
        return None

    def update_ai(self, dt, state):
        self.transition_model.update(state)
        previous = self.task
        events = []
        self._blocked_targets = set()
        navigation = "not_requested"
        if not self.enabled:
            self.status = "Disabled by user"
        else:
            # Chopping progress belongs to the station, so reevaluating current
            # contents and order urgency does not restart preparation.
            self.task = self._plan(state)
            self.recipe = self.task.recipe if self.task else None
            if self.task is None:
                self.status = ("Waiting for ingredients at handoff counters" if state.priority_order
                               else "Waiting for orders")
                if self.carrying:
                    self.status = "Waiting for station access to use " + self.carrying
                elif self._blocked_targets:
                    self.status = "Waiting for access to blocked stations"
                events.append("no_valid_action")
            else:
                task = self.task
                self.status = task.label
                if self.navigator.move_to(self, self._approach(task.station), state, dt):
                    if self.rect.inflate(50, 50).colliderect(task.station.rect):
                        result = execute_task(self, task, state, dt)
                        if result == "waiting":
                            self.status = ("Waiting for soup to finish cooking"
                                           if task.action == "scoop" else task.label)
                        elif result == "failed":
                            self.status = "Action failed; reconsidering task"
                            events.append("interaction_no_effect")
                        elif result == "completed":
                            events.append("task_completed")
                            if task.action == "serve":
                                if task.item == "salad":
                                    self.completed_salads += 1
                                elif task.item == "soup":
                                    self.completed_soups += 1
                elif self.navigator.reason in ("no_route", "collision_rejected"):
                    self.status = "Waiting for a clear path to " + task.station.label
                    events.append(self.navigator.reason)
                navigation = self.navigator.reason
                if self.navigator.stuck:
                    events.append("stalled_path_replanning")
        task = self.task
        target = ((task.station.label, tuple(task.station.rect), task.action, task.item) if task else None)
        blocked = sorted(self._blocked_targets)
        key = (target, self.status, navigation, tuple(blocked))
        if key != self._diagnostic_key:
            self._diagnostic_key = key
            self.diagnostic_revision += 1
            self.diagnostic = {"decision": self.status, "task": target, "navigation": navigation,
                               "route_exists": bool(self.navigator.path) if task else None,
                               "planned_path": self.navigator.planned_path if task else [],
                               "events": events + (["task_changed"] if previous != task else []),
                               "unreachable_targets": blocked,
                               "intentional_wait": navigation not in ("no_route", "collision_rejected")
                               and self.status.startswith(("Waiting", "Disabled"))}
            logging.getLogger(__name__).info("robot_decision %s", json.dumps(self.diagnostic))
