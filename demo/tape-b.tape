# Segment B — rewind / edit / play in a real chat session
Output demo/.seg-b.mp4
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

Type "echo '  Rewind to step 13, edit the decision, replay in a fresh child session.'; echo"
Enter
Sleep 2s
Type "cd /tmp/mulligan-demo-workspace && hermes chat --provider openrouter --model '~anthropic/claude-sonnet-latest' --query-file /root/mulligan/demo/query.txt --oneshot"
Enter
Sleep 40s
Sleep 2s
