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
import json
import os
import re
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
                  "robot_anticipating_actions"]

POS_PERIOD = 1.0 / 5          # position samples at 5 Hz of game time
# Robot knowledge sources (AnticipatoryRobot.contribution_source) that mean
# "acting before the human has shown the choice": the robot is anticipating.
ANTICIPATING_SOURCES = ("routine", "default", "movement")


class RunRecorder:
    def __init__(self, meta: dict, log_dir: str = "logs", enabled=True):
        self.base_meta = meta
        self.log_dir = log_dir
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
        self.run_id = time.strftime("%Y%m%d_%H%M%S")
        self.meta = dict(self.base_meta, run_id=self.run_id, score=0,
                         layout=state.layout.name)
        os.makedirs(self.log_dir, exist_ok=True)
        name = "_".join(str(self.meta[k]) for k in
                        ("participant", "robot", "layout", "condition"))
        self.path = os.path.join(self.log_dir, f"{name}_{self.run_id}.csv")
        self._file = open(self.path, "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, FIELDS)
        self._writer.writeheader()
        self._order_ids, self._order_refs = {}, []
        self._pos_acc = 0.0
        self._last_status = None
        self._last_diagnostic_revision = 0
        self._stats = {"served_human": 0, "served_robot": 0, "salads": 0,
                       "soups": 0, "expired": 0, "first_serve_t": "",
                       "robot_actions": 0, "robot_anticipating_actions": 0}
        for order in state.orders:
            self._log(0.0, "order_new", "system", item=order.kind,
                      order_id=self._oid(order))
        self._prev = None

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
        new = not os.path.exists(path)
        row = {k: self.meta.get(k, "") for k in SUMMARY_FIELDS}
        row.update(self._stats, completed=int(completed),
                   duration=round(t, 1), score=state.score)
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
                if order.time_left <= 0:
                    self._stats["expired"] += 1
                    self._log(t, "order_expired", "system", item=order.kind,
                              order_id=self._oid(order))
                else:
                    served_order = order
        for order in state.orders:
            if not any(o is order for o in prev["orders"]):
                self._log(t, "order_new", "system", item=order.kind,
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
            elif after_item is None:
                if st is not None and st.kind == "serve" and served_order:
                    self._served(t, name, before_item, sname, served_order)
                    served_order = None
                elif st is not None and st.kind == "trash":
                    self._log(t, "trash", name, before_item, sname)
                else:
                    self._log(t, "put", name, before_item, sname)
            else:
                self._log(t, "combine", name, after_item, sname)

        # Robot status text (what the robot says it is doing) ------------
        if robot:
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
    def _served(self, t, actor, item, station, order) -> None:
        self._stats["served_" + actor] += 1
        self._stats["salads" if item == "salad" else "soups"] += 1
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
