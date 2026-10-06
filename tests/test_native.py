import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from capcut_toolkit.cli import doctor
from capcut_toolkit.config import Config
from capcut_toolkit.native import build, deploy, file_hashes, inspect_template, mirror_paths, verify
from capcut_toolkit.safety import ToolkitError, read_json, write_json

TID = "11111111-1111-4111-8111-111111111111"
DID = "22222222-2222-4222-8222-222222222222"
PID = "33333333-3333-4333-8333-333333333333"


def fixture(base: Path) -> Config:
    base = base.resolve()
    projects = base / "projects"
    template = projects / "Empty"
    media = base / "media"
    media.mkdir()
    (media / "sample.mp4").write_bytes(b"synthetic-test-only")
    platform = {"os": "windows", "app_id": 359289, "app_source": "cc", "app_version": "9.5.0"}
    content = {
        "id": TID,
        "duration": 0,
        "tracks": [],
        "materials": {"videos": [], "audios": []},
        "platform": platform,
        "last_modified_platform": platform,
        "native_field_to_preserve": {"value": True},
    }
    for relative in mirror_paths(TID):
        write_json(template / relative, content)
    write_json(
        template / "Timelines/project.json",
        {"id": PID, "main_timeline_id": TID, "timelines": [{"id": TID}]},
    )
    write_json(
        template / "draft_meta_info.json",
        {
            "draft_name": "Empty",
            "draft_id": DID,
            "draft_fold_path": template.as_posix(),
            "draft_root_path": str(projects),
            "tm_duration": 0,
        },
    )
    write_json(
        template / "common_attachment/attachment_pc_timeline.json",
        {"timeline_id": TID, "path": template.as_posix()},
    )
    write_json(
        template / "timeline_layout.json",
        {"dockItems": [{"timelineIds": [TID], "timelineNames": ["Timeline 01"]}]},
    )
    write_json(
        projects / "root_meta_info.json",
        {
            "all_draft_store": [
                {"draft_id": DID, "draft_name": "Empty", "draft_fold_path": template.as_posix()}
            ],
            "draft_ids": 1,
        },
    )
    return Config(media, projects, template, base / "local", base / "vendor")


