"""Recipe metadata and robot-independent, seeded active-time order schedules."""
from dataclasses import dataclass
import random


@dataclass(frozen=True)
class Recipe:
    name: str
    category: str
    ingredients: tuple[str, str]
    cook_seconds: float = 0.0


RECIPES = {
    "cheese_sandwich": Recipe("Cheese Sandwich", "BREAKFAST", ("bread", "cheese")),
    "ham_sandwich": Recipe("Ham Sandwich", "BREAKFAST", ("bread", "ham")),
    "tomato_soup": Recipe("Tomato Soup", "LUNCH", ("tomato", "water"), 2.0),
    "chicken_soup": Recipe("Chicken Soup", "LUNCH", ("chicken", "water"), 3.0),
    "chicken_potatoes": Recipe("Chicken with Potatoes", "DINNER", ("chicken", "potato"), 4.0),
    "pasta_tomatoes": Recipe("Pasta with Tomatoes", "DINNER", ("pasta", "tomato"), 5.0),
}
PERIODS = ("BREAKFAST", "LUNCH", "DINNER")
CHOP_REQUIRED = {"tomato", "potato"}


def period_at(elapsed):
    return PERIODS[min(2, max(0, int((elapsed + 1e-9) // 60)))]


def meal_end_time(recipe):
    return 60.0 * (PERIODS.index(RECIPES[recipe].category) + 1)


def prepared(name):
    return "chopped_" + name if name in CHOP_REQUIRED else name


def sample_recipe(rng, elapsed):
    current = period_at(elapsed)
    category = rng.choices(PERIODS, [8 if p == current else 1 for p in PERIODS])[0]
    return rng.choice([key for key, recipe in RECIPES.items() if recipe.category == category])


def order_schedule(seed, duration=180, initial=3, interval=15, ttl=(65, 90), recipe=None):
    """Immutable arrivals; neither completions nor robot decisions consume this RNG."""
    rng = random.Random(seed)
    times = [0.0] * initial
    time = float(interval)
    while time < duration:
        times.append(time)
        time += interval
    return tuple((time, recipe or sample_recipe(rng, time), rng.uniform(*ttl)) for time in times)


def cooked_recipe(contents):
    return next((key for key, recipe in RECIPES.items() if recipe.cook_seconds
                 and set(contents) == {prepared(n) for n in recipe.ingredients}), None)
