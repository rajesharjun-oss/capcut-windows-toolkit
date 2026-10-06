# Development

Keep VectCutAPI pinned. Do not vendor someone's native project as a test fixture.
Tests use small synthetic native shells and generated media only.

Run core checks:

    python -m unittest discover -s tests -v
    python -m compileall -q capcut_toolkit
    python -m pip check

Development tooling is optional for end users. Install the exact versions in
requirements-dev.lock, then run:

    python -m ruff check .
    python -m ruff format --check .
    python -m mypy capcut_toolkit
    python -m build
    python -m pip_audit -r requirements.lock
    python scripts/check_release.py

Run the optional real-engine test in PowerShell after setup:

    $env:CAPCUT_TOOLKIT_ENGINE = (Resolve-Path vendor\VectCutAPI).Path
    python -m unittest discover -s tests -p test_engine_integration.py -v

This generates synthetic audio, video and an image with FFmpeg and deploys only
to a fabricated project root in a temporary directory. It never opens CapCut or
changes installed projects. CI repeats this integration on Linux; Windows CI
also exercises junction rejection, native metadata and deployment conflicts.

## Compatibility Changes

Add a tested adapter rather than falsifying app_version to bypass compatibility.
Use an empty native project produced by that installation, test source/audio
ranges and all timeline mirrors, and observe the new project open in CapCut.
Record OS, CapCut version, Python version and whether export was visually checked.
Do not advertise untested versions. Rendered typography/effects require UI review.

## Release

Run tests and release scanning before staging, then inspect git diff --cached.
Never force-add local/, vendor/, .venv, media or config.local.json. Public examples
use invented filenames. No workflow uploads local diagnostics automatically.
The scanner is defense in depth, not a substitute for a manual privacy review.
