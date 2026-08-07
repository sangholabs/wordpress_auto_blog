"""값을 출력하지 않고 Git 추적 후보와 전체 이력의 고신뢰 비밀키를 검사한다."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

from .config import ROOT

PATTERNS = {
    "OpenAI API key": re.compile(r"\bsk-(?!your|example)[A-Za-z0-9_-]{20,}"),
    "Anthropic API key": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    "Supabase secret": re.compile(r"\bsb_secret_[A-Za-z0-9_-]{10,}"),
    "JWT": re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
}


def _find(data: bytes, path: str) -> list[dict]:
    if len(data) > 2_000_000 or b"\x00" in data:
        return []
    findings = []
    for line_number, line in enumerate(data.decode("utf-8", "ignore").splitlines(), 1):
        for label, pattern in PATTERNS.items():
            if pattern.search(line):
                findings.append({"kind": label, "path": path, "line": line_number})
    return findings


def scan_worktree(root: Path = ROOT) -> list[dict]:
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
    )
    findings = []
    for raw in output.split(b"\0"):
        if not raw:
            continue
        relative = raw.decode("utf-8", "surrogateescape")
        path = root / relative
        if path.is_file():
            try:
                findings.extend(_find(path.read_bytes(), relative))
            except OSError:
                continue
    return findings


def scan_history(root: Path = ROOT) -> list[dict]:
    revisions = subprocess.check_output(["git", "rev-list", "--all"], cwd=root, text=True).splitlines()
    unique = set()
    for revision in revisions:
        paths = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", revision], cwd=root, text=True,
        ).splitlines()
        for path in paths:
            try:
                data = subprocess.check_output(
                    ["git", "show", f"{revision}:{path}"], cwd=root, stderr=subprocess.DEVNULL,
                )
            except subprocess.CalledProcessError:
                continue
            for finding in _find(data, path):
                unique.add((finding["kind"], finding["path"], finding["line"]))
    return [
        {"kind": kind, "path": path, "line": line}
        for kind, path, line in sorted(unique)
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Git 비밀키 노출 검사")
    parser.add_argument("--history", action="store_true", help="전체 Git 이력까지 검사")
    args = parser.parse_args(argv)
    findings = scan_history() if args.history else scan_worktree()
    if findings:
        print(f"잠재 비밀값 {len(findings)}건을 발견했습니다. 값은 표시하지 않습니다.")
        for item in findings:
            print(f"- {item['kind']}: {item['path']}:{item['line']}")
        return 1
    print("고신뢰 비밀키 패턴: 발견 없음")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
