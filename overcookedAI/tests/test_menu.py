"""Six-dish rules, seeded exposure, and observable divided-kitchen collaboration."""
from collections import Counter
import csv
import inspect
import random
import tempfile
import unittest
from unittest.mock import patch

import pygame

import config as C
from game import GameState, Order, interact, handle_counter_combinations
from menu import RECIPES, prepared, sample_recipe, period_at, order_schedule
from reactive_robot import ReactiveRobot
from anticipatory_robot import AnticipatoryRobot
from anticipatory_robot.adaptive import AdaptiveAnticipatoryRobot
from logger import RunRecorder
import menu_planner
from navigation import Navigator, approach_point


class MenuTests(unittest.TestCase):
    def test_distribution(self):
        for time, category in ((0, "BREAKFAST"), (60, "LUNCH"), (120, "DINNER")):
            rng = random.Random(812)
            counts = Counter(sample_recipe(rng, time) for _ in range(100000))
            self.assertEqual(set(counts), set(RECIPES))
            for key, recipe in RECIPES.items():
                expected = .4 if recipe.category == category else .05
                self.assertAlmostEqual(counts[key] / 100000, expected, delta=.006)

    def test_boundaries_and_backlog(self):
        state = GameState(seed=3, layout="divided")
        self.assertEqual(period_at(59.999), "BREAKFAST")
        self.assertEqual(period_at(60), "LUNCH")
        self.assertEqual(period_at(119.999), "LUNCH")
        self.assertEqual(period_at(120), "DINNER")
        original = state.priority_order
        state.update(60, (0, 0), False)
        self.assertEqual(state.meal_period, "LUNCH")
        self.assertTrue(any(o is original for o in state.orders))
        self.assertIsNone(original.cancel_reason)
        self.assertTrue(all(o is original or RECIPES[o.kind].category != "BREAKFAST"
                            for o in state.orders))
        state.update(60, (0, 0), False)
        self.assertEqual(state.meal_period, "DINNER")
        state.update(1000, (0, 0), False)
        self.assertEqual(state.elapsed, 180)

    def test_seed_independent_of_robot_and_backlog(self):
        states = [GameState(cls, seed=44, layout="divided")
                  for cls in (ReactiveRobot, AnticipatoryRobot)]
        self.assertEqual(states[0]._arrivals, states[1]._arrivals)
        for state in states:
            state.robot.enabled = False
        for _ in range(11):
            states[0].orders.clear()
            for state in states:
                state.update(15, (0, 0), False)
            # An arrival from a finished meal is suppressed for both robots,
            # even when only one of them has a backlog.
            released = [[(o.kind, o.time_left) for o in state.orders
                         if o.scheduled_at == state.elapsed] for state in states]
            self.assertEqual(released[0], released[1])
            self.assertEqual(states[0]._arrival_cursor, states[1]._arrival_cursor)
        self.assertEqual(order_schedule(44), order_schedule(44))
        self.assertNotEqual(order_schedule(44), order_schedule(45))

    def test_all_recipes_through_game_rules(self):
        for key, recipe in RECIPES.items():
            with self.subTest(recipe=key):
                state = GameState(seed=0, layout="divided", recipe=key)
                state.orders = [Order(key, 150)]
                actor = state.player
                if recipe.cook_seconds:
                    pot = next(s for s in state.stations if s.kind == "pot")
                    for name in recipe.ingredients:
                        actor.carrying = prepared(name)
                        interact(actor, pot, state)
                        self.assertIsNone(actor.carrying)
                    state.update(recipe.cook_seconds - .01, (0, 0), False)
                    self.assertFalse(pot.ready)
                    state.update(.02, (0, 0), False)
                    self.assertTrue(pot.ready)
                    actor.carrying = "plate"
                    interact(actor, pot, state)
                else:
                    counter = next(s for s in state.stations if s.kind == "counter")
                    actor.carrying, counter.held = recipe.ingredients
                    self.assertTrue(handle_counter_combinations(actor, counter, state))
                self.assertEqual(actor.carrying, key)
                interact(actor, next(s for s in state.stations if s.kind == "serve"), state)
                self.assertGreater(state.score, 0)

    def test_both_robots_complete_all_delivered_recipes(self):
        for layout in ("divided", "shared"):
            self.complete_delivered_recipes(layout)

    def complete_delivered_recipes(self, layout):
        for cls in (ReactiveRobot, AnticipatoryRobot, AdaptiveAnticipatoryRobot):
            for key, recipe in RECIPES.items():
                with self.subTest(robot=cls.__name__, recipe=key):
                    state = GameState(cls, seed=0, layout=layout, recipe=key)
                    state.orders = [Order(key, 150)]
                    handoffs = [s for s in state.stations if s.owner == "shared"]
                    for counter, item in zip(handoffs, recipe.ingredients):
                        counter.held = item
                    for _ in range(1800):
                        state.update(1 / 30, (0, 0), False)
                        if layout == "divided":
                            self.assertGreaterEqual(state.robot.rect.left, 582)
                        self.assertFalse(any(state.robot.rect.colliderect(s.rect) for s in state.stations))
                        if state.score:
                            break
                    self.assertGreater(state.score, 0, (state.robot.status, state.robot.carrying,
                        [(s.kind, s.held, s.contents) for s in state.stations if s.held or s.contents]))

    def test_human_collects_and_hands_off_every_recipe(self):
        for layout in ("divided", "shared"):
            for cls in (ReactiveRobot, AnticipatoryRobot, AdaptiveAnticipatoryRobot):
                for key, recipe in RECIPES.items():
                    with self.subTest(layout=layout, robot=cls.__name__, recipe=key):
                        state = GameState(cls, seed=42, layout=layout, recipe=key)
                        nav = Navigator()
                        def use(station, destination):
                            for _ in range(600):
                                arrived = nav.move_to(state.player, destination, state, 1 / 30)
                                state.update(1 / 30, (0, 0), False)
                                if arrived:
                                    break
                            self.assertTrue(arrived, station.label)
                            state.player_interact()
                        handoffs = [s for s in state.stations if s.owner == "shared"]
                        for name, counter in zip(recipe.ingredients, handoffs):
                            crate = next(s for s in state.stations if s.kind == "crate_" + name)
                            use(crate, approach_point(crate))
                            self.assertEqual(state.player.carrying, name)
                            use(counter, (counter.rect.left - state.player.rect.width / 2 - 2,
                                          counter.rect.centery))
                            self.assertIsNone(state.player.carrying)
                        for _ in range(1800):
                            state.update(1 / 30, (0, 0), False)
                            if state.score:
                                break
                        self.assertGreater(state.score, 0, state.robot.status)

    def test_anticipates_equipment_and_handoff_but_reactive_does_not(self):
        for layout in ("divided", "shared"):
            for key, recipe in RECIPES.items():
                for cls in (ReactiveRobot, AnticipatoryRobot, AdaptiveAnticipatoryRobot):
                    with self.subTest(layout=layout, robot=cls.__name__, recipe=key):
                        state = GameState(cls, seed=0, layout=layout, recipe=key)
                        state.player.carrying = recipe.ingredients[0]
                        state.update(.5, (0, 0), False)
                        if cls is ReactiveRobot:
                            self.assertIsNone(state.robot.task)
                        else:
                            self.assertIsNotNone(state.robot.task)
                            self.assertEqual(state.robot.task.action,
                                             "fetch" if recipe.cook_seconds else "wait_for_handoff")
                            self.assertFalse(state.robot.task.station.kind.startswith("crate_"))
                            self.assertEqual(state.robot.recipe, key)

    def test_no_hidden_schedule_access(self):
        class ObservableState:
            def __getattr__(self, name):
                if name.startswith("_") or name in ("rng", "order_kinds"):
                    raise AssertionError("Hidden information requested: " + name)
                return getattr(state, name)
        state = GameState(AnticipatoryRobot, seed=4, layout="divided")
        state.player.carrying = "bread"
        state.robot.update_ai(.5, ObservableState())
        source = inspect.getsource(menu_planner)
        self.assertNotIn("_arrivals", source)
        self.assertNotIn("order_schedule", source)

    def test_unique_human_supplies_and_reachable_processing(self):
        names = {n for r in RECIPES.values() for n in r.ingredients}
        for layout in ("divided", "shared"):
            state = GameState(AnticipatoryRobot, seed=0, layout=layout)
            crates = [s for s in state.stations if s.kind.startswith("crate_")]
            self.assertEqual(len(crates), len(names))
            self.assertEqual({s.kind[6:] for s in crates}, names)
            self.assertTrue(all(s.owner == "human" for s in crates))
            nav = Navigator()
            for station in crates:
                self.assertTrue(nav._route(state.player, approach_point(station), state, None), station.label)
                interact(state.robot, station, state)
                self.assertIsNone(state.robot.carrying)
            for kind in ("board", "pot", "plates", "serve"):
                stations = [s for s in state.stations if s.kind == kind and s.owner in (None, "robot")]
                self.assertEqual(len(stations), 2 if kind == "pot" else 1)
                for station in stations:
                    self.assertTrue(nav._route(state.robot, menu_planner.approach(station, state), state, None))

    def test_proactive_plate_is_staged_once_without_creating_ingredients(self):
        for layout in ("divided", "shared"):
            state = GameState(AnticipatoryRobot, seed=5, layout=layout, recipe="chicken_soup")
            state.player.carrying = "chicken"
            for _ in range(400):
                state.update(1 / 30, (0, 0), False)
            items = [s.held for s in state.stations] + [state.robot.carrying]
            self.assertEqual(items.count("plate"), 1)
            self.assertTrue(all(item in (None, "plate") for item in items))
            self.assertEqual(state.robot.task.action, "wait_for_handoff")
            self.assertLess(pygame.Vector2(state.robot.rect.center).distance_to(
                menu_planner.approach(state.robot.task.station, state)), 3)

    def test_human_change_of_plan_cancels_forecast(self):
        state = GameState(AnticipatoryRobot, seed=0, layout="divided")
        state.orders = [Order("cheese_sandwich", 90), Order("pasta_tomatoes", 100)]
        state.player.carrying = "bread"
        state.update(.5, (0, 0), False)
        self.assertEqual(state.robot.task.recipe, "cheese_sandwich")
        state.player.carrying = "pasta"
        state.update(.1, (0, 0), False)
        self.assertEqual(state.robot.task.item, "plate")
        self.assertEqual(state.robot.recipe, "pasta_tomatoes")

    def test_old_layouts_support_new_menu(self):
        for layout in ("shared", "scripted"):
            for key, recipe in RECIPES.items():
                with self.subTest(layout=layout, recipe=key):
                    state = GameState(AnticipatoryRobot, seed=0, layout=layout, recipe=key)
                    surfaces = [s for s in state.stations if s.kind == "counter" and s.owner != "human"]
                    surfaces[0].held, surfaces[1].held = recipe.ingredients
                    for _ in range(900):
                        state.update(1 / 30, (0, 0), False)
                        if state.score:
                            break
                    self.assertGreater(state.score, 0, state.robot.status)

    def test_pause_excludes_wall_clock_time(self):
        import main
        times = []
        events = [[pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p)], [],
                  [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p)], [pygame.event.Event(pygame.QUIT)]]
        with patch("sys.argv", ["main.py", "--robot", "none", "--layout", "divided", "--no-log"]):
            with patch("main.View") as view, patch("pygame.time.Clock") as clock:
                clock.return_value.tick.return_value = 50
                view.return_value.draw.side_effect = lambda state, *_: times.append(state.elapsed)
                with patch("pygame.event.get", side_effect=events):
                    main.main()
        self.assertEqual(times[:2], [0, 0])
        self.assertAlmostEqual(times[2], .05)

    def test_expired_batch_does_not_block_next_recipe(self):
        for cls in (ReactiveRobot, AnticipatoryRobot, AdaptiveAnticipatoryRobot):
            for ready in (False, True):
                with self.subTest(robot=cls.__name__, ready=ready):
                    state = GameState(cls, seed=0, layout="divided", recipe="pasta_tomatoes")
                    state.orders = [Order("pasta_tomatoes", 150)]
                    pot = next(s for s in state.stations if s.kind == "pot")
                    pot.contents = ["chicken", "water"] if ready else ["chicken"]
                    pot.ready = ready
                    for s, item in zip([s for s in state.stations if s.owner == "shared"], ("pasta", "tomato")):
                        s.held = item
                    for _ in range(1200):
                        state.update(1 / 30, (0, 0), False)
                        if state.score:
                            break
                    self.assertGreater(state.score, 0, state.robot.status)

    def test_logger_preserves_files_and_records_periods(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for key in RECIPES:
                state = GameState(seed=0, layout="divided", recipe=key)
                recorder = RunRecorder(dict(participant="test", robot="none", condition="menu", recipe=key, seed=0), directory)
                recorder.start(state)
                paths.append(recorder.path)
                recorder.before(state)
                state.update(60, (0, 0), False)
                recorder.after(state, 60)
                recorder.finish(state, False)
            self.assertEqual(len(paths), len(set(paths)))
            with open(paths[-1], encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([r["item"] for r in rows if r["action"] == "meal_period"], ["BREAKFAST", "LUNCH"])

    def test_only_requested_recipes_are_enabled(self):
        self.assertEqual(set(C.ORDER_KINDS), {"cheese_sandwich", "ham_sandwich", "tomato_soup",
                         "chicken_soup", "chicken_potatoes", "pasta_tomatoes"})
        for obsolete in ("salad", "soup", "potato_soup", "meat_vegetables"):
            with self.assertRaises(ValueError):
                GameState(recipe=obsolete)
        self.assertTrue(all(len(r.ingredients) == 2 for r in RECIPES.values()))

    def test_changed_intention_recovers_pot_while_old_order_remains(self):
        state = GameState(AnticipatoryRobot, seed=0, layout="divided")
        # Keep coverage of recovery when no second pot is available.
        pots = [s for s in state.stations if s.kind == "pot"]
        state.stations.remove(pots[1])
        target = Order("pasta_tomatoes", 150)
        state.orders = [Order("chicken_soup", 140), target]
        state.player.carrying = "pasta"
        pot = next(s for s in state.stations if s.kind == "pot")
        pot.contents = ["chicken"]
        for s, item in zip([s for s in state.stations if s.owner == "shared"], ("pasta", "tomato")):
            s.held = item
        for _ in range(1000):
            state.update(1 / 30, (0, 0), False)
            if not any(o is target for o in state.orders):
                break
        self.assertFalse(any(o is target for o in state.orders), state.robot.status)
        self.assertTrue(any(o.kind == "chicken_soup" for o in state.orders))
        self.assertTrue(any(s.held == "chicken" for s in state.stations))

    def test_forecast_alone_does_not_displace_an_active_batch(self):
        state = GameState(AnticipatoryRobot, seed=0, layout="divided")
        state.orders = [Order("chicken_soup", 140), Order("pasta_tomatoes", 150)]
        state.player.carrying = "pasta"
        pot = next(s for s in state.stations if s.kind == "pot")
        pot.contents = ["chicken"]
        for _ in range(300):
            state.update(1 / 30, (0, 0), False)
            self.assertEqual(pot.contents, ["chicken"])

    def test_blocked_pot_without_storage_preserves_delivered_ingredients(self):
        state = GameState(AnticipatoryRobot, seed=0, layout="divided")
        state.orders = [Order("chicken_soup", 140), Order("pasta_tomatoes", 150)]
        state.player.carrying = "pasta"
        pots = [s for s in state.stations if s.kind == "pot"]
        for pot in pots:
            pot.contents = ["chicken"]
        for counter in state.stations:
            if counter.kind == "counter" and counter.owner == "robot":
                counter.held = "bread"
        handoffs = [s for s in state.stations if s.owner == "shared"]
        for counter, ingredient in zip(handoffs, ("pasta", "tomato")):
            counter.held = ingredient
        for _ in range(300):
            state.update(1 / 30, (0, 0), False)
        self.assertTrue(all(pot.contents == ["chicken"] for pot in pots))
        self.assertEqual([s.held for s in handoffs], ["pasta", "tomato"])
        self.assertIsNone(state.robot.carrying)

    def test_human_can_prepare_and_serve_every_recipe_in_shared_kitchen(self):
        for key, recipe in RECIPES.items():
            with self.subTest(recipe=key):
                state = GameState(seed=0, layout="shared", recipe=key)
                nav = Navigator()
                def use(station):
                    for _ in range(600):
                        arrived = nav.move_to(state.player, approach_point(station), state, 1 / 30)
                        state.update(1 / 30, (0, 0), False)
                        if arrived:
                            break
                    self.assertTrue(arrived, station.label)
                    state.player_interact()
                board = next(s for s in state.stations if s.kind == "board" and s.owner == "human")
                counter = next(s for s in state.stations if s.kind == "counter" and s.owner == "human")
                pot = next(s for s in state.stations if s.kind == "pot")
                for name in recipe.ingredients:
                    use(next(s for s in state.stations if s.kind == "crate_" + name))
                    self.assertEqual(state.player.carrying, name)
                    if prepared(name) != name:
                        use(board)
                        state.update(C.CHOP_TIME + .01, (0, 0), True)
                        state.player_interact()
                        self.assertEqual(state.player.carrying, prepared(name))
                    use(pot if recipe.cook_seconds else counter)
                if recipe.cook_seconds:
                    state.update(recipe.cook_seconds, (0, 0), False)
                    use(next(s for s in state.stations if s.kind == "plates"))
                    use(pot)
                self.assertEqual(state.player.carrying, key)
                use(next(s for s in state.stations if s.kind == "serve"))
                self.assertGreater(state.score, 0)


if __name__ == "__main__":
    unittest.main()

