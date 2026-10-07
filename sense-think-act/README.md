# Project 2: Sense-Think-Act for an Elderly Home-Care Kitchen Robot

## Overview
A toy simulation of a home-care robot that helps an elderly person in a
kitchen. The robot cannot observe the person's true state directly, so it
must infer it from noisy signals and decide how to act, balancing
helpfulness, comfort, autonomy, and safety.

## Sense-Think-Act loop
- **Sense:** noisy observations of the person (position, reaching
  gesture, idle time) with injected errors and dropout.
- **Think:** an HMM forward filter estimates a belief over the hidden
  state (`Cooking`, `NeedsHelp`, `Resting`); a decision layer
  (MDP / rule-based) selects an action based on that belief.
- **Act:** `Wait`, `Keep distance`, `Ask if help needed`, `Fetch item`.
- **Adapt:** transition probabilities are updated online so the robot
  adjusts when the person's routine changes.

## Healthcare mapping
Safety near the stove, privacy of in-home sensing, user autonomy (asking
vs. acting), and comfort/personal space.

## Output
- A documented Python simulation that runs for 50+ time-steps and logs
  state, observation, belief, action, and reward at each step.
- A visualisation of the grid and the belief over time.
- A 2-4 page reflection document on design decisions, partial
  observability, and ethical considerations.

## Run
```bash
pip install -r requirements.txt
python main.py
```