@echo off
rem ASTS trigger watch - always-on 2-min poller. Started by Task Scheduler (asts-trigger-watch) or ACTA.
rem Exits at once if another instance is alive (pid check). pythonw = no console window.
set CLD1=C:\Users\rayon\Desktop\cld1
cd /d %CLD1%
set ANTHROPIC_API_KEY=
pythonw "%CLD1%\asts_trigger_watch.py" %*
