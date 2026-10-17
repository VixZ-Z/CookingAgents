"""Engine-only scheduling and an allowlisted robot observation boundary.

No observation contains an engine, callback, schedule, seed or RNG reference.
Only currently visible orders and mutable gameplay objects are shared.
"""
from dataclasses import dataclass
import random

import config as C
from recipes import CATEGORIES, MEAL_RECIPES, meal_period


@dataclass(frozen=True)
class ScheduledOrder:
    order_id: int
    kind: str
    scheduled_at: float
    ttl: float


def sample_recipe(rng, elapsed):
    period = meal_period(elapsed)
    category = rng.choices(CATEGORIES, weights=[0.8 if c == period else 0.1 for c in CATEGORIES])[0]
    return rng.choice([kind for kind, recipe in MEAL_RECIPES.items() if recipe.category == category])


def build_schedule(seed, recipe=None):
    """Dedicated local RNG, independent of queue capacity and robot actions."""
    rng = random.Random(seed)
    times = [0.0] * C.INITIAL_ORDERS
    times += [float(t) for t in range(C.ORDER_INTERVAL, C.GAME_TIME, C.ORDER_INTERVAL)]
    return tuple(ScheduledOrder(index + 1, recipe or sample_recipe(rng, t), t,
                                rng.uniform(*C.ORDER_TTL)) for index, t in enumerate(times))


@dataclass
class Score:
    value: int = 0


@dataclass(slots=True)
class RobotObservation:
    layout: object
    stations: list
    walls: list
    player: object
    robot: object
    orders: list
    _score: Score
    game_time: float
    human_activity_revision: int
    experiment: bool = True

    @property
    def score(self):
        return self._score.value

    @score.setter
    def score(self, value):
        self._score.value = value

    @property
    def elapsed(self):
        return C.GAME_TIME - self.game_time

    @property
    def priority_order(self):
        return min((o for o in self.orders if o.time_left > 0), key=lambda o: o.time_left, default=None)

    @property
    def meal_period(self):
        return meal_period(self.elapsed)
