"""Headless game logic (Phase 2). NO pygame imports allowed here.

Planned API:
    state = GameState(condition, seed, logger)
    state.step(human_action, robot_action)   # advances one fixed tick (config.DT)
    state.observation(actor) -> dict
    state.score, state.done

Actions are discrete symbols, e.g. ("move", dx, dy), ("interact",), ("chop",).
"""
