"""Run this file in PyCharm to configure and play CookingAgents graphically."""
from argparse import Namespace
import webbrowser

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
FIXED_LAYOUT = "divided"
FIXED_SEED = 42
FIXED_DURATION = 180
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScQfNMbLyOI7yvRXV2vJtdfgSkhJH2GyVaKQ8oKcw0rEnQBUg/viewform"
FORM_LINK_LABEL = "Open questionnaire and upload logs"


class MainMenu:
    """UI state only: no game objects, learned models or random-number draws."""

    def __init__(self):
        self.robot = "reactive"
        self.participant = "P001"
        self.logging_enabled = True
        self.focus = None
        self.select_all = False
        self.error = ""
        self.robot_buttons = {key: pygame.Rect(80, 211 + i * 51, 420, 42)
                              for i, (key, _) in enumerate(ROBOTS)}
        self.fields = {"participant": pygame.Rect(80, 418, 420, 46)}
        self.logging_button = pygame.Rect(80, 486, 420, 48)
        self.start_button = pygame.Rect(80, 650, 260, 55)
        self.quit_button = pygame.Rect(360, 650, 140, 55)
        self.title_font = pygame.font.SysFont("arial", 42, bold=True)
        self.font = pygame.font.SysFont("arial", 22)
        self.small = pygame.font.SysFont("arial", 17)
        self.notice_font = pygame.font.SysFont("arial", 20, bold=True)
        self.form_link = pygame.Rect((570, 660), self.small.size(FORM_LINK_LABEL))

    def configuration(self):
        """Build the existing CLI options shape, or explain invalid input."""
        self.error = ""
        participant = self.participant.strip()
        if not participant or len(participant) > 24 or not all(
                c.isascii() and (c.isalnum() or c in "_-") for c in participant):
            self.error = "Participant ID: use 1-24 letters, digits, - or _."
            return None
        self.error = configuration_error(self.robot, FIXED_LAYOUT) or ""
        if self.error:
            return None
        return Namespace(robot=self.robot, seed=FIXED_SEED, game_time=FIXED_DURATION,
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
            if self.form_link.collidepoint(event.pos):
                try:
                    opened = webbrowser.open(FORM_URL, new=2)
                except webbrowser.Error:
                    opened = False
                if not opened:
                    self.error = "Could not open the questionnaire. Please check your default browser."
                return None
            for key, rect in self.robot_buttons.items():
                if rect.collidepoint(event.pos):
                    self.robot = key
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
                elif (event.unicode and event.unicode.isascii()
                      and (event.unicode.isalnum() or event.unicode in "_-")):
                    value = ("" if self.select_all else value) + event.unicode
                else:
                    return None
                setattr(self, self.focus, value[:24])
                self.select_all = False
                self.error = ""
        return None

    def draw(self, screen):
        screen.fill(FLOOR)
        for x in range(0, C.WIDTH, 80):
            pygame.draw.line(screen, (195, 185, 165), (x, 0), (x, C.HEIGHT))
        accent = OWNER_EDGE["robot"]
        right_offset = -40

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
        text("Choose your robot teammate", (62, 98), color=DARK)
        for rect in ((60, 155, 460, 405), (550, 155 + right_offset, 490, 405)):
            pygame.draw.rect(screen, DARK, rect, border_radius=12)
        text("ROBOT TYPE", (80, 173), self.small, accent)
        text("HOW TO PLAY", (570, 173 + right_offset), self.small, accent)
        text("PARTICIPANT ID (same as questionnaire)", (80, 388), self.small, accent)
        for key, label in ROBOTS:
            button(self.robot_buttons[key], label, self.robot == key)
        for key, rect in self.fields.items():
            pygame.draw.rect(screen, (55, 70, 68) if self.focus == key else (60, 60, 60), rect, border_radius=7)
            pygame.draw.rect(screen, YELLOW if self.focus == key else (100, 100, 100), rect, 2, border_radius=7)
            if self.focus == key and self.select_all:
                pygame.draw.rect(screen, (55, 100, 130), rect.inflate(-14, -12), border_radius=3)
            text(getattr(self, key), (rect.x + 12, rect.y + 9))
        button(self.logging_button, "Logging: " + ("ON" if self.logging_enabled else "OFF"), self.logging_enabled)
        text("YOUR TASK", (570, 207 + right_offset), self.small, accent)
        for y, line in (
                (231, "Help the robot complete orders in 3 minutes."),
                (255, "Start with the order with the least time left."),
                (285, "Collect or return raw ingredients at left supplies."),
                (309, "Chop tomato or potato at Prep if you wish."),
                (333, "Use a prep tray to assemble sandwiches."),
                (357, "Deliver ingredients or dishes via purple Handoff."),
                (381, "The robot prepares and serves delivered food.")):
            text(line, (570, y + right_offset), self.small)
        text("CONTROLS", (570, 414 + right_offset), self.small, accent)
        for y, line in (
                (442, "WASD: move | E: pick up, put down or interact"),
                (466, "Hold SPACE near a board: chop"),
                (490, "P: pause | Esc: return to the main menu"),
                (514, "M: music on / off")):
            text(line, (570, y + right_offset), self.small)
        text("Music: Cypis - Gdzie jest biały węgorz? (Zejście)", (570, 578 + right_offset), self.small, DARK)
        text("AFTER PLAYING WITH ALL 3 ROBOTS:", (570, 562), self.notice_font, DARK)
        text("COMPLETE THE FORM AND UPLOAD LOGS", (570, 586), self.notice_font, DARK)
        text("(The logs should be in the logs folder", (570, 614), self.small, DARK)
        text("in the same location as the game.)", (570, 634), self.small, DARK)
        text("Enter your participant ID, select a robot, then start.", (62, 578), self.small, DARK)
        if self.error:
            text(self.error, (62, 606), self.small, (155, 25, 20))
        else:
            text("During play: Esc returns here. Every start creates a fresh session.", (62, 606), self.small, DARK)
        link_color = (20, 90, 150) if self.form_link.collidepoint(pygame.mouse.get_pos()) else (25, 65, 120)
        text(FORM_LINK_LABEL, self.form_link.topleft, self.small, link_color)
        pygame.draw.line(screen, link_color, self.form_link.bottomleft, self.form_link.bottomright)
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
        return run_game(options, FIXED_LAYOUT, menu_mode=True)
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
    import sys
    if "--self-check" in sys.argv:
        from build_check import run
        raise SystemExit(run())
    main()
