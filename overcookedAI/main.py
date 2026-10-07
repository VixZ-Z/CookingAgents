"""Entry point.

    python main.py                                  # scripted robot, original map
    python main.py --robot none --layout far        # preview a layout, human only
    python main.py --robot reactive --layout mixed  # (robot not implemented yet)

Robots : scripted | reactive | anticipatory | none
Layouts: scripted | near | far | mixed | swap   (see layouts.py)

Controls: WASD move, E interact, hold SPACE chop, B robot on/off,
P pause, R restart, ESC quit.
"""
import argparse

import pygame

import config as C
from game import GameState, interaction_target
from layouts import LAYOUT_NAMES
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
                    help="default: scripted for the scripted robot, else near")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    layout = args.layout or ("scripted" if args.robot == "scripted" else "near")
    if args.robot == "scripted" and layout != "scripted":
        ap.error("the scripted robot only works with --layout scripted")
    if args.robot != "scripted" and layout == "scripted" and args.robot != "none":
        ap.error("reactive/anticipatory robots use near/far/mixed/swap layouts")
    robot_cls = get_robot_class(args.robot)

    pygame.init()
    view = View()
    clock = pygame.time.Clock()
    state = GameState(robot_cls, args.seed, layout)
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
                    state = GameState(robot_cls, args.seed, layout)
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
            state.update(dt, move, keys[pygame.K_SPACE])

        view.draw(state, interaction_target(state.player, state.stations), paused)

    pygame.quit()


if __name__ == "__main__":
    main()
