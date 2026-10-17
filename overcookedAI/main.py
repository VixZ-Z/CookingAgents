"""Entry point.

    python main.py --robot reactive --seed 42       # divided meal-period experiment
    python main.py --robot anticipatory --seed 42   # identical geometry and schedule
    python main.py --legacy --robot scripted        # original salad/soup game

Robots : scripted | reactive | anticipatory | none
Layouts: scripted | shared | reactive | near | far | mixed | swap

Controls: WASD move, E interact, hold SPACE chop, B robot on/off,
P pause, R restart, ESC quit.
"""
import argparse
import logging

import pygame

import config as C
from game import GameState, interaction_target
from layouts import LAYOUT_NAMES
from logger import RunRecorder
from render import View


def get_robot_class(name: str):
    if name == "none":
        return None
    if name == "scripted":
        from scripted_robot import ScriptedRobot
        return ScriptedRobot
    if name == "reactive":
        from reactive_robot import ReactiveRobot
        return ReactiveRobot
    if name == "anticipatory":
        from anticipatory_robot import AnticipatoryRobot
        return AnticipatoryRobot
    raise ValueError(name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--robot", default="reactive",
                    choices=["scripted", "reactive", "anticipatory", "none"])
    ap.add_argument("--layout", default=None, choices=LAYOUT_NAMES,
                    help="experiment: divided reactive kitchen; --legacy restores historical layouts")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--recipe", choices=tuple(C.MEAL_KINDS) + tuple(C.ORDER_KINDS),
                    help="optional single-recipe practice; omit for six-recipe experiment")
    ap.add_argument("--legacy", action="store_true", help="preserved salad/soup prototype")
    ap.add_argument("--participant", default="dev",
                    help="participant id, used in the log file name")
    ap.add_argument("--condition", default="",
                    help="free label for the experiment condition, e.g. fixed_h")
    ap.add_argument("--no-log", action="store_true", help="do not write logs")
    ap.add_argument("--debug-agent", action="store_true",
                    help="print robot decision and navigation changes to the console")
    args = ap.parse_args()
    if args.debug_agent:
        logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")

    defaults = {"scripted": "scripted", "anticipatory": "shared", "reactive": "reactive"}
    layout = args.layout or (defaults.get(args.robot, "near") if args.legacy else "reactive")
    recipe = args.recipe
    if not args.legacy:
        if args.robot == "scripted" or layout != "reactive":
            ap.error("experiment: --layout reactive with reactive, anticipatory or none; use --legacy for old modes")
        if recipe is not None and recipe not in C.MEAL_KINDS:
            ap.error("the experiment supports six meal recipes; salad/soup require --legacy")
    elif recipe is not None and recipe not in C.ORDER_KINDS:
        ap.error("--legacy supports salad or soup")
    if args.legacy and args.robot == "anticipatory":
        if layout not in ("shared", "scripted"):
            ap.error("the anticipatory prototype uses --layout shared or scripted")
    if args.robot == "scripted" and layout != "scripted":
        ap.error("the scripted robot only works with --layout scripted")
    if args.robot == "reactive" and layout != "reactive":
        ap.error("the reactive robot requires --layout reactive")
    robot_cls = get_robot_class(args.robot)

    pygame.init()
    view = View()
    clock = pygame.time.Clock()
    state = GameState(robot_cls, args.seed, layout, recipe, experiment=not args.legacy)
    recorder = RunRecorder(
        {"participant": args.participant,
         "condition": args.condition or "default", "robot": args.robot,
         "recipe": recipe or ("mixed" if args.legacy else "meal_periods"), "seed": args.seed},
        enabled=not args.no_log)
    recorder.start(state)
    paused = False
    running = True

    while running:
        dt = min(clock.tick(C.FPS) / 1000.0, 0.05)
        # Include E-key interactions in the existing before/after event diff.
        recorder.before(state)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    recorder.finish(state, completed=state.game_over)
                    state = GameState(robot_cls, args.seed, layout, recipe, experiment=not args.legacy)
                    recorder.start(state)
                    recorder.before(state)
                    paused = False
                elif event.key == pygame.K_p and not state.game_over:
                    paused = not paused
                elif event.key == pygame.K_b and state.robot:
                    state.robot.enabled = not state.robot.enabled
                elif event.key == pygame.K_e and not state.game_over and not paused:
                    state.player_interact()

        if not running:
            break
        if not paused:
            keys = pygame.key.get_pressed()
            move = (keys[pygame.K_d] - keys[pygame.K_a],
                    keys[pygame.K_s] - keys[pygame.K_w])
            state.update(dt, move, keys[pygame.K_SPACE])
            recorder.after(state, dt)
            if state.game_over:
                recorder.finish(state, completed=True)

        view.draw(state, interaction_target(state.player, state.stations), paused)

    recorder.finish(state, completed=state.game_over)
    pygame.quit()


if __name__ == "__main__":
    main()
