# 통합 제어판 — 콘솔 메뉴 하나로 발행·자동발행·설정·대시보드·push 를 관리한다 (한글 OK)
import os
import re
import shutil
import subprocess
import sys

from . import banner_setup, pages, pipeline, policy_cli, schedule_task
from .config import ROOT, env, get_settings
from .set_option import set_option

MENU = """
==================== 블로그 자동화 제어판 ====================
 [WordPress 발행]
  1. 지금 1편 발행
  2. 키워드 새로 수집 후 발행
 [WordPress 자동발행]
  3. 자동발행 켜기      4. 자동발행 끄기      5. 시각 변경
 [WordPress 설정]
  6. 발행모드 (공개/초안)    7. 하루 편수
  8. 배너 레이아웃           9. 배너 개수        10. 로켓 전용
 [기타]
 11. 대시보드 열기          12. GitHub 올리기(push)
 13. 애드센스 필수 페이지 생성 (소개/개인정보/문의)
 14. Claude 로그인 (글 생성 엔진, PC마다 최초 1회)
 15. 쿠팡 배너 설정 도우미 (가전디지털 카테고리)
 16. 대표 이미지 켜기/끄기
 17. 정책·티스토리 작업실
  0. 종료
=============================================================="""


def _is_windows() -> bool:
    return os.name == "nt"


def _status():
    s = get_settings()
    p, c, cp = s.get("publish", {}), s.get("content", {}), s.get("coupang", {})
    if env("COUPANG_ACCESS_KEY") and env("COUPANG_SECRET_KEY"):
        coupang = "API 상품카드"
    elif (ROOT / "config" / "coupang_widget.html").exists():
        coupang = "다이나믹 배너"
    else:
        coupang = "검색링크(수익 없음)"
    on = lambda b: "켜짐" if b else "꺼짐"
    print("── WordPress 현재 설정 ─────────────────────")
    print(f" 발행모드:{p.get('status')} | 하루:{p.get('posts_per_day')}편 | 자동발행:매일 {p.get('schedule_time')}")
    print(f" 배너:{c.get('banner_layout')}/{c.get('max_banners')}개 | 로켓전용:{on(cp.get('rocket_only'))} | 대표이미지:{on(c.get('featured_image', True))}")
    print(f" 중복제거:{on(s.get('topic_queue', {}).get('one_per_product', True))} | 글엔진:{env('LLM_PROVIDER', 'claude_code')} | 쿠팡수익:{coupang}")
    print("────────────────────────────────────────────")


def _dashboard():
    args = [sys.executable, "-m", "src.dashboard"]
    if _is_windows():
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        subprocess.Popen(args, cwd=str(ROOT), creationflags=flags)
        print("대시보드를 새 창에서 열었습니다.")
        return
    log = ROOT / "logs" / "dashboard.log"
    log.parent.mkdir(exist_ok=True)
    with open(log, "a", encoding="utf-8") as output:
        subprocess.Popen(
            args,
            cwd=str(ROOT),
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    print("대시보드를 백그라운드에서 열었습니다. 잠시 후 브라우저를 확인하세요.")


def _push():
    subprocess.run(["git", "add", "."], cwd=str(ROOT))
    subprocess.run(["git", "commit", "-m", "update"], cwd=str(ROOT))
    subprocess.run(["git", "push"], cwd=str(ROOT))


def _claude_login():
    exe = shutil.which("claude")
    if not exe:
        print("claude 가 설치돼 있지 않습니다. 먼저: npm install -g @anthropic-ai/claude-code")
        return
    if _is_windows():
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        subprocess.Popen(["cmd", "/c", exe], creationflags=flags)
        print("새 창에서 claude 를 열었습니다. 로그인이 안 돼 있으면 안내대로 로그인하세요.")
    else:
        print("현재 터미널에서 claude 를 실행합니다. 로그인을 마치고 종료하면 메뉴로 돌아옵니다.")
        subprocess.run([exe], cwd=str(ROOT))
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
            if re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", t):
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
        elif c == "15":
            banner_setup.setup_banner()
        elif c == "16":
            set_option("featured_image", "true" if input("1) 켜기  2) 끄기 : ").strip() == "1" else "false")
        elif c == "17":
            policy_cli.interactive()
        elif c == "0":
            break
        else:
            print("잘못된 번호입니다.")
        input("\n[Enter] 메뉴로 돌아가기...")


if __name__ == "__main__":
    main()
