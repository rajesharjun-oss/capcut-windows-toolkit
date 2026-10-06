# Release Validation

Version 0.1.0 was checked on Windows with Python 3.11.9 and the VectCutAPI revision
recorded in upstream.json.

- 46 core tests passed, including Windows short-path handling, junction rejection, interrupted
  deployment, concurrent edits, filename timing and stream coverage checks.
- The optional real-engine integration test passed with generated video, audio
  and a still image. Deployment used an isolated synthetic project root.
- The setup script completed successfully using the pinned upstream and an
  existing Python/FFmpeg installation. A clean-machine installer was not tested.
- A build using a real, empty Windows CapCut 9.5.0 template passed staging and
  seven-mirror verification. The source template stayed unchanged. That build
  was not deployed to the installed CapCut project store during release testing.
- Lint, formatting, type checking, compilation, package build, skill validation,
  runtime dependency audit and publication privacy scan passed locally.

An independent agent also exercised separate winner announcement/celebration
ranges, a full-section caption and overlapping music using synthetic media and
the real engine. Findings from that review have regression tests.

These checks do not establish rendered typography, transition appearance,
successful playback on every installation, media quality or a universal CapCut
format contract. Every new installation must complete the one-clip open/playback
test before a larger edit. There is no bundled unattended rendering test.

The supported distribution is a repository checkout. Package builds are checked
for integrity; a wheel alone does not include the workflow skill, examples or
pinned upstream checkout. Use the repository setup instructions.
