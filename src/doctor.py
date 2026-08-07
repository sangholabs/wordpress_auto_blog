"""게시·유료 생성 없이 WordPress·티스토리 실행 준비 상태를 점검한다."""

from __future__ import annotations

import argparse
import importlib.metadata
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

import requests
from requests.auth import HTTPBasicAuth

from . import policy_schedule_task, schedule_task
from .config import ROOT, env, get_settings
from .policy_sources import GOV24_LIST_URL, _gov24_get
from .policy_storage import verify_status
from .secret_scan import scan_worktree

DEPENDENCIES = (
    "requests", "python-dotenv", "PyYAML", "beautifulsoup4", "playwright",
    "google-genai", "anthropic", "openai", "Markdown", "pytest",
)


class Report:
    def __init__(self) -> None:
        self.failed = 0
        self.warned = 0

    def item(self, level: str, label: str, detail: str) -> None:
        print(f"[{level}] {label}: {detail}")
        if level == "FAIL":
            self.failed += 1
        elif level == "WARN":
            self.warned += 1


def _offline(report: Report) -> None:
    version = sys.version_info
    report.item("PASS" if version >= (3, 12) else "FAIL", "Python", platform.python_version())
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    report.item("PASS" if in_venv else "WARN", "가상환경", sys.prefix)
    missing = []
    for package in DEPENDENCIES:
        try:
            importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            missing.append(package)
    report.item("PASS" if not missing else "FAIL", "Python 의존성", "정상" if not missing else "누락: " + ", ".join(missing))
    try:
        settings = get_settings()
        assert isinstance(settings.get("publish"), dict)
        assert isinstance(settings.get("policy_workspace"), dict)
    except Exception as exc:
        report.item("FAIL", "설정 YAML", str(exc))
        settings = {}
    else:
        local = ROOT / "config" / "settings.local.yaml"
        report.item("PASS", "설정 YAML", f"기본+{'로컬 병합' if local.exists() else '기본값'}")
    scripts = [ROOT / "control.sh", ROOT / "run.sh", ROOT / "run.bat", ROOT / "policy_run.bat"]
    absent = [path.name for path in scripts if not path.is_file()]
    report.item("PASS" if not absent else "FAIL", "실행 스크립트", "정상" if not absent else "누락: " + ", ".join(absent))
    if platform.system() != "Windows":
        not_executable = [path.name for path in scripts[:2] if path.exists() and not os.access(path, os.X_OK)]
        report.item("PASS" if not not_executable else "FAIL", "셸 실행권한", "정상" if not not_executable else "누락: " + ", ".join(not_executable))
    provider = env("LLM_PROVIDER", "claude_code")
    provider_ready = {
        "anthropic": bool(env("ANTHROPIC_API_KEY")),
        "gemini": bool(env("GEMINI_API_KEY")),
        "claude_code": bool(shutil.which("claude")),
    }.get(provider, False)
    report.item("PASS" if provider_ready else "FAIL", "글 생성 엔진", provider)
    wp_missing = [key for key in ("WP_SITE_URL", "WP_USERNAME", "WP_APP_PASSWORD") if not env(key)]
    report.item("PASS" if not wp_missing else "WARN", "WordPress 설정", "완료" if not wp_missing else "누락: " + ", ".join(wp_missing))
    policy_missing = [key for key in ("DATA_GO_KR_API_KEY",) if not env(key)]
    policy_cfg = settings.get("policy_workspace", {})
    if (
        policy_cfg.get("images_enabled", True)
        and policy_cfg.get("image_provider", "openai") == "openai"
        and not env("OPENAI_API_KEY")
    ):
        policy_missing.append("OPENAI_API_KEY")
    if policy_cfg.get("supabase_upload_enabled", True):
        for key in ("SUPABASE_URL",):
            if not env(key):
                policy_missing.append(key)
        if not any(env(key) for key in ("SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_ANON_KEY")):
            policy_missing.append("SUPABASE API key")
    report.item("PASS" if not policy_missing else "WARN", "티스토리 정책 설정", "완료" if not policy_missing else "누락: " + ", ".join(policy_missing))
    report.item("PASS", "WordPress 예약", "켜짐" if schedule_task.status() else "꺼짐")
    report.item("PASS", "티스토리 예약", "켜짐" if policy_schedule_task.status() else "꺼짐")
    findings = scan_worktree()
    report.item("PASS" if not findings else "FAIL", "Git 비밀값", "발견 없음" if not findings else f"잠재 위치 {len(findings)}건(값 숨김)")
    try:
        branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
        report.item("WARN" if dirty else "PASS", "Git 상태", f"{branch or 'detached'} / {'변경 있음' if dirty else '깨끗함'}")
    except (OSError, subprocess.CalledProcessError) as exc:
        report.item("WARN", "Git 상태", str(exc))


def _live(report: Report) -> None:
    try:
        items = _gov24_get(GOV24_LIST_URL, {"page": 1, "perPage": 1})
        report.item("PASS" if items else "FAIL", "보조금24 API", f"정상 응답 {len(items)}건")
    except Exception as exc:
        report.item("FAIL", "보조금24 API", str(exc))
    state = verify_status()
    report.item(
        "PASS" if state.get("verified") and state.get("public") else "FAIL",
        "Supabase Storage",
        f"bucket={state.get('bucket')} / public={state.get('public')}" + (f" / {state.get('error')}" if state.get("error") else ""),
    )
    site = env("WP_SITE_URL").rstrip("/")
    if not site:
        report.item("FAIL", "WordPress REST", "WP_SITE_URL 누락")
        return
    try:
        response = requests.get(
            f"{site}/wp-json/wp/v2/users/me",
            auth=HTTPBasicAuth(env("WP_USERNAME"), env("WP_APP_PASSWORD").replace(" ", "")),
            timeout=20,
        )
    except requests.RequestException as exc:
        report.item("FAIL", "WordPress REST", str(exc))
    else:
        report.item(
            "PASS" if response.status_code == 200 else "FAIL",
            "WordPress REST",
            f"HTTP {response.status_code} ({urlsplit(site).hostname})",
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WordPress·티스토리 읽기 전용 통합 진단")
    parser.add_argument("--live", action="store_true", help="외부 서비스를 읽기 전용으로 확인")
    args = parser.parse_args(argv)
    report = Report()
    print("=== WordPress·티스토리 프로젝트 진단 ===")
    _offline(report)
    if args.live:
        print("--- 외부 서비스 읽기 전용 검사 ---")
        _live(report)
    print(f"진단 완료: 실패 {report.failed} / 경고 {report.warned}")
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
