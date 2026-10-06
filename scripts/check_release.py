"""Check the Git publication set without scanning ignored personal/runtime files."""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_DIRS = {"local", "vendor", ".venv", ".tools", "dist", "build", "__pycache__"}
FORBIDDEN_SUFFIXES = {
    ".mp4",
    ".mov",
    ".m4v",
    ".mkv",
    ".avi",
    ".mp3",
    ".wav",
    ".m4a",
    ".aac",
    ".flac",
    ".ogg",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".zip",
    ".7z",
    ".rar",
    ".log",
    ".exe",
    ".dll",
}
SECRET_PATTERNS = [
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{30,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"[A-Za-z]:[\\/]Users[\\/][A-Za-z0-9_.-]+[\\/]"),
]


def main() -> int:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    names = sorted(set(result.stdout.decode("utf-8").split("\0")) - {""})
    failures = []
    for name in names:
        relative = Path(name)
        path = ROOT / relative
        if set(relative.parts) & FORBIDDEN_DIRS or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            failures.append(f"Runtime/media artifact: {name}")
            continue
        if path.name in {"config.local.json", ".env", "draft_content.json", "draft_meta_info.json"}:
            failures.append(f"Private configuration/native project: {name}")
            continue
        if path.stat().st_size > 1_000_000:
            failures.append(f"Oversized source file: {name}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError:
            failures.append(f"Unexpected binary file: {name}")
            continue
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            failures.append(f"Possible credential or personal absolute path: {name}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(
        f"Release scan passed: {len(names)} source/documentation files; no detected private artifacts."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
