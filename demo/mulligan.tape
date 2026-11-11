# Mulligan — 90s demo tape (VHS)
# Record with:  cd /root/mulligan && vhs demo/mulligan.tape
# Only single quotes appear inside Type strings: VHS ends a Type payload at the first
# double quote, so the chat beat reads its prompt from demo/query.txt.

Output demo/mulligan-90s.mp4

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
Sleep 5s
Type "clear"
Enter

Type "python3 demo/mg.py list"
Enter
Sleep 4s

Type "python3 demo/mg.py inspect r_demo_deploy"
Enter
Sleep 10s

Type "clear"
Enter
Type "echo '  Rewind to step 13, edit the decision, replay in a fresh child session.'; echo"
Enter
Sleep 3s

Type "cd /tmp/mulligan-demo-workspace && hermes chat --provider openrouter --model '~anthropic/claude-sonnet-latest' --query-file /root/mulligan/demo/query.txt --oneshot"
Enter
Wait+Screen@90s /Session:/
Sleep 3s

Type "cd /root/mulligan && clear"
Enter
Type "python3 demo/mg.py diff r_demo_deploy latest"
Enter
Sleep 12s

Type "clear"
Enter
Type "clear; echo '  Rewind. Edit. Replay.'; echo '  Take a mulligan on any Hermes decision.'"
Enter
Sleep 5s
