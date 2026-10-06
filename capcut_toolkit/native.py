"""Native CapCut 9.5 shell preservation and create-only transactional deployment."""

import copy
import json
import os
import shutil
import time
from pathlib import Path
from uuid import UUID, uuid4

from .config import Config
from .engine import generate
from .safety import (
    ToolkitError,
    capcut_closed,
    check_path_length,
    child,
    digest,
    no_links,
    read_json,
    safe_name,
    write_json,
)

MIRRORS = ["draft_content.json", "draft_content.json.bak", "template-2.tmp"]
NESTED_MIRRORS = [*MIRRORS, "template.tmp"]


def timeline_id(project: dict) -> str:
    value = project.get("main_timeline_id")
    try:
        if not isinstance(value, str) or str(UUID(value)).lower() != value.lower():
            raise ValueError()
    except ValueError as error:
        raise ToolkitError("The active native timeline must be a UUID.") from error
    return value


def tree_files(root: Path) -> list[Path]:
    root = no_links(root)
    found = []
    total = 0
    for folder, directories, files in os.walk(root, followlinks=False):
        for name in directories:
            no_links(Path(folder) / name)
        for name in files:
            path = no_links(Path(folder) / name)
            total += path.stat().st_size
            found.append(path)
            if len(found) > 10_000 or total > 100_000_000_000:
                raise ToolkitError("Project exceeds the file-count/size safety limit.")
    return found


def inspect_template(root: Path) -> dict:
    root = no_links(root)
    files = tree_files(root)
    if len(files) > 500 or sum(p.stat().st_size for p in files) > 64_000_000:
        raise ToolkitError("Select a small, empty native template project.")
    project = read_json(root / "Timelines/project.json")
    tid = timeline_id(project)
    timelines = project.get("timelines", [])
    if len(timelines) != 1 or timelines[0].get("id") != tid:
        raise ToolkitError("The template must have exactly one active timeline.")
    folders = [p.name for p in (root / "Timelines").iterdir() if p.is_dir()]
    if folders != [tid]:
        raise ToolkitError("Extra timeline folders in template; create a fresh empty project.")
    for relative in [*MIRRORS, *(f"Timelines/{tid}/{name}" for name in NESTED_MIRRORS)]:
        path = root / relative
        if not path.exists():
            continue
        content = read_json(path)
        if content.get("duration", 0) != 0 or any(
            t.get("segments") for t in content.get("tracks", [])
        ):
            raise ToolkitError("Native template contains footage. Use a new empty CapCut project.")
        if any(content.get("materials", {}).get(key) for key in ("videos", "audios", "texts")):
            raise ToolkitError(
                "Native template contains materials. Use a new empty CapCut project."
            )
    content = read_json(root / "Timelines" / tid / "draft_content.json")
    read_json(root / "draft_content.json")
    for key in ("platform", "last_modified_platform"):
        platform = content.get(key, {})
        if not (
            platform.get("os", "").lower() == "windows"
            and platform.get("app_source") == "cc"
            and platform.get("app_id") == 359289
            and platform.get("app_version") == "9.5.0"
        ):
            raise ToolkitError(
                "Only native Windows CapCut 9.5.0 templates are supported by this release."
            )
    return {
        "timeline_id": tid,
        "content": content,
        "project": project,
        "meta": read_json(root / "draft_meta_info.json"),
        "file_count": len(files),
    }


