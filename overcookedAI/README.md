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
config.py           layout, recipes, task split, schedules, seeds, routine change
game.py             headless logic: state, step(), orders, scoring   (Phase 2)
logger.py           unified event/position logger (CSV/JSONL)        (done)
agents/             base, reactive, anticipatory, scripted_human     (Phase 3-4)
render.py           pygame drawing + keyboard input                  (Phase 5)
run_sim.py          batch headless runs per condition                (Phase 4)
run_participant.py  participant wrapper                              (Phase 5)
kitchen_chaos_robot.py   legacy prototype (reference only)
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
Legacy prototype: `python kitchen_chaos_robot.py` (needs `pygame`).
