"""Recipe compatibility layer for the existing two robot architectures.

Shared logistics use current delivered inventory only. Anticipatory callers may
add early plate preparation and prepositioning using their existing intent model.
No policy stores the engine, schedule, seed or order RNG.
"""
import json
import logging

import pygame
import config as C

from navigation import approach_point
from recipes import MEAL_RECIPES, ingredient, combination, cooked_recipe
from robot_tasks import Task, execute_task


class MealPolicy:
    def __init__(self, actor):
        self.actor = actor
        self._cache_key = None
        self._cache = {}
        self._diagnostic_key = None
        self.blocked = set()
        actor.completed_meals = dict.fromkeys(MEAL_RECIPES, 0)
        actor.meal_recipe = None

    @staticmethod
    def approach(station):
        if station.owner == "shared":
            return pygame.Vector2(station.rect.right + 26, station.rect.centery)
        return approach_point(station)

    @staticmethod
    def surfaces(state, own=False):
        return [s for s in state.stations if s.kind in ("counter", "board")
                and s.owner in (("robot",) if own else ("robot", "shared"))]

    def choose(self, stations, state):
        actor, nav = self.actor, self.actor.navigator
        bounds, obstacles = nav._geometry(actor, state)
        key = (tuple(actor.pos), tuple(bounds), tuple(tuple(r) for r in obstacles))
        if key != self._cache_key:
            self._cache_key, self._cache = key, {}
        for station in sorted(stations, key=lambda s: pygame.Vector2(actor.rect.center).distance_to(self.approach(s))):
            if station.owner not in ("robot", "shared"):
                continue
            goal = self.approach(station)
            target = tuple(goal)
            if target not in self._cache:
                start = actor.pos + pygame.Vector2(actor.rect.size) / 2
                self._cache[target] = (nav._clear(start, goal, bounds, obstacles)
                                       or bool(nav._route(actor, goal, state, None)))
            if self._cache[target]:
                return station
            self.blocked.add((station.label, tuple(station.rect)))
        return None

    def task(self, stations, action, item, label, recipe, state):
        target = self.choose(stations, state)
        return Task(target, action, item, label, recipe) if target else None

    def store(self, item, recipe, state):
        surfaces = self.surfaces(state, own=True)
        return self.task([s for s in surfaces if s.held is None and s.kind == "counter"],
                         "put", item, "Storing " + item, recipe, state) or self.task(
                             [s for s in surfaces if s.held is None], "put", item,
                             "Storing " + item, recipe, state)

    def pot(self, recipe, state, item=None):
        required = set(MEAL_RECIPES[recipe].ingredients)
        candidates = [s for s in state.stations if s.kind == "pot" and s.owner == "robot"
                      and set(ingredient(i) for i in s.contents) <= required]
        if item is not None:
            candidates = [s for s in candidates if not s.ready and len(s.contents) < 2
                          and ingredient(item) not in [ingredient(i) for i in s.contents]]
        partial = [s for s in candidates if s.contents]
        return self.choose(partial or candidates, state)

    def plate(self, recipe, state):
        return self.task([s for s in self.surfaces(state) if s.held == "plate"],
                         "take", "plate", "Collecting plate", recipe, state) or self.task(
                             [s for s in state.stations if s.kind == "plates"], "fetch", "plate",
                             "Fetching plate for " + MEAL_RECIPES[recipe].name, recipe, state)

    def ready(self, recipe, state):
        items = [s.held for s in self.surfaces(state) if s.held and self.choose([s], state)]
        items.append(self.actor.carrying)
        if recipe in items or "assembled_" + recipe in items:
            return True
        if MEAL_RECIPES[recipe].cooked:
            pot = self.pot(recipe, state)
            if pot:
                items += pot.contents
        return set(MEAL_RECIPES[recipe].ingredients) <= {ingredient(i) for i in items}

    def carried(self, item, recipe, state):
        if item in MEAL_RECIPES:
            if any(o.kind == item and o.time_left > 0 for o in state.orders):
                return self.task([s for s in state.stations if s.kind == "serve"], "serve", item,
                                 "Serving " + MEAL_RECIPES[item].name, item, state)
            return self.store(item, recipe, state)
        definition = MEAL_RECIPES[recipe]
        if definition.cooked:
            if item == "plate":
                return self.task([s for s in state.stations if s.kind == "pot"
                                  and cooked_recipe(s.contents) == recipe], "scoop", item,
                                 "Plating " + definition.name, recipe, state)
            if ingredient(item) in definition.ingredients:
                pot = self.pot(recipe, state, item)
                if pot:
                    return Task(pot, "put_pot", item, "Cooking " + definition.name, recipe)
        else:
            matches = [s for s in self.surfaces(state) if s.held
                       and combination(item, s.held) in (recipe, "assembled_" + recipe)]
            target = self.choose(matches, state)
            if target:
                return Task(target, "combine", target.held, "Assembling " + definition.name, recipe)
        return None

    def for_recipe(self, recipe, state):
        surfaces = self.surfaces(state)
        definition = MEAL_RECIPES[recipe]
        finished = self.task([s for s in surfaces if s.held == recipe], "take", recipe,
                             "Collecting " + definition.name, recipe, state)
        if finished:
            return finished
        if definition.cooked:
            pot = self.pot(recipe, state)
            if pot is None:
                return None
            if cooked_recipe(pot.contents) == recipe:
                return self.plate(recipe, state)
            missing = set(definition.ingredients) - {ingredient(i) for i in pot.contents}
            return self.task([s for s in surfaces if ingredient(s.held) in missing], "take", None,
                             "Collecting ingredients for " + definition.name, recipe, state)
        if self.choose([s for s in surfaces if s.held == "assembled_" + recipe], state):
            return self.plate(recipe, state)
        for name in definition.ingredients:
            candidates = [s for s in surfaces if ingredient(s.held) == name]
            # Do not move stored ingredients between counters while waiting for
            # their partner, or collect redundant handoffs into finite storage.
            if any(s.owner == "robot" and ingredient(s.held) == name for s in surfaces):
                candidates = [s for s in candidates if s.owner == "robot"]
            candidates = [s for s in candidates if self.carried(s.held, recipe, state)
                          or (s.owner == "shared" and self.store(s.held, recipe, state))]
            task = self.task(candidates, "take", None, "Collecting " + name, recipe, state)
            if task:
                return task
        return None

    def plan(self, state, anticipatory=False, expected_counter=None):
        active = [o for o in state.orders if o.time_left > 0 and o.kind in MEAL_RECIPES]
        readiness = {o.kind: self.ready(o.kind, state) for o in active}
        active.sort(key=lambda o: (False if anticipatory else not readiness[o.kind], o.time_left))
        if self.actor.carrying:
            for order in active:
                task = self.carried(self.actor.carrying, order.kind, state)
                if task:
                    return task
            if self.actor.carrying == "plate":
                for pot in (s for s in state.stations if s.kind == "pot"):
                    kind = cooked_recipe(pot.contents)
                    if kind and active:
                        return self.task([pot], "scoop", "plate", "Clearing obsolete cooked batch", kind, state)
            return self.store(self.actor.carrying, active[0].kind if active else None, state)
        for kind in dict.fromkeys(o.kind for o in active):
            task = self.for_recipe(kind, state)
            if task:
                if task.action == "take":
                    task.item = task.station.held
                return task
        # A started batch for an expired order must not permanently occupy the
        # cooker. Recover an uncooked portion or plate a finished batch to store.
        if active:
            for pot in (s for s in state.stations if s.kind == "pot" and s.contents):
                if any(set(ingredient(i) for i in pot.contents) <= set(MEAL_RECIPES[o.kind].ingredients)
                       and MEAL_RECIPES[o.kind].cooked for o in active):
                    continue
                if len(pot.contents) == 1 and self.store(pot.contents[0], active[0].kind, state):
                    return self.task([pot], "take", pot.contents[0], "Clearing obsolete batch",
                                     active[0].kind, state)
                kind = cooked_recipe(pot.contents)
                if kind and self.store(kind, active[0].kind, state):
                    return self.plate(kind, state)
        if anticipatory and active:
            kind = active[0].kind
            if (not any(s.held == "plate" for s in self.surfaces(state))
                    and self.store("plate", kind, state)):
                return self.plate(kind, state)
            counters = [s for s in state.stations if s.owner == "shared" and s.held is None]
            if expected_counter in counters:
                counters = [expected_counter]
            return self.task(counters, "wait_delivery", None, "Waiting at predicted handoff", kind, state)
        return None

    def update(self, dt, state, anticipatory=False, expected_counter=None, starting=False):
        actor = self.actor
        previous = actor.task
        self.blocked = set()
        events, navigation = [], "not_requested"
        if not actor.enabled:
            actor.status = "Disabled by user"
        elif starting or state.elapsed < C.ROBOT_START_DELAY - 1e-9:
            actor.status = "Starting after 0.5 seconds"
        else:
            actor.task = self.plan(state, anticipatory, expected_counter)
            task = actor.task
            actor.meal_recipe = task.recipe if task else None
            if task is None:
                actor.status = "Waiting for delivered ingredients" if state.priority_order else "Waiting for orders"
                if actor.carrying or self.blocked:
                    actor.status = "Waiting for station or storage access"
                events.append("no_valid_action")
            else:
                actor.status = task.label
                arrived = actor.navigator.move_to(actor, self.approach(task.station), state, dt)
                navigation = actor.navigator.reason
                if arrived and task.action != "wait_delivery":
                    if actor.rect.inflate(50, 50).colliderect(task.station.rect):
                        result = execute_task(actor, task, state, dt)
                        if result == "waiting":
                            actor.status = "Waiting for cooking: " + MEAL_RECIPES[task.recipe].name
                        elif result == "failed":
                            actor.status = "Action failed; replanning"
                            events.append("interaction_no_effect")
                        elif result == "completed":
                            events.append("task_completed")
                            if task.action == "serve":
                                actor.completed_meals[task.recipe] += 1
                elif navigation in ("no_route", "collision_rejected"):
                    actor.status = "Waiting for a clear path to " + task.station.label
                    events.append(navigation)
        task = actor.task
        target = ((task.station.label, tuple(task.station.rect), task.action, task.item) if task else None)
        blocked = sorted(self.blocked)
        key = (target, actor.status, navigation, tuple(blocked))
        if key != self._diagnostic_key:
            self._diagnostic_key = key
            actor.diagnostic_revision += 1
            actor.diagnostic = {"decision": actor.status, "task": target, "navigation": navigation,
                                "route_exists": bool(actor.navigator.path) if task else None,
                                "planned_path": actor.navigator.planned_path if task else [],
                                "events": events + (["task_changed"] if previous != task else []),
                                "unreachable_targets": blocked,
                                "intentional_wait": navigation not in ("no_route", "collision_rejected")
                                and actor.status.startswith(("Waiting", "Starting", "Disabled"))}
            logging.getLogger(__name__).info("robot_decision %s", json.dumps(actor.diagnostic))
