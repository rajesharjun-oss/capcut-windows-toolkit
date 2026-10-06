import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__
from .config import REVISION, Config
from .media import inventory
from .native import build, deploy, inspect_template, project_index, verify
from .plan import validate_plan
from .safety import ToolkitError, read_json, run, write_json


def doctor(config: Config | None) -> dict:
    checks: dict[str, dict] = {
        "python": {"ok": sys.version_info >= (3, 11), "version": sys.version.split()[0]},
        "windows": {"ok": os.name == "nt"},
        **{name: {"ok": shutil.which(name) is not None} for name in ("git", "ffmpeg", "ffprobe")},
    }
    if config:
        try:
            revision = run(["git", "-C", str(config.vectcut_path), "rev-parse", "HEAD"]).strip()
            checks["vectcut"] = {"ok": revision == REVISION, "revision": revision}
        except (ToolkitError, OSError):
            checks["vectcut"] = {"ok": False}
        try:
            native = inspect_template(config.native_template)
            checks["native_template"] = {
                "ok": True,
                "files": native["file_count"],
                "app_version": "9.5.0",
            }
        except (ToolkitError, OSError, KeyError) as error:
            checks["native_template"] = {"ok": False, "message": str(error)}
        try:
            project_index(config)
            checks["project_index"] = {"ok": True}
        except (ToolkitError, OSError, KeyError) as error:
            checks["project_index"] = {"ok": False, "message": str(error)}
        checks["engine_dependencies"] = {
            "ok": all(
                __import__("importlib.util", fromlist=["find_spec"]).find_spec(name) is not None
                for name in ("imageio", "numpy", "PIL")
            )
        }
    return {"version": __version__, "ok": all(c["ok"] for c in checks.values()), "checks": checks}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Local CapCut Desktop draft toolkit")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--config", type=Path, default=Path("config.local.json"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Read-only dependency and native-template checks")
    scan = commands.add_parser("inventory", help="Probe approved local media; no uploads")
    scan.add_argument("--output", type=Path, required=True)
    for command in ("validate", "build"):
        child = commands.add_parser(command)
        child.add_argument("--plan", type=Path, required=True)
    check = commands.add_parser("verify")
    check.add_argument("--job", type=Path, required=True)
    install = commands.add_parser("deploy", help="Create a new project; never overwrite")
    install.add_argument("--job", type=Path, required=True)
    install.add_argument("--confirm", required=True, help="Exact reviewed project name")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor" and not args.config.exists():
            result = doctor(None)
            print(json.dumps(result, indent=2))
            return 0 if result["ok"] else 1
        config = Config.load(args.config)
        if args.command == "doctor":
            result = doctor(config)
            print(json.dumps(result, indent=2))
            return 0 if result["ok"] else 1
        if args.command == "inventory":
            output = args.output.resolve()
            if not output.is_relative_to(config.work_root):
                raise ToolkitError(
                    "Inventory reports must stay inside work_root (private local data)."
                )
            items = inventory(config.media_root)
            write_json(output, {"media": items})
            result = {"files": len(items), "report": str(output)}
        elif args.command in {"validate", "build"}:
            plan = validate_plan(read_json(args.plan), config.media_root)
            if args.command == "validate":
                result = {
                    "valid": True,
                    "duration_seconds": plan["duration"] / 1e6,
                    "clips": len(plan["clips"]),
                    "music": len(plan["music"]),
                    "captions": len(plan["captions"]),
                }
            else:
                job = build(config, plan)
                result = {
                    "job": str(job),
                    "status": "staged_not_deployed",
                    "next": "Review resolved-plan.json, save/close CapCut, then deploy.",
                }
        elif args.command == "verify":
            manifest = read_json(args.job / "manifest.json")
            result = verify(args.job / "project", Path(manifest["destination"]), manifest)
        else:
            result = {
                "deployed": str(deploy(config, args.job, args.confirm)),
                "next": "Open CapCut and verify playback before exporting.",
            }
        print(json.dumps(result, indent=2))
        return 0
    except (
        ToolkitError,
        OSError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
        subprocess.TimeoutExpired,
    ) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
