# 쿠팡 다이나믹 배너를 안내에 따라 만들어 config/coupang_widget.html 에 저장하는 도우미
import webbrowser

from .config import ROOT

WIDGET = ROOT / "config" / "coupang_widget.html"
PARTNERS_URL = "https://partners.coupang.com/"

GUIDE = """
================ 쿠팡 다이나믹 배너 만들기 (가전디지털) ================
브라우저에서 쿠팡 파트너스를 엽니다. 아래 순서대로 진행하세요.

 1. 파트너스 로그인.
 2. 상단 '링크 생성' → '다이나믹 배너' → '배너 생성'.
 3. 배너 제목: 아무 이름 (예: 가전배너1).
 4. 배너 타입: '카테고리 베스트' 선택.
 5. 배너 데이터(카테고리): '가전디지털' 선택  ← 주제와 맞는 상품이 노출됩니다.
 6. 크기: 너비 300, 높이 250, 테두리 0.
 7. '배너 만들기' → iframe 코드 복사.
 8. (선택) 카테고리를 조금씩 바꿔 2~3개 더 만들면 소제목마다 다른 배너가 들어갑니다.
======================================================================
"""


def setup_banner():
    print(GUIDE)
    try:
        webbrowser.open(PARTNERS_URL)
        print(f"브라우저에서 {PARTNERS_URL} 를 열었습니다.")
    except Exception:
        print(f"브라우저 자동 열기에 실패했습니다. 직접 접속하세요: {PARTNERS_URL}")

    print("\n생성한 iframe 코드를 한 줄씩 붙여넣으세요. 여러 개면 계속, 다 되면 빈 줄에서 Enter.")
    codes = []
    while True:
        line = input(f"배너 {len(codes) + 1} iframe (없으면 Enter): ").strip()
        if not line:
            break
        if "<iframe" not in line:
            print("  iframe 코드가 아닌 것 같습니다. 다시 붙여넣어 주세요.")
            continue
        codes.append(line)

    if not codes:
        print("입력이 없어 취소했습니다. 기존 배너 파일은 그대로 둡니다.")
        return
    content = "<!-- 쿠팡 다이나믹 배너 (가전디지털 카테고리 베스트). '---' 로 여러 개 구분. -->\n"
    content += "\n---\n".join(codes) + "\n"
    WIDGET.write_text(content, encoding="utf-8")
    print(f"\n저장 완료 → {WIDGET}  (배너 {len(codes)}개)")
    print("이후 발행되는 글부터 이 배너가 적용됩니다.")


if __name__ == "__main__":
    setup_banner()
