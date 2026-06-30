# 전체 파이프라인: 키워드 수집 → 주제 큐 → 글 생성 → 발행 → 발행 기록 (cron/스케줄러용)
import json
import sys

from . import keyword_research, topic_queue
from .config import DATA_DIR, get_settings
from .formatter import save_preview
from .generate_post import generate_post
from .wp_publish import publish_post

PUBLISHED = DATA_DIR / "published.json"
QUEUE = DATA_DIR / "topic_queue.json"


def _load_published() -> set[str]:
    if PUBLISHED.exists():
        return set(json.loads(PUBLISHED.read_text(encoding="utf-8")))
    return set()


def _mark_published(keyword: str):
    done = _load_published()
    done.add(keyword)
    PUBLISHED.write_text(
        json.dumps(sorted(done), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def run(refresh_keywords: bool = False):
    if refresh_keywords or not QUEUE.exists():
        keyword_research.collect()
        topic_queue.build()
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    done = _load_published()
    target = get_settings()["publish"]["posts_per_day"]
    count = 0
    for topic in queue:
        if topic["keyword"] in done:
            continue
        post = generate_post(topic)
        save_preview(post)
        publish_post(post)
        _mark_published(topic["keyword"])
        count += 1
        if count >= target:
            break
    if count == 0:
        print("처리할 새 주제가 없습니다. `python -m src.pipeline --refresh` 로 키워드를 갱신하세요.")
    else:
        print(f"파이프라인 완료. {count}건 발행.")


if __name__ == "__main__":
    run(refresh_keywords="--refresh" in sys.argv)
