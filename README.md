# CapCut Windows Toolkit

Create editable CapCut Desktop drafts from explicit edit plans, with a reusable
Codex skill and native Windows deployment checks.

**Status: experimental 0.1.0.** This is a local, plan-driven toolkit, not an
official CapCut product, hosted editor, automatic highlight selector, or finished
Windows companion installer. It builds on [VectCutAPI](https://github.com/sun-guannan/VectCutAPI)
at a pinned commit and uses a native empty CapCut project as the compatibility
shell. It does not run VectCutAPI's HTTP server.

## Supported Environment

- Windows with locally installed **CapCut Desktop 9.5.0**.
- Native Windows Codex session / PowerShell with access to approved folders.
- Python 3.11 recommended; package requires Python 3.11+.
- Git and FFmpeg (ffmpeg and ffprobe) on PATH.
- A new, empty, single-timeline project created by the user's CapCut.
- Local media, with enough free space to copy used source files into each draft.

Other CapCut versions are deliberately rejected pending testing. This is an
unofficial native-draft integration; an application update can break it. No
CapCut binaries, native user templates, fonts, songs or event media are bundled.

## Start With Codex

Clone/open this repository as a local project in Codex. Paste:

> Read README.md and AGENTS.md and use the capcut-editor skill. Inspect the setup
> script, set up dependencies with my permission, and ask me to select my media
> folder and empty native CapCut template. Run doctor and create a separate
> one-clip test before editing my event. Preserve originals and existing projects.

The skill is in .agents/skills/capcut-editor/SKILL.md. It is repository-scoped,
not silently installed globally. A cloud-only session cannot directly open
CapCut on your PC; use a local Windows session. Desktop UI tools are optional:
without them, the user performs preview and export in CapCut.

## Setup

Install prerequisites from [Python for Windows](https://www.python.org/downloads/windows/),
[Git for Windows](https://git-scm.com/install/windows), and the Windows build
providers linked by [FFmpeg](https://ffmpeg.org/download.html). Use Python 3.11
with the py launcher enabled. Ensure git, ffmpeg and ffprobe are on PATH, then
restart PowerShell. Setup does not silently install these system tools.

Use a short checkout/work directory. Generated filenames are checked against
Windows path limits before copying. Do not change system security policy to
work around an overly long path; shorten work_root instead.

Review scripts/setup.ps1 and upstream.json, then run from this repository:

    .\scripts\setup.ps1
    Copy-Item config.example.json config.local.json

The script creates .venv, fetches the pinned upstream into vendor/, installs
only the local engine's locked dependencies, and runs tests. It does not install
CapCut, alter PowerShell execution policy, open network ports or modify drafts.
If execution policy blocks it, follow your organization's policy; do not disable
security controls. Python/dependency downloads require network permission.

In CapCut, create an empty project named Toolkit_Empty_Template, return home,
and close CapCut. Set the actual folder path in config.local.json. Set
media_root to the selected event folder. Environment variables are supported;
relative config paths resolve against the config file, not the terminal folder.

    .\.venv\Scripts\python.exe -m capcut_toolkit doctor
    .\.venv\Scripts\python.exe -m capcut_toolkit inventory --output local\inventory.json

Doctor reads but does not modify CapCut. Without a config, it checks system tools
only. With a config, it also checks the native template, engine and project index.

## One-Clip Test

Put a short authorized sample.mp4 (at least five seconds) in your media folder,
or copy examples/one-clip.json into local/ and edit its relative filename.

    .\.venv\Scripts\python.exe -m capcut_toolkit validate --plan examples\one-clip.json
    .\.venv\Scripts\python.exe -m capcut_toolkit build --plan examples\one-clip.json

Build prints a job directory. It creates staged files only. Inspect its
resolved-plan.json, then substitute that returned path below:

    .\.venv\Scripts\python.exe -m capcut_toolkit verify --job local\builds\JOB_ID
    # Save and close CapCut first. Explicitly approve this new project.
    .\.venv\Scripts\python.exe -m capcut_toolkit deploy --job local\builds\JOB_ID --confirm Toolkit_OneClip_Test

Open CapCut and verify the clip, title, orientation and playback. JSON checks are
not proof of successful rendering. Do not proceed to a large edit until this test
opens on the target computer.

## Build An Event

Have Codex review selected footage and create local/event-plan.json using
[the edit-plan format](docs/edit-plans.md). examples/event-plan.json illustrates
the structure; its filenames are illustrative, not bundled footage.

Run the same validate/build/verify/deploy sequence. Each revision must use a new
project name, for example Event_Highlight_Review_02. There is no overwrite flag.
Keep captions for the full intended section using explicit start/end times.
Use [editing guidance](docs/editing-guide.md) for review, not as a promise of
automatic artistic judgment. [The optional KP preset](presets/kp-trad-day.md)
preserves the latest approved event direction without distributing private media.

### Included

- Relative-path media inventory with ffprobe metadata and filename timing notes.
- Explicit video/image sequence, source trims, multiple ranges per source, speed,
  original audio, rotation, optional blur fill, simple transitions and fades.
- Music source offsets, validated 1-1.5 second overlapping crossfades, automatic
  muting under clips explicitly marked as speech with 0.5 second fade shoulders.
- Whole-section captions, bounded text size and safe-width layout defaults.
- Native root/nested timeline mirrors, project metadata, copied assets,
  integrity manifest and create-only index registration.

### Not Included

- Automatic identification of people, winners or the "best" footage.
- Automatic beat detection, music licensing/downloads, AI cloud analysis.
- Arbitrary existing-draft editing, unattended desktop export, or universal
  CapCut version support. Mixing/orientation/typography need rendered review.
- A web service, public API, account system or installer.

## Safety And Recovery

Original media is read-only. Each draft contains copies of used full source files;
source trims are nondestructive. Symlinks, junctions, remote media URLs, traversal
paths, malformed plans and unexpected template types are rejected.

Deployment requires CapCut to be closed, verifies the staged file hashes, refuses
existing project names, backs up root_meta_info.json under local/backups/,
checks for concurrent changes, then registers the new project. Failed copies are
retained for diagnosis instead of deleting data. A race with a separately launched
CapCut cannot be eliminated completely; keep CapCut closed during deployment.

To undo a successful deployment, remove only the newly created project through
CapCut. Do not restore an old global index after other projects have changed.
For an interrupted deployment or a stale toolkit lock, see recovery.json in the
specific backup and review the state before taking action.

Plans, inventories, native templates, logs and projects may contain personal data.
Keep them in ignored local folders. Do not attach them to public issues without
redaction. See [SECURITY.md](SECURITY.md).

## Verification And Contribution

    .\.venv\Scripts\python.exe -m unittest discover -s tests -v
    .\.venv\Scripts\python.exe -m compileall -q capcut_toolkit
    .\.venv\Scripts\python.exe -m pip check

See [CONTRIBUTING.md](CONTRIBUTING.md) for lint/type/build/security checks and
compatibility evidence. Tests use synthetic fixtures; no private media is needed.
Read [release validation](docs/validation.md) for what was and was not tested.

## Attribution

Toolkit code is licensed under Apache-2.0. VectCutAPI is separately fetched at the
commit in upstream.json; its Apache-2.0 license and notices remain with that
checkout. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). CapCut is a third-party
application; this project is not affiliated with or endorsed by its publisher.
