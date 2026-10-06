import json
import math
import os
import shutil
from pathlib import Path

from .safety import ToolkitError, child, no_links, run
from .timing import filename_ranges

VIDEO = {".mp4", ".mov", ".m4v", ".mkv", ".avi"}
IMAGE = {".jpg", ".jpeg", ".png", ".webp"}
AUDIO = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}


def probe(path: Path) -> dict:
    if not shutil.which("ffprobe"):
        raise ToolkitError(
            "ffprobe is missing from PATH. Install FFmpeg and restart your terminal."
        )
    path = no_links(path)
    suffix = path.suffix.lower()
    if suffix not in VIDEO | IMAGE | AUDIO:
        raise ToolkitError(f"Unsupported media extension: {suffix}")
    raw = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-show_entries",
            "format=duration,start_time:stream=codec_type,width,height,duration,start_time:stream_tags=rotate:"
            "stream_side_data=rotation",
            "-of",
            "json",
            str(path),
        ],
        30,
    )
    data = json.loads(raw)
    streams = data.get("streams", [])
    video: dict = next((s for s in streams if s["codec_type"] == "video"), {})
    audio: dict = next((s for s in streams if s["codec_type"] == "audio"), {})
    has_audio = bool(audio)
    kind = "image" if suffix in IMAGE else "audio" if suffix in AUDIO else "video"
    container = data.get("format", {})
    origin = float(container.get("start_time", 0) or 0)

    def coverage(stream: dict) -> tuple[float, float]:
        if not stream or kind == "image":
            return 0, 0
        start = max(0.0, float(stream.get("start_time", origin) or 0) - origin)
        value = stream.get("duration")
        if value in (None, "N/A") and len(streams) == 1:
            value = container.get("duration")
        try:
            if value is None:
                raise ValueError("Missing stream duration")
            length = float(value)
        except (ValueError, TypeError) as error:
            raise ToolkitError(
                f"Cannot establish stream coverage for {path.name}. "
                "Create a normalized copy with FFmpeg first."
            ) from error
        if not math.isfinite(start) or not math.isfinite(length) or length <= 0:
            raise ToolkitError(f"Invalid stream timing in {path.name}.")
        return start, start + length

    video_start, video_end = coverage(video)
    audio_start, audio_end = coverage(audio)
    duration = audio_end if kind == "audio" else video_end
    if kind != "image" and (not math.isfinite(duration) or duration <= 0):
        raise ToolkitError(f"No valid duration in {path.name}.")
    if kind == "audio" and not has_audio or kind != "audio" and not video:
        raise ToolkitError(f"Media does not contain its expected stream: {path.name}")
    width, height = int(video.get("width", 0)), int(video.get("height", 0))
    if kind != "audio" and not (0 < width <= 16384 and 0 < height <= 16384):
        raise ToolkitError("Media dimensions exceed the supported limit.")
    rotation = float(video.get("tags", {}).get("rotate", 0))
    for item in video.get("side_data_list", []):
        if "rotation" in item:
            rotation = float(item["rotation"])
    return {
        "kind": kind,
        "duration": duration,
        "width": width,
        "height": height,
        "has_audio": has_audio,
        "metadata_rotation": rotation,
        "video_start": video_start,
        "video_end": video_end,
        "audio_start": audio_start,
        "audio_end": audio_end,
    }


def inventory(root: Path, limit: int = 2000) -> list[dict]:
    root = no_links(root)
    items: list[dict] = []
    for directory, folders, files in os.walk(root, followlinks=False):
        for name in folders:
            no_links(Path(directory) / name)
        for name in sorted(files):
            path = Path(directory) / name
            if path.suffix.lower() not in VIDEO | IMAGE | AUDIO:
                continue
            if len(items) >= limit:
                raise ToolkitError(
                    f"Media inventory exceeds {limit} files; select a smaller folder."
                )
            relative = path.relative_to(root).as_posix()
            checked = child(root, relative)
            items.append(
                {
                    "file": relative,
                    "category": Path(relative).parent.as_posix(),
                    "timing_ranges": filename_ranges(name),
                    **probe(checked),
                }
            )
    return sorted(items, key=lambda item: item["file"].casefold())
