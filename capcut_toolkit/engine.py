"""Thin adapter around the pinned VectCutAPI local draft library."""

import json
import sys
from pathlib import Path
from uuid import uuid4

from .config import REVISION
from .plan import music_envelope
from .safety import ToolkitError, run


def load_engine(repo: Path):
    if not (repo / "pyJianYingDraft").is_dir():
        raise ToolkitError("VectCutAPI is missing. Run scripts/setup.ps1.")
    revision = run(["git", "-C", str(repo), "rev-parse", "HEAD"]).strip()
    if revision != REVISION:
        raise ToolkitError("VectCutAPI is not at the tested pinned revision.")
    run(
        [
            "git",
            "-C",
            str(repo),
            "diff",
            "--exit-code",
            "HEAD",
            "--",
            "pyJianYingDraft",
            "draft_profiles.py",
            "settings",
        ]
    )
    sys.path.insert(0, str(repo))
    import settings
    import settings.local

    settings.IS_CAPCUT_ENV = True
    settings.local.IS_CAPCUT_ENV = True
    import pyJianYingDraft

    return pyJianYingDraft


def generate(plan: dict, repo: Path, paths: dict[str, Path]) -> dict:
    d = load_engine(repo)
    from draft_profiles import get_draft_profile

    canvas = plan["canvas"]
    script = d.Script_file(canvas["width"], canvas["height"], canvas["fps"])
    script.add_track(d.Track_type.video, "main")
    visuals = {}
    for item in plan["clips"]:
        relative = item["file"]
        if relative not in visuals:
            info = item["media"]
            material = d.Video_material(
                "photo" if info["kind"] == "image" else "video",
                path=str(paths[relative]),
                material_name=Path(relative).name,
                duration=info["duration"],
                width=info["width"],
                height=info["height"],
            )
            # Upstream derives IDs from basenames; different folders can share a basename.
            material.material_id = uuid4().hex
            material.width, material.height = info["width"], info["height"]
            visuals[relative] = material
        segment = d.Video_segment(
            visuals[relative],
            d.Timerange(item["start"], item["duration"]),
            source_timerange=d.Timerange(item["source_start"], item["source_duration"]),
            speed=item["speed"],
            volume=item["volume"],
            clip_settings=d.Clip_settings(rotation=item["rotation"]),
        )
        if item["background"] == "blur":
            segment.add_background_filling("blur")
        if item["transition"] != "cut":
            transition = (
                d.CapCut_Transition_type.Mix
                if item["transition"] == "mix"
                else d.CapCut_Transition_type.Black_Fade
            )
            segment.add_transition(transition, duration=item["transition_duration"])
        if item["fade_in"]:
            segment.add_keyframe(d.Keyframe_property.alpha, 0, 0)
            segment.add_keyframe(d.Keyframe_property.alpha, item["fade_in"], 1)
        if item["fade_out"]:
            segment.add_keyframe(d.Keyframe_property.alpha, item["duration"] - item["fade_out"], 1)
            segment.add_keyframe(d.Keyframe_property.alpha, item["duration"], 0)
        script.add_segment(segment, "main")
    speech = [
        (item["start"], item["start"] + item["duration"])
        for item in plan["clips"]
        if item["speech"]
    ]
    for index, cue in enumerate(plan["music"]):
        material = d.Audio_material(
            path=str(paths[cue["file"]]),
            material_name=Path(cue["file"]).name,
            duration=cue["media"]["duration"],
        )
        material.material_id = uuid4().hex
        track = f"music_{index + 1}"
        script.add_track(d.Track_type.audio, track)
        segment = d.Audio_segment(
            material,
            d.Timerange(cue["start"], cue["duration"]),
            source_timerange=d.Timerange(cue["source_start"], cue["source_duration"]),
            volume=1.0,
        )
        for offset, volume in music_envelope(cue, speech):
            segment.add_keyframe(offset, volume)
        script.add_segment(segment, track)
    if plan["captions"]:
        script.add_track(d.Track_type.text, "captions")
    for cue in plan["captions"]:
        position = cue["position"]
        segment = d.Text_segment(
            cue["text"],
            d.Timerange(cue["start"], cue["duration"]),
            style=d.Text_style(
                size=cue["size"], bold=True, align=0 if position == "top-left" else 1
            ),
            clip_settings=d.Clip_settings(
                transform_x=0,
                transform_y={"top-left": 0.72, "center": 0, "lower-third": -0.6}[position],
            ),
            border=d.Text_border(width=0.02),
            fixed_width=round(canvas["width"] * 0.8),
        )
        script.add_segment(segment, "captions")
    content = json.loads(script.dumps(get_draft_profile("capcut_legacy")))
    if content["duration"] != plan["duration"]:
        raise ToolkitError("Draft engine duration does not match the validated edit plan.")
    return content
