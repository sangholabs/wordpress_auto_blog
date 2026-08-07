# 전체 파이프라인: 키워드 수집 → 주제 큐 → 글 생성 → 발행 → 발행 기록 (cron/스케줄러용)
import argparse
import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from . import keyword_research, topic_queue
from .config import DATA_DIR, get_settings
from .formatter import save_preview
from .generate_post import generate_post
from .wp_publish import publish_post

PUBLISHED = DATA_DIR / "published.json"
QUEUE = DATA_DIR / "topic_queue.json"
LOCK = DATA_DIR / "wordpress_pipeline.lock"
LOCK_STALE_HOURS = 12


def _load_published() -> set[str]:
    if PUBLISHED.exists():
        try:
            value = json.loads(PUBLISHED.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"WordPress 발행 기록을 읽을 수 없습니다: {PUBLISHED}") from exc
        if not isinstance(value, list):
            raise RuntimeError(f"WordPress 발행 기록 형식이 올바르지 않습니다: {PUBLISHED}")
        return {str(item) for item in value}
    return set()


def _mark_published(keyword: str):
    done = _load_published()
    done.add(keyword)
    temporary = PUBLISHED.with_suffix(PUBLISHED.suffix + ".tmp")
    temporary.write_text(
        json.dumps(sorted(done), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(temporary, PUBLISHED)


def _lock_is_stale(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        started = datetime.fromisoformat(str(payload.get("started_at", "")))
    except (OSError, ValueError, json.JSONDecodeError):
        return True
    return datetime.now().astimezone() - started.astimezone() > timedelta(hours=LOCK_STALE_HOURS)


@contextmanager
def _pipeline_lock(path: Path | None = None):
    path = path or LOCK
    if path.exists() and _lock_is_stale(path):
        path.unlink(missing_ok=True)
    payload = json.dumps(
        {"pid": os.getpid(), "started_at": datetime.now().astimezone().isoformat()},
        ensure_ascii=False,
    )
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError("WordPress 파이프라인이 이미 실행 중입니다. 중복 발행을 막기 위해 종료합니다.") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(payload)
        yield
    finally:
        path.unlink(missing_ok=True)


def run(refresh_keywords: bool = False, count: int | None = None) -> dict:
    configured = int(get_settings()["publish"]["posts_per_day"])
    target = configured if count is None else int(count)
    if target < 1:
        raise ValueError("발행 편수는 1 이상이어야 합니다.")
    result = {
        "status": "completed", "target": target, "published": 0,
        "skipped": 0, "failed": 0, "errors": [],
    }
    with _pipeline_lock():
        if refresh_keywords or not QUEUE.exists():
            keyword_research.collect()
            topic_queue.build()
        try:
            queue = json.loads(QUEUE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"WordPress 주제 큐를 읽을 수 없습니다: {QUEUE}") from exc
        if not isinstance(queue, list):
            raise RuntimeError("WordPress 주제 큐 형식이 올바르지 않습니다.")
        done = _load_published()
        attempts = 0
        max_attempts = target * 3
        for topic in queue:
            keyword = str(topic.get("keyword", "")).strip()
            if not keyword or keyword in done:
                continue
            attempts += 1
            print(f"[WordPress {result['published'] + 1}/{target}] {keyword}", flush=True)
            try:
                post = generate_post(topic)
                save_preview(post)
                published_post = publish_post(post) or {}
                _mark_published(keyword)
                done.add(keyword)
                if published_post.get("_duplicate_skipped"):
                    result["skipped"] += 1
                    print(f"[건너뜀] WordPress에 동일 slug 글이 이미 있습니다: {keyword}", flush=True)
                    continue
                result["published"] += 1
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                result["failed"] += 1
                message = f"{keyword}: {exc}"
                result["errors"].append(message)
                print(f"[오류] {message}", flush=True)
            if result["published"] >= target or attempts >= max_attempts:
                break
    if result["published"] == 0 and not result["errors"]:
        print("처리할 새 주제가 없습니다. `python -m src.pipeline --refresh` 로 키워드를 갱신하세요.")
    else:
        print(
            f"파이프라인 완료. 발행 {result['published']}건 / "
            f"중복 건너뜀 {result['skipped']}건 / 실패 {result['failed']}건.",
            flush=True,
        )
    if result["published"] < target and result["errors"]:
        result["status"] = "partial" if result["published"] else "failed"
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WordPress 글 생성·발행 파이프라인")
    parser.add_argument("--refresh", action="store_true", help="키워드와 주제 큐를 먼저 갱신")
    parser.add_argument("--count", type=int, help="이번 실행에서 발행할 편수")
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args(sys.argv[1:])
    outcome = run(refresh_keywords=args.refresh, count=args.count)
    raise SystemExit(0 if outcome["status"] in {"completed", "partial"} else 1)
