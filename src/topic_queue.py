# 수집 키워드를 상업적 의도·롱테일 기준으로 점수화하고 중복 제거해 주제 큐를 만든다 (0토큰)
import json
from functools import lru_cache

from .config import DATA_DIR, get_settings

KEYWORDS_FILE = DATA_DIR / "keywords.json"
QUEUE_FILE = DATA_DIR / "topic_queue.json"
PUBLISHED_FILE = DATA_DIR / "published.json"

# 구매 의도가 강한 신호 — 쿠팡 전환에 유리 (설정 미지정 시 기본값)
INTENT_WORDS = ["추천", "비교", "후기", "순위", "가성비", "best", "TOP", "단점", "vs"]


@lru_cache(maxsize=1)
def _score_cfg():
    s = get_settings().get("topic_queue", {})
    words = [w.lower() for w in s.get("intent_words", INTENT_WORDS)]
    return words, s.get("longtail_min_words", 2), s.get("longtail_max_words", 5)


def score_keyword(kw: str) -> int:
    intent, lo, hi = _score_cfg()
    score = 0
    for w in intent:
        if w in kw.lower():
            score += 3
    words = len(kw.split())
    if lo <= words <= hi:  # 적당한 롱테일이 경쟁 낮고 전환 좋음
        score += 2
    if len(kw) >= 6:
        score += 1
    return score


def _published_set() -> set[str]:
    if PUBLISHED_FILE.exists():
        return set(json.loads(PUBLISHED_FILE.read_text(encoding="utf-8")))
    return set()


def build() -> list[dict]:
    keywords = json.loads(KEYWORDS_FILE.read_text(encoding="utf-8"))
    done = _published_set()
    queue = []
    for slug, kws in keywords.items():
        for kw in kws:
            if kw in done:
                continue
            queue.append({"category": slug, "keyword": kw, "score": score_keyword(kw)})
    queue.sort(key=lambda x: x["score"], reverse=True)
    QUEUE_FILE.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"주제 큐 {len(queue)}건 생성 → {QUEUE_FILE}")
    return queue


if __name__ == "__main__":
    build()
