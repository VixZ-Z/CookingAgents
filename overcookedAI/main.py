"""Entry point.

    python main.py                                  # scripted robot, original map
    python main.py --robot none --layout far        # preview a layout, human only
    python main.py --robot anticipatory --seed 0   # shared kitchen, salads and soups

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
    ap.add_argument("--robot", default="scripted",
                    choices=["scripted", "reactive", "anticipatory", "none"])
    ap.add_argument("--layout", default=None, choices=LAYOUT_NAMES,
                    help="default: scripted for scripted, shared for anticipatory, reactive for reactive, else near")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--recipe", choices=C.ORDER_KINDS,
                    help="limit orders to one recipe; default includes salad and soup")
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
    layout = args.layout or defaults.get(args.robot, "near")
    recipe = args.recipe
    if args.robot == "anticipatory":
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
    state = GameState(robot_cls, args.seed, layout, recipe)
    recorder = RunRecorder(
        {"participant": args.participant,
         "condition": args.condition or "default", "robot": args.robot,
         "recipe": recipe or "mixed", "seed": args.seed},
        enabled=not args.no_log)
    recorder.start(state)
    paused = False
    running = True

    while running:
        dt = min(clock.tick(C.FPS) / 1000.0, 0.05)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    recorder.finish(state, completed=state.game_over)
                    state = GameState(robot_cls, args.seed, layout, recipe)
                    recorder.start(state)
                    paused = False
                elif event.key == pygame.K_p and not state.game_over:
                    paused = not paused
                elif event.key == pygame.K_b and state.robot:
                    state.robot.enabled = not state.robot.enabled
                elif event.key == pygame.K_e and not state.game_over and not paused:
                    state.player_interact()

        if not paused:
            keys = pygame.key.get_pressed()
            move = (keys[pygame.K_d] - keys[pygame.K_a],
                    keys[pygame.K_s] - keys[pygame.K_w])
            recorder.before(state)
            state.update(dt, move, keys[pygame.K_SPACE])
            recorder.after(state, dt)
            if state.game_over:
                recorder.finish(state, completed=True)

        view.draw(state, interaction_target(state.player, state.stations), paused)

    recorder.finish(state, completed=state.game_over)
    pygame.quit()


if __name__ == "__main__":
    main()
