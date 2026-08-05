"""WordPress와 티스토리가 함께 쓰는 쿠팡 파트너스 HTML 렌더러."""

from __future__ import annotations

import json
import html
import re
from urllib.parse import parse_qs, quote, urlsplit, urlunsplit

from bs4 import BeautifulSoup

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


def normalize_coupang_product_urls(values: list[str] | tuple[str, ...]) -> list[str]:
    """사용자가 넣은 쿠팡 상품/파트너스 URL을 검증하고 중복을 제거한다."""
    normalized: list[str] = []
    for raw in values:
        value = str(raw).strip()
        if not value:
            continue
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme.lower() != "https" or not host:
            raise ValueError(f"쿠팡 링크는 HTTPS 주소여야 합니다: {value}")
        if parsed.username or parsed.password:
            raise ValueError(f"사용자 정보가 포함된 URL은 사용할 수 없습니다: {value}")
        if host != "coupa.ng" and host != "coupang.com" and not host.endswith(".coupang.com"):
            raise ValueError(f"쿠팡 도메인의 상품 링크만 사용할 수 있습니다: {value}")
        clean = urlunsplit(("https", parsed.netloc, parsed.path or "/", parsed.query, parsed.fragment))
        if clean not in normalized:
            normalized.append(clean)
    return normalized


def is_partners_tracking_url(url: str) -> bool:
    """쿠팡 파트너스에서 발급되는 대표적인 단축 링크인지 확인한다."""
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    return host in {"link.coupang.com", "coupa.ng"}


def coupang_product_cta(keyword: str, url: str) -> str:
    """사용자가 지정한 상품 링크를 티스토리용 제휴 버튼으로 렌더링한다."""
    clean = normalize_coupang_product_urls([url])[0]
    label = html.escape(keyword or "추천 상품")
    href = html.escape(clean, quote=True)
    return (
        f'<a href="{href}" target="_blank" rel="nofollow sponsored noopener" '
        'data-policy-coupang-product-link="true" '
        'style="display:block;text-align:center;background:#2d6cdf;color:#fff;padding:14px;'
        'border-radius:8px;font-weight:bold;text-decoration:none;margin:24px 0">'
        f'쿠팡에서 “{label}” 상품 확인하기</a>'
    )


def _dimension(value: object, default: int) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return number if 1 <= number <= 2000 else default


def _query_dimension(url: str, key: str, default: int) -> int:
    value = parse_qs(urlsplit(url).query).get(key, [default])[0]
    return _dimension(value, default)


def _official_asset_host(url: str, *, image: bool = False) -> bool:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme.lower() != "https" or not host or parsed.username or parsed.password:
        return False
    if image:
        return host == "ads-partners.coupang.com" or host == "coupangcdn.com" or host.endswith(".coupangcdn.com")
    return host in {"ads-partners.coupang.com", "coupa.ng"}


