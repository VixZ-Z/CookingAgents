"""Session music with an application-wide mute preference and optional audio."""
import logging
from pathlib import Path

import pygame


TRACK = Path(__file__).resolve().parent / "assets" / "music" / "background.mp3"


class GameMusic:
    def __init__(self):
        self.enabled = True
        self._loaded = False
        self._started = False
        self._paused = False

    def start(self):
        """Load a fresh session; retain the user's mute choice between sessions."""
        self.stop()
        self._paused = False
        if not pygame.mixer.get_init():
            return
        try:
            pygame.mixer.music.load(str(TRACK))
            pygame.mixer.music.set_volume(0.3)
            self._loaded = True
            self._sync()
        except (pygame.error, OSError) as error:
            self._loaded = False
            logging.getLogger(__name__).warning("Background music unavailable: %s", error)

    def toggle(self):
        self.enabled = not self.enabled
        self._sync()

    def set_paused(self, paused):
        self._paused = paused
        self._sync()

    def _sync(self):
        if not self._loaded:
            return
        try:
            if not self.enabled or self._paused:
                if self._started:
                    pygame.mixer.music.pause()
            elif self._started:
                pygame.mixer.music.unpause()
            else:
                pygame.mixer.music.play(loops=-1)
                self._started = True
        except pygame.error as error:
            self._loaded = False
            logging.getLogger(__name__).warning("Background music unavailable: %s", error)

    def stop(self):
        if self._loaded and pygame.mixer.get_init():
            pygame.mixer.music.stop()
        self._loaded = self._started = False


game_music = GameMusic()
