import os
from dataclasses import dataclass
from pathlib import Path

from .safety import ToolkitError, keys, no_links, read_json

ROOT = Path(__file__).resolve().parents[1]
REVISION = "cfa4779a52f1dc59a56d90cc5868778eb50c6a97"


@dataclass(frozen=True)
class Config:
    media_root: Path
    capcut_root: Path
    native_template: Path
    work_root: Path
    vectcut_path: Path

    def __post_init__(self) -> None:
        # Direct library callers can supply Windows 8.3 aliases as well as long paths.
        for name in self.__dataclass_fields__:
            object.__setattr__(self, name, no_links(getattr(self, name)))

    @classmethod
    def load(cls, path: Path) -> "Config":
        data = keys(
            read_json(path),
            {
                "media_root",
                "capcut_root",
                "native_template",
                "work_root",
                "vectcut_path",
            },
            {"media_root", "native_template"},
            "config",
        )
        defaults = {
            "capcut_root": str(
                Path(os.environ.get("LOCALAPPDATA", ""))
                / "CapCut/User Data/Projects/com.lveditor.draft"
            ),
            "work_root": str(ROOT / "local"),
            "vectcut_path": str(ROOT / "vendor/VectCutAPI"),
        }
        paths = {}
        for name in cls.__dataclass_fields__:
            value = data.get(name, defaults.get(name))
            if not isinstance(value, str) or not value.strip():
                raise ToolkitError(f"{name} must be a local path.")
            expanded = Path(os.path.expandvars(value)).expanduser()
            if str(expanded).startswith(("\\\\", "//")):
                raise ToolkitError("Use local disks, not network shares.")
            if not expanded.is_absolute():
                expanded = path.resolve().parent / expanded
            paths[name] = no_links(expanded)
        result = cls(**paths)
        if not result.media_root.is_dir() or not result.native_template.is_dir():
            raise ToolkitError("media_root and native_template must be existing directories.")
        if result.native_template.parent != result.capcut_root:
            raise ToolkitError("Select an empty native project directly inside capcut_root.")
        for protected in (result.media_root, result.capcut_root, result.vectcut_path):
            if result.work_root.is_relative_to(protected) or protected.is_relative_to(
                result.work_root
            ):
                raise ToolkitError(
                    "work_root must not overlap media, CapCut projects, or VectCutAPI."
                )
        return result
