# 자동발행 작업(Windows 작업 스케줄러)을 settings 의 시각으로 등록/해제한다
import subprocess
import sys

from .config import ROOT, get_settings

TASK = "blog-auto"


def on():
    t = get_settings().get("publish", {}).get("schedule_time", "09:00")
    bat = ROOT / "run.bat"
    r = subprocess.run(
        ["schtasks", "/create", "/tn", TASK, "/tr", str(bat), "/sc", "daily", "/st", t, "/f"]
    )
    print(f"자동발행 등록 완료 (매일 {t})" if r.returncode == 0
          else "등록 실패 — 관리자 권한으로 다시 실행해 보세요.")


def off():
    subprocess.run(["schtasks", "/delete", "/tn", TASK, "/f"])
    print("자동발행 해제됨")


if __name__ == "__main__":
    off() if (len(sys.argv) > 1 and sys.argv[1] == "off") else on()
