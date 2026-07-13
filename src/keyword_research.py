# 검색 자동완성으로 카테고리별 롱테일 키워드를 수집한다 (LLM 미사용, 0토큰)
import json
import time

import requests

from .config import DATA_DIR, get_categories, get_settings

KEYWORDS_FILE = DATA_DIR / "keywords.json"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def _cfg() -> dict:
    return get_settings().get("keyword_research", {})


def google_suggest(query: str) -> list[str]:
    url = "https://suggestqueries.google.com/complete/search"
    params = {"client": "firefox", "hl": "ko", "q": query}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=_cfg().get("timeout_sec", 10))
        return r.json()[1]
    except Exception:
        return []


def naver_suggest(query: str) -> list[str]:
    url = "https://ac.search.naver.com/nx/ac"
    params = {"q": query, "st": 100, "frm": "nv", "r_format": "json"}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=_cfg().get("timeout_sec", 10))
        items = r.json().get("items", [[]])[0]
        return [i[0] for i in items]
    except Exception:
        return []


def collect() -> dict:
    cfg = _cfg()
    delay = cfg.get("request_delay_sec", 0.5)
    use_google = cfg.get("use_google", True)
    use_naver = cfg.get("use_naver", True)
    cats = get_categories()["categories"]
    result = {}
    for cat in cats:
        found: set[str] = set()
        for seed in cat["seed_keywords"]:
            if use_google:
                found.update(google_suggest(seed))
            if use_naver:
                found.update(naver_suggest(seed))
            time.sleep(delay)  # 과도한 요청 방지
        result[cat["slug"]] = sorted(found)
    KEYWORDS_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    total = sum(len(v) for v in result.values())
    print(f"키워드 {total}개 수집 → {KEYWORDS_FILE}")
    return result


if __name__ == "__main__":
    collect()
