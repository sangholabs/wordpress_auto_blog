"""WordPress와 티스토리가 함께 쓰는 쿠팡 파트너스 HTML 렌더러."""

from __future__ import annotations

import json
import html
import re
from urllib.parse import quote

from .config import ROOT, env
from .coupang import search_products


def coupang_cta(keyword: str) -> str:
    tag = env("COUPANG_PARTNERS_TAG", "YOUR_TAG")
    url = f"https://www.coupang.com/np/search?q={quote(keyword)}&subId={quote(tag)}"
    label = html.escape(keyword)
    return (
        f'<a href="{url}" target="_blank" rel="nofollow sponsored" '
        'style="display:block;text-align:center;background:#2d6cdf;color:#fff;padding:14px;'
        'border-radius:8px;font-weight:bold;text-decoration:none;margin:24px 0">'
        f'쿠팡에서 “{label}” 관련 상품 보기</a>'
    )


def load_widgets() -> list[str]:
    widget = ROOT / "config" / "coupang_widget.html"
    if not widget.exists():
        return []
    raw = widget.read_text(encoding="utf-8").strip()
    raw = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL).strip()
    if not raw:
        return []
    blocks = [b.strip() for b in re.split(r"(?m)^-{3,}\s*$", raw) if b.strip()]
    return [f'<div class="coupang-widget" style="text-align:center;margin:24px 0">{b}</div>' for b in blocks]


def from_cache(keyword: str) -> list[dict]:
    cache = ROOT / "data" / "product_links.json"
    if not cache.exists():
        return []
    try:
        return json.loads(cache.read_text(encoding="utf-8")).get(keyword, [])
    except (json.JSONDecodeError, OSError):
        return []


def products_for(keyword: str) -> list[dict]:
    return search_products(keyword) or from_cache(keyword)


def cards_html(products: list[dict]) -> str:
    cards = ""
    for product in products:
        name = html.escape(str(product.get("name", "")))
        url = html.escape(str(product.get("url", "")), quote=True)
        image_url = html.escape(str(product.get("image", "")), quote=True)
        price = f'{int(product["price"]):,}원' if product.get("price") else ""
        image = (
            f'<img src="{image_url}" alt="{name}" loading="lazy" '
            'style="width:100%;aspect-ratio:1/1;object-fit:cover">'
            if product.get("image") else ""
        )
        cards += (
            '<div style="border:1px solid #e3e8f0;border-radius:10px;overflow:hidden;text-align:center">'
            f'<a href="{url}" target="_blank" rel="nofollow sponsored" '
            'style="text-decoration:none;color:#222;display:block">'
            f'{image}<div style="font-size:14px;line-height:1.4;padding:8px">{name}</div>'
            f'<div style="font-weight:bold;color:#d6293e;padding:4px 8px">{price}</div>'
            '<span style="display:block;background:#2d6cdf;color:#fff;padding:8px;font-size:14px;font-weight:bold">'
            '상품 보기</span></a></div>'
        )
    return (
        '<div class="products" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));'
        f'gap:14px;margin:24px 0">{cards}</div>'
    )


def monetization_mode() -> str:
    if env("COUPANG_ACCESS_KEY") and env("COUPANG_SECRET_KEY"):
        return "api"
    if (ROOT / "config" / "coupang_widget.html").exists():
        return "widget"
    return "search-link"
