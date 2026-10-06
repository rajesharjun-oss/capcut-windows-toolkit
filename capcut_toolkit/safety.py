"""Filesystem and subprocess boundaries shared by every command."""

import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path, PureWindowsPath
from typing import Any


class ToolkitError(ValueError):
    """An actionable, user-facing failure."""


def read_json(path: Path, limit: int = 32_000_000) -> Any:
    if path.stat().st_size > limit:
        raise ToolkitError(f"JSON exceeds {limit} bytes: {path.name}")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ToolkitError(f"Duplicate JSON field: {key}")
            result[key] = value
        return result

    def bad_constant(value):
        raise ToolkitError(f"Non-finite JSON value: {value}")

    return json.loads(
        path.read_text(encoding="utf-8-sig"),
        object_pairs_hook=unique,
        parse_constant=bad_constant,
    )


def write_json(path: Path, value: Any) -> None:
    path = no_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def no_links(path: Path) -> Path:
    path = path.absolute()
    for part in (path, *path.parents):
        if not part.exists() and not part.is_symlink():
            continue
        attributes = getattr(part.lstat(), "st_file_attributes", 0)
        if part.is_symlink() or attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ToolkitError(f"Symlinks/junctions are not allowed: {part}")
    return path.resolve()


def check_path_length(path: Path) -> None:
    # CapCut and external media tools may not opt in to Windows long paths.
    if os.name == "nt" and len(str(path.absolute())) > 259:
        raise ToolkitError(
            "A generated path exceeds Windows compatibility limits. "
            "Choose a shorter work_root/project name before building."
        )


def safe_name(name: str) -> str:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", name):
        raise ToolkitError(
            "Project names must be 1-80 ASCII letters, digits, underscores or hyphens."
        )
    if PureWindowsPath(name).is_reserved():
        raise ToolkitError("A Windows device name cannot be a project name.")
    return name


def child(root: Path, relative: str, *, existing: bool = True) -> Path:
    if not isinstance(relative, str) or not relative or len(relative) > 1000:
        raise ToolkitError("Expected a nonempty relative path.")
    win = PureWindowsPath(relative)
    if win.is_absolute() or win.drive or relative.startswith(("/", "\\")) or ":" in relative:
        raise ToolkitError("Absolute, network, URL and alternate-stream media paths are forbidden.")
    if any(part in {"..", "."} for part in relative.replace("\\", "/").split("/")):
        raise ToolkitError("Path traversal is forbidden.")
    root = no_links(root)
    result = no_links(root / relative.replace("\\", "/"))
    if not result.is_relative_to(root) or result == root:
        raise ToolkitError("Path escaped its approved root.")
    if existing and not result.is_file():
        raise ToolkitError(f"File not found: {relative}")
    return result


def run(args: list[str], timeout: int = 60) -> str:
    result = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        shell=False,
    )
    if result.returncode:
        # Tool stderr can contain filenames or content; do not echo it into shared logs.
        raise ToolkitError(f"{Path(args[0]).name} failed (exit {result.returncode}).")
    return result.stdout


def capcut_closed() -> None:
    if os.name != "nt":
        raise ToolkitError("Deployment requires Windows; planning and tests are cross-platform.")
    output = run(["tasklist", "/FI", "IMAGENAME eq CapCut.exe", "/FO", "CSV", "/NH"], 15)
    if '"capcut.exe"' in output.lower():
        raise ToolkitError(
            "Save your work and close CapCut completely, then retry after reviewing recovery files."
        )


def keys(value: Any, allowed: set[str], required: set[str], label: str) -> dict:
    if not isinstance(value, dict):
        raise ToolkitError(f"{label} must be an object.")
    if set(value) - allowed or required - set(value):
        raise ToolkitError(f"{label} has missing or unknown fields.")
    return value
