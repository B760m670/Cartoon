"""Быстрая проверка пайплайна: python -m unittest discover tests"""

import tempfile
import unittest
from pathlib import Path

from cartoon import audio, encoder, easing
from cartoon.loader import load_characters, load_episode
from cartoon.scene import Scene
from cartoon.timeline import Track


class TimelineTest(unittest.TestCase):
    def test_interpolation(self):
        tr = Track([{"t": 0, "x": 0}, {"t": 2, "x": 100, "ease": "linear"}], {"x": 5, "y": 1})
        self.assertEqual(tr.value("x", -1), 0)
        self.assertAlmostEqual(tr.value("x", 1), 50)
        self.assertEqual(tr.value("x", 3), 100)
        self.assertEqual(tr.value("y", 1), 1)

    def test_easings_bounds(self):
        for name, fn in easing.EASINGS.items():
            self.assertAlmostEqual(fn(0), 0, places=5, msg=name)
            self.assertAlmostEqual(fn(1), 1, places=5, msg=name)


class RenderTest(unittest.TestCase):
    def test_episode_loads(self):
        ep = load_episode("000_test")
        self.assertGreater(len(ep.scene_files), 0)
        chars = load_characters()
        for f in ep.scene_files:
            from cartoon.loader import read_yaml
            Scene(f.stem, read_yaml(f), chars, 320, 180)

    def test_short_clip(self):
        chars = load_characters()
        spec = {
            "duration": 0.5,
            "background": {"type": "meadow"},
            "actors": [{"character": "krug", "keyframes": [{"t": 0, "x": 300}, {"t": 0.5, "x": 500}],
                        "actions": [{"t": 0, "type": "say", "text": "Тест"}]}],
        }
        scene = Scene("t", spec, chars, 320, 180)
        with tempfile.TemporaryDirectory() as d:
            wav, mp4 = Path(d) / "a.wav", Path(d) / "a.mp4"
            audio.write_wav(wav, audio.render_track(scene.sound_events(), 0.5))
            w = encoder.VideoWriter(mp4, 320, 180, 12, wav)
            for i in range(6):
                w.write(scene.frame(i / 12))
            w.close()
            info = encoder.probe(mp4)
            self.assertIn("h264", info)
            self.assertIn("aac", info)


if __name__ == "__main__":
    unittest.main()
