@echo off
REM Tistory policy package runner for Windows Task Scheduler
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d %~dp0
if not exist logs mkdir logs
".\.venv\Scripts\python.exe" -m src.policy_runner >> logs\policy_pipeline.log 2>&1
