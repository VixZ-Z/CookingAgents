"""Run logging for the human-in-the-loop experiments.

Two outputs per game (all rows carry the run metadata, so files can be
concatenated and loaded straight into pandas):

* ``logs/<run>.csv``  one row per event and per position sample (5 Hz)
* ``logs/summary.csv`` one row per run (appended when the run ends)

``RunRecorder`` is non-invasive: it compares the game state before and after
each update and infers who did what, so game.py and the robots need no
logging code. See LOGGING.md for the column dictionary.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid
import time

import pygame

from game import interaction_target

META_FIELDS = ["run_id", "participant", "condition", "robot", "layout",
               "recipe", "seed", "score"]
DATA_FIELDS = ["t", "kind", "actor", "action", "item", "station", "order_id",
               "x", "y", "anticipating", "info"]
FIELDS = META_FIELDS + DATA_FIELDS
SUMMARY_FIELDS = ["run_id", "participant", "condition", "robot", "layout",
                  "recipe", "seed", "completed", "duration", "score",
                  "served_human", "served_robot", "salads", "soups",
                  "expired", "first_serve_t", "robot_actions",
                  "robot_anticipating_actions",
                  "handoffs", "dwell_mean", "robot_arrival_mean", "robot_late_share",
                  "h_samples", "h_mae", "h_bias",
                  "human_distance_px", "human_still_s", "robot_wait_s"]
H_OUTCOME_WINDOW = 15.0       # seconds of estimates scored against one human handoff event
HANDOFF_REACH = 50            # same reach used to attribute robot interactions

POS_PERIOD = 1.0 / 5          # position samples at 5 Hz of game time
# Forecast-based contributions, including preparation before a predicted handoff.
# Horizon preparation can anticipate delivery timing for an already visible item.
ANTICIPATING_SOURCES = ("routine", "default", "movement", "transition", "horizon")


def default_log_directory():
    """Keep participant output beside the game, including frozen executables."""
    game_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    return game_dir / "logs"


class RunRecorder:
    def __init__(self, meta: dict, log_dir=None, enabled=True):
        self.base_meta = meta
        self.log_dir = os.fspath(default_log_directory() if log_dir is None else log_dir)
        self.enabled = enabled
        self._file = None
        self._prev = None
        self._robot = None

    # ------------------------------------------------------------------
    # Run lifecycle
    # ------------------------------------------------------------------
    def start(self, state) -> None:
        """Begin a new run. Call finish() on the old state first."""
        if not self.enabled:
            return
        self._robot = state.robot
        self.run_id = time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
        self.meta = dict(self.base_meta, run_id=self.run_id, score=0,
                         layout=state.layout.name)
        os.makedirs(self.log_dir, exist_ok=True)
        name = "_".join(str(self.meta[k]) for k in
                        ("participant", "robot", "layout", "condition"))
        self.path = os.path.join(self.log_dir, f"{name}_{self.run_id}.csv")
        self._file = open(self.path, "x", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, FIELDS)
        self._writer.writeheader()
        self._order_ids, self._order_refs = {}, []
        self._pos_acc = 0.0
        self._last_status = None
        self._last_meal_period = state.meal_period
        self._log(0.0, "meal_period", "system", item=state.meal_period)
        self._last_diagnostic_revision = 0
        self._last_transition_revision = 0
        self._last_preference_revision = 0
        self._last_horizon_time = -float("inf")
        self._last_horizon_key = None
        self._stats = {"served_human": 0, "served_robot": 0, "salads": 0,
                       "soups": 0, "expired": 0, "first_serve_t": "",
                       "robot_actions": 0, "robot_anticipating_actions": 0}
        self._pending_handoffs = {}      # station index -> (item, human put time)
        self._robot_near = {}            # shared station index -> time the robot arrived
        self._handoffs = []              # (dwell, robot arrival minus human put)
        self._h_window = []              # recent (t, remaining, target, source) estimates
        self._h_errors = []              # signed errors of estimates that named the right station
        self._last_pace_revision = 0
        self._human_distance = self._human_still = self._robot_wait = 0.0
        self._human_pos = None
        for order in state.orders:
            self._log(0.0, "order_new", "system", item=order.kind,
                      order_id=self._oid(order))
        self._log(0.0, "run_config", "system", info=json.dumps(self._run_config(state)))
        if hasattr(state.robot, "horizon"):
            self._log(0.0, "h_config", "system", info=json.dumps(state.robot.horizon.snapshot(state)))
        self._prev = None

    def _run_config(self, state) -> dict:
        """Parameters needed to reproduce and compare runs."""
        import config as C
        orders = [(o.kind, round(o.time_left, 1)) for o in state.orders]
        commit = ""  # Local experiments do not invoke Git.
        names = ("GAME_TIME", "PLAYER_SPEED", "ROBOT_SPEED", "CHOP_TIME", "POT_TIME",
                 "FIXED_H_SECONDS", "H_INTERACTION_SECONDS", "H_HANDOFF_LATENESS_WEIGHT",
                 "TRANSITION_MIN_SAMPLES", "TRANSITION_MIN_PROBABILITY", "HUMAN_IDLE_TIMEOUT",
                 "ORDER_TTL", "ORDER_INTERVAL", "MAX_ORDERS")
        horizon = getattr(state.robot, "horizon", None)
        return dict(commit=commit, parameters={n: getattr(C, n) for n in names},
                    fixed_h_used=horizon.fixed_seconds if horizon and horizon.mode == "fixed" else None,
                    initial_orders=orders,
                    schedule_hash=hashlib.md5(json.dumps(state._arrivals or orders).encode()).hexdigest()[:8])

    def finish(self, state, completed: bool) -> None:
        """Close the current run and append its summary row."""
        if self._file is None:
            return
        t = state.elapsed
        self._log(t, "game_end", "system", info="completed" if completed
                  else "aborted")
        self._file.close()
        self._file = None
        path = os.path.join(self.log_dir, "summary.csv")
        if os.path.exists(path):
            with open(path, newline="", encoding="utf-8") as f:
                header = next(csv.reader(f), [])
            if header != SUMMARY_FIELDS:        # keep rows of an older schema aligned
                os.replace(path, os.path.join(self.log_dir, f"summary_old_{self.run_id}.csv"))
        new = not os.path.exists(path)
        row = {k: self.meta.get(k, "") for k in SUMMARY_FIELDS}
        dwell = [d for d, _ in self._handoffs]
        arrival = [a for _, a in self._handoffs]
        errors = self._h_errors
        row.update(self._stats, completed=int(completed),
                   duration=round(t, 1), score=state.score,
                   handoffs=len(self._handoffs),
                   dwell_mean=round(sum(dwell) / len(dwell), 3) if dwell else "",
                   robot_arrival_mean=round(sum(arrival) / len(arrival), 3) if arrival else "",
                   robot_late_share=round(sum(a > 0 for a in arrival) / len(arrival), 3) if arrival else "",
                   h_samples=len(errors),
                   h_mae=round(sum(abs(e) for e in errors) / len(errors), 3) if errors else "",
                   h_bias=round(sum(errors) / len(errors), 3) if errors else "",
                   human_distance_px=round(self._human_distance, 1),
                   human_still_s=round(self._human_still, 2),
                   robot_wait_s=round(self._robot_wait, 2))
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, SUMMARY_FIELDS)
            if new:
                writer.writeheader()
            writer.writerow(row)

    # ------------------------------------------------------------------
    # Per-frame hooks
    # ------------------------------------------------------------------
    def before(self, state) -> None:
        """Snapshot the state just before game.update()."""
        if self._file is None:
            return
        robot = state.robot
        task = getattr(robot, "task", None)
        self._prev = {
            "carry": {"human": state.player.carrying,
                      "robot": robot.carrying if robot else None},
            "stations": [(s.held, s.ready) for s in state.stations],
            "orders": list(state.orders),
            "swapped": state.swapped,
            "task": (task.station, task.action) if task else (None, None),
        }

    def after(self, state, dt: float) -> None:
        """Compare with the snapshot and log what happened this frame."""
        if self._file is None or self._prev is None:
            return
        prev, t = self._prev, state.elapsed
        if state.meal_period != self._last_meal_period:
            self._last_meal_period = state.meal_period
            self._log(t, "meal_period", "system", item=state.meal_period)
        self.meta["score"] = state.score
        robot = state.robot

        # World events -------------------------------------------------
        for st, (held, ready) in zip(state.stations, prev["stations"]):
            if st.ready and not ready:
                self._log(t, "pot_ready", "system", station=self._name(state, st))
            if (st.kind == "board" and held and not held.startswith("chopped_")
                    and st.held == "chopped_" + held):
                robot_chops = (prev["task"][0] is st
                               and prev["task"][1] == "chop")
                chopper = "robot" if robot_chops else "human"
                self._log(t, "chop", chopper, item=st.held,
                          station=self._name(state, st))
        if state.swapped and not prev["swapped"]:
            self._log(t, "crates_swapped", "system")

        # Orders -------------------------------------------------------
        served_order = None
        # Compare orders by identity: their time_left changes every frame.
        for order in prev["orders"]:
            if not any(o is order for o in state.orders):
                if order.cancel_reason:
                    self._log(t, "order_cancelled", "system", item=order.kind,
                              order_id=self._oid(order), info=order.cancel_reason)
                elif order.time_left <= 0:
                    self._stats["expired"] += 1
                    self._log(t, "order_expired", "system", item=order.kind,
                              order_id=self._oid(order))
                else:
                    served_order = order
        for order in state.orders:
            if not any(o is order for o in prev["orders"]):
                self._log(order.scheduled_at if order.scheduled_at is not None else t,
                          "order_new", "system", item=order.kind,
                          order_id=self._oid(order))

        # Actor actions (carried item changed) ---------------------------
        actors = [("human", state.player)]
        if robot:
            actors.append(("robot", robot))
        for name, actor in actors:
            before_item, after_item = prev["carry"][name], actor.carrying
            if before_item == after_item:
                continue
            st = self._station_of(state, name, actor, prev)
            sname = self._name(state, st)
            if before_item is None:
                self._log(t, "take", name, after_item, sname)
                self._handoff_event(state, t, name, "take", after_item, st)
            elif after_item is None:
                if st is not None and st.kind == "serve" and served_order:
                    self._served(t, name, before_item, sname, served_order)
                    served_order = None
                elif st is not None and st.kind == "trash":
                    self._log(t, "trash", name, before_item, sname)
                else:
                    self._log(t, "put", name, before_item, sname)
                    self._handoff_event(state, t, name, "put", before_item, st)
            else:
                self._log(t, "combine", name, after_item, sname)

        self._track_activity(state, dt, robot)

        # Robot status text (what the robot says it is doing) ------------
        if robot:
            if hasattr(robot, "horizon"):
                data = robot.horizon.snapshot(state)
                data["scheduling"] = robot.scheduling
                key = (data["target"], data["action"], data["item"], data["source"],
                       data["remaining"] is None, robot.scheduling.get("choice"))
                if key != self._last_horizon_key or t - self._last_horizon_time >= 0.5:
                    self._last_horizon_key, self._last_horizon_time = key, t
                    self._log(t, "horizon", "robot", info=json.dumps(data))
                    if data["remaining"] is not None and data["target"] is not None:
                        self._h_window.append((t, data["remaining"], data["target"], data["source"]))
                pace = robot.horizon.pace
                if pace.revision != self._last_pace_revision:
                    self._last_pace_revision = pace.revision
                    self._log(t, "pace", "robot", info=json.dumps(pace.snapshot()))
            preferences = getattr(robot, "preferences", None)
            if preferences and preferences.revision != self._last_preference_revision:
                self._last_preference_revision = preferences.revision
                self._log(t, "collaboration_pattern", "robot", info=json.dumps(preferences.snapshot()))
            transitions = getattr(robot, "transition_model", None)
            if transitions and transitions.revision != self._last_transition_revision:
                self._last_transition_revision = transitions.revision
                self._log(t, "human_transition", "robot",
                          info=json.dumps(transitions.snapshot()))
            revision = getattr(robot, "diagnostic_revision", 0)
            if revision != self._last_diagnostic_revision:
                self._last_diagnostic_revision = revision
                self._log(t, "diagnostic", "robot", info=json.dumps(robot.diagnostic))
            # Drop countdown numbers ("Starting in 0.48s") so only real
            # changes of activity are logged.
            status = re.sub(r"\d+(\.\d+)?s", "", robot.status).strip()
            if status != self._last_status:
                self._last_status = status
                self._log(t, "status", "robot", item=status)

        # Positions at 5 Hz ---------------------------------------------
        self._pos_acc += dt
        while self._pos_acc >= POS_PERIOD:
            self._pos_acc -= POS_PERIOD
            for name, actor in actors:
                self._log(t, "pos", name, item=actor.carrying or "",
                          x=round(actor.pos.x, 1), y=round(actor.pos.y, 1),
                          kind="pos")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _track_activity(self, state, dt, robot) -> None:
        """Human walking/standing time and the robot's presence at each handoff counter."""
        pos = pygame.Vector2(state.player.pos)
        if self._human_pos is not None and dt > 0:
            moved = pos.distance_to(self._human_pos)
            self._human_distance += moved
            if moved / dt < 5:              # includes chopping in place
                self._human_still += dt
        self._human_pos = pos
        if robot is None:
            return
        if getattr(robot, "enabled", True) and hasattr(robot, "task") and robot.task is None:
            self._robot_wait += dt
        reach = robot.rect.inflate(HANDOFF_REACH, HANDOFF_REACH)
        for index, st in enumerate(state.stations):
            if st.owner != "shared":
                continue
            if reach.colliderect(st.rect):
                self._robot_near.setdefault(index, state.elapsed)
            else:
                self._robot_near.pop(index, None)

    def _handoff_event(self, state, t, actor, kind, item, station) -> None:
        """Pair human placements on a shared counter with the robot's pickup, and
        score the horizon estimates made before each human handoff action."""
        if station is None or station.owner != "shared":
            return
        index = state.stations.index(station)
        if actor == "human":
            if kind == "put":
                self._pending_handoffs[index] = (item, t)
            else:
                self._pending_handoffs.pop(index, None)
            self._h_outcome(state, t, kind, item, index)
        elif kind == "take" and index in self._pending_handoffs:
            put_item, put_t = self._pending_handoffs.pop(index)
            arrival = self._robot_near.get(index, t) - put_t
            dwell = t - put_t
            self._handoffs.append((dwell, arrival))
            self._log(t, "handoff", "robot", put_item, self._name(state, station),
                      info=json.dumps(dict(human_put_t=round(put_t, 3), robot_take_t=round(t, 3),
                                           dwell=round(dwell, 3),
                                           robot_arrival_minus_put=round(arrival, 3),
                                           robot_ready=int(arrival <= 0))))

    def _h_outcome(self, state, t, kind, item, index) -> None:
        window = [w for w in self._h_window if t - w[0] <= H_OUTCOME_WINDOW]
        self._h_window = []
        if not hasattr(state.robot, "horizon"):
            return
        # Estimate error = predicted remaining - actual remaining, only for estimates
        # that named the station the human actually used.
        errors = [remaining - (t - when) for when, remaining, target, _ in window if target == index]
        self._h_errors.extend(errors)
        self._log(t, "h_outcome", "system", item, self._name(state, state.stations[index]),
                  info=json.dumps(dict(
                      action=kind, estimates=len(window), right_station=len(errors),
                      mae=round(sum(map(abs, errors)) / len(errors), 3) if errors else None,
                      bias=round(sum(errors) / len(errors), 3) if errors else None,
                      last_source=window[-1][3] if window else None)))

    def _served(self, t, actor, item, station, order) -> None:
        self._stats["served_" + actor] += 1
        if item == "salad":
            self._stats["salads"] += 1
        elif item in ("soup", "tomato_soup", "potato_soup", "chicken_soup"):
            self._stats["soups"] += 1
        if self._stats["first_serve_t"] == "":
            self._stats["first_serve_t"] = round(t, 1)
        self._log(t, "serve", actor, item, station,
                  order_id=self._oid(order),
                  info=f"order_time_left={order.time_left:.1f}")

    def _oid(self, order) -> int:
        """Stable small integer id per order object."""
        if id(order) not in self._order_ids:
            self._order_refs.append(order)      # keep alive: ids stay unique
            self._order_ids[id(order)] = len(self._order_ids) + 1
        return self._order_ids[id(order)]

    @staticmethod
    def _name(state, station) -> str:
        if station is None:
            return ""
        return f"{station.label}#{state.stations.index(station)}"

    @staticmethod
    def _station_of(state, name, actor, prev):
        """Station an actor just used: robot task target, else nearest."""
        if name == "robot" and prev["task"][0] is not None:
            return prev["task"][0]
        if name == "human":
            return interaction_target(actor, state.stations)
        reach = actor.rect.inflate(50, 50)
        near = [s for s in state.stations if reach.colliderect(s.rect)]
        return min(near, key=lambda s: pygame.Vector2(actor.rect.center)
                   .distance_to(s.rect.center), default=None)

    def _log(self, t, action, actor, item="", station="", order_id="",
             info="", x="", y="", kind="event") -> None:
        anticipating = ""
        if actor == "robot":
            source = getattr(self._robot, "contribution_source", None)
            anticipating = int(source in ANTICIPATING_SOURCES)
            if action in ("take", "put", "combine", "serve"):
                self._stats["robot_actions"] += 1
                self._stats["robot_anticipating_actions"] += anticipating
        row = dict(self.meta, t=round(t, 3), kind=kind, actor=actor,
                   action=action, item=item, station=station,
                   order_id=order_id, x=x, y=y, anticipating=anticipating,
                   info=info)
        self._writer.writerow(row)
