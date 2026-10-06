"""Opt-in FFmpeg + pinned engine test; never accesses installed CapCut projects."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from test_native import fixture

from capcut_toolkit.config import Config
from capcut_toolkit.media import probe
from capcut_toolkit.native import build, deploy, verify
from capcut_toolkit.plan import validate_plan
from capcut_toolkit.safety import read_json, run


@unittest.skipUnless(
    os.environ.get("CAPCUT_TOOLKIT_ENGINE") and shutil.which("ffmpeg"),
    "Set CAPCUT_TOOLKIT_ENGINE to the pinned upstream path for integration testing.",
)
class EngineIntegration(unittest.TestCase):
    def test_synthetic_audio_video_and_native_shell(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            config = fixture(base)
            config = Config(
                config.media_root,
                config.capcut_root,
                config.native_template,
                config.work_root,
                Path(os.environ["CAPCUT_TOOLKIT_ENGINE"]),
            )
            # All generated fixtures are under the temporary test directory.
            run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc2=size=320x180:rate=30",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:sample_rate=48000",
                    "-t",
                    "5",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    str(config.media_root / "sample.mp4"),
                ]
            )
            run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-n",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=220:sample_rate=48000",
                    "-t",
                    "5",
                    str(config.media_root / "music.wav"),
                ]
            )
            run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-n",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=green:size=320x180",
                    "-frames:v",
                    "1",
                    str(config.media_root / "photo.png"),
                ]
            )
            self.assertTrue(probe(config.media_root / "sample.mp4")["has_audio"])
            plan = validate_plan(
                {
                    "version": 1,
                    "project_name": "Synthetic_Integration",
                    "clips": [
                        {"file": "photo.png", "duration": 1, "fade_in": 0.2},
                        {"file": "sample.mp4", "in": 0, "out": 2, "speech": True},
                        {"file": "sample.mp4", "in": 2, "out": 5},
                    ],
                    "music": [{"file": "music.wav", "in": 0, "out": 5, "at": 1}],
                    "captions": [
                        {"text": "Synthetic test", "start": 0, "end": 6, "position": "center"}
                    ],
                },
                config.media_root,
            )
            job = build(config, plan)
            manifest = read_json(job / "manifest.json")
            verify(job / "project", Path(manifest["destination"]), manifest)
            content = read_json(job / "project/draft_content.json")
            self.assertEqual(content["duration"], 6_000_000)
            self.assertEqual(len(content["materials"]["videos"]), 2)
            caption_track = next(t for t in content["tracks"] if t["type"] == "text")
            self.assertEqual(
                caption_track["segments"][0]["target_timerange"]["duration"], 6_000_000
            )
            # The process check is replaced ONLY for this fake CapCut root in a temp directory.
            deployed = deploy(config, job, "Synthetic_Integration", closed_check=lambda: None)
            self.assertTrue(deployed.is_dir())


if __name__ == "__main__":
    unittest.main()