def parse_coupang_asset(source: str) -> dict:
    """쿠팡 파트너스가 발급한 URL/HTML/iframe/script 소재를 안전한 구조로 변환한다."""
    original = str(source).strip()
    if not original:
        raise ValueError("쿠팡 광고 소재가 비어 있습니다.")
    code = original[:-1].rstrip() if original.endswith(",") else original
    if "<" not in code:
        url = normalize_coupang_product_urls([code])[0]
        return {
            "type": "product-link", "source_code": original, "url": url,
            "width": 0, "height": 0, "partners_tracking": is_partners_tracking_url(url),
        }

    soup = BeautifulSoup(code, "html.parser")
    tags = soup.find_all(True)
    tag_names = {tag.name.lower() for tag in tags}

    if tag_names and tag_names <= {"script"}:
        scripts = soup.find_all("script")
        external = next((tag for tag in scripts if tag.get("src")), None)
        inline = "\n".join(tag.get_text("\n", strip=True) for tag in scripts if not tag.get("src"))
        if not external or external.get("src") != "https://ads-partners.coupang.com/g.js":
            raise ValueError("쿠팡 PartnersCoupang 공식 스크립트만 사용할 수 있습니다.")
        match = re.fullmatch(
            r"\s*new\s+PartnersCoupang\.G\s*\(\s*(\{.*\})\s*\)\s*;?\s*",
            inline, flags=re.DOTALL,
        )
        if not match:
            raise ValueError("PartnersCoupang.G 설정 JSON을 확인할 수 없습니다.")
        try:
            options = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            raise ValueError("PartnersCoupang.G 설정이 올바른 JSON이 아닙니다.") from exc
        allowed = {"id", "template", "trackingCode", "subId", "width", "height"}
        if not isinstance(options, dict) or not options or set(options) - allowed:
            raise ValueError("쿠팡 배너 설정에 허용되지 않은 항목이 있습니다.")
        if not isinstance(options.get("id"), int) or options["id"] <= 0:
            raise ValueError("쿠팡 배너 id가 올바르지 않습니다.")
        tracking = str(options.get("trackingCode", ""))
        if not re.fullmatch(r"[A-Za-z0-9_-]+", tracking):
            raise ValueError("쿠팡 trackingCode가 올바르지 않습니다.")
        template = str(options.get("template", "banner"))
        if template not in {"banner", "carousel"}:
            raise ValueError("지원하지 않는 쿠팡 배너 template입니다.")
        width = _dimension(options.get("width"), 300)
        height = _dimension(options.get("height"), 250)
        clean_options = {
            "id": options["id"], "template": template, "trackingCode": tracking,
            "subId": options.get("subId"), "width": width, "height": height,
        }
        return {
            "type": "dynamic-banner" if template == "carousel" else "category-banner-script",
            "source_code": original, "options": clean_options, "width": width, "height": height,
            "partners_tracking": True,
        }

    if tag_names == {"iframe"} and len(tags) == 1:
        frame = tags[0]
        src = str(frame.get("src", "")).strip()
        if not _official_asset_host(src):
            raise ValueError("쿠팡 공식 iframe 주소만 사용할 수 있습니다.")
        width = _dimension(frame.get("width"), _query_dimension(src, "width", 300))
        height = _dimension(frame.get("height"), _query_dimension(src, "height", 250))
        return {
            "type": "product-banner-iframe" if (urlsplit(src).hostname or "").lower() == "coupa.ng" else "category-banner-iframe",
            "source_code": original, "src": src, "width": width, "height": height,
            "partners_tracking": True,
        }

    if tag_names == {"a", "img"} and len(tags) == 2:
        anchor, image = soup.find("a"), soup.find("img")
        if image.parent is not anchor:
            raise ValueError("쿠팡 이미지 배너는 링크 안에 이미지가 있어야 합니다.")
        href = normalize_coupang_product_urls([str(anchor.get("href", ""))])[0]
        src = str(image.get("src", "")).strip()
        if not _official_asset_host(src, image=True):
            raise ValueError("쿠팡 공식 배너 이미지 주소만 사용할 수 있습니다.")
        width = _dimension(image.get("width"), _query_dimension(src, "w", 728))
        height = _dimension(image.get("height"), _query_dimension(src, "h", 90))
        image_host = (urlsplit(src).hostname or "").lower()
        return {
            "type": "product-banner" if image_host.endswith("coupangcdn.com") else "category-banner",
            "source_code": original, "url": href, "image_url": src,
            "alt": str(image.get("alt", "")).strip(), "width": width, "height": height,
            "partners_tracking": is_partners_tracking_url(href),
        }

    raise ValueError("지원 형식은 쿠팡 상품 URL, 링크+이미지, iframe, PartnersCoupang 스크립트입니다.")


def parse_coupang_assets(values: list[str] | tuple[str, ...]) -> list[dict]:
    assets: list[dict] = []
    fingerprints: set[str] = set()
    for value in values:
        if not str(value).strip():
            continue
        asset = parse_coupang_asset(value)
        fingerprint = json.dumps(asset, ensure_ascii=False, sort_keys=True)
        if fingerprint not in fingerprints:
            assets.append(asset)
            fingerprints.add(fingerprint)
    return assets


