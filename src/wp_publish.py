# 설치형 WordPress(카페24 등) REST API 로 글을 발행한다 (Application Password 인증)
import re
import sys
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth

from .config import env, get_categories, get_settings


def _base() -> str:
    return env("WP_SITE_URL").rstrip("/") + "/wp-json/wp/v2"


def _auth() -> HTTPBasicAuth:
    return HTTPBasicAuth(env("WP_USERNAME"), env("WP_APP_PASSWORD").replace(" ", ""))


def _category_id(name: str) -> int | None:
    # 카테고리명을 ID로 변환한다. 없으면 새로 만든다.
    base, auth = _base(), _auth()
    r = requests.get(f"{base}/categories", params={"search": name}, auth=auth, timeout=20)
    r.raise_for_status()
    for c in r.json():
        if c["name"] == name:
            return c["id"]
    r = requests.post(f"{base}/categories", json={"name": name}, auth=auth, timeout=20)
    return r.json()["id"] if r.status_code < 400 else None


def _category_name(slug: str) -> str | None:
    for c in get_categories()["categories"]:
        if c["slug"] == slug:
            return c["name"]
    return None


def publish_post(post: dict, status: str | None = None) -> dict:
    from .formatter import to_html

    if not env("WP_SITE_URL") or not env("WP_USERNAME") or not env("WP_APP_PASSWORD"):
        raise RuntimeError(
            "WP_SITE_URL/WP_USERNAME/WP_APP_PASSWORD 가 비어 있습니다. "
            "SETUP.md 6단계를 참고해 Application Password 를 발급하세요."
        )
    status = status or get_settings()["publish"]["status"]
    kw = post.get("keyword", "")
    payload = {
        "title": post["title"],
        "slug": re.sub(r"\s+", "-", kw.strip()) or None,  # 긴 제목 대신 키워드 기반 짧은 슬러그
        "content": to_html(post, for_wordpress=True),
        "status": status,
        "excerpt": post.get("meta_description", ""),
        "meta": {  # Rank Math SEO 자동 설정(지원 안 하면 아래에서 제거 후 재시도)
            "rank_math_focus_keyword": kw,
            "rank_math_description": post.get("meta_description", ""),
        },
    }
    name = _category_name(post.get("category", ""))
    if name:
        cid = _category_id(name)
        if cid:
            payload["categories"] = [cid]
    from .images import generate_featured_media  # 순환 임포트 방지
    media_id = generate_featured_media(kw)
    if media_id:
        payload["featured_media"] = media_id
    r = requests.post(f"{_base()}/posts", json=payload, auth=_auth(), timeout=30)
    if r.status_code >= 400 and "meta" in payload:
        payload.pop("meta")  # Rank Math meta 미지원 환경이면 빼고 재시도
        r = requests.post(f"{_base()}/posts", json=payload, auth=_auth(), timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"게시 실패 {r.status_code}: {r.text}")
    d = r.json()
    print(f"게시 완료({status}) → {d.get('link')}")
    return d


def _post_from_md(md_path: Path) -> dict:
    md = md_path.read_text(encoding="utf-8")
    title = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
    meta = re.search(r"^>\s*메타설명:\s*(.+)$", md, re.MULTILINE)
    keyword = md_path.stem.replace("draft_", "").replace("-", " ")
    return {
        "keyword": keyword,
        "category": "",
        "title": title.group(1).strip() if title else keyword,
        "meta_description": meta.group(1).strip() if meta else "",
        "markdown": md,
    }


if __name__ == "__main__":
    # 사용: python -m src.wp_publish output/draft_xxx.md
    publish_post(_post_from_md(Path(sys.argv[1])))
