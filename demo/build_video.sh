#!/bin/sh
# Build the Mulligan demo video from its three VHS segments.
#
#   ./demo/build_video.sh
#
# Segments are rendered separately because VHS drops idle frames: a single tape
# compresses the long beats and leaves the diff on screen for about a second.
# Recording them apart gives each beat a deterministic hold.
#
# Requires: vhs, ttyd, ffmpeg. Under root the VHS headless browser needs
# --no-sandbox (wrap the rod Chromium binary accordingly).
set -eu
cd "$(dirname "$0")/.."

vhs demo/tape-a.tape
vhs demo/tape-b.tape      # live chat; creates the branch that segment C diffs
vhs demo/tape-c.tape

printf "file '%s'\n" "$PWD/demo/.seg-a.mp4" "$PWD/demo/.seg-b.mp4" "$PWD/demo/.seg-c.mp4" > /tmp/mulligan-concat.txt
ffmpeg -v error -y -f concat -safe 0 -i /tmp/mulligan-concat.txt -c copy demo/mulligan-90s.mp4

ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 demo/mulligan-90s.mp4
echo "wrote demo/mulligan-90s.mp4 (add narration with the command in demo/narration_timings.txt)"
