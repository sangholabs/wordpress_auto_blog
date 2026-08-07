"""티스토리 정책 패키지 자동 생성을 Windows/macOS에 독립 등록한다."""

from __future__ import annotations

import os
import platform
import plistlib
import re
import subprocess
import sys
from pathlib import Path

from .config import ROOT
from . import policy_settings

TASK = "blog-policy-tistory-auto"
LAUNCHD_LABEL = "com.wordpress-auto-blog.policy-tistory"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
PLIST_PATH = LAUNCH_AGENTS_DIR / f"{LAUNCHD_LABEL}.plist"


def _system() -> str:
    return platform.system()


def _schedule_time() -> str:
    value = str(policy_settings.get().get("schedule_time", "09:30"))
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        raise ValueError(f"잘못된 티스토리 자동생성 시각: {value} (HH:MM 형식 필요)")
    return value


def _detail(result: subprocess.CompletedProcess) -> str:
    return (getattr(result, "stderr", "") or getattr(result, "stdout", "") or "").strip()


def _set_enabled(enabled: bool) -> None:
    policy_settings.set_value("auto_generate", enabled)


def _windows_status() -> bool:
    try:
        result = subprocess.run(["schtasks", "/query", "/tn", TASK], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def _windows_action() -> str:
    runner = ROOT / "policy_run.bat"
    return f'cmd.exe /d /c ""{runner}""'


def _windows_on(time_value: str) -> bool:
    python = ROOT / ".venv" / "Scripts" / "python.exe"
    if not python.is_file():
        print("Windows 가상환경 `.venv\\Scripts\\python.exe`를 찾을 수 없습니다.")
        return False
    runner = ROOT / "policy_run.bat"
    if not runner.is_file():
        print("티스토리 예약 실행 파일 `policy_run.bat`을 찾을 수 없습니다.")
        return False
    try:
        result = subprocess.run(
            ["schtasks", "/create", "/tn", TASK, "/tr", _windows_action(),
             "/sc", "daily", "/st", time_value, "/f"],
            capture_output=True, text=True,
        )
    except FileNotFoundError:
        print("schtasks 명령을 찾을 수 없습니다. Windows에서 실행 중인지 확인하세요.")
        return False
    if result.returncode == 0:
        _set_enabled(True)
        print(f"티스토리 자동생성 등록 완료 (Windows, 매일 {time_value})")
        return True
    detail = _detail(result)
    print(f"티스토리 자동생성 등록 실패.{f' ({detail})' if detail else ''}")
    return False


def _windows_off() -> bool:
    if not _windows_status():
        _set_enabled(False)
        print("등록된 Windows 티스토리 자동생성 작업이 없습니다.")
        return True
    try:
        result = subprocess.run(
            ["schtasks", "/delete", "/tn", TASK, "/f"], capture_output=True, text=True
        )
    except FileNotFoundError:
        print("schtasks 명령을 찾을 수 없습니다. Windows에서 실행 중인지 확인하세요.")
        return False
    if result.returncode == 0:
        _set_enabled(False)
        print("티스토리 자동생성 해제됨 (Windows)")
        return True
    print(f"티스토리 자동생성 해제 실패.{f' ({_detail(result)})' if _detail(result) else ''}")
    return False


def _launchd_domain() -> str:
    return f"gui/{os.getuid()}"


def _launchd_target() -> str:
    return f"{_launchd_domain()}/{LAUNCHD_LABEL}"


def _launchd_payload(time_value: str) -> dict:
    hour, minute = (int(part) for part in time_value.split(":"))
    python = ROOT / ".venv" / "bin" / "python"
    log = ROOT / "logs" / "policy_pipeline.log"
    return {
        "Label": LAUNCHD_LABEL,
        "ProgramArguments": [str(python), "-m", "src.policy_runner"],
        "WorkingDirectory": str(ROOT),
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "StandardOutPath": str(log),
        "StandardErrorPath": str(log),
        "EnvironmentVariables": {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"),
            "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
        },
    }


def _launchd_status() -> bool:
    try:
        result = subprocess.run(
            ["launchctl", "print", _launchd_target()], capture_output=True, text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def _launchd_bootout() -> bool:
    try:
        result = subprocess.run(
            ["launchctl", "bootout", _launchd_target()], capture_output=True, text=True
        )
    except FileNotFoundError:
        return False
    return result.returncode == 0


def _launchd_on(time_value: str) -> bool:
    python = ROOT / ".venv" / "bin" / "python"
    if not python.is_file() or not os.access(python, os.X_OK):
        print("macOS 가상환경 `.venv/bin/python`을 찾을 수 없습니다.")
        return False
    if _launchd_status() and not _launchd_bootout():
        print("기존 티스토리 launchd 작업을 해제하지 못했습니다.")
        return False
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    (ROOT / "logs").mkdir(exist_ok=True)
    with open(PLIST_PATH, "wb") as file:
        plistlib.dump(_launchd_payload(time_value), file, sort_keys=False)
    try:
        result = subprocess.run(
            ["launchctl", "bootstrap", _launchd_domain(), str(PLIST_PATH)],
            capture_output=True, text=True,
        )
    except FileNotFoundError:
        PLIST_PATH.unlink(missing_ok=True)
        print("launchctl 명령을 찾을 수 없습니다. macOS에서 실행 중인지 확인하세요.")
        return False
    if result.returncode == 0:
        _set_enabled(True)
        print(f"티스토리 자동생성 등록 완료 (macOS launchd, 매일 {time_value})")
        print(f"로그: {ROOT / 'logs' / 'policy_pipeline.log'}")
        return True
    detail = _detail(result)
    PLIST_PATH.unlink(missing_ok=True)
    print(f"티스토리 자동생성 등록 실패.{f' ({detail})' if detail else ''}")
    return False


def _launchd_off() -> bool:
    if _launchd_status() and not _launchd_bootout():
        print("티스토리 launchd 작업 해제에 실패했습니다.")
        return False
    PLIST_PATH.unlink(missing_ok=True)
    _set_enabled(False)
    print("티스토리 자동생성 해제됨 (macOS launchd)")
    return True


def status() -> bool:
    system = _system()
    if system == "Windows":
        return _windows_status()
    if system == "Darwin":
        return _launchd_status()
    return False


def on() -> bool:
    try:
        time_value = _schedule_time()
    except ValueError as exc:
        print(exc)
        return False
    system = _system()
    if system == "Windows":
        return _windows_on(time_value)
    if system == "Darwin":
        return _launchd_on(time_value)
    print(f"티스토리 자동생성을 지원하지 않는 운영체제입니다: {system}")
    return False


def off() -> bool:
    system = _system()
    if system == "Windows":
        return _windows_off()
    if system == "Darwin":
        return _launchd_off()
    print(f"티스토리 자동생성을 지원하지 않는 운영체제입니다: {system}")
    return False


def main(args: list[str] | None = None) -> int:
    args = sys.argv[1:] if args is None else args
    action = args[0].lower() if args else "on"
    if action == "on":
        return 0 if on() else 1
    if action == "off":
        return 0 if off() else 1
    if action == "status":
        enabled = status()
        print("티스토리 자동생성: 켜짐" if enabled else "티스토리 자동생성: 꺼짐")
        return 0 if enabled else 1
    print("사용: python -m src.policy_schedule_task [on|off|status]")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
