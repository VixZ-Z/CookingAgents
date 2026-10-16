"""Shared robot tasks executed through the existing game rules."""
from dataclasses import dataclass

import config as C
from game import Station, chop_name, handle_counter_combinations, interact


@dataclass
class Task:
    station: Station
    action: str
    item: str | None
    label: str
    recipe: str | None


def execute_task(actor, task, state, dt):
    """Execute an in-range task; return completed, working, waiting or failed."""
    station = task.station
    if task.action == "wait_for_handoff":
        return "waiting"
    if task.action == "chop":
        chopped = chop_name(station.held)
        if actor.carrying is not None or chopped is None:
            return "failed"
        station.progress += dt
        if station.progress < C.CHOP_TIME:
            return "working"
        station.held, station.progress = chopped, 0
        return "completed"
    if task.action == "scoop" and not station.ready:
        return "waiting"
    before = (actor.carrying, station.held, tuple(station.contents), state.score)
    if task.action == "combine":
        handle_counter_combinations(actor, station)
    else:
        interact(actor, station, state)
    after = (actor.carrying, station.held, tuple(station.contents), state.score)
    return "completed" if before != after else "failed"
