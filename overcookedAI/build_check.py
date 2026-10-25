"""Optional offline smoke check of the distributed executable (--self-check)."""
import csv
import json
import os
from pathlib import Path
import traceback
from unittest.mock import patch


def run():
    """Exercise packaged assets, all menu robots and CSV output without a window."""
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    import pygame
    import config as C
    import launcher
    import main
    from game import GameState, Order
    from logger import default_log_directory
    from music import TRACK, game_music
    from navigation import approach_point

    folder = default_log_directory().parent
    report = {"passed": False, "sessions": [], "two_pot_modes": []}
    try:
        pygame.init()
        menu = launcher.MainMenu()
        screen = pygame.display.set_mode((C.WIDTH, C.HEIGHT))
        menu.draw(screen)
        assert TRACK.is_file(), "Bundled music is missing"
        game_music.start()
        assert pygame.mixer.music.get_busy(), "Bundled MP3 did not play"
        game_music.stop()
        report["music"] = True
        returns = GameState(seed=42, layout="divided")
        crates = [s for s in returns.stations if s.kind.startswith("crate_")]
        for crate in crates:
            returns.player.rect.center = approach_point(crate)
            returns.player.pos.update(returns.player.rect.topleft)
            returns.player_interact()
            assert returns.player.carrying == crate.kind.removeprefix("crate_")
            returns.player_interact()
            assert returns.player.carrying is None, "Ingredient could not be returned"
            assert returns.human_actions[-1].symbol.action == "put"
        report["ingredient_returns"] = len(crates)
        boundary = GameState(seed=42, layout="divided")
        boundary._arrivals = ()
        protected = Order("cheese_sandwich", 100)
        cancelled = Order("ham_sandwich", 110)
        future = Order("tomato_soup", 120)
        boundary.orders = [protected, cancelled, future]
        boundary.game_time = C.GAME_TIME - 59.99
        boundary.update(.01, (0, 0), False)
        boundary.update(.01, (0, 0), False)
        assert boundary.orders == [protected, future], "Meal cleanup lost the current order"
        assert cancelled.cancel_reason == "meal_end"
        report["meal_cleanup"] = True
        for robot, _ in launcher.ROBOTS:
            menu.robot = robot
            menu.participant = "BUILD_CHECK"
            states = []

            def create(*args, **kwargs):
                state = GameState(*args, **kwargs)
                states.append(state)
                return state

            # Exercise mute, pause, resume and restart through the actual loop.
            events = ([[] for _ in range(12)]
                      + [[pygame.event.Event(pygame.KEYDOWN, key=key)] for key in
                         (pygame.K_m, pygame.K_m, pygame.K_p, pygame.K_p, pygame.K_r)]
                      + [[] for _ in range(12)]
                      + [[pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)]])
            with patch("main.GameState", side_effect=create), patch("pygame.time.Clock") as clock:
                clock.return_value.tick.return_value = 50
                with patch("pygame.event.get", side_effect=events):
                    assert launcher.launch_selected(menu) == "menu"
            assert len(states) == 2, "Restart did not create a fresh session"
            assert all(state.layout.name == "divided" for state in states)
            assert all(sum(s.kind == "pot" for s in state.stations) == 2 for state in states)
            assert not pygame.mixer.music.get_busy(), "Music continued in the menu"
            report["sessions"].append(robot)

            probe = GameState(main.get_robot_class(robot), seed=42, layout="divided")
            probe._arrivals = ()
            target = Order("pasta_tomatoes", 150)
            probe.orders = [Order("chicken_soup", 140), target]
            probe.player.carrying = "pasta"
            pots = [s for s in probe.stations if s.kind == "pot"]
            pots[0].contents = ["chicken"]
            for counter, item in zip([s for s in probe.stations if s.owner == "shared"],
                                      ("pasta", "chopped_tomato")):
                counter.held = item
            for _ in range(1200):
                probe.update(1 / 30, (0, 0), False)
                assert pots[0].contents == ["chicken"], "Robot disturbed the unrelated batch"
                if not any(order is target for order in probe.orders):
                    break
            assert probe.score > 0 and not any(order is target for order in probe.orders), probe.robot.status
            report["two_pot_modes"].append(robot)

        logs = default_log_directory()
        paths = list(logs.glob("BUILD_CHECK_*.csv"))
        assert len(paths) == 6, "Expected six separate session logs"
        for path in paths:
            with path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            assert any(row["action"] == "game_end" for row in rows)
            assert any(row["action"] == "run_config" for row in rows)
            assert all(row["seed"] == "42" for row in rows)
        with (logs / "summary.csv").open(newline="", encoding="utf-8") as stream:
            assert len(list(csv.DictReader(stream))) == 6
        report.update(passed=True, logs=str(logs), log_files=len(paths))
    except Exception:
        report["error"] = traceback.format_exc()
    finally:
        game_music.stop()
        pygame.quit()
        (folder / "build-check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["passed"] else 1
