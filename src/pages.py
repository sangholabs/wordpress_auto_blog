# 애드센스 필수 3종 페이지(소개/개인정보처리방침/문의)를 WordPress '페이지'로 발행한다
from datetime import date

import requests

from .config import env
from .wp_publish import _auth, _base


def _find_page(slug: str):
    try:
        r = requests.get(f"{_base()}/pages", params={"slug": slug}, auth=_auth(), timeout=20)
        data = r.json()
        return data[0]["id"] if r.status_code < 400 and data else None
    except Exception:
        return None


def _publish_page(title: str, slug: str, content: str):
    if _find_page(slug):
        print(f"이미 존재하여 건너뜀: {title}")
        return
    payload = {"title": title, "slug": slug, "content": content, "status": "publish"}
    r = requests.post(f"{_base()}/pages", json=payload, auth=_auth(), timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"페이지 발행 실패 {r.status_code}: {r.text}")
    print(f"페이지 발행 완료: {title} → {r.json().get('link')}")


def _about() -> str:
    name = env("SITE_NAME", "본 블로그")
    owner = env("SITE_OWNER", "운영자")
    return f"""<h2>{name} 소개</h2>
<p>{name}은(는) 에어프라이어, 로봇청소기, 공기청정기 등 생활·가전 제품을 고를 때 실제로 도움이 되는 선택 기준과 비교 정보를 제공하는 블로그입니다.</p>
<p>제품이 너무 많아 무엇을 봐야 할지 막막한 분들을 위해, 용량·기능·가격대 같은 핵심 기준을 정리하고 상황(1인 가구, 가족 구성, 예산)에 맞는 유형을 안내합니다. 광고성 나열이 아니라 "어떻게 고르는지"에 초점을 둡니다.</p>
<h3>운영자</h3>
<p>본 블로그는 {owner}이(가) 운영합니다. 문의는 문의 페이지를 이용해 주세요.</p>
<h3>제휴 안내</h3>
<p>본 블로그는 쿠팡 파트너스 활동의 일환으로 일정액의 수수료를 제공받을 수 있으며, 해당 사실을 콘텐츠에 명시합니다.</p>"""


def _privacy() -> str:
    name = env("SITE_NAME", "본 사이트")
    email = env("SITE_EMAIL", "example@example.com")
    today = date.today().isoformat()
    return f"""<h2>개인정보 처리방침</h2>
<p>{name}(이하 '사이트')은(는) 이용자의 개인정보를 중요하게 생각하며 관련 법령을 준수합니다. 본 방침은 사이트가 수집하는 정보와 이용 방식을 설명합니다.</p>
<h3>1. 수집하는 정보</h3>
<p>사이트는 회원가입 기능이 없으며 이름·연락처 등 개인정보를 직접 수집하지 않습니다. 다만 방문 통계와 광고 제공을 위해 쿠키 및 접속 로그(브라우저 종류, 방문 시각, IP 등)가 자동으로 수집될 수 있습니다.</p>
<h3>2. 쿠키와 광고 (Google AdSense)</h3>
<p>사이트는 Google AdSense를 통해 광고를 게재할 수 있습니다. Google을 포함한 제3자 광고 사업자는 쿠키를 사용해 이용자의 관심에 기반한 광고를 제공할 수 있습니다. 이용자는 <a href="https://www.google.com/settings/ads" target="_blank" rel="noopener">Google 광고 설정</a>에서 맞춤 광고를 해제할 수 있습니다.</p>
<h3>3. 제휴 링크 (쿠팡 파트너스)</h3>
<p>사이트는 쿠팡 파트너스 활동의 일환으로 제휴 링크를 포함하며, 이를 통해 발생한 구매에 대해 일정액의 수수료를 받을 수 있습니다. 이용자에게 추가 비용은 발생하지 않습니다.</p>
<h3>4. 제3자 제공 및 보관</h3>
<p>사이트는 수집된 정보를 이용자의 동의 없이 제3자에게 판매·제공하지 않습니다. 자동 수집 정보는 통계·광고 목적 범위 내에서만 이용됩니다.</p>
<h3>5. 이용자의 권리</h3>
<p>이용자는 브라우저 설정을 통해 쿠키 저장을 거부할 수 있습니다. 다만 이 경우 사이트 일부 기능 이용에 제한이 있을 수 있습니다.</p>
<h3>6. 문의</h3>
<p>개인정보 관련 문의는 {email} 로 연락 주시기 바랍니다.</p>
<p>본 방침은 {today}부터 적용됩니다.</p>"""


def _contact() -> str:
    name = env("SITE_NAME", "본 블로그")
    email = env("SITE_EMAIL", "example@example.com")
    return f"""<h2>문의하기</h2>
<p>{name}에 대한 문의, 제휴 제안, 콘텐츠 정정 요청은 아래 이메일로 연락 주세요.</p>
<p><strong>이메일:</strong> {email}</p>
<p>보내주신 문의는 확인 후 순차적으로 답변드립니다.</p>"""


def create_required_pages():
    if not env("SITE_EMAIL"):
        print("[안내] .env 의 SITE_NAME/SITE_OWNER/SITE_EMAIL 을 먼저 채워주세요.")
    _publish_page("소개", "about", _about())
    _publish_page("개인정보처리방침", "privacy-policy", _privacy())
    _publish_page("문의", "contact", _contact())
    print("완료. 워드프레스 메뉴에 이 3개 페이지를 추가해 상단/하단에 노출하세요.")


if __name__ == "__main__":
    create_required_pages()
