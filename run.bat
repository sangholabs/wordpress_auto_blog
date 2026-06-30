@echo off
REM 매일 1회 전체 파이프라인 실행 (작업 스케줄러 등록용)
cd /d %~dp0
".\.venv\Scripts\python.exe" -m src.pipeline >> logs\pipeline.log 2>&1
