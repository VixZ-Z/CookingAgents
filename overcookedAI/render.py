"""All pygame drawing for Kitchen Chaos. Reads the GameState only."""
import pygame

import config as C

FLOOR = (211, 199, 176)
COUNTER = (120, 82, 55)
COUNTER_EDGE = (75, 50, 34)
WHITE = (245, 245, 245)
RED = (210, 60, 55)
GREEN = (80, 180, 90)
ORANGE = (235, 130, 55)
YELLOW = (240, 210, 70)
BLUE = (70, 130, 210)
GRAY = (130, 130, 130)
DARK = (35, 35, 35)
PINK = (220, 100, 130)

# Border colour per station owner (shared counters get their own colour)
OWNER_EDGE = {"robot": (55, 205, 210), "human": (90, 150, 235),
              "shared": (175, 95, 205)}

ITEM_COLORS = {
    "tomato": RED,
    "onion": (210, 190, 150),
    "lettuce": GREEN,
    "chopped_tomato": (245, 100, 90),
    "chopped_onion": (240, 225, 190),
    "chopped_lettuce": (120, 220, 120),
    "plate": WHITE,
    "salad": (120, 200, 100),
    "soup": ORANGE,
}


def draw_progress(surf, rect, ratio):
    bar = pygame.Rect(rect.x + 8, rect.bottom - 12, rect.width - 16, 7)
    pygame.draw.rect(surf, DARK, bar, border_radius=3)
    fill = bar.copy()
    fill.width = int(fill.width * ratio)
    pygame.draw.rect(surf, YELLOW, fill, border_radius=3)


def draw_carried_special(surf, item, x, y):
    inner = RED if item == "plated_tomato" else GREEN
    pygame.draw.circle(surf, WHITE, (x, y), 19)
    pygame.draw.circle(surf, inner, (x, y), 10)


def draw_item(surf, item, x, y):
    if item in ("plated_tomato", "plated_lettuce"):
        draw_carried_special(surf, item, x, y)
        return
    if item == "plate":
        pygame.draw.circle(surf, (220, 220, 220), (x, y), 19)
        pygame.draw.circle(surf, WHITE, (x, y), 15)
        return
    if item == "salad":
        pygame.draw.circle(surf, WHITE, (x, y), 20)
        pygame.draw.circle(surf, GREEN, (x - 5, y), 9)
        pygame.draw.circle(surf, RED, (x + 6, y - 3), 7)
        return
    if item == "soup":
        pygame.draw.circle(surf, WHITE, (x, y), 20)
        pygame.draw.circle(surf, ORANGE, (x, y), 14)
        return
    pygame.draw.circle(surf, ITEM_COLORS.get(item, PINK), (x, y), 15)
    if item.startswith("chopped_"):
        for ox, oy in [(-7, -4), (4, -7), (-2, 6), (7, 5)]:
            pygame.draw.circle(surf, WHITE, (x + ox, y + oy), 2)


