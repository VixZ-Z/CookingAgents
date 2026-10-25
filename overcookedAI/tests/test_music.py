"""Real MP3 playback and session controls using SDL's silent audio driver."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import main
from music import GameMusic


def key(value):
    return pygame.event.Event(pygame.KEYDOWN, key=value)


class MusicTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.music = GameMusic()
        self.addCleanup(pygame.quit)
        self.addCleanup(self.music.stop)

    def test_real_track_plays_from_any_working_directory_and_stops(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as folder:
            try:
                os.chdir(folder)
                self.music.start()
            finally:
                os.chdir(previous)
        self.assertTrue(pygame.mixer.music.get_busy())
        self.music.stop()
        self.assertFalse(pygame.mixer.music.get_busy())

    def test_muting_and_pause_preserve_choice_across_sessions(self):
        self.music.start()
        self.music.toggle()
        self.assertFalse(pygame.mixer.music.get_busy())
        self.music.stop()
        self.music.start()
        self.assertFalse(self.music.enabled)
        self.assertFalse(pygame.mixer.music.get_busy())
        self.music.set_paused(True)
        self.music.toggle()
        self.assertFalse(pygame.mixer.music.get_busy())
        self.music.set_paused(False)
        self.assertTrue(pygame.mixer.music.get_busy())

    def test_missing_audio_or_track_does_not_prevent_playing(self):
        with patch("pygame.mixer.get_init", return_value=None):
            self.music.start()
            self.music.toggle()
        with patch("music.TRACK", Path("missing-track.mp3")):
            with self.assertLogs("music", level="WARNING"):
                self.music.start()
        self.assertFalse(pygame.mixer.music.get_busy())

    def test_game_keys_toggle_pause_restart_and_exit(self):
        frames = []
        events = [[key(value)] for value in
                  (pygame.K_m, pygame.K_p, pygame.K_m, pygame.K_p, pygame.K_r, pygame.K_ESCAPE)]
        options = type("Options", (), dict(robot="reactive", seed=42, recipe=None,
                       fixed_h=None, participant="test", condition="music", no_log=True))()
        with patch("main.game_music", self.music), patch("main.RunRecorder"), patch("main.View") as view:
            view.return_value.draw.side_effect = lambda *args, **kwargs: frames.append(
                (self.music.enabled, pygame.mixer.music.get_busy()))
            with patch("pygame.time.Clock") as clock, patch("pygame.event.get", side_effect=events):
                clock.return_value.tick.return_value = 50
                self.assertEqual(main.run_game(options, "divided", menu_mode=True), "menu")
        self.assertEqual(frames, [(False, False), (False, False), (True, False),
                                  (True, True), (True, True)])
        self.assertFalse(pygame.mixer.music.get_busy())

    def test_session_error_stops_music_and_closes_recorder(self):
        options = type("Options", (), dict(robot="reactive", seed=42, recipe=None,
                       fixed_h=None, participant="test", condition="music", no_log=True))()
        with patch("main.game_music", self.music), patch("main.RunRecorder") as recorder:
            with patch("main.View") as view, patch("pygame.event.get", return_value=[]):
                view.return_value.draw.side_effect = RuntimeError("test draw failure")
                with self.assertRaisesRegex(RuntimeError, "test draw failure"):
                    main.run_game(options, "divided")
            recorder.return_value.finish.assert_called_once()
        self.assertFalse(pygame.mixer.music.get_busy())


if __name__ == "__main__":
    unittest.main()
