@echo off
rem ASTS trigger watch - fast lane (phase B, OFF until tested). Set Rules "fire cmd" = C:\Users\rayon\Desktop\cld1\fire_lane.bat
rem Runs one sub-only Claude session on this PC that re-scores the Trade Map on the newest Hits row and fires the cloud Trader.
rem Zero API key; the session uses the logged-in Claude Code CLI (Max sub). One credit-costing run per fire.
set CLD1=C:\Users\rayon\Desktop\cld1
cd /d %CLD1%
set ANTHROPIC_API_KEY=
type "%CLD1%\fire_lane_prompt.md" | claude -p --dangerously-skip-permissions >> "%CLD1%\fire_lane.log" 2>&1
