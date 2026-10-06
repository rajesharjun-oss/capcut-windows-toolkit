import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from capcut_toolkit.media import probe
from capcut_toolkit.plan import validate_plan
from capcut_toolkit.safety import ToolkitError


class MediaCoverageTests(unittest.TestCase):
    def test_container_duration_cannot_extend_stream_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.mp4"
            path.touch()
            for video_duration, audio_duration, speech in ((2, 82, False), (82, 2, True)):
                data = {
                    "format": {"duration": "82", "start_time": "0"},
                    "streams": [
                        {
                            "codec_type": "video",
                            "width": 320,
                            "height": 180,
                            "duration": str(video_duration),
                            "start_time": "0",
                        },
                        {"codec_type": "audio", "duration": str(audio_duration), "start_time": "0"},
                    ],
                }
                with (
                    patch("capcut_toolkit.media.shutil.which", return_value="ffprobe"),
                    patch("capcut_toolkit.media.run", return_value=json.dumps(data)),
                ):
                    info = probe(path)
                    self.assertEqual(info["duration"], video_duration)
                    self.assertEqual(info["audio_end"], audio_duration)
                    with self.assertRaises(ToolkitError):
                        validate_plan(
                            {
                                "version": 1,
                                "project_name": "Coverage",
                                "clips": [
                                    {"file": "sample.mp4", "in": 61, "out": 66, "speech": speech}
                                ],
                            },
                            path.parent,
                        )

    def test_unknown_multistream_duration_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.mp4"
            path.touch()
            data = {
                "format": {"duration": "82"},
                "streams": [
                    {"codec_type": "video", "width": 320, "height": 180},
                    {"codec_type": "audio", "duration": "82"},
                ],
            }
            with (
                patch("capcut_toolkit.media.shutil.which", return_value="ffprobe"),
                patch("capcut_toolkit.media.run", return_value=json.dumps(data)),
                self.assertRaises(ToolkitError),
            ):
                probe(path)
