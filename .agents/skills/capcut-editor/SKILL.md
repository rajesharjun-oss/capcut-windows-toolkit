---
name: capcut-editor
description: Build and revise local Windows CapCut event-highlight drafts from user-selected media using this toolkit. Use for source trims, music mixing, captions and native timeline deployment.
---

# CapCut Editor

Use the repository's CLI from its root. This skill supplies an editing workflow,
not desktop control, music licenses, or a hosted renderer.

## Start

1. Read README.md for setup and supported versions. Inspect config.local.json;
   ask for media/template folders if missing. Keep the native empty template and
   personal media outside version control.
2. Run doctor. Fix missing tools using approved installation steps. Do not bypass
   native template/version checks or enlarge filesystem permissions unnecessarily.
3. For a new machine or CapCut update, stage a one-clip project with a short title.
   Have the user save/close CapCut, explicitly authorize deployment, and verify
   the project opens and plays before a larger edit.

## Edit

1. Run inventory into local/. Review representative decoded frames and listen to
   relevant audio with available tools, or ask the user to identify moments.
   Folder names help organize scenes but do not establish identities or winners.
   An inventory alone is not a visual review or automatic highlight selection.
2. Make a JSON plan using docs/edit-plans.md. Preserve explicit source timestamps,
   separate announcement/celebration ranges, and the requested clip order.
   The latest user correction wins; do not import obsolete KP settings.
3. Ask only for consequential unknowns such as must-include moments, music rights,
   roles/names and intended duration. State assumptions. No universal event order.
4. Build the story with varied shot lengths and footage coverage. Read
   docs/editing-guide.md for sound, typography, photo and transition review.
   If the user explicitly wants the KP style, consult presets/kp-trad-day.md;
   it is not a default for unrelated events.
5. Validate, then build. Review resolved-plan.json for source ranges, music source
   offsets, speech muting and caption coverage. CLI time values are seconds;
   01m01s means 61 seconds. Do not confuse source time with timeline position.

## Deploy And Review

- Deploy only a reviewed job, with exact project-name confirmation, while CapCut
  is closed. Each revision needs a new project name; existing drafts are immutable
  to this CLI. Originals remain unchanged and assets are copied into the new draft.
- Use supported desktop tools if available; otherwise ask the user to open and
  review in CapCut. Check orientation, clipping, every caption, song entrances,
  speech audibility and final celebration. Do not assume JSON validity means a
  correctly rendered edit.
- Export in CapCut after review. No unattended UI-export automation is bundled.
  Preserve the editable draft and master export; compression makes a separate file.
- On failure, retain diagnostics locally, explain the specific check, and stop
  before deployment. Do not try alternate paths or overwrite other projects.

Relative documentation paths above refer to the repository root, three levels
above this skill directory. Do not upload local reports in public issue comments.
