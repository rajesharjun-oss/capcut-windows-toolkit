"""Time values are seconds; minute notation is never interpreted as decimals."""

import math
import re
from pathlib import Path

from .safety import ToolkitError

TOKEN = r"(?:\d+\s*m\s*)?\d+(?:\.\d+)?\s*(?:seconds?|secs?|s)?"


def seconds(value) -> float:
    if isinstance(value, bool):
        raise ToolkitError("A time cannot be a boolean.")
    if isinstance(value, (int, float)):
        result = float(value)
    elif isinstance(value, str):
        text = value.strip().lower()
        if re.fullmatch(r"\d+:[0-5]\d(?:\.\d+)?", text):
            minute, second = text.split(":")
            result = int(minute) * 60 + float(second)
        else:
            match = re.fullmatch(
                r"(?:(\d+)\s*m\s*)?(\d+(?:\.\d+)?)\s*(?:seconds?|secs?|s)?",
                text,
            )
            if not match:
                raise ToolkitError(f"Invalid time notation: {value!r}")
            minute, second = match.groups()
            if minute and float(second) >= 60:
                raise ToolkitError("Seconds in minute notation must be less than 60.")
            result = int(minute or 0) * 60 + float(second)
    else:
        raise ToolkitError("Time must be seconds or a string such as 01m01s.")
    if not math.isfinite(result) or not 0 <= result <= 86_400:
        raise ToolkitError("Time must be finite and between zero and 24 hours.")
    return result


def filename_ranges(filename: str) -> list[tuple[float, float | None]]:
    text = Path(filename).stem.lower().replace("_", " ")
    pairs = re.findall(rf"\b({TOKEN})\s+(?:to|-)\s+({TOKEN})\b", text)
    if pairs:
        result: list[tuple[float, float | None]] = [(seconds(a), seconds(b)) for a, b in pairs]
        if any(b is not None and b <= a for a, b in result):
            raise ToolkitError("Filename out-point must be after its in-point.")
        return result
    match = re.search(rf"\b(?:from|start)\s*({TOKEN})\b", text)
    end = re.search(rf"\b(?:end|ends? at|stops? at)\s*({TOKEN})\b", text)
    if match or end:
        start = seconds(match[1]) if match else 0.0
        stop = seconds(end[1]) if end else None
        if stop is not None and stop <= start:
            raise ToolkitError("Filename out-point must be after its in-point.")
        return [(start, stop)]
    return []


def us(value: float) -> int:
    return round(value * 1_000_000)
