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


def _root(kw: str) -> str:
    # 주제의 '상품 뿌리'를 뽑는다(유사 중복 제거용). 띄어쓰기를 없애고 의도어·연도를 제거해
    # "무선청소기"와 "무선 청소기 비교"가 같은 뿌리로 묶이게 한다.
    intent, _, _ = _score_cfg()
    t = kw.lower().replace(" ", "")
    for w in list(intent) + ["추천순위", "2024", "2025", "2026", "년"]:
        t = t.replace(w, "")
    return t or kw.lower().replace(" ", "")


def _same_product(a: str, b: str) -> bool:
    # 두 뿌리가 같은 상품인지. 수식어가 붙은 세부 종류(글라스에어프라이어=에어프라이어)를 묶되,
    # 로봇청소기/무선청소기처럼 서로 포함 안 되는 건 별개로 둔다.
    if a == b:
        return True
    short, long = sorted((a, b), key=len)
    return len(short) >= 4 and (long.startswith(short) or long.endswith(short))


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
    if get_settings().get("topic_queue", {}).get("one_per_product", True):
        # 같은 상품 뿌리 단어는 최고 점수 1개만 남긴다(유사 중복 글 방지)
        seen, deduped = [], []
        for t in queue:
            r = _root(t["keyword"])
            if any(_same_product(r, s) for s in seen):
                continue
            seen.append(r)
            deduped.append(t)
        queue = deduped
    QUEUE_FILE.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"주제 큐 {len(queue)}건 생성 → {QUEUE_FILE}")
    return queue


if __name__ == "__main__":
    build()
