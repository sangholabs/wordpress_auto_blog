@echo off
REM daily pipeline run for Task Scheduler
set PYTHONUTF8=1
cd /d %~dp0
if not exist logs mkdir logs
".\.venv\Scripts\python.exe" -m src.pipeline >> logs\pipeline.log 2>&1
