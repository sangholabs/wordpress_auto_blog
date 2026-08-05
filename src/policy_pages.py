"""티스토리에 수동 등록할 애드센스 필수 페이지 패키지를 만든다."""

from __future__ import annotations

import html
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

from .config import ROOT, env

OUTPUT_ROOT = ROOT / "output" / "tistory" / "pages"
PAGE_STYLE = (
    "max-width:720px;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,"
    "'Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:#222;"
    "font-size:17px;line-height:1.85;word-break:keep-all;overflow-wrap:break-word"
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8-sig")


def _wrap(content: str) -> str:
    return f'<article style="{PAGE_STYLE}">{content}</article>'


def _about(site_name: str, owner: str) -> str:
    name = html.escape(site_name)
    operator = html.escape(owner)
    return _wrap(f"""
<h2 style="font-size:26px;margin:30px 0 14px">{name} 소개</h2>
<p>{name}은 30~50대 주부와 직장인이 놓치기 쉬운 국가정책·생활 혜택을 공식 출처 기준으로 쉽게 정리하는 블로그입니다.</p>
<p>지원 대상, 혜택, 신청기간, 신청방법과 구비서류를 한눈에 확인할 수 있도록 설명하며, 게시일 이후 정책이 변경될 수 있어 각 글에 공식 출처와 확인 기준일을 함께 제공합니다.</p>
<h2 style="font-size:22px;margin:30px 0 12px">운영 원칙</h2>
<ul><li>정부24, 보조금24, 복지로, 고용24와 정부 부처 등 공식 자료를 우선합니다.</li><li>공식 자료에 없는 금액·자격·날짜는 추측하지 않습니다.</li><li>중요한 신청 전에는 공식 페이지와 담당 기관에 다시 확인하도록 안내합니다.</li></ul>
<h2 style="font-size:22px;margin:30px 0 12px">운영자 및 제휴 안내</h2>
<p>본 블로그는 {operator}이 운영합니다. 일부 글에는 쿠팡 파트너스 제휴 링크가 포함될 수 있으며, 해당 링크를 통한 구매 시 일정액의 수수료를 제공받을 수 있습니다. 이용자의 구매 가격에는 영향을 주지 않습니다.</p>
""")


def _privacy(site_name: str, email: str) -> str:
    name = html.escape(site_name)
    contact = html.escape(email)
    today = date.today().isoformat()
    return _wrap(f"""
<h2 style="font-size:26px;margin:30px 0 14px">개인정보 처리방침</h2>
<p>{name}(이하 ‘블로그’)은 이용자의 개인정보를 중요하게 생각하며 관련 법령을 준수합니다.</p>
<h2 style="font-size:22px;margin:30px 0 12px">1. 수집하는 정보</h2>
<p>블로그는 회원가입 기능을 운영하지 않으며 이름·연락처를 직접 수집하지 않습니다. 다만 방문 통계와 서비스 제공 과정에서 브라우저 종류, 방문 시각, IP, 쿠키 등의 정보가 자동으로 처리될 수 있습니다.</p>
<h2 style="font-size:22px;margin:30px 0 12px">2. 쿠키와 Google AdSense</h2>
<p>블로그는 Google AdSense 광고를 게재할 수 있습니다. Google 등 제3자 광고 사업자는 쿠키를 사용해 이용자의 이전 방문 기록을 바탕으로 광고를 제공할 수 있습니다. 이용자는 <a href="https://myadcenter.google.com/" target="_blank" rel="noopener">Google 광고 설정</a>에서 맞춤 광고를 관리할 수 있습니다.</p>
<h2 style="font-size:22px;margin:30px 0 12px">3. 쿠팡 파트너스</h2>
<p>블로그에는 쿠팡 파트너스 제휴 링크가 포함될 수 있으며, 이를 통한 구매 시 블로그 운영자가 일정액의 수수료를 제공받을 수 있습니다.</p>
<h2 style="font-size:22px;margin:30px 0 12px">4. 제3자 제공과 이용자의 권리</h2>
<p>블로그는 이용자의 정보를 임의로 판매하지 않습니다. 이용자는 브라우저 설정에서 쿠키 저장을 거부하거나 삭제할 수 있으며, 이 경우 일부 기능이나 맞춤 광고 이용이 제한될 수 있습니다.</p>
<h2 style="font-size:22px;margin:30px 0 12px">5. 문의</h2>
<p>개인정보 관련 문의: {contact}</p>
<p>시행일: {today}</p>
""")


def _contact(site_name: str, email: str) -> str:
    name = html.escape(site_name)
    contact = html.escape(email)
    return _wrap(f"""
<h2 style="font-size:26px;margin:30px 0 14px">문의하기</h2>
<p>{name}의 콘텐츠 정정 요청, 정책 정보 제보, 제휴 문의는 아래 이메일로 보내주세요.</p>
<p style="padding:16px;background:#f5f7fb;border:1px solid #dfe5ef;border-radius:8px"><strong>이메일:</strong> {contact}</p>
<p>정책 내용 정정을 요청할 때에는 해당 글 주소와 확인 가능한 공식 출처를 함께 보내주시면 더 빠르게 검토할 수 있습니다.</p>
""")


def create_required_pages_package() -> Path:
    site_name = env("TISTORY_SITE_NAME", env("SITE_NAME", "본 블로그"))
    owner = env("TISTORY_SITE_OWNER", env("SITE_OWNER", "운영자"))
    email = env("TISTORY_SITE_EMAIL", env("SITE_EMAIL", "example@example.com"))
    if email == "example@example.com":
        print("[안내] .env의 TISTORY_SITE_EMAIL 또는 SITE_EMAIL을 실제 문의 이메일로 설정하세요.")
    pages = [
        ("01_소개", "소개", _about(site_name, owner)),
        ("02_개인정보처리방침", "개인정보처리방침", _privacy(site_name, email)),
        ("03_문의", "문의", _contact(site_name, email)),
    ]
    for folder_name, title, body in pages:
        folder = OUTPUT_ROOT / folder_name
        plain = BeautifulSoup(body, "html.parser").get_text("\n", strip=True)
        _write(folder / "01_제목.txt", title + "\n")
        _write(folder / "02_HTML블록용.txt", body)
        _write(folder / "03_일반텍스트.txt", plain + "\n")
    guide = """티스토리 애드센스 필수 페이지 수동 등록

1. 티스토리 블로그관리의 페이지 관리에서 새 페이지를 만듭니다.
2. 각 폴더의 01_제목.txt를 제목에 붙여넣습니다.
3. 기본모드에서 'HTML 블록'을 추가하고 02_HTML블록용.txt 전체를 붙여넣습니다.
4. '코드블록'은 HTML 소스를 글에 그대로 표시하므로 사용하지 않습니다.
5. 발행 전 소개의 운영자명과 개인정보처리방침·문의의 이메일을 실제 정보로 확인합니다.
6. 생성된 페이지를 블로그 메뉴나 푸터에서 쉽게 찾을 수 있도록 연결합니다.

이 패키지는 WordPress에 게시하지 않으며 티스토리 수동 등록용 파일만 만듭니다.
"""
    _write(OUTPUT_ROOT / "00_게시가이드.txt", guide)
    print(f"티스토리 필수 페이지 패키지 생성 완료 → {OUTPUT_ROOT}")
    return OUTPUT_ROOT


if __name__ == "__main__":
    create_required_pages_package()
