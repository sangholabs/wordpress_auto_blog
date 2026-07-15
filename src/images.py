# 대표 이미지를 자동 생성(Pollinations, 무료·키 불필요)해 WordPress 미디어로 업로드한다
import time
from urllib.parse import quote

import requests

from .config import get_settings
from .wp_publish import _auth, _base


# 한국어 상품명 → 영어(AI 이미지 정확도↑). 구체적인 것부터 위에 둔다.
_KO_EN = {
    "에어프라이어": "air fryer",
    "로봇청소기": "robot vacuum cleaner",
    "무선청소기": "cordless stick vacuum cleaner",
    "청소기": "vacuum cleaner",
    "전기밥솥": "electric rice cooker with digital display and control buttons, closed lid",
    "밥솥": "electric rice cooker with digital display, closed lid",
    "커피머신": "espresso coffee machine",
    "식기세척기": "modern built-in dishwasher, stainless steel front panel",
    "공기청정기": "air purifier",
    "제습기": "dehumidifier",
    "가습기": "humidifier",
    "선풍기": "electric fan",
    "전기포트": "electric kettle",
    "믹서기": "blender",
    "토스터": "toaster",
    "전자레인지": "microwave oven",
    "냉장고": "refrigerator",
    "세탁기": "washing machine",
    "건조기": "clothes dryer",
    "인덕션": "induction cooktop",
}


def _prompt(keyword: str) -> str:
    kw = keyword.replace(" ", "")
    subject = next((en for ko, en in _KO_EN.items() if ko in kw), "modern home appliance")
    return (f"{subject}, professional product photography, clean white studio background, "
            "centered composition, soft lighting, high detail, e-commerce hero image, no text, no watermark")


def generate_featured_media(keyword: str) -> int | None:
    # 실패해도 발행이 멈추지 않게 항상 None 으로 폴백한다.
    if not get_settings().get("content", {}).get("featured_image", True):
        return None
    try:
        seed = abs(hash(keyword)) % 100000  # 키워드별 고정 시드 → 글마다 다른 이미지
        img_url = (
            "https://image.pollinations.ai/prompt/"
            f"{quote(_prompt(keyword))}?width=1200&height=630&nologo=true&seed={seed}"
        )
        r = requests.get(img_url, timeout=90)
        if r.status_code >= 400 or not r.content:
            print("대표 이미지 생성 실패(건너뜀)")
            return None
        ct = r.headers.get("content-type", "image/jpeg")
        ext = "png" if "png" in ct else "jpg"
        fn = f"featured-{int(time.time())}.{ext}"  # 파일명은 ASCII(한글 금지 — HTTP 헤더 오류 방지)
        headers = {
            "Content-Disposition": f'attachment; filename="{fn}"',
            "Content-Type": ct,
        }
        m = requests.post(
            f"{_base()}/media", headers=headers, data=r.content, auth=_auth(), timeout=90
        )
        if m.status_code >= 400:
            print(f"대표 이미지 업로드 실패(건너뜀): {m.status_code} {m.text[:200]}")
            return None
        mid = m.json().get("id")
        print(f"대표 이미지 설정됨 (media id {mid})")
        return mid
    except Exception as e:
        print(f"대표 이미지 생성/업로드 예외(건너뜀): {e}")
        return None