class View:
    def __init__(self):
        self.screen = pygame.display.set_mode((C.WIDTH, C.HEIGHT))
        pygame.display.set_caption("Kitchen Chaos - Robot teammate")
        self.font = pygame.font.SysFont("arial", 22)
        self.small = pygame.font.SysFont("arial", 16)
        self.big = pygame.font.SysFont("arial", 42, bold=True)

    # -- stations -------------------------------------------------------
    def station(self, st):
        s = self.screen
        pygame.draw.rect(s, COUNTER, st.rect, border_radius=8)
        pygame.draw.rect(s, OWNER_EDGE.get(st.owner, COUNTER_EDGE),
                         st.rect, 4, border_radius=8)
        title = self.small.render(st.label, True, WHITE)
        s.blit(title, (st.rect.centerx - title.get_width() // 2, st.rect.y + 6))
        cx, cy = st.rect.centerx, st.rect.centery

        if st.kind.startswith("crate_"):
            draw_item(s, st.kind[6:], cx, cy + 8)
        elif st.kind == "plates":
            draw_item(s, "plate", cx, cy + 8)
        elif st.kind == "board":
            pygame.draw.rect(s, (190, 150, 100),
                             (st.rect.x + 12, st.rect.y + 28,
                              st.rect.width - 24, st.rect.height - 40),
                             border_radius=5)
            if st.held:
                draw_item(s, st.held, cx, cy + 12)
            if st.progress > 0:
                draw_progress(s, st.rect, min(st.progress / C.CHOP_TIME, 1))
        elif st.kind == "pot":
            pot = pygame.Rect(st.rect.x + 14, st.rect.y + 30,
                              st.rect.width - 28, st.rect.height - 42)
            pygame.draw.rect(s, DARK, pot, border_radius=10)
            pygame.draw.rect(s, GRAY, pot, 3, border_radius=10)
            if st.contents:
                n = self.small.render(str(len(st.contents)), True, WHITE)
                s.blit(n, (pot.centerx - n.get_width() // 2,
                           pot.centery - n.get_height() // 2))
            if st.ready:
                pygame.draw.circle(s, ORANGE, pot.center, 14)
            if st.progress > 0 and not st.ready:
                draw_progress(s, st.rect, min(st.progress / C.POT_TIME, 1))
        elif st.kind == "counter":
            if st.held:
                draw_item(s, st.held, cx, cy + 10)
        elif st.kind == "serve":
            pygame.draw.rect(s, (210, 180, 70),
                             (st.rect.x + 9, st.rect.y + 32,
                              st.rect.width - 18, 18), border_radius=4)

    # -- agents ---------------------------------------------------------
    def player(self, p):
        s = self.screen
        pygame.draw.rect(s, BLUE, p.rect, border_radius=10)
        pygame.draw.circle(s, (255, 220, 185), (p.rect.centerx, p.rect.y + 8), 9)
        if p.carrying:
            draw_item(s, p.carrying, p.rect.centerx, p.rect.y - 14)

    def robot(self, r):
        s = self.screen
        pygame.draw.rect(s, (48, 176, 180), r.rect, border_radius=9)
        pygame.draw.rect(s, DARK, (r.rect.x + 5, r.rect.y + 7, 32, 16), border_radius=5)
        for off in (-8, 8):
            pygame.draw.circle(s, YELLOW, (r.rect.centerx + off, r.rect.y + 15), 3)
        pygame.draw.line(s, GRAY, (r.rect.centerx, r.rect.top),
                         (r.rect.centerx, r.rect.top - 8), 3)
        pygame.draw.circle(s, RED, (r.rect.centerx, r.rect.top - 8), 3)
        if r.carrying:
            draw_item(s, r.carrying, r.rect.centerx, r.rect.y - 20)

    # -- HUD ------------------------------------------------------------
    def hud(self, state):
        s = self.screen
        pygame.draw.rect(s, DARK, (0, 0, C.WIDTH, 80))
        s.blit(self.font.render(f"Score: {state.score}", True, WHITE), (20, 16))
        s.blit(self.font.render(f"Time: {max(0, int(state.game_time))}", True, WHITE),
               (20, 45))
        x = 270
        for o in sorted(state.orders, key=lambda order: order.time_left):
            box = pygame.Rect(x, 10, 195, 60)
            pygame.draw.rect(s, (65, 65, 65), box, border_radius=8)
            urgent = o is state.priority_order
            pygame.draw.rect(s, YELLOW if urgent else WHITE, box, 3 if urgent else 2,
                             border_radius=8)
            s.blit(self.small.render(o.name + (" *" if urgent else ""), True, WHITE),
                   (box.x + 10, box.y + 8))
            remain = self.small.render(f"{int(o.time_left)}s", True,
                                       YELLOW if o.time_left < 10 else WHITE)
            s.blit(remain, (box.right - remain.get_width() - 10, box.y + 8))
            s.blit(self.small.render(C.INGREDIENTS[o.kind], True, WHITE),
                   (box.x + 10, box.y + 34))
            x += 205

    def help(self, target):
        s = self.screen
        lines = [
            "WASD - move",
            "E - interact / pick up / put down",
            "Hold SPACE - chop | B - robot on/off | P - pause",
            "Salad: chopped tomato + chopped lettuce + plate",
            "Soup: chopped tomato + chopped onion -> pot -> plate",
        ]
        panel = pygame.Rect(12, C.HEIGHT - 128, 530, 116)
        pygame.draw.rect(s, (30, 30, 30), panel, border_radius=8)
        for i, line in enumerate(lines):
            s.blit(self.small.render(line, True, WHITE), (24, panel.y + 8 + i * 20))
        if target:
            pygame.draw.rect(s, YELLOW, target.rect.inflate(6, 6), 3, border_radius=8)
            hint = self.small.render(f"Nearby: {target.label}", True, YELLOW)
            s.blit(hint, (C.WIDTH - hint.get_width() - 20, C.HEIGHT - 32))

    # -- frame ----------------------------------------------------------
    def anticipation(self, robot):
        """Visible intentions for the shared-kitchen pilot."""
        intent = getattr(robot, "intent", None)
        if intent and intent.goal:
            pygame.draw.rect(self.screen, BLUE, intent.goal.rect.inflate(10, 10), 2,
                             border_radius=8)
        task = getattr(robot, "task", None)
        if task:
            pygame.draw.rect(self.screen, (48, 176, 180), task.station.rect.inflate(16, 16),
                             2, border_radius=8)
        navigator = getattr(robot, "navigator", None)
        if navigator and navigator.path:
            points = [robot.rect.center] + [tuple(p) for p in navigator.path]
            pygame.draw.lines(self.screen, (48, 176, 180), False, points, 2)
        if intent and intent.velocity.length() > 20:
            point = tuple(round(v) for v in intent.projected_position)
            pygame.draw.circle(self.screen, BLUE, point, 10, 2)

    def draw(self, state, target, paused=False):
        s = self.screen
        s.fill(FLOOR)
        for x in range(0, C.WIDTH, 80):
            pygame.draw.line(s, (195, 185, 165), (x, 80), (x, 595))
        for y in range(80, 595, 80):
            pygame.draw.line(s, (195, 185, 165), (0, y), (C.WIDTH, y))
        for st in state.stations:
            self.station(st)
        robot = state.robot
        if robot:
            self.anticipation(robot)
            self.robot(robot)
        self.player(state.player)
        self.hud(state)
        self.help(target)

        status = ("ROBOT: " + (robot.status if robot.enabled
                               else "PAUSED (B to enable)")
                  if robot else "ROBOT: none")
        info = [status,
                "Turquoise = robot, blue = yours, purple = shared",
                f"Layout: {state.layout.name} | R: restart | ESC: exit"]
        if robot and getattr(robot, "intent", None):
            info[1] = getattr(robot, "cooperation_description", robot.intent.description)
            order = state.priority_order
            info[2] = (f"Priority: {order.name} ({order.time_left:.0f}s) | yellow order *"
                       if order else "Waiting for the next order")
        for i, line in enumerate(info):
            while self.small.size(line)[0] > C.WIDTH - 585:
                line = line[:-4] + "..."
            s.blit(self.small.render(line, True, DARK), (570, 610 + i * 24))

        if paused or state.game_over:
            ov = pygame.Surface((C.WIDTH, C.HEIGHT), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 175))
            s.blit(ov, (0, 0))
            lines = ["TIME'S UP!" if state.game_over else "PAUSED",
                     f"Score: {state.score}",
                     "R - restart" if state.game_over else "P - resume"]
            for i, line in enumerate(lines):
                t = self.big.render(line, True, WHITE)
                s.blit(t, (C.WIDTH // 2 - t.get_width() // 2, 270 + 60 * i))
        pygame.display.flip()
