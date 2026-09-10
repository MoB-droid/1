@echo off
rem ASTS Trigger Watch - continuous poller (2 min loop). Started by ACTA / Task Scheduler.
rem Exits immediately if another instance is already running (pid check).
set CLD1=C:\Users\rayon\Desktop\cld1
cd /d %CLD1%
set ANTHROPIC_API_KEY=
python "%CLD1%\asts_trigger_watch.py" %*
