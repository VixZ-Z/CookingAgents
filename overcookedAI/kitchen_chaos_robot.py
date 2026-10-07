import pygame
import sys
import random
from dataclasses import dataclass, field

pygame.init()

WIDTH, HEIGHT = 1100, 720
FPS = 60
TILE = 64
GAME_TIME = 180

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Kitchen Chaos - Robot teammate")
clock = pygame.time.Clock()

FONT = pygame.font.SysFont("arial", 22)
SMALL = pygame.font.SysFont("arial", 16)
BIG = pygame.font.SysFont("arial", 42, bold=True)

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

PLAYER_SPEED = 230

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


@dataclass
class Order:
    kind: str
    time_left: float

    @property
    def name(self):
        return "Salad" if self.kind == "salad" else "Soup"


@dataclass
class Station:
    rect: pygame.Rect
    kind: str
    label: str
    held: str | None = None
    contents: list[str] = field(default_factory=list)
    progress: float = 0.0
    ready: bool = False
    reserved: bool = False

    def draw(self, surf):
        pygame.draw.rect(surf, COUNTER, self.rect, border_radius=8)
        pygame.draw.rect(surf, (55, 205, 210) if self.reserved else COUNTER_EDGE, self.rect, 4, border_radius=8)

        title = SMALL.render(self.label, True, WHITE)
        surf.blit(title, (self.rect.centerx - title.get_width() // 2, self.rect.y + 6))

        if self.kind == "crate_tomato":
            draw_item(surf, "tomato", self.rect.centerx, self.rect.centery + 8)
        elif self.kind == "crate_onion":
            draw_item(surf, "onion", self.rect.centerx, self.rect.centery + 8)
        elif self.kind == "crate_lettuce":
            draw_item(surf, "lettuce", self.rect.centerx, self.rect.centery + 8)
        elif self.kind == "plates":
            draw_item(surf, "plate", self.rect.centerx, self.rect.centery + 8)
        elif self.kind == "board":
            pygame.draw.rect(
                surf,
                (190, 150, 100),
                (self.rect.x + 12, self.rect.y + 28, self.rect.width - 24, self.rect.height - 40),
                border_radius=5,
            )
            if self.held:
                draw_item(surf, self.held, self.rect.centerx, self.rect.centery + 12)
            if self.progress > 0:
                draw_progress(surf, self.rect, min(self.progress / 1.5, 1))
        elif self.kind == "pot":
            pot_rect = pygame.Rect(
                self.rect.x + 14,
                self.rect.y + 30,
                self.rect.width - 28,
                self.rect.height - 42,
            )
            pygame.draw.rect(surf, DARK, pot_rect, border_radius=10)
            pygame.draw.rect(surf, GRAY, pot_rect, 3, border_radius=10)

            if self.contents:
                txt = SMALL.render(str(len(self.contents)), True, WHITE)
                surf.blit(
                    txt,
                    (
                        pot_rect.centerx - txt.get_width() // 2,
                        pot_rect.centery - txt.get_height() // 2,
                    ),
                )

            if self.ready:
                pygame.draw.circle(surf, ORANGE, pot_rect.center, 14)

            if self.progress > 0 and not self.ready:
                draw_progress(surf, self.rect, min(self.progress / 5.0, 1))

        elif self.kind == "counter":
            if self.held:
                if self.held in ("plated_tomato", "plated_lettuce"):
                    draw_carried_special(
                        surf, self.held, self.rect.centerx, self.rect.centery + 10
                    )
                else:
                    draw_item(surf, self.held, self.rect.centerx, self.rect.centery + 10)

        elif self.kind == "serve":
            pygame.draw.rect(
                surf,
                (210, 180, 70),
                (
                    self.rect.x + 9,
                    self.rect.y + 32,
                    self.rect.width - 18,
                    18,
                ),
                border_radius=4,
            )


def draw_progress(surf, rect, ratio):
    bar = pygame.Rect(rect.x + 8, rect.bottom - 12, rect.width - 16, 7)
    pygame.draw.rect(surf, DARK, bar, border_radius=3)

    fill = bar.copy()
    fill.width = int(fill.width * ratio)
    pygame.draw.rect(surf, YELLOW, fill, border_radius=3)


def draw_item(surf, item, x, y):
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

    color = ITEM_COLORS.get(item, PINK)
    pygame.draw.circle(surf, color, (x, y), 15)

    if item.startswith("chopped_"):
        for ox, oy in [(-7, -4), (4, -7), (-2, 6), (7, 5)]:
            pygame.draw.circle(surf, WHITE, (x + ox, y + oy), 2)


def draw_carried_special(surf, item, x, y):
    if item == "plated_tomato":
        pygame.draw.circle(surf, WHITE, (x, y), 19)
        pygame.draw.circle(surf, RED, (x, y), 10)
    elif item == "plated_lettuce":
        pygame.draw.circle(surf, WHITE, (x, y), 19)
        pygame.draw.circle(surf, GREEN, (x, y), 10)


class Player:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 42, 42)
        self.pos = pygame.Vector2(x, y)
        self.carrying = None

    def update(self, dt, obstacles):
        keys = pygame.key.get_pressed()

        move = pygame.Vector2(
            keys[pygame.K_d] - keys[pygame.K_a],
            keys[pygame.K_s] - keys[pygame.K_w],
        )

        if move.length_squared() > 0:
            move = move.normalize() * PLAYER_SPEED * dt

        self.pos.x += move.x
        self.rect.x = round(self.pos.x)

        for obstacle in obstacles:
            if self.rect.colliderect(obstacle):
                if move.x > 0:
                    self.rect.right = obstacle.left
                elif move.x < 0:
                    self.rect.left = obstacle.right
                self.pos.x = self.rect.x

        self.pos.y += move.y
        self.rect.y = round(self.pos.y)

        for obstacle in obstacles:
            if self.rect.colliderect(obstacle):
                if move.y > 0:
                    self.rect.bottom = obstacle.top
                elif move.y < 0:
                    self.rect.top = obstacle.bottom
                self.pos.y = self.rect.y

        self.rect.clamp_ip(pygame.Rect(0, 90, WIDTH, 505))
        self.pos.update(self.rect.x, self.rect.y)

    def draw(self, surf):
        pygame.draw.rect(surf, BLUE, self.rect, border_radius=10)
        pygame.draw.circle(
            surf,
            (255, 220, 185),
            (self.rect.centerx, self.rect.y + 8),
            9,
        )

        if self.carrying:
            if self.carrying in ("plated_tomato", "plated_lettuce"):
                draw_carried_special(
                    surf,
                    self.carrying,
                    self.rect.centerx,
                    self.rect.y - 14,
                )
            else:
                draw_item(
                    surf,
                    self.carrying,
                    self.rect.centerx,
                    self.rect.y - 14,
                )


def interaction_target(player, stations):
    expanded = player.rect.inflate(50, 50)
    nearby = [s for s in stations if expanded.colliderect(s.rect) and not s.reserved]

    if not nearby:
        return None

    return min(
        nearby,
        key=lambda s: pygame.Vector2(player.rect.center).distance_to(s.rect.center),
    )


def chop_name(item):
    return {
        "tomato": "chopped_tomato",
        "onion": "chopped_onion",
        "lettuce": "chopped_lettuce",
    }.get(item)


def can_go_in_pot(item):
    return item in ("chopped_tomato", "chopped_onion")


def interact(player, station, orders, score_ref):
    if station is None:
        return

    crate_map = {
        "crate_tomato": "tomato",
        "crate_onion": "onion",
        "crate_lettuce": "lettuce",
    }

    if station.kind == "trash":
        player.carrying = None
        return

    if station.kind in crate_map:
        if player.carrying is None:
            player.carrying = crate_map[station.kind]
        return

    if station.kind == "plates":
        if player.carrying is None:
            player.carrying = "plate"
        return

    if station.kind == "counter":
        if player.carrying is None and station.held is not None:
            player.carrying = station.held
            station.held = None
        elif player.carrying is not None and station.held is None:
            station.held = player.carrying
            player.carrying = None
        return

    if station.kind == "board":
        if player.carrying is None and station.held is not None:
            player.carrying = station.held
            station.held = None
            station.progress = 0

        elif (
            player.carrying is not None
            and station.held is None
            and (chop_name(player.carrying) or player.carrying.startswith("chopped_"))
        ):
            station.held = player.carrying
            player.carrying = None
            station.progress = 0
        return

    if station.kind == "pot":
        if (
            player.carrying
            and can_go_in_pot(player.carrying)
            and not station.ready
            and len(station.contents) < 2
            and player.carrying not in station.contents
        ):
            station.contents.append(player.carrying)
            player.carrying = None

            if len(station.contents) == 2:
                station.progress = 0
            return

        if player.carrying == "plate" and station.ready:
            player.carrying = "soup"
            station.contents.clear()
            station.progress = 0
            station.ready = False
            return

    if station.kind == "serve":
        if player.carrying in ("salad", "soup"):
            dish = player.carrying

            matching_index = next(
                (i for i, order in enumerate(orders) if order.kind == dish),
                None,
            )

            if matching_index is not None:
                order = orders.pop(matching_index)
                bonus = max(0, int(order.time_left))
                score_ref[0] += 100 + bonus
            else:
                return  # Keep the dish until a matching order appears.

            player.carrying = None


def handle_counter_combinations(player, station):
    if station.kind not in ("counter", "board"):
        return False

    a = player.carrying
    b = station.held

    combos = {
        frozenset(("plate", "chopped_tomato")): "plated_tomato",
        frozenset(("plate", "chopped_lettuce")): "plated_lettuce",
        frozenset(("plated_tomato", "chopped_lettuce")): "salad",
        frozenset(("plated_lettuce", "chopped_tomato")): "salad",
    }

    if a is None or b is None:
        return False

    result = combos.get(frozenset((a, b)))

    if result:
        player.carrying = result
        station.held = None
        return True

    return False


def make_stations():
    y_top = 120
    y_bottom = 510

    return [
        Station(pygame.Rect(40, y_top, TILE, TILE), "crate_tomato", "Tomato"),
        Station(pygame.Rect(120, y_top, TILE, TILE), "crate_onion", "Onion"),
        Station(pygame.Rect(200, y_top, TILE, TILE), "crate_lettuce", "Lettuce"),
        Station(pygame.Rect(320, y_top, TILE, TILE), "board", "Chop"),
        Station(pygame.Rect(400, y_top, TILE, TILE), "board", "Chop"),
        Station(pygame.Rect(520, y_top, TILE, TILE), "counter", "Counter"),
        Station(pygame.Rect(600, y_top, TILE, TILE), "counter", "Counter"),
        Station(pygame.Rect(720, y_top, TILE, TILE), "pot", "Pot"),
        Station(pygame.Rect(800, y_top, TILE, TILE), "pot", "Pot"),
        Station(pygame.Rect(920, y_top, TILE, TILE), "serve", "Serve"),
        Station(pygame.Rect(140, y_bottom, TILE, TILE), "counter", "Counter"),
        Station(pygame.Rect(260, y_bottom, TILE, TILE), "counter", "Counter"),
        Station(pygame.Rect(420, y_bottom, TILE, TILE), "plates", "Plates"),
        Station(pygame.Rect(540, y_bottom, TILE, TILE), "counter", "Counter"),
        Station(pygame.Rect(660, y_bottom, TILE, TILE), "counter", "Counter"),
        Station(pygame.Rect(820, y_bottom, TILE, TILE), "counter", "Counter"),
        Station(pygame.Rect(960, y_bottom, TILE, TILE), "trash", "Trash"),
    ]


def add_order(orders):
    if len(orders) < 4:
        kind = random.choice(["salad", "soup"])
        orders.append(Order(kind, random.uniform(65, 90)))


def reset_game():
    stations = make_stations()
    player = Player(WIDTH // 2 - 20, HEIGHT // 2)

    orders = []
    for _ in range(3):
        add_order(orders)

    return player, stations, orders, [0], GAME_TIME, 0.0, False


def draw_ui(orders, score, game_time):
    pygame.draw.rect(screen, DARK, (0, 0, WIDTH, 80))

    score_txt = FONT.render(f"Score: {score}", True, WHITE)
    time_txt = FONT.render(f"Time: {max(0, int(game_time))}", True, WHITE)

    screen.blit(score_txt, (20, 16))
    screen.blit(time_txt, (20, 45))

    x = 270

    for order in orders:
        box = pygame.Rect(x, 10, 195, 60)
        pygame.draw.rect(screen, (65, 65, 65), box, border_radius=8)
        pygame.draw.rect(screen, WHITE, box, 2, border_radius=8)

        name = SMALL.render(order.name, True, WHITE)
        remain = SMALL.render(
            f"{int(order.time_left)}s",
            True,
            YELLOW if order.time_left < 10 else WHITE,
        )

        screen.blit(name, (box.x + 10, box.y + 8))
        screen.blit(
            remain,
            (box.right - remain.get_width() - 10, box.y + 8),
        )

        ingredients = (
            "Tomato + Lettuce"
            if order.kind == "salad"
            else "Tomato + Onion"
        )

        ing_txt = SMALL.render(ingredients, True, WHITE)
        screen.blit(ing_txt, (box.x + 10, box.y + 34))

        x += 205


def draw_help(target):
    lines = [
        "WASD - move",
        "E - interact / pick up / put down",
        "Hold SPACE - chop | B - robot on/off | P - pause",
        "Salad: chopped tomato + chopped lettuce + plate",
        "Soup: chopped tomato + chopped onion -> pot -> plate",
    ]

    panel = pygame.Rect(12, HEIGHT - 128, 530, 116)
    pygame.draw.rect(screen, (30, 30, 30), panel, border_radius=8)

    for i, line in enumerate(lines):
        txt = SMALL.render(line, True, WHITE)
        screen.blit(txt, (24, panel.y + 8 + i * 20))

    if target:
        pygame.draw.rect(screen, YELLOW, target.rect.inflate(6, 6), 3, border_radius=8)
        hint = SMALL.render(f"Nearby: {target.label}", True, YELLOW)
        screen.blit(
            hint,
            (WIDTH - hint.get_width() - 20, HEIGHT - 32),
        )


class Robot(Player):
    """Rule-based teammate: chooses urgent orders and uses real kitchen actions.

    Reserved equipment prevents the player and robot from taking each other's
    ingredients. Movement uses the clear aisle between the two station rows.
    """
    def __init__(self, stations):
        super().__init__(580, 350)
        self.enabled = True
        self.steps = []
        self.status = "Choosing an order"
        self.board = [s for s in stations if s.kind == "board"][1]
        self.pot = [s for s in stations if s.kind == "pot"][1]
        self.counter = [s for s in stations if s.kind == "counter"][1]
        for st in (self.board, self.pot, self.counter):
            st.reserved = True
            st.label = "BOT " + st.label
        self.route = []
        self.destination = None

    def plan(self, stations, orders, player):
        candidates = [o for o in orders if o.time_left > 30]
        # Prefer another recipe when the player already carries a finished dish.
        other = [o for o in candidates if o.kind != player.carrying]
        if other:
            candidates = other
        if not candidates:
            self.status = "Waiting for orders"
            return
        kind = min(candidates, key=lambda o: o.time_left).kind
        find = lambda k: next(s for s in stations if s.kind == k)
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

    def update_ai(self, dt, stations, orders, score_ref, player):
        if not self.enabled:
            return
        if not self.steps:
            self.plan(stations, orders, player)
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
            step = 205 * dt
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
                if st.progress < 1.5:
                    return
                st.held = chop_name(st.held)
                st.progress = 0
        elif action == "put_second":
            interact(self, st, orders, score_ref)
        elif action == "combine":
            handle_counter_combinations(self, st)
        elif action == "wait_soup":
            if not st.ready:
                self.status = "Waiting for soup"
                return
            interact(self, st, orders, score_ref)
        elif action == "serve":
            if not any(o.kind == self.carrying for o in orders):
                self.status = "Waiting for matching order"
                return
            interact(self, st, orders, score_ref)
        else:
            interact(self, st, orders, score_ref)
        self.steps.pop(0)
        self.destination = None
        self.route = []

    def draw(self, surf):
        pygame.draw.rect(surf, (48, 176, 180), self.rect, border_radius=9)
        pygame.draw.rect(surf, DARK, (self.rect.x + 5, self.rect.y + 7, 32, 16), border_radius=5)
        for offset in (-8, 8):
            pygame.draw.circle(surf, YELLOW, (self.rect.centerx + offset, self.rect.y + 15), 3)
        pygame.draw.line(surf, GRAY, (self.rect.centerx, self.rect.top), (self.rect.centerx, self.rect.top - 8), 3)
        pygame.draw.circle(surf, RED, (self.rect.centerx, self.rect.top - 8), 3)
        if self.carrying:
            drawer = draw_carried_special if self.carrying.startswith("plated_") else draw_item
            drawer(surf, self.carrying, self.rect.centerx, self.rect.y - 20)


def update_pots(stations, dt):
    for st in stations:
        if st.kind == "pot" and len(st.contents) == 2 and not st.ready:
            st.progress += dt
            if set(st.contents) == {"chopped_tomato", "chopped_onion"} and st.progress >= 5:
                st.ready = True


def main():
    player, stations, orders, score_ref, game_time, order_timer, game_over = reset_game()
    robot = Robot(stations)
    paused = False
    running = True
    while running:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key == pygame.K_r:
                    player, stations, orders, score_ref, game_time, order_timer, game_over = reset_game()
                    robot = Robot(stations)
                    paused = False
                if event.key == pygame.K_p and not game_over:
                    paused = not paused
                if event.key == pygame.K_b:
                    robot.enabled = not robot.enabled
                if not game_over and not paused and event.key == pygame.K_e:
                    target = interaction_target(player, stations)
                    if not (target and handle_counter_combinations(player, target)):
                        interact(player, target, orders, score_ref)
        if not game_over and not paused:
            player.update(dt, [s.rect for s in stations])
            target = interaction_target(player, stations)
            if target and target.kind == "board" and pygame.key.get_pressed()[pygame.K_SPACE] and chop_name(target.held):
                target.progress += dt
                if target.progress >= 1.5:
                    target.held = chop_name(target.held)
                    target.progress = 0
            update_pots(stations, dt)
            robot.update_ai(dt, stations, orders, score_ref, player)
            game_time = max(0, game_time - dt)
            game_over = game_time <= 0
            for order in orders[:]:
                order.time_left -= dt
                if order.time_left <= 0:
                    orders.remove(order)
                    score_ref[0] = max(0, score_ref[0] - 20)
            order_timer += dt
            if order_timer >= 15:
                order_timer = 0
                add_order(orders)
        screen.fill(FLOOR)
        for x in range(0, WIDTH, 80):
            pygame.draw.line(screen, (195, 185, 165), (x, 80), (x, 595))
        for y in range(80, 595, 80):
            pygame.draw.line(screen, (195, 185, 165), (0, y), (WIDTH, y))
        for st in stations:
            st.draw(screen)
        robot.draw(screen)
        player.draw(screen)
        draw_ui(orders, score_ref[0], game_time)
        draw_help(interaction_target(player, stations))
        status = ["ROBOT: " + (robot.status if robot.enabled else "PAUSED (B to enable)"),
                  "Turquoise stations belong to the robot.",
                  "E at Trash: discard item | R: restart | ESC: exit"]
        for i, line in enumerate(status):
            screen.blit(SMALL.render(line, True, DARK), (570, 610 + i * 24))
        if paused or game_over:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 175))
            screen.blit(overlay, (0, 0))
            lines = ["TIME'S UP!" if game_over else "PAUSED", f"Score: {score_ref[0]}",
                     "R - restart" if game_over else "P - resume"]
            for i, line in enumerate(lines):
                text = BIG.render(line, True, WHITE)
                screen.blit(text, (WIDTH // 2 - text.get_width() // 2, 270 + 60 * i))
        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()
