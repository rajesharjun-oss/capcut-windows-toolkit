# Edit Plans, Version 1

A plan is JSON, not executable code. Unknown fields and duplicate JSON keys are
errors. All file references must be relative to the configured media_root.
There are no URL fetches or arbitrary command fields.

## Root

version: 1, project_name and clips are required. Optional fields:
canvas, music, captions. Names use ASCII letters, digits, underscores and
hyphens, 1-80 characters, not Windows device names. Canvas defaults to
1920x1080 at 30 fps; 3840x2160 is also supported. Fps: 24, 25, 30, 50 or 60.
Limits: 1000 clips, 100 music cues, 200 captions, total video <=30 minutes.

## Video/Image Clips

Clips play consecutively in array order. file is required.

| Field | Meaning |
|---|---|
| in, out | Source in/out-point; NOT placement on the edited timeline |
| duration | Timeline duration when no out-point exists; default 6s for video, 3s for images |
| range_index | Zero-based filename range to select when multiple ranges exist |
| important_walk | Defaults a start-only excerpt to 8s instead of 6s |
| speed | 0.25-4, default 1; source duration / speed gives timeline duration |
| volume | 0-1, defaults to 0 except speech defaults to 1 |
| speech | true preserves original audio and mutes overlapping music |
| rotation | Clockwise multiples of 90; inspect footage before choosing |
| background | black (default) or blur; do not stretch portrait footage |
| transition | cut (default), mix, black; applies at the following boundary |
| transition_duration | Seconds, default 0.35; at most half either adjacent clip |
| fade_in, fade_out | Opacity fades in seconds; default 0 |
| section | Optional short editorial label, not an on-screen caption |

Do not specify both out and duration. Speech must have an audio stream and normal
speed; speech boundaries use clean cuts. Images accept duration, not source ranges.
Rotation metadata requires an explicit rotation choice after decoded-frame review.
Metadata orientation and a baked-in sideways picture are different problems.

### Time Grammar

- JSON number 61 means 61 seconds.
- "01m01s" and "1:01" also mean 61 seconds, never 1.01.
- Filename "15 to 40 secs": in=15, out=40.
- Filename "stops at 9s": in=0, out=9.
- Filename "from 21 secs": in=21, default 6s (8s for important_walk).
- Filename "start 21s end 31s": in=21, out=31.
- Multiple filename ranges require range_index or explicit in/out.
- Explicit in/out overrides filename notes. Do not silently use the first of
  multiple announcement/celebration ranges.
- Auto-length defaults stop at source end. Explicit ranges/durations beyond the
  available source are errors, not silently clamped.

Two entries may reference the same source at different source ranges. This is
how announcement 61-66s and celebration 70-80s remain separate timeline clips.

## Music

Required: file, in, out, at. at is the edited timeline position.
Optional: volume (default 0.7), fade_in, fade_out (default 1 second each).

Example: a cue at 20s using source 286-315s plays 29 seconds, until timeline 49s.
It does not start at timeline 4:46. For inaccurate seeking/encoder-delay problems,
extract and listen to a separate lossless WAV excerpt, then use that WAV from
zero. Preserve the original. Do not claim a source correction without listening.

To crossfade a 10s song starting at 9s into the next song, start the next at 18s.
Set outgoing fade_out=1 and incoming fade_in=1. Overlaps must be 1-1.5s with
matching fade durations, at most two simultaneous songs. Back-to-back cues
without an overlap are rejected; deliberate silent gaps are allowed.

Music is muted throughout speech-marked footage, fading down in the preceding
0.5s and up in the following 0.5s. A song starting after speech gets the remaining
fade-up shoulder; adjust/listen deliberately if an immediate vocal entry matters.
This does not normalize loudness or guarantee absence of clipping; listen and
adjust cue volume. No automatic beat detection is claimed.

## Captions

Required: text, start, end (timeline times). Optional position is top-left
(default), center, or lower-third; size is a CapCut style value 1-4, default 3.
Captions use a single aligned text block, not separate independently centered
heading/subtitle layers. Up to three lines, each <=48 characters.

Set end to the section's end to persist through all associated shots. Captions
cannot overlap each other or extend past the video. Layout defaults are not
pixel-perfect guarantees: inspect actual font, wrapping, contrast and margins in
CapCut. The CLI does not infer names or automatically label people.
