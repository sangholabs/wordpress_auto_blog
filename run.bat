@echo off
REM daily pipeline run for Task Scheduler
cd /d %~dp0
".\.venv\Scripts\python.exe" -m src.pipeline >> logs\pipeline.log 2>&1
