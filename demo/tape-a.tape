# Segment A — title, mg_list, mg_inspect
Output demo/.seg-a.mp4
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

Type "clear; echo '  MULLIGAN'; echo '  Take a mulligan on any Hermes decision.'; echo; echo '  A recorded run: 15 steps, and it breaks at step 13.'"
Enter
Sleep 4s
Type "clear"
Enter
Type "python3 demo/mg.py list"
Enter
Sleep 3s
Type "python3 demo/mg.py inspect r_demo_deploy"
Enter
Sleep 8s
