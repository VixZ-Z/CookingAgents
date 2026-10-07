# Project 1: Adapting to Changing Human Routines in Overcooked

## Overview
This project investigates human-robot collaboration in a custom
Overcooked-inspired kitchen. A human and an autonomous robot work in
separate work areas and share a counter, jointly completing the same meal
orders. The scenario is a simplified model of a care setting where a robot
must coordinate with a person whose habits can change over time.

## Research question
Does forgetting old observations help a robot adapt faster after a change
in the human's routine?

## What we do
- Build a custom Overcooked-AI environment with separate work areas, a
  shared counter, recipes, and configurable ingredient locations.
- Implement two robot agents:
  - a **reactive baseline** that responds only to the current state;
  - an **anticipatory agent** that learns the human's transition
    patterns and predicts their next actions.
- Compare **fixed vs. dynamic forgetting horizon (h)** in the learned
  transition model as a secondary analysis.
- Run controlled experiments (simulated runs and, if feasible,
  participant sessions with questionnaires), logging every game event.
- Analyse task performance and adaptation speed with appropriate
  statistical tests, and discuss human factors and relevance to
  healthcare.

## Output
A 7-8 page IEEE-format research paper with results, analysis, and
discussion.

## Run
See setup and run instructions below (to be added).