"""Shared recipe execution with a separate observable-intent anticipation policy.

Only the anticipatory policy forecasts human intentions. Reactive
decisions use live orders and delivered supply. Neither reads order scheduling.
"""
import pygame

import config as C
from game import chop_name, COMBOS
from menu import RECIPES, prepared
from navigation import approach_point
from robot_tasks import Task, execute_task


def approach(station, state):
    if station.owner == "shared":
        return pygame.Vector2(station.rect.right + 26, station.rect.centery)
    return approach_point(station)


def plan(robot, state, anticipatory=False):
    bounds, obstacles = robot.navigator._geometry(robot, state)
    center = pygame.Vector2(robot.rect.center)
    cache = {}

    def choose(stations):
        for st in sorted(stations, key=lambda s: center.distance_to(approach(s, state))):
            if st.owner not in (None, "robot", "shared"):
                continue
            if st.kind.startswith("crate_"):
                continue
            if (anticipatory and state.layout.name != "divided"
                    and pygame.Vector2(state.player.rect.center).distance_to(approach(st, state)) < 65):
                continue  # Leave the human's current workstation accessible.
            key = id(st)
            if key not in cache:
                goal = approach(st, state)
                cache[key] = (robot.navigator._clear(center, goal, bounds, obstacles)
                              or bool(robot.navigator._route(robot, goal, state, None)))
            if cache[key]:
                return st
        return None

    def task(stations, action, item, recipe, label):
        st = choose(stations)
        return Task(st, action, item, label, recipe) if st else None

    surfaces = [s for s in state.stations if s.kind in ("counter", "board")
                and s.owner in (None, "robot", "shared")]
    pots = [s for s in state.stations if s.kind == "pot" and s.owner in (None, "robot")]
    orders = sorted((o for o in state.orders if o.kind in RECIPES and o.time_left > 0),
                    key=lambda o: o.time_left)
    human_name = None
    human_finished = ({s.held for s in state.stations if s.owner == "human" and s.held in RECIPES}
                      if anticipatory else set())
    human_finished.add(state.player.carrying if anticipatory else None)
    if anticipatory:
        from anticipatory_robot.model import ingredient_name
        carried_name = ingredient_name(state.player.carrying)
        human_name = carried_name or getattr(robot.intent, "ingredient", None)
        matching = [o for o in orders if human_name in RECIPES[o.kind].ingredients
                    or o.kind in human_finished]
        if matching:
            orders = matching + [o for o in orders if o not in matching]
        robot.priority_order = orders[0] if orders else None
        robot.human_ingredient = human_name
        robot.contribution_source = None
        if carried_name:
            robot.contribution_source = "observed"
        elif human_name:
            robot.contribution_source = "transition" if robot.intent.source == "transition" else "movement"

    item = robot.carrying
    if item in C.ORDER_KINDS and any(o.kind == item for o in state.orders):
        return task([s for s in state.stations if s.kind == "serve"], "serve", item, item, "Serving " + item)
    if item in RECIPES:
        return task([s for s in state.stations if s.kind == "trash"], "trash", item, None,
                    "Clearing a dish whose order expired")

    def store(recipe, handoff=False, preserve=False):
        destinations = [s for s in surfaces if s.kind == "counter" and s.held is None]
        if handoff:
            shared = [s for s in destinations if s.owner == "shared"]
            if shared:
                destinations = shared
        else:
            own = [s for s in destinations if s.owner != "shared"]
            destinations = own or destinations
        result = task(destinations, "put", item, recipe, "Staging " + str(item))
        if result or destinations:
            return result
        if preserve:
            return None
        return task([s for s in state.stations if s.kind == "trash"], "trash", item, recipe,
                    "Clearing unused supply because storage is full")

    # Actual completed work overrides any ingredient forecast, including an older
    # more urgent order. Free our hands before collecting a delivered dish.
    completed = [s for s in surfaces if any(s.held == o.kind for o in orders)]
    if completed:
        if item:
            return store(None)
        result = task(completed, "take", None, None, "Receiving completed dish")
        if result:
            result.item = result.recipe = result.station.held
            return result
    if anticipatory and item and any(o.kind in human_finished for o in orders):
        return store(None)

    # A fully supplied selected recipe can reclaim a pot occupied by an
    # incomplete older batch. A forecast alone must not displace useful work.
    focus = RECIPES[orders[0].kind] if anticipatory and orders else None
    focus_items = set(map(prepared, focus.ingredients)) if focus else set()
    focus_inventory = [s.held for s in surfaces] + [item]
    focus_inventory += [ingredient for p in pots if set(p.contents) <= focus_items
                        for ingredient in p.contents]
    focus_supplied = focus is not None and all(
        name in focus_inventory or prepared(name) in focus_inventory
        for name in focus.ingredients)
    if (focus_supplied and item and item != "plate"
            and item not in focus_items and item not in focus.ingredients):
        # Preserve recovered supply instead of immediately putting it back into
        # the pot for another order, or discarding it when storage is full.
        return store(orders[0].kind, preserve=True)

    valid_batches = [set(map(prepared, RECIPES[o.kind].ingredients)) for o in orders
                     if RECIPES[o.kind].cook_seconds]
    # Keep batches compatible with any active order, regardless of the
    # current human-intent prediction; this prevents recovery/cooking loops.
    stale = [p for p in pots if p.contents and not any(set(p.contents) <= batch for batch in valid_batches)]
    if focus_supplied and focus.cook_seconds and not choose(
            [p for p in pots if set(p.contents) <= focus_items]):
        storage = choose([s for s in surfaces if s.kind == "counter" and s.held is None])
        if storage:
            stale += [p for p in pots if p not in stale and len(p.contents) == 1
                      and not p.ready and not set(p.contents) <= focus_items]
    # Use another compatible pot before disturbing an unrelated batch.
    if choose([p for p in pots if p not in stale
               and any(set(p.contents) <= batch for batch in valid_batches)]):
        stale = []
    if stale and item is None:
        if any(p.ready for p in stale):
            return (task([s for s in surfaces if s.held == "plate"], "take", "plate", None,
                         "Collecting plate to clear expired batch") or
                    task([s for s in state.stations if s.kind == "plates"], "fetch", "plate", None,
                         "Fetching plate to clear expired batch"))
        return task(stale, "take_pot", None, None, "Recovering unused ingredient from pot")
    if stale and item == "plate":
        return task([p for p in stale if p.ready], "scoop", item, None, "Clearing a finished batch")

    # For non-cooked recipes, anticipate collaboration as soon as the human
    # stages *either* ingredient. The adaptive policy may instead expect the
    # human to assemble a complete dish; never interrupt that learned workflow.
    # This branch is anticipatory only: reactive behavior remains unchanged.
    if anticipatory:
        for order in orders:
            key, recipe = order.kind, RECIPES[order.kind]
            if recipe.cook_seconds or len(recipe.ingredients) != 2:
                continue
            names = tuple(recipe.ingredients)
            preferences = getattr(robot, "preferences", None)
            complete_expected = (preferences is not None and
                                 preferences.preferred(key) == "complete")
            if complete_expected or key in human_finished:
                continue
            shared = [s for s in surfaces if s.kind == "counter" and s.owner == "shared"]
            if item in names:
                # Combine immediately when the other ingredient arrives,
                # regardless of the order in which ingredients were supplied.
                matching = [s for s in surfaces if s.held in names and s.held != item and
                            COMBOS.get(frozenset((item, s.held))) == key]
                result = task(matching, "combine", None, key, "Assembling " + recipe.name)
                if result:
                    result.item = result.station.held
                    return result
                # Keep the first ingredient in hand, close to the handoff, so
                # that we can combine it without another collection trip.
                waiting = [s for s in shared if s.held is None]
                if not waiting:
                    waiting = shared
                other = next(n for n in names if n != item)
                result = task(waiting, "wait_for_handoff", other, key,
                              "Anticipating " + recipe.name + ": waiting for " + other)
                if result:
                    return result
            elif item is None:
                # Pick up whichever ingredient appears first (bread OR cheese,
                # bread OR ham); do not enforce the recipe's written order.
                available = [s for s in shared if s.held in names]
                result = task(available, "take", None, key,
                              "Anticipating " + recipe.name + ": collecting first ingredient")
                if result:
                    result.item = result.station.held
                    return result

    for order in orders:
        key, recipe = order.kind, RECIPES[order.kind]
        names = recipe.ingredients
        # Once Adaptive has learned that the human delivers the completed
        # sandwich, do not grab its loose ingredients from the counters.
        # The completed dish is handled above, before this order loop.
        preferences = getattr(robot, "preferences", None) if anticipatory else None
        complete_expected = (preferences is not None and
                             preferences.preferred(key) == "complete")
        ingredients = set(map(prepared, names))
        compatible = [p for p in pots if set(p.contents) <= ingredients]
        full = [p for p in compatible if len(p.contents) == 2]
        inventory = [s.held for s in surfaces]
        inventory += [x for p in compatible for x in p.contents] + [item]
        supplied = all(n in inventory or prepared(n) in inventory for n in names)
        if item:
            if item in names and chop_name(item):
                return task([s for s in surfaces if s.kind == "board" and not s.held],
                            "put", item, key, "Preparing " + item) or store(key)
            if item == "plate" and full:
                return task(full, "scoop", item, key, "Plating " + recipe.name)
            if item in ingredients:
                predicted_complement = (anticipatory and human_name in names
                                        and item != prepared(human_name))
                if recipe.cook_seconds and (supplied or predicted_complement):
                    targets = [p for p in compatible if not p.ready and len(p.contents) < 2
                               and item not in p.contents]
                    partial = [p for p in targets if p.contents]
                    result = task(partial or targets, "put_pot", item, key, "Cooking " + recipe.name)
                    if result:
                        return result
                if not recipe.cook_seconds:
                    result = task([s for s in surfaces if s.held and
                                   COMBOS.get(frozenset((item, s.held))) == key],
                                  "combine", None, key, "Assembling " + recipe.name)
                    if result:
                        result.item = result.station.held
                        return result
                # Reuse or deliver a speculative complement; never discard on a mere prediction change.
                return store(key, anticipatory and not supplied)
            continue

        finished = task([s for s in surfaces if s.held == key], "take", key, key, "Collecting " + recipe.name)
        if finished:
            return finished
        if full:
            plate = task([s for s in surfaces if s.held == "plate"], "take", "plate", key, "Collecting plate")
            return plate or task([s for s in state.stations if s.kind == "plates"],
                                 "fetch", "plate", key, "Fetching plate")
        if recipe.cook_seconds:
            partial = [p for p in compatible if len(p.contents) == 1 and not p.ready]
            # Keep a stable destination while walking; nearest-pot selection
            # would swap the donor and recipient halfway between the pots.
            destination = next((p for p in partial if choose([p])), None)
            if destination:
                # If both ingredients were placed in separate pots, bring the
                # missing one to a started batch instead of waiting forever.
                donors = [p for p in partial if p is not destination
                          and p.contents[0] not in destination.contents]
                result = task(donors, "take_pot", None, key, "Consolidating " + recipe.name)
                if result:
                    return result
        for name in names:
            ready = prepared(name)
            if any(ready in p.contents for p in compatible):
                continue
            raw_board = task([s for s in surfaces if s.kind == "board" and s.held == name
                              and chop_name(name)], "chop", name, key, "Chopping " + name)
            if raw_board:
                return raw_board
            for candidate in dict.fromkeys((ready, name)):
                sources = [s for s in surfaces if s.held == candidate]
                if not recipe.cook_seconds:
                    # A learned 'complete' means the human is assembling the
                    # sandwich. Do not undo that by collecting their bread.
                    if complete_expected:
                        continue
                    # For individual handoffs, keeping one ingredient in hand
                    # is useful only when waiting at a shared counter (handled
                    # in the anticipatory branch above), or when a compatible
                    # second ingredient exists to combine with. Prevent
                    # repeated take/put of a lone ingredient on Stage#15.
                    complement_available = any(
                        other.held is not None and other is not source and
                        COMBOS.get(frozenset((candidate, other.held))) == key
                        for source in sources for other in surfaces
                    )
                    if not complement_available:
                        continue
                # A staged cooking ingredient should not be collected until it
                # can be used. Otherwise the robot repeatedly takes it from a
                # counter and puts it back when the complementary ingredient is
                # absent (Collecting <-> Staging loop).
                if recipe.cook_seconds and not supplied:
                    predicted_complement = (anticipatory and human_name in names
                                            and candidate != prepared(human_name))
                    sources = [s for s in sources if s.kind == "board" or predicted_complement]
                    if not sources:
                        continue
                if recipe.cook_seconds:
                    targets = [p for p in compatible if not p.ready and len(p.contents) < 2
                               and ready not in p.contents]
                    if not choose(targets):
                        continue  # Do not collect and restage an unusable cooking ingredient.
                if candidate != ready and not choose([s for s in surfaces if s.kind == "board" and not s.held]):
                    continue
                result = task(sources, "take", candidate, key, "Collecting " + candidate)
                if result:
                    return result
        if anticipatory and (human_name in names or key in human_finished or
                             (complete_expected and any(
                                 s.owner == "shared" and s.held in names for s in surfaces))):
            preferences = getattr(robot, "preferences", None)
            style = preferences.preferred(key) if preferences else "individual"
            complete = key in human_finished or style == "complete"
            # Prepare equipment before the predicted delivery, never ingredient supply.
            if not complete and recipe.cook_seconds and "plate" not in inventory and state.player.carrying != "plate":
                if choose([s for s in surfaces if s.kind == "counter" and s.held is None]):
                    result = task([s for s in state.stations if s.kind == "plates"],
                                  "fetch", "plate", key, "Anticipating " + recipe.name + ": stage a plate")
                    if result:
                        return result
            # A bread/ingredient already on the shared counter does not mean
            # the human has finished: they can still combine it into the dish.
            # Adaptive can therefore wait at that *occupied* handoff counter.
            shared_counters = [s for s in surfaces if s.owner == "shared" and s.kind == "counter"]
            handoffs = [s for s in shared_counters if s.held is None]
            if complete and preferences is not None:
                # Prefer direct evidence of where the current dish is being
                # assembled; fall back to the last completed handoff location.
                ingredients_on_counter = [s for s in shared_counters
                                          if s.held in names or s.held in tuple(map(prepared, names))]
                if len(ingredients_on_counter) == 1:
                    handoffs = ingredients_on_counter
                else:
                    last = preferences.complete_handoff_stations.get(key)
                    if last is not None and 0 <= last < len(state.stations):
                        station = state.stations[last]
                        if station in shared_counters and station.held in (None, *names, *tuple(map(prepared, names))):
                            handoffs = [station]
            if len(handoffs) != 1:
                goal = getattr(robot.intent, "goal", None)
                if goal is not None and any(goal is s for s in handoffs):
                    handoffs = [goal]
                else:
                    # Predict the closest available delivery point to the human.
                    handoffs.sort(key=lambda s: pygame.Vector2(state.player.rect.center).distance_to(s.rect.center))
                    handoffs = handoffs[:1]
            expected = key if complete else (prepared(human_name) if style == "partial" else human_name)
            result = task(handoffs, "wait_for_handoff", expected, key,
                          "Anticipating " + recipe.name + ": ready for " + str(expected))
            if result:
                return result
    if item:
        if item == "plate":
            stale = [p for p in pots if p.ready]
            if stale:
                return task(stale, "scoop", item, None, "Clearing a finished batch")
        return store(orders[0].kind if orders else None)
    # Free a board left by a changed/expired intention without generating more supply.
    blocked = [s for s in surfaces if s.kind == "board" and s.held]
    if choose([s for s in surfaces if s.kind == "counter" and s.held is None]):
        result = task(blocked, "take", None, None, "Clearing unused board")
        if result:
            result.item = result.station.held
        return result
    return None


def update_anticipatory(robot, state, dt):
    robot._menu_mode = True
    robot.intent = robot.model.observe(state, dt)
    robot._update_activity(dt, state)
    if not robot.enabled:
        robot.status = "Disabled by user"
        return
    if state.elapsed + dt < C.ROBOT_START_DELAY:
        return
    previous = robot.task
    robot.task = plan(robot, state, anticipatory=True)
    task = robot.task
    robot.status = task.label if task else "Waiting for observable human work or delivered ingredients"
    if robot.navigator.make_space(robot, state, dt):
        robot.status = "Making room for you"
        return
    if task and robot.navigator.move_to(robot, approach(task.station, state), state, dt):
        if robot.rect.inflate(50, 50).colliderect(task.station.rect):
            result = execute_task(robot, task, state, dt)
            if result == "waiting" and task.action == "scoop":
                robot.status = "Waiting for cooking"
    robot.diagnostic_revision += int(previous != task)
    robot.diagnostic = {"decision": robot.status, "navigation": robot.navigator.reason,
                        "intentional_wait": task is None, "events": ["task_changed"] if previous != task else []}
