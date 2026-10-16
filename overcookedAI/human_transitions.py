"""Online first-order transitions between observed, completed human actions.

Both agents learn the same model. Only the anticipatory policy uses forecasts.
Counts are cumulative per recipe; no forgetting, timing horizon or hidden plans.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class ActionSymbol:
    action: str
    item: str
    station_kind: str

    @property
    def key(self):
        return f"{self.action}:{self.item}:{self.station_kind}"

    def as_dict(self):
        return dict(action=self.action, item=self.item, station_kind=self.station_kind)

    @property
    def description(self):
        if self.action == "chop":
            return "finish chopping " + self.item.removeprefix("chopped_")
        return self.action + " " + self.item


@dataclass(frozen=True)
class HumanActionEvent:
    symbol: ActionSymbol
    recipe: str | None
    order: object | None
    time: float
    station_index: int


@dataclass(frozen=True)
class TransitionPrediction:
    recipe: str
    source: ActionSymbol
    target: ActionSymbol
    probability: float
    samples: int

    @property
    def description(self):
        return (f"Next: {self.target.description} at {self.target.station_kind} "
                f"({self.probability:.0%}, n={self.samples})")


class HumanTransitionModel:
    def __init__(self):
        self.counts = {}
        self.last_target = {}
        self.previous = None
        self.prediction = None
        self.revision = 0
        self.cursor = 0
        self.observations = 0
        self.evaluated_predictions = 0
        self.correct_predictions = 0

    @property
    def transition_count(self):
        return sum(sum(row.values()) for row in self.counts.values())

    def distribution(self, recipe, source):
        row = self.counts.get((recipe, source), {})
        total = sum(row.values())
        return {target: count / total for target, count in row.items()} if total else {}

    def predict(self, recipe, source):
        key = (recipe, source)
        row = self.counts.get(key)
        if not row:
            return None
        target = max(row, key=lambda symbol: (row[symbol], symbol == self.last_target[key]))
        total = sum(row.values())
        return TransitionPrediction(recipe, source, target, row[target] / total, total)

    def observe(self, event):
        self.observations += 1
        previous = self.previous
        if (previous is not None and event.order is not None
                and previous.order is event.order and event.recipe is not None
                and previous.recipe == event.recipe):
            # Score the forecast made before seeing this outcome, then learn it.
            if self.prediction is not None:
                self.evaluated_predictions += 1
                self.correct_predictions += int(self.prediction.target == event.symbol)
            key = (event.recipe, previous.symbol)
            self.counts.setdefault(key, Counter())[event.symbol] += 1
            self.last_target[key] = event.symbol
        self.previous = event if event.recipe and event.symbol.action != "serve" else None
        self.prediction = (self.predict(event.recipe, event.symbol) if self.previous else None)
        self.revision += 1

    def update(self, state):
        for event in state.human_actions[self.cursor:]:
            self.observe(event)
        self.cursor = len(state.human_actions)
        # Expiry, serving and reprioritisation invalidate the current context,
        # but retain all learned rows for later orders of the same recipe.
        if self.previous is not None and self.previous.order is not state.priority_order:
            self.previous = None
            self.prediction = None
            self.revision += 1
        return self.prediction

    def snapshot(self):
        prediction = self.prediction
        return {
            "observations": self.observations,
            "transitions": self.transition_count,
            "recipe": self.previous.recipe if self.previous else None,
            "source": self.previous.symbol.as_dict() if self.previous else None,
            "next_action": prediction.target.as_dict() if prediction else None,
            "probability": prediction.probability if prediction else None,
            "samples": prediction.samples if prediction else 0,
            "distribution": ({symbol.key: probability for symbol, probability in
                              self.distribution(prediction.recipe, prediction.source).items()}
                             if prediction else {}),
            "evaluated_predictions": self.evaluated_predictions,
            "correct_predictions": self.correct_predictions,
        }
