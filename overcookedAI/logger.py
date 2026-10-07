"""Event/position logger shared by Project 1 (and reusable by Project 2).

One schema for everything. Every row carries the run metadata so a single
file can be concatenated across runs and loaded straight into pandas.
"""
from __future__ import annotations

import csv
import json
import os

FIELDS = [
    "condition", "participant", "seed", "score",   # run metadata
    "t", "kind",                                   # kind: "event" | "pos"
    "actor",                                       # "human" | "robot"
    "action", "item", "station", "order_id",       # event data
    "x", "y",                                      # positions (kind == "pos")
]


class Logger:
    def __init__(self, path: str, condition: str, participant: str = "sim",
                 seed: int = 0, fmt: str = "csv"):
        assert fmt in ("csv", "jsonl")
        self.meta = {"condition": condition, "participant": participant,
                     "seed": seed, "score": 0}
        self.fmt = fmt
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._f = open(path, "w", newline="", encoding="utf-8")
        self._w = csv.DictWriter(self._f, FIELDS) if fmt == "csv" else None
        if self._w:
            self._w.writeheader()

    def set_score(self, score: int) -> None:
        self.meta["score"] = score

    def _write(self, row: dict) -> None:
        full = {k: "" for k in FIELDS}
        full.update(self.meta)
        full.update(row)
        if self._w:
            self._w.writerow(full)
        else:
            self._f.write(json.dumps(full) + "\n")

    def event(self, t: float, actor: str, action: str, item: str = "",
              station: str = "", order_id: int | str = "") -> None:
        self._write({"t": round(t, 3), "kind": "event", "actor": actor,
                     "action": action, "item": item, "station": station,
                     "order_id": order_id})

    def position(self, t: float, actor: str, x: float, y: float) -> None:
        self._write({"t": round(t, 3), "kind": "pos", "actor": actor,
                     "x": round(x, 2), "y": round(y, 2)})

    def close(self) -> None:
        self._f.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
