"""Six experiment recipes; legacy salad/soup rules remain in game.py."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Recipe:
    name: str
    category: str
    ingredients: tuple[str, str]
    cooked: bool


MEAL_RECIPES = {
    "cheese_sandwich": Recipe("Cheese Sandwich", "breakfast", ("bread", "cheese"), False),
    "ham_sandwich": Recipe("Ham Sandwich", "breakfast", ("bread", "ham"), False),
    "tomato_soup": Recipe("Tomato Soup", "lunch", ("tomato", "water"), True),
    "potato_soup": Recipe("Potato Soup", "lunch", ("potato", "water"), True),
    "chicken_potatoes": Recipe("Chicken with Potatoes", "dinner", ("chicken", "potato"), True),
    "meat_vegetables": Recipe("Meat with Vegetables", "dinner", ("meat", "vegetables"), True),
}
MEAL_KINDS = tuple(MEAL_RECIPES)
MEAL_INGREDIENTS = tuple(dict.fromkeys(i for r in MEAL_RECIPES.values() for i in r.ingredients))
CATEGORIES = ("breakfast", "lunch", "dinner")


def meal_period(elapsed):
    return CATEGORIES[min(2, max(0, int(elapsed // 60)))]


def ingredient(item):
    """Chopping is optional for the new simple recipes."""
    if item and item.startswith("chopped_"):
        item = item[8:]
    return item if item in MEAL_INGREDIENTS else None


def cooked_recipe(contents):
    names = [ingredient(i) for i in contents]
    return next((kind for kind, recipe in MEAL_RECIPES.items()
                 if recipe.cooked and len(names) == 2 and set(names) == set(recipe.ingredients)), None)


def can_add_to_cooker(item, contents):
    names = [ingredient(i) for i in contents]
    name = ingredient(item)
    return (name is not None and len(contents) < 2 and name not in names
            and any(recipe.cooked and set(names + [name]) <= set(recipe.ingredients)
                    for recipe in MEAL_RECIPES.values()))


def combination(a, b):
    for kind, recipe in MEAL_RECIPES.items():
        if not recipe.cooked and {ingredient(a), ingredient(b)} == set(recipe.ingredients):
            return "assembled_" + kind
        if {a, b} == {"plate", "assembled_" + kind}:
            return kind
    return None
