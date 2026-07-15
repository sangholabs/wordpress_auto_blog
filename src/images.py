# 대표 이미지를 자동 생성(Pollinations, 무료·키 불필요)해 WordPress 미디어로 업로드한다
import requests
from urllib.parse import quote

from .config import get_settings
from .wp_publish import _auth, _base


def _prompt(keyword: str) -> str:
    return f"{keyword}, product review blog hero image, clean studio background, high quality photo, modern, minimal"


def generate_featured_media(keyword: str) -> int | None:
    # 실패해도 발행이 멈추지 않게 항상 None 으로 폴백한다.
    if not get_settings().get("content", {}).get("featured_image", True):
        return None
    try:
        img_url = (
            "https://image.pollinations.ai/prompt/"
            f"{quote(_prompt(keyword))}?width=1200&height=630&nologo=true"
        )
        r = requests.get(img_url, timeout=90)
        if r.status_code >= 400 or not r.content:
            print("대표 이미지 생성 실패(건너뜀)")
            return None
        fn = keyword.strip().replace(" ", "_") + ".jpg"
        headers = {
            "Content-Disposition": f'attachment; filename="{fn}"',
            "Content-Type": "image/jpeg",
        }
        m = requests.post(
            f"{_base()}/media", headers=headers, data=r.content, auth=_auth(), timeout=90
        )
        if m.status_code >= 400:
            print(f"대표 이미지 업로드 실패(건너뜀): {m.status_code}")
            return None
        return m.json().get("id")
    except Exception as e:
        print(f"대표 이미지 생성/업로드 예외(건너뜀): {e}")
        return None
