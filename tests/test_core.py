import copy
import json
import math
import tempfile
import unittest
from pathlib import Path

from capcut_toolkit.plan import music_envelope, validate_plan
from capcut_toolkit.safety import ToolkitError, child, read_json, safe_name, write_json
from capcut_toolkit.timing import filename_ranges, seconds


class TimingTests(unittest.TestCase):
    def test_minutes_are_seconds_not_decimals(self):
        for value in ("01m01s", "1:01", 61, "61 seconds"):
            self.assertEqual(seconds(value), 61)
        self.assertEqual(seconds("04m46s"), 286)

    def test_invalid_times(self):
        for value in (True, -1, math.nan, math.inf, "1.01.0", "1m60s", "1:99"):
            with self.subTest(value=value), self.assertRaises(ToolkitError):
                seconds(value)

    def test_filename_forms(self):
        for text, expected in (
            ("clip 15 to 40 secs.mp4", [(15, 40)]),
            ("clip stops at 9s.mp4", [(0, 9)]),
            ("clip from 21 secs.mp4", [(21, None)]),
            ("clip start 21s end 31s.mp4", [(21, 31)]),
            ("winner 01m01s to 01m06s and 01m10s to 01m20s.mp4", [(61, 66), (70, 80)]),
            ("20261002_153505.mp4", []),
        ):
            with self.subTest(text=text):
                self.assertEqual(filename_ranges(text), expected)

    def test_reversed_range(self):
        with self.assertRaises(ToolkitError):
            filename_ranges("clip 40 to 15 secs.mp4")


