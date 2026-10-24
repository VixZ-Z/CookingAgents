"""Run this file in PyCharm to configure and play CookingAgents graphically."""
from argparse import Namespace
import math

import pygame

import config as C
from main import configuration_error, run_game
from render import DARK, FLOOR, WHITE, YELLOW, OWNER_EDGE


ROBOTS = (
    ("reactive", "Reactive"),
    ("anticipatory", "Anticipatory"),
    ("adaptive_anticipatory", "Adaptive Anticipatory"),
)
LAYOUTS = (("divided", "Divided Kitchen"),)


class MainMenu:
    """UI state only: no game objects, learned models or random-number draws."""

    def __init__(self):
        self.robot = "reactive"
        self.layout = "divided"
        self.seed = "42"
        self.participant = "P001"
        self.duration = "180"
        self.logging_enabled = True
        self.focus = None
        self.select_all = False
        self.error = ""
        self.robot_buttons = {key: pygame.Rect(80, 211 + i * 51, 420, 42)
                              for i, (key, _) in enumerate(ROBOTS)}
        self.layout_buttons = {key: pygame.Rect(570 + i * 225, 211, 215, 46)
                               for i, (key, _) in enumerate(LAYOUTS)}
        self.fields = {"seed": pygame.Rect(570, 316, 200, 46),
                       "duration": pygame.Rect(800, 316, 210, 46),
                       "participant": pygame.Rect(80, 442, 420, 46)}
        self.logging_button = pygame.Rect(570, 396, 440, 48)
        self.start_button = pygame.Rect(660, 630, 250, 55)
        self.quit_button = pygame.Rect(930, 630, 110, 55)
        self.title_font = pygame.font.SysFont("arial", 42, bold=True)
        self.font = pygame.font.SysFont("arial", 22)
        self.small = pygame.font.SysFont("arial", 17)

    def configuration(self):
        """Build the existing CLI options shape, or explain invalid input."""
        self.error = ""
        try:
            seed = int(self.seed.strip())
        except ValueError:
            self.error = "Random seed must be a whole number, for example 42."
            return None
        try:
            duration = float(self.duration)
        except ValueError:
            duration = float("nan")
        if not math.isfinite(duration) or duration <= 0:
            self.error = "Game duration must be a positive number of seconds."
            return None
        participant = self.participant.strip()
        if not participant or len(participant) > 24 or not all(
                c.isascii() and (c.isalnum() or c in "_-") for c in participant):
            self.error = "Participant ID: use 1-24 letters, digits, - or _."
            return None
        self.error = configuration_error(self.robot, self.layout) or ""
        if self.error:
            return None
        return Namespace(robot=self.robot, seed=seed, game_time=duration,
                         recipe=None, fixed_h=None, participant=participant,
                         condition=self.robot, no_log=not self.logging_enabled)

    def handle_event(self, event):
        """Return start/quit for application actions; selection stays in this UI."""
        if event.type == pygame.QUIT:
            return "quit"
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.focus = None
            for key, rect in self.fields.items():
                if rect.collidepoint(event.pos):
                    self.focus, self.select_all = key, True
                    return None
            self.error = ""
            for key, rect in self.robot_buttons.items():
                if rect.collidepoint(event.pos):
                    self.robot = key
            for key, rect in self.layout_buttons.items():
                if rect.collidepoint(event.pos):
                    self.layout = key
            if self.logging_button.collidepoint(event.pos):
                self.logging_enabled = not self.logging_enabled
            if self.start_button.collidepoint(event.pos):
                return "start"
            if self.quit_button.collidepoint(event.pos):
                return "quit"
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "quit"
            if event.key == pygame.K_RETURN:
                return "start"
            if event.key == pygame.K_TAB:
                names = tuple(self.fields)
                self.focus = names[(names.index(self.focus) + 1) % len(names)] if self.focus in names else names[0]
                self.select_all = True
            elif self.focus:
                value = getattr(self, self.focus)
                if event.key == pygame.K_a and getattr(event, "mod", 0) & pygame.KMOD_CTRL:
                    self.select_all = True
                    return None
                if event.key == pygame.K_BACKSPACE:
                    value = "" if self.select_all else value[:-1]
                elif event.unicode and (
                        (self.focus == "participant" and event.unicode.isascii()
                         and (event.unicode.isalnum() or event.unicode in "_-"))
                        or (self.focus != "participant" and event.unicode in "0123456789.-")):
                    value = ("" if self.select_all else value) + event.unicode
                else:
                    return None
                setattr(self, self.focus, value[:24] if self.focus == "participant" else value[:16])
                self.select_all = False
                self.error = ""
        return None

    def draw(self, screen):
        screen.fill(FLOOR)
        for x in range(0, C.WIDTH, 80):
            pygame.draw.line(screen, (195, 185, 165), (x, 0), (x, C.HEIGHT))
        accent = OWNER_EDGE["robot"]

        def text(value, point, font=None, color=WHITE):
            screen.blit((font or self.font).render(value, True, color), point)

        def button(rect, label, selected=False):
            hovered = rect.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(screen, (55, 70, 68) if selected else (60, 60, 60), rect, border_radius=8)
            pygame.draw.rect(screen, accent if selected else (YELLOW if hovered else (100, 100, 100)),
                             rect, 2, border_radius=8)
            label_image = self.font.render(label, True, WHITE)
            screen.blit(label_image, label_image.get_rect(center=rect.center))

        text("CookingAgents", (60, 40), self.title_font, DARK)
        text("Configure your kitchen experiment", (62, 98), color=DARK)
        for rect in ((60, 155, 460, 380), (550, 155, 490, 380)):
            pygame.draw.rect(screen, DARK, rect, border_radius=12)
        text("ROBOT TYPE", (80, 173), self.small, accent)
        text("KITCHEN LAYOUT", (570, 173), self.small, accent)
        text("PARTICIPANT ID (same as questionnaire)", (80, 412), self.small, accent)
        for key, label in ROBOTS:
            button(self.robot_buttons[key], label, self.robot == key)
        for key, label in LAYOUTS:
            button(self.layout_buttons[key], label, self.layout == key)
        text("Random seed", (570, 285))
        text("Duration (seconds)", (800, 285))
        for key, rect in self.fields.items():
            pygame.draw.rect(screen, (55, 70, 68) if self.focus == key else (60, 60, 60), rect, border_radius=7)
            pygame.draw.rect(screen, YELLOW if self.focus == key else (100, 100, 100), rect, 2, border_radius=7)
            if self.focus == key and self.select_all:
                pygame.draw.rect(screen, (55, 100, 130), rect.inflate(-14, -12), border_radius=3)
            text(getattr(self, key), (rect.x + 12, rect.y + 9))
        button(self.logging_button, "Logging: " + ("ON" if self.logging_enabled else "OFF"), self.logging_enabled)
        text("Same seed = same scheduled orders.", (570, 466), self.small)
        hint = ("No Robot + Divided is a layout preview."
                if self.robot == "none" and self.layout == "divided"
                else "Pauses do not count toward game duration.")
        text(hint, (570, 491), self.small)
        text("Select a field to replace its value. Tab switches fields.", (62, 555), self.small, DARK)
        if self.error:
            text(self.error, (62, 588), self.small, (155, 25, 20))
        else:
            text("During play: Esc returns here. Every start creates a fresh session.", (62, 588), self.small, DARK)
        button(self.start_button, "START GAME", True)
        button(self.quit_button, "QUIT")
        pygame.display.flip()


def launch_selected(menu):
    options = menu.configuration()
    if options is None:
        return "menu"
    previous_duration = C.GAME_TIME
    try:
        C.GAME_TIME = options.game_time
        return run_game(options, menu.layout, menu_mode=True)
    finally:
        C.GAME_TIME = previous_duration


def main():
    pygame.init()
    try:
        screen = pygame.display.set_mode((C.WIDTH, C.HEIGHT))
        menu = MainMenu()
        clock = pygame.time.Clock()
        running = True
        while running:
            clock.tick(C.FPS)
            pygame.display.set_caption("CookingAgents - Main Menu")
            for event in pygame.event.get():
                action = menu.handle_event(event)
                if action == "quit":
                    running = False
                    break
                if action == "start":
                    if launch_selected(menu) == "quit":
                        running = False
                    screen = pygame.display.get_surface()
                    break
            if running:
                menu.draw(screen)
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
