"""Validate an explicit edit decision list before importing the draft engine."""

import math
from pathlib import Path

from .media import probe
from .safety import ToolkitError, child, keys, safe_name
from .timing import filename_ranges, seconds, us


def number(value, low: float, high: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ToolkitError(f"{label} must be a number.")
    if not math.isfinite(value) or not low <= value <= high:
        raise ToolkitError(f"{label} must be between {low} and {high}.")
    return float(value)


def validate_plan(data: dict, media_root: Path, probe_fn=probe) -> dict:
    keys(
        data,
        {"version", "project_name", "canvas", "clips", "music", "captions"},
        {"version", "project_name", "clips"},
        "plan",
    )
    if type(data["version"]) is not int or data["version"] != 1:
        raise ToolkitError("Only plan version 1 is supported.")
    name = safe_name(data["project_name"])
    canvas = data.get("canvas", {"width": 1920, "height": 1080, "fps": 30})
    keys(canvas, {"width", "height", "fps"}, {"width", "height", "fps"}, "canvas")
    if any(type(value) is not int for value in canvas.values()):
        raise ToolkitError("Canvas dimensions and fps must be integers.")
    if (canvas["width"], canvas["height"]) not in {(1920, 1080), (3840, 2160)}:
        raise ToolkitError("Version 0.1 supports 16:9 landscape at 1080p or 2160p.")
    if canvas["fps"] not in {24, 25, 30, 50, 60}:
        raise ToolkitError("Unsupported frame rate.")
    raw_clips = data["clips"]
    if not isinstance(raw_clips, list) or not 1 <= len(raw_clips) <= 1000:
        raise ToolkitError("An edit needs 1-1000 clips.")
    cache = {}

    def source(relative):
        path = child(media_root, relative)
        if relative not in cache:
            cache[relative] = probe_fn(path)
        return cache[relative]

    clips, cursor = [], 0
    for raw in raw_clips:
        keys(
            raw,
            {
                "file",
                "in",
                "out",
                "duration",
                "range_index",
                "important_walk",
                "speed",
                "volume",
                "speech",
                "rotation",
                "background",
                "transition",
                "transition_duration",
                "section",
                "fade_in",
                "fade_out",
            },
            {"file"},
            "clip",
        )
        info = source(raw["file"])
        if info["kind"] == "audio":
            raise ToolkitError("Audio belongs in music, not the main video track.")
        for flag in ("speech", "important_walk"):
            if flag in raw and type(raw[flag]) is not bool:
                raise ToolkitError(f"{flag} must be true or false.")
        speed = number(raw.get("speed", 1), 0.25, 4, "speed")
        speech = raw.get("speech", False)
        if speech and (not info["has_audio"] or speed != 1):
            raise ToolkitError("Speech clips require original audio at normal speed.")
        end: float | None
        if info["kind"] == "image":
            if any(k in raw for k in ("in", "out", "range_index", "speed")):
                raise ToolkitError("Images use duration, not source timing or speed.")
            start, end = 0.0, seconds(raw.get("duration", 3))
        else:
            if "range_index" in raw and ("in" in raw or "out" in raw):
                raise ToolkitError("Choose either range_index or explicit in/out.")
            notes = filename_ranges(raw["file"]) if "in" not in raw and "out" not in raw else []
            if len(notes) > 1 and "range_index" not in raw:
                raise ToolkitError(
                    "Multiple filename ranges: select range_index or explicit in/out."
                )
            selected = raw.get("range_index", 0)
            if (
                type(selected) is not int
                or selected < 0
                or ("range_index" in raw and selected >= len(notes))
            ):
                raise ToolkitError(
                    "range_index must select an existing filename range (zero-based)."
                )
            start, end = notes[selected] if notes else (0.0, None)
            start = seconds(raw.get("in", start))
            end = seconds(raw["out"]) if "out" in raw else end
            if end is not None and "duration" in raw:
                raise ToolkitError("Do not combine an out-point with duration.")
            if end is None:
                duration = seconds(raw.get("duration", 8 if raw.get("important_walk") else 6))
                end = start + duration * speed
                if "duration" not in raw:
                    end = min(end, info["duration"])
            if (
                start < info["video_start"] - 0.001
                or start >= info["duration"]
                or end > info["duration"] + 0.001
            ):
                raise ToolkitError(f"Source range exceeds {raw['file']}.")
        duration_us = us((end - start) / speed)
        if duration_us < 100_000:
            raise ToolkitError("Each clip must last at least 0.1 seconds.")
        volume = number(raw.get("volume", 1 if speech else 0), 0, 1, "volume")
        if speech and volume == 0:
            raise ToolkitError("Speech cannot have zero original volume.")
        if (
            volume > 0
            and info["kind"] == "video"
            and (
                not info["has_audio"]
                or start < info["audio_start"] - 0.001
                or end > info["audio_end"] + 0.001
            )
        ):
            raise ToolkitError("Original audio does not cover the requested source range.")
        rotation = raw.get("rotation", 0)
        if type(rotation) is not int or rotation not in {-270, -180, -90, 0, 90, 180, 270}:
            raise ToolkitError("rotation must be a multiple of 90 degrees.")
        if info["metadata_rotation"] and "rotation" not in raw:
            raise ToolkitError(
                "Rotation metadata detected; inspect a decoded frame and set rotation explicitly."
            )
        background = raw.get("background", "black")
        if background not in {"black", "blur"}:
            raise ToolkitError("background must be black or blur.")
        transition = raw.get("transition", "cut")
        if transition not in {"cut", "mix", "black"}:
            raise ToolkitError("transition must be cut, mix, or black.")
        td = seconds(raw.get("transition_duration", 0.35)) if transition != "cut" else 0
        fade_in, fade_out = seconds(raw.get("fade_in", 0)), seconds(raw.get("fade_out", 0))
        if max(td, fade_in + fade_out) > duration_us / 1e6 / 2:
            raise ToolkitError("Visual fades/transitions are too long for this clip.")
        section = raw.get("section", "")
        if not isinstance(section, str) or len(section) > 100:
            raise ToolkitError("section must be a short string.")
        clips.append(
            {
                "file": raw["file"],
                "source_start": us(start),
                "source_duration": us(end - start),
                "start": cursor,
                "duration": duration_us,
                "speed": speed,
                "volume": volume,
                "speech": speech,
                "rotation": rotation,
                "background": background,
                "transition": transition,
                "transition_duration": us(td),
                "section": section,
                "fade_in": us(fade_in),
                "fade_out": us(fade_out),
                "media": info,
            }
        )
        cursor += duration_us
    if cursor > 1_800_000_000:
        raise ToolkitError("This release limits edits to 30 minutes.")
    if clips[-1]["transition"] != "cut":
        raise ToolkitError("The last clip cannot transition to a nonexistent following clip.")
    for left, right in zip(clips, clips[1:]):
        if left["transition_duration"] > min(left["duration"], right["duration"]) // 2:
            raise ToolkitError("Transition is too long for its neighboring clip.")
        if (left["speech"] or right["speech"]) and left["transition"] != "cut":
            raise ToolkitError("Use clean cuts at speech boundaries.")
    music = []
    raw_music = data.get("music", [])
    if not isinstance(raw_music, list) or len(raw_music) > 100:
        raise ToolkitError("music must be an array with at most 100 cues.")
    for raw in raw_music:
        keys(
            raw,
            {"file", "in", "out", "at", "volume", "fade_in", "fade_out"},
            {"file", "in", "out", "at"},
            "music cue",
        )
        info = source(raw["file"])
        if info["kind"] != "audio":
            raise ToolkitError("Music cues need audio files.")
        start, end, at = seconds(raw["in"]), seconds(raw["out"]), seconds(raw["at"])
        duration = end - start
        fi, fo = seconds(raw.get("fade_in", 1)), seconds(raw.get("fade_out", 1))
        if (
            us(duration) < 100_000
            or start < info["audio_start"] - 0.001
            or end > info["duration"] + 0.001
            or us(at + duration) > cursor
        ):
            raise ToolkitError("Music source or timeline range is invalid.")
        if fi + fo > duration:
            raise ToolkitError("Music fades exceed cue duration.")
        music.append(
            {
                "file": raw["file"],
                "source_start": us(start),
                "source_duration": us(duration),
                "start": us(at),
                "duration": us(duration),
                "volume": number(raw.get("volume", 0.7), 0, 1, "music volume"),
                "fade_in": us(fi),
                "fade_out": us(fo),
                "media": info,
            }
        )
    music.sort(key=lambda item: item["start"])
    for i, cue in enumerate(music):
        if i >= 2 and music[i - 2]["start"] + music[i - 2]["duration"] > cue["start"]:
            raise ToolkitError("More than two songs overlap.")
        if i:
            outgoing = music[i - 1]
            overlap = outgoing["start"] + outgoing["duration"] - cue["start"]
            if overlap == 0:
                raise ToolkitError(
                    "Back-to-back music needs a 1-1.5s overlap or a deliberate silent gap."
                )
            if overlap > 0 and (
                not 1_000_000 <= overlap <= 1_500_000
                or outgoing["fade_out"] != overlap
                or cue["fade_in"] != overlap
            ):
                raise ToolkitError("Overlapping songs require matching 1-1.5s crossfades.")
    captions = []
    raw_captions = data.get("captions", [])
    if not isinstance(raw_captions, list) or len(raw_captions) > 200:
        raise ToolkitError("captions must be an array with at most 200 items.")
    for raw in raw_captions:
        keys(raw, {"text", "start", "end", "position", "size"}, {"text", "start", "end"}, "caption")
        text = raw["text"]
        if not isinstance(text, str) or not text.strip() or len(text.splitlines()) > 3:
            raise ToolkitError("Caption text must contain 1-3 nonempty lines.")
        if any(len(line) > 48 for line in text.splitlines()):
            raise ToolkitError("Wrap caption lines to at most 48 characters, then visually check.")
        if any(ord(ch) < 32 and ch != "\n" for ch in text):
            raise ToolkitError("Caption text contains control characters.")
        start, end = us(seconds(raw["start"])), us(seconds(raw["end"]))
        if not 0 <= start < end <= cursor:
            raise ToolkitError("Caption must remain within the video timeline.")
        position = raw.get("position", "top-left")
        if position not in {"top-left", "center", "lower-third"}:
            raise ToolkitError("Unknown caption position.")
        captions.append(
            {
                "text": text,
                "start": start,
                "duration": end - start,
                "position": position,
                "size": number(raw.get("size", 3), 1, 4, "caption size"),
            }
        )
    captions.sort(key=lambda item: item["start"])
    if any(a["start"] + a["duration"] > b["start"] for a, b in zip(captions, captions[1:])):
        raise ToolkitError("Caption overlaps are not supported in this release.")
    return {
        "project_name": name,
        "canvas": canvas,
        "duration": cursor,
        "clips": clips,
        "music": music,
        "captions": captions,
    }


def music_envelope(cue: dict, speech: list[tuple[int, int]]) -> list[tuple[int, float]]:
    """Linear crossfades; mute music from speech start to end with 0.5s shoulders."""
    duration, start = cue["duration"], cue["start"]
    points = {0, duration, cue["fade_in"], duration - cue["fade_out"]}
    for a, b in speech:
        points.update(max(0, min(duration, t - start)) for t in (a - 500_000, a, b, b + 500_000))
    # Sampling makes products of fade/duck envelopes closely follow their intended curves.
    points.update(range(0, duration, 50_000))
    result = []
    for t in sorted(points):
        level = 1.0
        if cue["fade_in"]:
            level = min(level, t / cue["fade_in"])
        if cue["fade_out"]:
            level = min(level, (duration - t) / cue["fade_out"])
        absolute = start + t
        for a, b in speech:
            if a <= absolute <= b:
                level = 0
            elif a - 500_000 < absolute < a:
                level = min(level, (a - absolute) / 500_000)
            elif b < absolute < b + 500_000:
                level = min(level, (absolute - b) / 500_000)
        result.append((t, round(cue["volume"] * max(0, level), 6)))
    # Remove exactly collinear interior points without changing the envelope.
    simplified: list[tuple[int, float]] = []
    for point in result:
        while len(simplified) >= 2:
            left, middle = simplified[-2:]
            if (
                abs(
                    (middle[1] - left[1]) * (point[0] - middle[0])
                    - (point[1] - middle[1]) * (middle[0] - left[0])
                )
                > 0.00001
            ):
                break
            simplified.pop()
        simplified.append(point)
    return simplified