def remap(value, replacements: dict[str, str]):
    if isinstance(value, dict):
        return {key: remap(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [remap(item, replacements) for item in value]
    if isinstance(value, str):
        for old, new in sorted(replacements.items(), key=lambda pair: len(pair[0]), reverse=True):
            if old:
                value = value.replace(old, new)
    return value


def mirror_paths(tid: str) -> list[str]:
    return [*MIRRORS, *(f"Timelines/{tid}/{name}" for name in NESTED_MIRRORS)]


def file_hashes(root: Path) -> dict[str, str]:
    root = no_links(root)
    return {path.relative_to(root).as_posix(): digest(path) for path in tree_files(root)}


def project_index(config: Config) -> tuple[dict, dict]:
    root = read_json(no_links(config.capcut_root / "root_meta_info.json"))
    entries = root.get("all_draft_store")
    if not isinstance(entries, list) or any(not isinstance(e, dict) for e in entries):
        raise ToolkitError("Unrecognized CapCut project index. No changes made.")
    donor = next(
        (
            e
            for e in entries
            if str(e.get("draft_fold_path", "")).replace("\\", "/").casefold()
            == config.native_template.as_posix().casefold()
        ),
        None,
    )
    if donor is None:
        raise ToolkitError("Empty native template is not registered in CapCut's project index.")
    return root, donor


def build(config: Config, plan: dict) -> Path:
    native = inspect_template(config.native_template)
    original_hashes = file_hashes(config.native_template)
    name = safe_name(plan["project_name"])
    destination = no_links(config.capcut_root / name)
    if destination.exists():
        raise ToolkitError("Project already exists. Choose a new name for this revision.")
    job = no_links(config.work_root / "builds" / uuid4().hex)
    stage = job / "project"
    relatives = [p.relative_to(config.native_template) for p in tree_files(config.native_template)]
    relatives.append(Path("assets") / ("0" * 64 + ".jpeg"))
    for base in (stage, destination):
        for native_relative in relatives:
            check_path_length(base / native_relative)
    stage.parent.mkdir(parents=True)
    shutil.copytree(config.native_template, stage)
    tid, draft_id, project_id = (str(uuid4()).upper() for _ in range(3))
    old_tid = native["timeline_id"]
    (stage / "Timelines" / old_tid).rename(stage / "Timelines" / tid)
    replacements = {
        str(config.native_template): str(destination),
        config.native_template.as_posix(): destination.as_posix(),
        old_tid: tid,
        native["meta"]["draft_id"]: draft_id,
        native["project"]["id"]: project_id,
    }
    original_root_id = read_json(config.native_template / "draft_content.json").get("id")
    if original_root_id:
        replacements[original_root_id] = tid
    for path in tree_files(stage):
        if path.name == ".locked":
            path.unlink()
        elif path.suffix in {".json", ".bak", ".tmp"}:
            if not path.read_text(encoding="utf-8-sig").strip():
                continue
            value = remap(read_json(path), replacements)
            path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        elif path.name == "draft_settings":
            # CapCut stores this attachment as INI on some installations.
            text = path.read_text(encoding="utf-8-sig")
            path.write_text(remap(text, replacements), encoding="utf-8")
        elif path.name != "draft_cover.jpg":
            raise ToolkitError(
                f"Unknown native attachment: {path.name}; review before supporting it."
            )
    paths, asset_manifest = {}, {}
    for item in [*plan["clips"], *plan["music"]]:
        relative = item["file"]
        if relative in paths:
            continue
        source = child(config.media_root, relative)
        source_hash = digest(source)
        asset = Path("assets") / (source_hash + source.suffix.lower())
        target = stage / asset
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(source, target)
        if digest(target) != source_hash or digest(source) != source_hash:
            raise ToolkitError("Source changed while copying; retry with stable media.")
        paths[relative] = target
        asset_manifest[relative] = asset.as_posix()
    generated = generate(plan, config.vectcut_path, paths)
    content = copy.deepcopy(native["content"])
    for key in (
        "canvas_config",
        "tracks",
        "materials",
        "keyframes",
        "keyframe_graph_list",
        "relationships",
        "group_container",
        "fps",
    ):
        if key in generated:
            content[key] = generated[key]
    for collection in ("videos", "audios"):
        for material in content["materials"].get(collection, []):
            asset = Path(material["path"]).relative_to(stage)
            material["path"] = str(destination / asset)
            material["remote_url"] = str(destination / asset)
    now = time.time_ns() // 1000
    content.update(
        id=tid,
        name="Timeline 01",
        duration=plan["duration"],
        path="",
        create_time=now,
        update_time=now,
    )
    for relative in mirror_paths(tid):
        path = stage / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    project = remap(native["project"], replacements)
    project.update(id=project_id, main_timeline_id=tid, create_time=now, update_time=now)
    project["timelines"] = [
        {
            "id": tid,
            "name": "Timeline 01",
            "is_marked_delete": False,
            "create_time": now,
            "update_time": now,
        }
    ]
    for filename in ("project.json", "project.json.bak"):
        (stage / "Timelines" / filename).write_text(json.dumps(project), encoding="utf-8")
    meta = remap(native["meta"], replacements)
    meta.update(
        draft_name=name,
        draft_id=draft_id,
        draft_fold_path=destination.as_posix(),
        draft_root_path=str(config.capcut_root),
        draft_need_rename_folder=False,
        draft_removable_storage_device="",
        tm_duration=plan["duration"],
        tm_draft_create=now,
        tm_draft_modified=now,
    )
    (stage / "draft_meta_info.json").write_text(json.dumps(meta), encoding="utf-8")
    if file_hashes(config.native_template) != original_hashes:
        raise ToolkitError("Native template changed while building. Close CapCut and rebuild.")
    manifest = {
        "version": 1,
        "project_name": name,
        "destination": str(destination),
        "timeline_id": tid,
        "duration": plan["duration"],
        "draft_id": draft_id,
        "assets": asset_manifest,
        "files": file_hashes(stage),
    }
    write_json(job / "manifest.json", manifest)
    write_json(job / "resolved-plan.json", plan)
    verify(stage, destination, manifest)
    return job


def verify(stage: Path, destination: Path, manifest: dict) -> dict:
    if file_hashes(stage) != manifest["files"]:
        raise ToolkitError("Staged project changed after validation. Rebuild; do not deploy it.")
    project = read_json(stage / "Timelines/project.json")
    tid = timeline_id(project)
    if tid != manifest["timeline_id"]:
        raise ToolkitError("Active timeline does not match the manifest.")
    content = read_json(stage / "draft_content.json")
    for relative in mirror_paths(tid):
        if read_json(stage / relative) != content:
            raise ToolkitError(f"Timeline mirror mismatch: {relative}")
    if content["duration"] != manifest["duration"] or content["id"] != tid:
        raise ToolkitError("Draft duration or ID does not match.")
    meta = read_json(stage / "draft_meta_info.json")
    if (
        meta["draft_fold_path"] != destination.as_posix()
        or meta["draft_root_path"] != str(destination.parent)
        or meta["draft_name"] != manifest["project_name"]
        or meta["tm_duration"] != manifest["duration"]
        or meta["draft_id"] != manifest["draft_id"]
        or meta["draft_need_rename_folder"] is not False
        or meta["draft_removable_storage_device"] != ""
    ):
        raise ToolkitError("Deployment metadata does not match the destination.")
    for collection in ("videos", "audios"):
        for material in content["materials"].get(collection, []):
            path = Path(material["path"])
            try:
                asset_relative = path.relative_to(destination)
            except ValueError as error:
                raise ToolkitError("Material points outside the new project.") from error
            if (
                asset_relative.parts[0] != "assets"
                or not child(stage, asset_relative.as_posix()).is_file()
            ):
                raise ToolkitError("Material is missing from the project assets.")
    for track in content["tracks"]:
        for segment in track["segments"]:
            timerange = segment["target_timerange"]
            if (
                timerange["start"] < 0
                or timerange["duration"] <= 0
                or sum(timerange.values()) > content["duration"]
            ):
                raise ToolkitError("A segment exceeds the project timeline.")
    return {
        "status": "verified",
        "duration_seconds": content["duration"] / 1e6,
        "tracks": len(content["tracks"]),
        "mirrors": len(mirror_paths(tid)),
    }


def deploy(config: Config, job: Path, confirm: str, closed_check=capcut_closed) -> Path:
    job = no_links(job)
    builds = no_links(config.work_root / "builds")
    if job.parent != builds:
        raise ToolkitError("Deploy only a job directly inside this config's work_root/builds.")
    manifest = read_json(job / "manifest.json")
    name = safe_name(manifest["project_name"])
    if confirm != name:
        raise ToolkitError("Pass --confirm with the exact project name after reviewing the draft.")
    destination = no_links(config.capcut_root / name)
    if manifest["destination"] != str(destination) or destination.exists():
        raise ToolkitError("Destination changed or already exists. Build a new project revision.")
    stage = no_links(job / "project")
    verify(stage, destination, manifest)
    closed_check()
    root_path = no_links(config.capcut_root / "root_meta_info.json")
    original = root_path.read_bytes()
    root, donor = project_index(config)
    entries = root["all_draft_store"]
    if any(
        e.get("draft_name") == name or e.get("draft_id") == manifest["draft_id"] for e in entries
    ):
        raise ToolkitError("Project name/ID already exists in CapCut's index.")
    meta = read_json(stage / "draft_meta_info.json")
    entry = copy.deepcopy(donor)
    for key in (
        "draft_id",
        "draft_name",
        "draft_fold_path",
        "draft_root_path",
        "tm_duration",
        "tm_draft_create",
        "tm_draft_modified",
    ):
        entry[key] = meta[key]
    entry.update(
        draft_cover=str(destination / "draft_cover.jpg"),
        draft_json_file=str(destination / "draft_content.json"),
        tm_draft_removed=0,
    )
    root["all_draft_store"] = [entry, *entries]
    root["draft_ids"] = len(root["all_draft_store"])
    root["root_path"] = str(config.capcut_root)
    backup = no_links(config.work_root / "backups" / uuid4().hex)
    check_path_length(backup / "recovery.json")
    backup.mkdir(parents=True)
    (backup / "root_meta_info.json").write_bytes(original)
    write_json(
        backup / "recovery.json",
        {
            "new_project": str(destination),
            "index": str(root_path),
            "instruction": "Close CapCut. Remove only this new project in CapCut if unwanted. "
            "Restore the index backup only if no projects were changed since this deployment.",
        },
    )
    lock = no_links(config.capcut_root / ".capcut-toolkit-deploy.lock")
    try:
        lock_handle = lock.open("x")
    except FileExistsError as error:
        raise ToolkitError(
            "Another toolkit deployment is active; review a stale lock manually."
        ) from error
    incoming = no_links(config.capcut_root / (".capcut-toolkit-" + uuid4().hex))
    index_temp = no_links(config.capcut_root / (".capcut-toolkit-index-" + uuid4().hex))
    installed = False
    try:
        for relative in manifest["files"]:
            check_path_length(incoming / relative)
        shutil.copytree(stage, incoming)
        verify(incoming, destination, manifest)
        closed_check()
        if root_path.read_bytes() != original or destination.exists():
            raise ToolkitError("CapCut projects changed during deployment. Retry after review.")
        write_json(index_temp, root)
        # On Windows rename does not replace an existing destination.
        incoming.rename(destination)
        installed = True
        closed_check()
        if root_path.read_bytes() != original:
            raise ToolkitError("CapCut index changed; refusing to overwrite it.")
        os.replace(index_temp, root_path)
    except Exception:
        if installed and destination.exists():
            # CapCut or another writer may already have adopted/edited this folder.
            # Preserve it even when index registration failed; recovery is reviewed manually.
            write_json(
                backup / "deployment-interrupted.json",
                {
                    "preserved_project": str(destination),
                    "instruction": "Do not move or delete this folder automatically. "
                    "Review CapCut's current index and project before recovery.",
                },
            )
        raise
    finally:
        lock_handle.close()
        lock.unlink(missing_ok=True)
        index_temp.unlink(missing_ok=True)
        if incoming.exists():
            incoming.rename(backup / "failed-stage")
    write_json(job / "deployment.json", {"project": str(destination), "backup": str(backup)})
    return destination
