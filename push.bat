@echo off
REM 변경분을 add → commit → push 한다. 더블클릭 또는 터미널에서 실행.
cd /d %~dp0
git add .
git commit -m "핸드오프·컨텍스트 노트 추가(개인정보 제거), 배너 레이아웃 per_h2 확정"
git push
echo.
echo === 완료. 위 결과를 확인하세요 ===
pause
