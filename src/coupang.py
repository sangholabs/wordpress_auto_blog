# 쿠팡 파트너스 Open API 클라이언트 — 키워드로 실제 판매 상품(추적URL 포함)을 가져온다
import hashlib
import hmac
import time

import requests

from .config import env, get_settings

HOST = "https://api-gateway.coupang.com"
PATH = "/v2/providers/affiliate_open_api/apis/openapi/products/search"


def _authorization(method: str, path: str, query: str) -> str:
    access = env("COUPANG_ACCESS_KEY")
    secret = env("COUPANG_SECRET_KEY")
    signed_date = time.strftime("%y%m%dT%H%M%SZ", time.gmtime())
    message = signed_date + method + path + query
    signature = hmac.new(
        secret.encode(), message.encode(), hashlib.sha256
    ).hexdigest()
    return (
        f"CEA algorithm=HmacSHA256, access-key={access}, "
        f"signed-date={signed_date}, signature={signature}"
    )


def search_products(
    keyword: str, limit: int | None = None, *, options: dict | None = None,
) -> list[dict]:
    # API 키가 없으면 빈 리스트를 반환해 호출부가 폴백하도록 한다.
    if not env("COUPANG_ACCESS_KEY") or not env("COUPANG_SECRET_KEY"):
        return []
    cfg = dict(get_settings().get("coupang", {}))
    cfg.update(options or {})
    limit = limit or cfg.get("search_limit", 5)
    query = f"keyword={requests.utils.quote(keyword)}&limit={limit}"
    url = f"{HOST}{PATH}?{query}"
    headers = {"Authorization": _authorization("GET", PATH, query)}
    try:
        r = requests.get(url, headers=headers, timeout=cfg.get("api_timeout_sec", 15))
        r.raise_for_status()
        data = r.json().get("data", {}).get("productData", [])
    except Exception as e:
        print(f"쿠팡 API 호출 실패(검색 링크로 폴백): {e}")
        return []
    return [
        {
            "name": p.get("productName", ""),
            "url": p.get("productUrl", ""),
            "image": p.get("productImage", ""),
            "price": p.get("productPrice", 0),
            "rocket": bool(p.get("isRocket") or p.get("isRocketWow") or p.get("rocket")),
        }
        for p in data
    ]
