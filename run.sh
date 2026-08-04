#!/bin/zsh
set -eu

PROJECT_DIR=${0:A:h}
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  print -u2 "[오류] macOS 가상환경을 찾을 수 없습니다. SETUP.md를 확인하세요."
  exit 1
fi

export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
mkdir -p "$PROJECT_DIR/logs"
cd "$PROJECT_DIR"
exec "$PYTHON_BIN" -m src.pipeline "$@"
