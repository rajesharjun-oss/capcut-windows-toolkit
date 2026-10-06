# Editorial And Export Review

Use this as a checklist, not a fixed story for every event.

1. Confirm audience, duration, aspect ratio and must-include moments. This release
   supports landscape drafts. Ask for identities/roles only when labels need them.
2. Inventory sources, then inspect representative decoded frames and listen to
   important sound. Folder names and timestamps are hints, not proof of content.
3. Select a varied sequence: establishing views, details, people, action,
   reactions and a coherent finish. Do not fill duration with repeated footage.
4. Match source audio and music to intent. Speech/announcements need intelligible
   original sound. Use authorized music; source timestamps differ from timeline
   timestamps. Review both sides of every song crossfade.
5. Use clean cuts for speech, deliberate rhythm cuts for dancing, and restrained
   short mixes for slower walks. Do not imply beat matching without measuring or
   listening. CapCut may need to download built-in transition resources.
6. Keep captions inside safe margins, consistent in size and aligned as a block.
   Let them last for the entire named section. Preview long text and different fonts.
7. Photos can serve as brief b-roll, not replace a motion-driven edit. Subtle
   photo animation can be adjusted in CapCut; this CLI does not automate Ken Burns.
8. Review the entire CapCut timeline before export. Check missing assets,
   orientation, frozen/black frames, clipped captions, music offsets, announcement
   audibility and winner celebration coverage.

## Export

Export a master in CapCut at the project resolution/fps, with appropriate quality
for the destination. Keep that master. The repository does not contain a
version-fragile UI-click exporter or claim unattended rendering.

For a smaller delivery copy, use FFmpeg with an explicit, new output filename:

    ffmpeg -n -i "master.mp4" -map 0:v:0 -map 0:a? -c:v libx264 -preset slow -crf 20 -c:a aac -b:a 192k -movflags +faststart "delivery.mp4"

This is lossy recompression, not lossless compression. Inspect demanding motion,
fabric details and captions; compare audio and duration. Do not overwrite the
master. Use lower CRF for higher quality/larger output after a short sample test.
Codec licensing/distribution and music rights remain the user's responsibility.
