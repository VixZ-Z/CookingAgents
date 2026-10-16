"""Timing-assisted variants of the delivered-items reactive policy.

Available cooking work takes precedence. While waiting for supplies, h selects
between staging one plate and getting ready at the predicted handoff counter.
"""
import math

import config as C
from human_horizon import HumanHorizon, path_distance
from robot_tasks import Task
from .robot import ReactiveRobot


class HorizonRobot(ReactiveRobot):
    h_mode = None

    def __init__(self, state):
        super().__init__(state)
        self.horizon = HumanHorizon(state, self.h_mode)
        self.scheduling = {}
        self._prefetching = False

    @property
    def horizon_description(self):
        remaining = self.horizon.remaining
        value = "unknown" if remaining is None else f"{remaining:.1f}s"
        return f"{self.h_mode.title()} h: {value} | {self.horizon.estimate.source}"

    @property
    def contribution_source(self):
        return ("horizon" if self.scheduling.get("choice") in
                ("prepare_plate", "store_prefetched_plate", "receive") else None)

    def _forecast_order(self, state):
        item = self.horizon.estimate.item
        orders = [o for o in state.orders if o.time_left > 0]
        compatible = [o for o in orders if item == o.kind or any(
            item in (name, "chopped_" + name, "plated_" + name)
            for name in C.RECIPE_INGREDIENTS[o.kind])]
        return min(compatible, key=lambda o: o.time_left, default=None)

    def _cost(self, seconds):
        h = self.horizon.remaining
        idle = max(0.0, h - seconds)
        late = max(0.0, seconds - h)
        return dict(duration=seconds, robot_idle=idle, handoff_lateness=late,
                    cost=idle + C.H_HANDOFF_LATENESS_WEIGHT * late)

    def _carried_task(self, item, recipe, state):
        if (recipe == "salad" and item in ("plate", "chopped_tomato", "chopped_lettuce")
                and not self._recipe_ready(recipe, state)):
            # A staged plate is not a reason to commit a shared tomato to salad
            # before a second ingredient has actually been delivered.
            return self._store(item, recipe, state)
        return super()._carried_task(item, recipe, state)

    def _plan(self, state):
        if self._prefetching and self.carrying == "plate":
            order = self._forecast_order(state)
            if not any(o.time_left > 0 and self._recipe_ready(o.kind, state) for o in state.orders):
                task = self._store("plate", order.kind if order else None, state)
                self.scheduling = {"choice": "store_prefetched_plate"}
                return task
            self._prefetching = False
        if self._prefetching and any(s.held == "plate" for s in self._surfaces(state, own=True)):
            self._prefetching = False
        baseline = super()._plan(state)
        if baseline:
            self._prefetching = False
            self.scheduling = {"choice": "available_work"}
            return baseline
        self.scheduling = {"choice": "wait_for_observation"}
        estimate, h = self.horizon.estimate, self.horizon.remaining
        order = self._forecast_order(state)
        if (self.carrying is not None or h is None or h <= 0 or order is None
                or estimate.action != "put" or not self._reachable(estimate.target, state)):
            self._prefetching = False
            return None
        handoff = self._approach(estimate.target)
        receive_seconds = path_distance(self, handoff, state) / self.speed
        if not math.isfinite(receive_seconds):
            return None
        candidates = {"receive": self._cost(receive_seconds)}
        task = Task(estimate.target, "wait_for_handoff", None,
                    "Waiting near predicted handoff", order.kind)
        plates = [s for s in state.stations if s.kind == "plates" and s.owner == "robot"]
        storage = self._choose([s for s in self._surfaces(state, own=True)
                                if s.kind == "counter" and s.held is None], state)
        plate = self._choose(plates, state)
        plate_exists = any(s.held in ("plate", "plated_tomato", "plated_lettuce", "salad", "soup")
                           for s in self._surfaces(state))
        needs_plate = estimate.item not in ("plate", "plated_tomato", "plated_lettuce", "salad", "soup")
        if plate and storage and not plate_exists and needs_plate:
            duration = (path_distance(self, self._approach(plate), state)
                        + path_distance(self, self._approach(storage), state, start=self._approach(plate))
                        + path_distance(self, handoff, state, start=self._approach(storage))) / self.speed
            duration += 2 * C.H_INTERACTION_SECONDS
            if math.isfinite(duration) and duration < order.time_left:
                candidates["prepare_plate"] = self._cost(duration)
                if candidates["prepare_plate"]["cost"] < candidates["receive"]["cost"]:
                    task = Task(plate, "fetch", "plate", "Preparing a plate before the handoff", order.kind)
                    self._prefetching = True
        choice = "prepare_plate" if task.action == "fetch" else "receive"
        self._prefetching = choice == "prepare_plate"
        self.scheduling = {"choice": choice, "candidates": candidates}
        return task

    def update_ai(self, dt, state):
        self.transition_model.update(state)
        self.horizon.update(state, dt, self.transition_model)
        self.scheduling = {"choice": "disabled"}
        super().update_ai(dt, state)


class AnticipatoryFixedHRobot(HorizonRobot):
    h_mode = "fixed"


class AnticipatoryDynamicHRobot(HorizonRobot):
    h_mode = "dynamic"
