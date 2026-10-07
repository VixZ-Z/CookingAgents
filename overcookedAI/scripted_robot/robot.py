"""Scripted robot (the original teammate).

Chooses the most urgent order and cooks it on its own reserved equipment
(2nd board, pot and counter). It only looks at the current state; the sole
link to the human is that it avoids the dish type the player is carrying.
Movement follows the clear aisle between the two station rows.
Only works with the 'scripted' layout.
"""
import pygame

import config as C
from game import chop_name, handle_counter_combinations, interact
from robot_base import RobotBase


class ScriptedRobot(RobotBase):
    def __init__(self, state):
        super().__init__(*state.layout.robot_start)
        self.steps = []
        self.status = "Choosing an order"
        self.route = []
        self.destination = None

        def own(kind):
            return [s for s in state.stations if s.kind == kind][C.ROBOT_OWNED_INDEX]

        self.board, self.pot, self.counter = own("board"), own("pot"), own("counter")
        for st in (self.board, self.pot, self.counter):
            st.owner = "robot"
            st.label = "BOT " + st.label

    def plan(self, state):
        candidates = [o for o in state.orders if o.time_left > 30]
        # Prefer another recipe when the player already carries a finished dish.
        other = [o for o in candidates if o.kind != state.player.carrying]
        if other:
            candidates = other
        if not candidates:
            self.status = "Waiting for orders"
            return
        kind = min(candidates, key=lambda o: o.time_left).kind
        find = lambda k: next(s for s in state.stations if s.kind == k)
        steps = []
        for ingredient in ("tomato", "lettuce" if kind == "salad" else "onion"):
            steps.extend([(find("crate_" + ingredient), "take"),
                          (self.board, "put"), (self.board, "chop"),
                          (self.board, "take")])
            if kind == "soup":
                steps.append((self.pot, "put"))
            elif ingredient == "tomato":
                steps.append((self.counter, "put"))
            else:
                # Temporarily store lettuce on the board while plating tomato.
                steps.extend([(self.board, "put_second"),
                              (find("plates"), "take"),
                              (self.counter, "combine"),
                              (self.board, "combine")])
        if kind == "soup":
            steps.extend([(find("plates"), "take"), (self.pot, "wait_soup")])
        steps.append((find("serve"), "serve"))
        self.steps = steps
        self.status = "Preparing " + kind

    def update_ai(self, dt, state):
        if not self.enabled:
            return
        if not self.steps:
            self.plan(state)
        if not self.steps:
            return
        st, action = self.steps[0]
        goal = pygame.Vector2(st.rect.centerx,
                              st.rect.bottom + 24 if st.rect.y < 300 else st.rect.top - 24)
        if self.destination is not st:
            self.destination = st
            self.route = [pygame.Vector2(self.rect.centerx, 350),
                          pygame.Vector2(goal.x, 350), goal]
        if self.route:
            center = pygame.Vector2(self.rect.center)
            delta = self.route[0] - center
            step = C.ROBOT_SPEED * dt
            if delta.length() <= step + 1:
                center = self.route.pop(0)
            else:
                center += delta.normalize() * step
            self.rect.center = (round(center.x), round(center.y))
            self.pos.update(self.rect.topleft)
            return

        if action == "chop":
            if st.held in ("tomato", "onion", "lettuce"):
                st.progress += dt
                if st.progress < C.CHOP_TIME:
                    return
                st.held = chop_name(st.held)
                st.progress = 0
        elif action == "put_second":
            interact(self, st, state)
        elif action == "combine":
            handle_counter_combinations(self, st)
        elif action == "wait_soup":
            if not st.ready:
                self.status = "Waiting for soup"
                return
            interact(self, st, state)
        elif action == "serve":
            if not any(o.kind == self.carrying for o in state.orders):
                self.status = "Waiting for matching order"
                return
            interact(self, st, state)
        else:
            interact(self, st, state)
        self.steps.pop(0)
        self.destination = None
        self.route = []
