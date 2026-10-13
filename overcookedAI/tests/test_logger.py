"""RunRecorder: events, positions, anticipation flag and summary row."""
import csv
import glob
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from anticipatory_robot import AnticipatoryRobot
from game import GameState, Order
from logger import RunRecorder

META = {"participant": "T01", "condition": "test", "robot": "anticipatory",
        "recipe": "mixed", "seed": 0}


def read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class LoggerTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def run_log(self, state, seconds, human_script=None):
        rec = RunRecorder(META, self.dir.name)
        rec.start(state)
        for _ in range(int(seconds * 60)):
            rec.before(state)
            if human_script:
                human_script(state)
            state.update(1 / 60, (0, 0), False)
            rec.after(state, 1 / 60)
        rec.finish(state, completed=False)
        return read(glob.glob(os.path.join(self.dir.name, "T01_*.csv"))[0])

    def test_robot_events_positions_and_anticipation_flag(self):
        state = GameState(AnticipatoryRobot, seed=0, layout="shared")
        rows = self.run_log(state, 20)
        kinds = {r["kind"] for r in rows}
        self.assertEqual(kinds, {"event", "pos"})
        self.assertTrue(all(r["participant"] == "T01" for r in rows))
        self.assertTrue(all(r["layout"] == "shared" for r in rows))
        # 5 Hz position samples for two actors over 20 s
        pos = [r for r in rows if r["kind"] == "pos"]
        self.assertAlmostEqual(len(pos), 2 * 5 * 20, delta=6)
        takes = [r for r in rows
                 if r["actor"] == "robot" and r["action"] == "take"]
        self.assertTrue(takes)
        # nobody has shown a choice yet: the robot acts on its default guess
        self.assertEqual(takes[0]["anticipating"], "1")
        self.assertEqual(rows[-1]["action"], "game_end")
        self.assertEqual(rows[-1]["info"], "aborted")

    def test_human_serve_and_summary_row(self):
        state = GameState(None, seed=0, layout="shared")
        state.orders.append(Order("salad", 50.0))
        serve = next(s for s in state.stations if s.kind == "serve")
        state.player.rect.center = (serve.rect.centerx, serve.rect.bottom + 20)
        state.player.pos.update(state.player.rect.topleft)
        state.player.carrying = "salad"
        done = []

        def script(st):
            if not done:
                st.player_interact()
                done.append(1)

        rows = self.run_log(state, 1, script)
        served = [r for r in rows if r["action"] == "serve"]
        self.assertEqual(len(served), 1)
        self.assertEqual(served[0]["actor"], "human")
        self.assertEqual(served[0]["item"], "salad")
        self.assertNotEqual(served[0]["order_id"], "")
        summary = read(os.path.join(self.dir.name, "summary.csv"))
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["served_human"], "1")
        self.assertEqual(summary[0]["completed"], "0")
        self.assertGreater(int(summary[0]["score"]), 100)

    def test_disabled_recorder_writes_nothing(self):
        state = GameState(None, seed=0, layout="shared")
        rec = RunRecorder(META, self.dir.name, enabled=False)
        rec.start(state)
        rec.before(state)
        state.update(0.1, (0, 0), False)
        rec.after(state, 0.1)
        rec.finish(state, completed=True)
        self.assertEqual(os.listdir(self.dir.name), [])


if __name__ == "__main__":
    pygame.init()
    unittest.main()
