# 통합 제어판 — 콘솔 메뉴 하나로 발행·자동발행·설정·대시보드·push 를 관리한다 (한글 OK)
import re
import shutil
import subprocess
import sys

from . import pages, pipeline, schedule_task
from .config import ROOT, get_settings
from .set_option import set_option

MENU = """
==================== 블로그 자동화 제어판 ====================
 [발행]
  1. 지금 1편 발행
  2. 키워드 새로 수집 후 발행
 [자동발행]
  3. 자동발행 켜기      4. 자동발행 끄기      5. 시각 변경
 [설정]
  6. 발행모드 (공개/초안)    7. 하루 편수
  8. 배너 레이아웃           9. 배너 개수        10. 로켓 전용
 [기타]
 11. 대시보드 열기          12. GitHub 올리기(push)
 13. 애드센스 필수 페이지 생성 (소개/개인정보/문의)
 14. Claude 로그인 (글 생성 엔진, PC마다 최초 1회)
  0. 종료
=============================================================="""


def _status():
    s = get_settings()
    p, c, cp = s.get("publish", {}), s.get("content", {}), s.get("coupang", {})
    print(f"현재 → 발행모드:{p.get('status')} | 하루:{p.get('posts_per_day')}편 | "
          f"시각:{p.get('schedule_time')} | 배너:{c.get('banner_layout')}/{c.get('max_banners')}개 | "
          f"로켓전용:{'켜짐' if cp.get('rocket_only') else '꺼짐'}")


def _dashboard():
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    subprocess.Popen([sys.executable, "-m", "src.dashboard"], cwd=str(ROOT), creationflags=flags)
    print("대시보드를 새 창에서 열었습니다.")


def _push():
    subprocess.run(["git", "add", "."], cwd=str(ROOT))
    subprocess.run(["git", "commit", "-m", "update"], cwd=str(ROOT))
    subprocess.run(["git", "push"], cwd=str(ROOT))


def _claude_login():
    exe = shutil.which("claude")
    if not exe:
        print("claude 가 설치돼 있지 않습니다. 먼저: npm install -g @anthropic-ai/claude-code")
        return
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    subprocess.Popen(["cmd", "/c", exe], creationflags=flags)
    print("새 창에서 claude 를 열었습니다. 로그인이 안 돼 있으면 안내대로 로그인하세요.")
    print("로그인은 이 PC에 저장되어, 이후 발행은 자동으로 인증을 사용합니다. (창은 닫아도 됨)")


def _ask_int(prompt: str, lo: int, hi: int):
    v = input(prompt).strip()
    if v.isdigit() and lo <= int(v) <= hi:
        return v
    print(f"{lo}~{hi} 사이 숫자만 입력하세요. 변경을 취소합니다.")
    return None


def main():
    while True:
        print(MENU)
        _status()
        c = input("번호 선택: ").strip()
        if c == "1":
            pipeline.run(refresh_keywords=False)
        elif c == "2":
            pipeline.run(refresh_keywords=True)
        elif c == "3":
            schedule_task.on()
        elif c == "4":
            schedule_task.off()
        elif c == "5":
            t = input("자동발행 시각(HH:MM, 예 09:00): ").strip()
            if re.fullmatch(r"[0-2]\d:[0-5]\d", t):
                set_option("schedule_time", t)
                schedule_task.on()
            else:
                print("HH:MM 형식으로 입력하세요. 변경을 취소합니다.")
        elif c == "6":
            set_option("status", "publish" if input("1) 공개  2) 초안 : ").strip() == "1" else "draft")
        elif c == "7":
            v = _ask_int("하루 편수(1-5): ", 1, 5)
            if v:
                set_option("posts_per_day", v)
        elif c == "8":
            m = {"1": "per_h2", "2": "grouped", "3": "grouped_h2"}
            set_option("banner_layout", m.get(input("1) 소제목분산  2) 한자리모아  3) 혼합 : ").strip(), "per_h2"))
        elif c == "9":
            v = _ask_int("배너 개수(1-3): ", 1, 3)
            if v:
                set_option("max_banners", v)
        elif c == "10":
            set_option("rocket_only", "true" if input("1) 켜기  2) 끄기 : ").strip() == "1" else "false")
        elif c == "11":
            _dashboard()
        elif c == "12":
            _push()
        elif c == "13":
            pages.create_required_pages()
        elif c == "14":
            _claude_login()
        elif c == "0":
            break
        else:
            print("잘못된 번호입니다.")
        input("\n[Enter] 메뉴로 돌아가기...")


if __name__ == "__main__":
    main()
