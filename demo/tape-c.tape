# Segment C — mg_diff and tagline
Output demo/.seg-c.mp4
Set Shell "bash"
Set Framerate 24
Set FontFamily "JetBrains Mono, DejaVu Sans Mono, monospace"
Set FontSize 15
Set Width 1600
Set Height 900
Set Padding 20
Set Theme "Catppuccin Mocha"
Set TypingSpeed 12ms
Set BorderRadius 6

Hide
Type "export PS1='$ '; cd /root/mulligan; clear"
Enter
Show

Type "python3 demo/mg.py diff r_demo_deploy latest"
Enter
Sleep 10s
Type "clear"
Enter
Type "clear; echo '  Rewind. Edit. Replay.'; echo '  Take a mulligan on any Hermes decision.'"
Enter
Sleep 11s