class SafetyTests(unittest.TestCase):
    def test_names(self):
        self.assertEqual(safe_name("Event_Review-02"), "Event_Review-02")
        for name in ("../Event", "CON", "NUL", "COM1", "x/y", "", "x" * 81, ".hidden"):
            with self.subTest(name=name), self.assertRaises(ToolkitError):
                safe_name(name)

    def test_path_boundaries(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "clip.mp4").touch()
            self.assertEqual(child(root, "clip.mp4"), root.resolve() / "clip.mp4")
            for value in (
                "../outside.mp4",
                "x/../../clip.mp4",
                "C:/clip.mp4",
                "//host/file.mp4",
                "/clip.mp4",
                "https://host/file.mp4",
                "clip.mp4:secret",
                "file:///clip.mp4",
            ):
                with self.subTest(value=value), self.assertRaises(ToolkitError):
                    child(root, value)

    def test_duplicate_keys_and_nonfinite_json(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.json"
            for text in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
                path.write_text(text)
                with self.assertRaises(ToolkitError):
                    read_json(path)

    def test_output_never_overwrites(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "out.json"
            write_json(path, {"first": True})
            with self.assertRaises(FileExistsError):
                write_json(path, {"second": True})
            self.assertEqual(read_json(path), {"first": True})


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in (
            "sample.mp4",
            "silent.mp4",
            "song.wav",
            "other.wav",
            "photo.png",
            "walk from 21 secs.mp4",
            "winner 01m01s to 01m06s and 01m10s to 01m20s.mp4",
        ):
            (self.root / name).touch()
        self.plan = {
            "version": 1,
            "project_name": "Test",
            "clips": [{"file": "sample.mp4", "in": 0, "out": 30}],
        }

    @staticmethod
    def probe(path):
        kind = "audio" if path.suffix == ".wav" else "image" if path.suffix == ".png" else "video"
        return {
            "kind": kind,
            "duration": 400,
            "width": 1920,
            "height": 1080,
            "has_audio": path.name != "silent.mp4",
            "metadata_rotation": 0,
            "video_start": 0,
            "video_end": 400,
            "audio_start": 0,
            "audio_end": 400,
        }

    def resolve(self):
        return validate_plan(self.plan, self.root, self.probe)

    def test_two_subclips_one_source(self):
        self.plan["clips"] = [
            {"file": "sample.mp4", "in": "01m01s", "out": "01m06s", "speech": True},
            {"file": "sample.mp4", "in": "01m10s", "out": "01m20s"},
        ]
        result = self.resolve()
        self.assertEqual(result["duration"], 15_000_000)
        self.assertEqual(result["clips"][1]["source_start"], 70_000_000)
        self.assertEqual(result["clips"][1]["start"], 5_000_000)
        self.assertEqual(result["clips"][0]["volume"], 1)

    def test_ambiguous_filename_needs_selection(self):
        self.plan["clips"] = [{"file": "winner 01m01s to 01m06s and 01m10s to 01m20s.mp4"}]
        with self.assertRaises(ToolkitError):
            self.resolve()
        self.plan["clips"][0]["range_index"] = 1
        self.assertEqual(self.resolve()["clips"][0]["source_start"], 70_000_000)

    def test_start_only_default_and_walk(self):
        self.plan["clips"] = [{"file": "walk from 21 secs.mp4"}]
        self.assertEqual(self.resolve()["duration"], 6_000_000)
        self.plan["clips"][0]["important_walk"] = True
        self.assertEqual(self.resolve()["duration"], 8_000_000)

    def test_speed_and_explicit_source(self):
        self.plan["clips"] = [{"file": "sample.mp4", "in": 10, "out": 14, "speed": 0.5}]
        self.assertEqual(self.resolve()["duration"], 8_000_000)

    def test_out_of_bounds(self):
        self.plan["clips"][0]["out"] = 401
        with self.assertRaises(ToolkitError):
            self.resolve()

    def test_conflicting_duration(self):
        self.plan["clips"][0]["duration"] = 4
        with self.assertRaises(ToolkitError):
            self.resolve()

    def test_invalid_clip_values(self):
        baseline = copy.deepcopy(self.plan)
        for key, value in (
            ("volume", math.nan),
            ("speed", 0),
            ("speech", "yes"),
            ("rotation", 45),
            ("transition", "flash"),
            ("command", "delete"),
        ):
            self.plan = copy.deepcopy(baseline)
            self.plan["clips"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ToolkitError):
                self.resolve()

    def test_silent_speech_rejected(self):
        self.plan["clips"] = [{"file": "silent.mp4", "speech": True}]
        with self.assertRaises(ToolkitError):
            self.resolve()

    def test_photo_duration(self):
        self.plan["clips"] = [{"file": "photo.png", "duration": 2}]
        self.assertEqual(self.resolve()["duration"], 2_000_000)

    def test_caption_persists_to_explicit_end(self):
        self.plan["captions"] = [{"text": "Outgoing\nMr and Miss KP", "start": 3, "end": 30}]
        cue = self.resolve()["captions"][0]
        self.assertEqual(cue["start"] + cue["duration"], 30_000_000)

    def test_bad_captions(self):
        for caption in (
            {"text": "x" * 49, "start": 0, "end": 5},
            {"text": "Title", "start": 0, "end": 31},
            {"text": "Title", "start": 0, "end": 5, "size": 12},
        ):
            self.plan["captions"] = [caption]
            with self.subTest(caption=caption), self.assertRaises(ToolkitError):
                self.resolve()

    def test_music_source_offset(self):
        self.plan["music"] = [{"file": "song.wav", "in": "04m46s", "out": 315, "at": 0}]
        self.assertEqual(self.resolve()["music"][0]["source_start"], 286_000_000)

    def test_music_must_survive_microsecond_rounding(self):
        self.plan["music"] = [
            {"file": "song.wav", "in": 0, "out": 0.0000001, "at": 0, "fade_in": 0, "fade_out": 0}
        ]
        with self.assertRaises(ToolkitError):
            self.resolve()

    def test_speech_requires_audio_throughout_excerpt(self):
        self.plan["clips"] = [{"file": "sample.mp4", "in": 61, "out": 66, "speech": True}]

        def short_audio(path):
            return {**self.probe(path), "audio_end": 2}

        with self.assertRaises(ToolkitError):
            validate_plan(self.plan, self.root, short_audio)

    def test_crossfade_rules(self):
        self.plan["music"] = [
            {"file": "song.wav", "in": 0, "out": 10, "at": 0},
            {"file": "other.wav", "in": 0, "out": 10, "at": 9},
        ]
        self.assertEqual(len(self.resolve()["music"]), 2)
        for at in (10, 9.5, 8):
            self.plan["music"][1]["at"] = at
            with self.subTest(at=at), self.assertRaises(ToolkitError):
                self.resolve()

    def test_unknown_root_field(self):
        self.plan["execute"] = "anything"
        with self.assertRaises(ToolkitError):
            self.resolve()

    def test_example_plan(self):
        path = Path(__file__).resolve().parents[1] / "examples/event-plan.json"
        self.plan = json.loads(path.read_text())
        for collection in ("clips", "music"):
            for item in self.plan[collection]:
                file = self.root / item["file"]
                file.parent.mkdir(parents=True, exist_ok=True)
                file.touch()
        self.assertEqual(self.resolve()["duration"], 54_000_000)


class EnvelopeTests(unittest.TestCase):
    @staticmethod
    def at(points, time):
        for a, b in zip(points, points[1:]):
            if a[0] <= time <= b[0]:
                return a[1] + (b[1] - a[1]) * (time - a[0]) / (b[0] - a[0])
        return points[-1][1]

    def test_music_muted_for_entire_announcement(self):
        cue = {
            "start": 0,
            "duration": 20_000_000,
            "volume": 0.8,
            "fade_in": 1_000_000,
            "fade_out": 1_000_000,
        }
        envelope = music_envelope(cue, [(5_000_000, 10_000_000)])
        for time in range(5_000_000, 10_000_001, 100_000):
            self.assertEqual(self.at(envelope, time), 0)
        self.assertAlmostEqual(self.at(envelope, 4_750_000), 0.4)
        self.assertAlmostEqual(self.at(envelope, 10_250_000), 0.4)

    def test_crossfade_never_two_full_volume_songs(self):
        outgoing = {
            "start": 0,
            "duration": 10_000_000,
            "volume": 1,
            "fade_in": 0,
            "fade_out": 1_000_000,
        }
        incoming = {
            "start": 9_000_000,
            "duration": 10_000_000,
            "volume": 1,
            "fade_in": 1_000_000,
            "fade_out": 1_000_000,
        }
        a, b = music_envelope(outgoing, []), music_envelope(incoming, [])
        for t in range(0, 1_000_001, 50_000):
            self.assertAlmostEqual(self.at(a, 9_000_000 + t) + self.at(b, t), 1)


if __name__ == "__main__":
    unittest.main()
