# Security

This release is a local CLI. It has no network listener, accounts, authentication
service, uploads, telemetry or remote command execution endpoint. Do not expose
VectCutAPI's development HTTP service as a public API.

- Review the code and pinned upstream before setup. Dependencies are executable
  code; run with ordinary user privileges, not an administrator terminal.
- Use trusted media and a patched FFmpeg build. Media parsing is not a hardened
  sandbox; hostile files should be inspected in an isolated environment.
- Only explicitly approved media roots are read. File references cannot use URLs,
  absolute paths, traversal, symlinks/junctions or NTFS alternate streams.
- Native templates are user-provided, empty, single-timeline Windows 9.5.0 drafts.
- Deployment only creates new projects; it checks process state and races, hashes
  staged files and copies, and backs up the project index.
- If a conflict occurs after the new folder is installed, that folder remains
  in place for manual reconciliation. Recovery notes are written to the backup
  folder. Never blindly restore an old index or delete a potentially edited draft.
- Do not run while CapCut is editing the template or during deployment. Never
  force-kill the editor to bypass a safety check.
- Runtime state belongs in ignored local/. No secrets or personal projects belong
  in Git. Keep logs and inventory filenames out of public support reports.
- There is no guarantee against a malicious local administrator or another
  process modifying files between checks. Local machine integrity is assumed.

Report security concerns privately using the repository's private vulnerability
reporting feature when enabled, or contact the maintainer privately. Do not include
raw footage, tokens, project indexes or full personal paths in public issues.

A future hosted bridge would need authentication, device pairing, per-job
authorization, rate limits and storage isolation. This CLI must not be reused as
an unauthenticated web backend.
