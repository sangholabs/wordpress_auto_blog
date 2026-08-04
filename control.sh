#!/bin/zsh
set -eu

PROJECT_DIR=${0:A:h}
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  print -u2 "[오류] macOS 가상환경을 찾을 수 없습니다."
  print -u2 "SETUP.md에 따라 python3.12 -m venv .venv 후 의존성을 설치하세요."
  exit 1
fi

export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
cd "$PROJECT_DIR"
exec "$PYTHON_BIN" -m src.menu
