"""제어판에서 변경 내용을 검증한 뒤 명시적 확인을 받아 GitHub에 올린다."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime

from .config import ROOT
from .secret_scan import scan_worktree


def _capture(args: list[str]) -> str:
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"{' '.join(args)} 실패: {detail}")
    return result.stdout.strip()


def push_interactive() -> bool:
    branch = _capture(["git", "branch", "--show-current"])
    if not branch:
        raise RuntimeError("현재 Git 브랜치를 확인할 수 없습니다(detached HEAD).")
    remote = _capture(["git", "remote", "get-url", "origin"])
    status = _capture(["git", "status", "--short"])
    print(f"브랜치: {branch}\n원격: {remote}")
    if not status:
        print("올릴 변경이 없습니다.")
        return True
    print("── 변경 파일 ──")
    print(status)
    print("전체 테스트를 실행합니다.")
    tests = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT)
    if tests.returncode != 0:
        print("테스트가 실패해 commit/push를 중단했습니다.")
        return False
    findings = scan_worktree()
    if findings:
        print("잠재 비밀값이 있어 중단했습니다. 값은 표시하지 않습니다.")
        for item in findings:
            print(f"- {item['kind']}: {item['path']}:{item['line']}")
        return False
    if input("위 변경을 commit하고 origin에 push할까요? (yes 입력): ").strip().lower() != "yes":
        print("GitHub 올리기를 취소했습니다.")
        return False
    message = input("커밋 메시지(비우면 취소): ").strip()
    if not message:
        print("커밋 메시지가 없어 취소했습니다.")
        return False
    subprocess.run(["git", "add", "--all"], cwd=ROOT, check=True)
    commit = subprocess.run(["git", "commit", "-m", message], cwd=ROOT)
    if commit.returncode != 0:
        print("커밋에 실패했습니다. push하지 않았습니다.")
        return False
    push = subprocess.run(["git", "push", "origin", branch], cwd=ROOT)
    if push.returncode != 0:
        print(f"push에 실패했습니다. 로컬 커밋은 남아 있습니다: {datetime.now():%Y-%m-%d %H:%M}")
        return False
    print(f"GitHub push 완료: origin/{branch}")
    return True
