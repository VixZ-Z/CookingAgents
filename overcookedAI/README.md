# Project 1: Adapting to Changing Human Routines in Overcooked

Requires **Python 3.10+** (uses `str | None` type syntax).

## Overview
A human and an autonomous robot cook together in a custom Overcooked-inspired
kitchen. Each dish needs both agents (human: tomato; robot: onion/lettuce,
plates, pot, serving; meeting point: a shared counter).

## Research question
Does forgetting old observations help a robot adapt faster after a change
in the human's routine?

## Structure
```
main.py             entry point / main loop (--robot, --layout, --seed)
config.py           constants and the original station layout (pixels)
layouts.py          selectable layouts: scripted, near, far, mixed, swap
game.py             game logic: stations, orders, player, rules, scoring
render.py           all pygame drawing
robot_base.py       common robot interface
scripted_robot/     original robot (works, scripted layout only)
reactive_robot/     baseline robot (stub)
anticipatory_robot/ robot.py + model.py (stubs)
logger.py           event/position logger (not wired in yet)
run_sim.py, run_participant.py   stubs for later phases
```

## Phases
0. Design: task split, approval from instructor
1. Foundation: `config.py`, `logger.py`, structure  <- current
2. Headless `game.py` with fixed timestep and seeding
3. Agent interface + discrete human action symbols
4. Scripted human, routine change, reactive + anticipatory agents, `run_sim.py`
5. Participant wrapper, pilot, freeze conditions, data collection
6. Analysis and paper

## Run
```
pip install -r requirements.txt
python main.py                                   # scripted robot
python main.py --robot none --layout far         # preview a layout
```
Layouts: `scripted | near | far | mixed | swap`.
Controls: WASD move, E interact, hold SPACE chop, B robot on/off, P pause,
R restart, ESC quit.