def generated(plan, repo, paths):
    return {
        "canvas_config": {"width": 1920, "height": 1080},
        "fps": 30,
        "tracks": [
            {
                "type": "video",
                "segments": [
                    {
                        "id": "segment1",
                        "material_id": "material1",
                        "target_timerange": {"start": 0, "duration": plan["duration"]},
                        "source_timerange": {"start": 0, "duration": plan["duration"]},
                    },
                ],
            }
        ],
        "materials": {"videos": [{"id": "material1", "path": str(paths["sample.mp4"])}]},
    }


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = fixture(Path(self.temp.name))
        self.plan = {
            "project_name": "Smoke_Test",
            "duration": 5_000_000,
            "clips": [{"file": "sample.mp4"}],
            "music": [],
        }

    def stage(self):
        with patch("capcut_toolkit.native.generate", generated):
            return build(self.config, self.plan)

    def test_all_mirrors_and_native_fields(self):
        originals = file_hashes(self.config.native_template)
        job = self.stage()
        manifest = read_json(job / "manifest.json")
        result = verify(job / "project", self.config.capcut_root / "Smoke_Test", manifest)
        self.assertEqual(result["mirrors"], 7)
        self.assertEqual(file_hashes(self.config.native_template), originals)
        content = read_json(job / "project/draft_content.json")
        self.assertEqual(content["native_field_to_preserve"], {"value": True})
        attachment = read_json(job / "project/common_attachment/attachment_pc_timeline.json")
        self.assertEqual(attachment["timeline_id"], manifest["timeline_id"])
        self.assertNotIn(str(job), json.dumps(content))
        self.assertFalse((self.config.capcut_root / "Smoke_Test").exists())

    @unittest.skipUnless(os.name == "nt", "Windows short-path regression")
    def test_short_path_alias_hashes_match(self):
        import ctypes

        get_short_path = ctypes.WinDLL("kernel32", use_last_error=True).GetShortPathNameW
        get_short_path.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        get_short_path.restype = ctypes.c_uint32
        buffer = ctypes.create_unicode_buffer(32768)
        result = get_short_path(str(self.config.native_template), buffer, len(buffer))
        self.assertGreater(result, 0)
        alias = Path(buffer.value)
        self.assertEqual(file_hashes(alias), file_hashes(self.config.native_template))

    def test_unknown_version_rejected(self):
        path = self.config.native_template / "Timelines" / TID / "draft_content.json"
        content = read_json(path)
        content["platform"]["app_version"] = "10.0.0"
        path.write_text(json.dumps(content))
        with self.assertRaises(ToolkitError):
            inspect_template(self.config.native_template)

    def test_empty_native_attachment_is_preserved(self):
        (self.config.native_template / "draft_biz_config.json").touch()
        job = self.stage()
        self.assertEqual((job / "project/draft_biz_config.json").read_bytes(), b"")

    def test_nonempty_template_rejected(self):
        path = self.config.native_template / "draft_content.json"
        content = read_json(path)
        content["duration"] = 1
        path.write_text(json.dumps(content))
        with self.assertRaises(ToolkitError):
            self.stage()

    def test_tamper_rejected(self):
        job = self.stage()
        (job / "project/template-2.tmp").write_text("{}")
        with self.assertRaises(ToolkitError):
            deploy(self.config, job, "Smoke_Test", closed_check=lambda: None)
        self.assertFalse((self.config.capcut_root / "Smoke_Test").exists())

    def test_create_only_and_backup(self):
        job = self.stage()
        original = (self.config.capcut_root / "root_meta_info.json").read_bytes()
        result = deploy(self.config, job, "Smoke_Test", closed_check=lambda: None)
        self.assertTrue(result.exists())
        backups = list((self.config.work_root / "backups").glob("*/root_meta_info.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)
        index = read_json(self.config.capcut_root / "root_meta_info.json")
        self.assertEqual(index["draft_ids"], 2)
        with self.assertRaises(ToolkitError):
            deploy(self.config, job, "Smoke_Test", closed_check=lambda: None)

    def test_wrong_confirmation(self):
        job = self.stage()
        with self.assertRaises(ToolkitError):
            deploy(self.config, job, "Different_Name", closed_check=lambda: None)

    def test_running_capcut_blocks(self):
        job = self.stage()

        def running():
            raise ToolkitError("CapCut is running")

        with self.assertRaises(ToolkitError):
            deploy(self.config, job, "Smoke_Test", closed_check=running)
        self.assertFalse((self.config.capcut_root / "Smoke_Test").exists())

    def test_changed_index_preserved(self):
        job = self.stage()
        path = self.config.capcut_root / "root_meta_info.json"
        count = 0

        def concurrent():
            nonlocal count
            count += 1
            if count == 2:
                path.write_text('{"changed_by_capcut":true}')

        with self.assertRaises(ToolkitError):
            deploy(self.config, job, "Smoke_Test", closed_check=concurrent)
        self.assertEqual(read_json(path), {"changed_by_capcut": True})
        self.assertFalse((self.config.capcut_root / "Smoke_Test").exists())

    def test_index_commit_failure_keeps_recovery(self):
        job = self.stage()
        original = (self.config.capcut_root / "root_meta_info.json").read_bytes()
        with patch("capcut_toolkit.native.os.replace", side_effect=OSError("injected failure")):
            with self.assertRaises(OSError):
                deploy(self.config, job, "Smoke_Test", closed_check=lambda: None)
        self.assertEqual((self.config.capcut_root / "root_meta_info.json").read_bytes(), original)
        self.assertTrue((self.config.capcut_root / "Smoke_Test").exists())
        self.assertEqual(
            len(list((self.config.work_root / "backups").glob("*/deployment-interrupted.json"))), 1
        )

    def test_concurrent_registration_preserves_project_and_edits(self):
        job = self.stage()
        index = self.config.capcut_root / "root_meta_info.json"
        destination = self.config.capcut_root / "Smoke_Test"
        count = 0

        def concurrent():
            nonlocal count
            count += 1
            if count == 3:
                root = read_json(index)
                root["all_draft_store"].append({"draft_fold_path": destination.as_posix()})
                index.write_text(json.dumps(root))
                (destination / "user-edit.txt").write_text("Preserve this concurrent edit")

        with self.assertRaises(ToolkitError):
            deploy(self.config, job, "Smoke_Test", closed_check=concurrent)
        self.assertTrue((destination / "user-edit.txt").is_file())
        self.assertEqual(
            read_json(index)["all_draft_store"][-1]["draft_fold_path"], destination.as_posix()
        )

    def test_doctor_rejects_unregistered_template(self):
        index = self.config.capcut_root / "root_meta_info.json"
        index.write_text('{"all_draft_store":[]}')
        self.assertFalse(doctor(self.config)["checks"]["project_index"]["ok"])

    @unittest.skipUnless(os.name == "nt", "Windows junction regression")
    def test_junctions_rejected_before_writing(self):
        import _winapi

        self.config.work_root.mkdir()
        target = self.config.media_root / "protected"
        target.mkdir()
        builds = self.config.work_root / "builds"
        _winapi.CreateJunction(str(target), str(builds))
        try:
            with self.assertRaises(ToolkitError):
                self.stage()
            self.assertEqual(list(target.iterdir()), [])
        finally:
            builds.rmdir()
        job = self.stage()
        backups = self.config.work_root / "backups"
        _winapi.CreateJunction(str(target), str(backups))
        try:
            with self.assertRaises(ToolkitError):
                deploy(self.config, job, "Smoke_Test", closed_check=lambda: None)
            self.assertEqual(list(target.iterdir()), [])
            self.assertFalse((self.config.capcut_root / "Smoke_Test").exists())
        finally:
            backups.rmdir()

    @unittest.skipUnless(os.name == "nt", "Windows path length regression")
    def test_long_paths_rejected_before_staging(self):
        config = Config(
            self.config.media_root,
            self.config.capcut_root,
            self.config.native_template,
            self.config.work_root / ("x" * 180),
            self.config.vectcut_path,
        )
        with self.assertRaisesRegex(ToolkitError, "shorter work_root"):
            build(config, self.plan)
        self.assertFalse(config.work_root.exists())

    def test_config_no_overlapping_work_root(self):
        path = Path(self.temp.name) / "config.json"
        data = {key: str(value) for key, value in vars(self.config).items()}
        write_json(path, data)
        self.assertEqual(Config.load(path), self.config)
        data["work_root"] = str(self.config.media_root / "local")
        path.write_text(json.dumps(data))
        with self.assertRaises(ToolkitError):
            Config.load(path)

    def test_path_id_injection(self):
        project = self.config.native_template / "Timelines/project.json"
        data = read_json(project)
        data["main_timeline_id"] = "../../elsewhere"
        project.write_text(json.dumps(data))
        with self.assertRaises(ToolkitError):
            inspect_template(self.config.native_template)


if __name__ == "__main__":
    unittest.main()