def coupang_asset_label(asset: dict) -> str:
    labels = {
        "product-link": "상품 링크", "category-banner": "카테고리 이미지 배너",
        "category-banner-iframe": "카테고리 iframe 배너",
        "category-banner-script": "카테고리 스크립트 배너",
        "dynamic-banner": "다이나믹 배너", "product-banner": "상품 이미지 배너",
        "product-banner-iframe": "상품 iframe 배너",
    }
    size = f" {asset.get('width')}×{asset.get('height')}" if asset.get("width") and asset.get("height") else ""
    return labels.get(str(asset.get("type")), "쿠팡 소재") + size


def render_coupang_asset(asset: dict, keyword: str = "추천 상품") -> str:
    """검증된 쿠팡 소재를 모바일 폭을 넘지 않는 티스토리 HTML로 만든다."""
    kind = str(asset.get("type", ""))
    if kind == "product-link":
        return coupang_product_cta(keyword, str(asset["url"]))
    width = _dimension(asset.get("width"), 300)
    height = _dimension(asset.get("height"), 250)
    wrapper = (
        f'<div data-policy-coupang-asset="{html.escape(kind, quote=True)}" '
        f'data-policy-coupang-size="{width}x{height}" '
        'style="width:100%;overflow-x:auto;text-align:center;margin:24px 0;-webkit-overflow-scrolling:touch">'
    )
    if kind in {"category-banner", "product-banner"}:
        href = html.escape(str(asset["url"]), quote=True)
        src = html.escape(str(asset["image_url"]), quote=True)
        alt = html.escape(str(asset.get("alt") or keyword), quote=True)
        content = (
            f'<a href="{href}" target="_blank" rel="nofollow sponsored noopener" referrerpolicy="unsafe-url" '
            f'style="display:inline-block;max-width:100%"><img src="{src}" alt="{alt}" width="{width}" height="{height}" '
            f'style="display:block;max-width:100%;height:auto;margin:0 auto"></a>'
        )
    elif kind in {"category-banner-iframe", "product-banner-iframe"}:
        src = html.escape(str(asset["src"]), quote=True)
        content = (
            f'<span style="display:inline-block;width:{width}px;max-width:100%;aspect-ratio:{width}/{height}">'
            f'<iframe src="{src}" width="{width}" height="{height}" frameborder="0" scrolling="no" '
            'referrerpolicy="unsafe-url" loading="lazy" '
            'style="display:block;width:100%;height:100%;border:0"></iframe></span>'
        )
    elif kind in {"dynamic-banner", "category-banner-script"}:
        options = json.dumps(asset["options"], ensure_ascii=True, separators=(",", ":"))
        content = (
            '<script src="https://ads-partners.coupang.com/g.js"></script>'
            f'<script>new PartnersCoupang.G({options});</script>'
        )
    else:
        raise ValueError(f"알 수 없는 쿠팡 소재 형식: {kind}")
    return wrapper + content + "</div>"


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


def _rocket(product: dict) -> bool:
    return bool(product.get("rocket") or product.get("isRocket") or product.get("is_rocket"))


def from_cache(keyword: str, *, options: dict | None = None) -> list[dict]:
    cache = ROOT / "data" / "product_links.json"
    if not cache.exists():
        return []
    try:
        products = json.loads(cache.read_text(encoding="utf-8")).get(keyword, [])
        if (options or {}).get("rocket_only"):
            products = [product for product in products if _rocket(product)]
        return products
    except (json.JSONDecodeError, OSError):
        return []


def products_for(keyword: str, *, options: dict | None = None) -> list[dict]:
    products = search_products(keyword, options=options)
    if (options or {}).get("rocket_only"):
        products = [product for product in products if _rocket(product)]
    return products or from_cache(keyword, options=options)


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
