import json
from pathlib import Path

import pytest

from src import pipeline


def _prepare(monkeypatch, tmp_path, topics):
    queue = tmp_path / "topic_queue.json"
    queue.write_text(json.dumps(topics, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(pipeline, "QUEUE", queue)
    monkeypatch.setattr(pipeline, "PUBLISHED", tmp_path / "published.json")
    monkeypatch.setattr(pipeline, "LOCK", tmp_path / "pipeline.lock")
    monkeypatch.setattr(pipeline, "get_settings", lambda: {"publish": {"posts_per_day": 3}})
    monkeypatch.setattr(pipeline, "generate_post", lambda topic: {**topic, "title": topic["keyword"], "markdown": "본문"})
    monkeypatch.setattr(pipeline, "save_preview", lambda post: None)


def test_manual_count_one_publishes_exactly_one(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path, [{"keyword": "하나"}, {"keyword": "둘"}, {"keyword": "셋"}])
    published = []
    monkeypatch.setattr(pipeline, "publish_post", lambda post: published.append(post["keyword"]))

    result = pipeline.run(count=1)

    assert published == ["하나"]
    assert result["target"] == 1 and result["published"] == 1


def test_pipeline_continues_after_candidate_failure(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path, [{"keyword": "실패"}, {"keyword": "성공1"}, {"keyword": "성공2"}])
    published = []

    def publish(post):
        if post["keyword"] == "실패":
            raise RuntimeError("mock failure")
        published.append(post["keyword"])

    monkeypatch.setattr(pipeline, "publish_post", publish)
    result = pipeline.run(count=2)

    assert published == ["성공1", "성공2"]
    assert result["published"] == 2 and result["failed"] == 1
    assert json.loads((tmp_path / "published.json").read_text(encoding="utf-8")) == ["성공1", "성공2"]


def test_pipeline_marks_server_duplicate_and_continues_to_new_topic(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path, [{"keyword": "기존"}, {"keyword": "신규"}])
    calls = []

    def publish(post):
        calls.append(post["keyword"])
        return {"_duplicate_skipped": True} if post["keyword"] == "기존" else {"id": 2}

    monkeypatch.setattr(pipeline, "publish_post", publish)
    result = pipeline.run(count=1)

    assert calls == ["기존", "신규"]
    assert result["published"] == 1 and result["skipped"] == 1
    assert json.loads((tmp_path / "published.json").read_text(encoding="utf-8")) == ["기존", "신규"]


def test_pipeline_lock_rejects_concurrent_run(tmp_path):
    lock = tmp_path / "pipeline.lock"
    with pipeline._pipeline_lock(lock):
        with pytest.raises(RuntimeError, match="이미 실행 중"):
            with pipeline._pipeline_lock(lock):
                pass
    assert not lock.exists()


def test_atomic_published_record_never_leaves_tmp(monkeypatch, tmp_path):
    target = tmp_path / "published.json"
    monkeypatch.setattr(pipeline, "PUBLISHED", target)
    pipeline._mark_published("정책")
    assert json.loads(target.read_text(encoding="utf-8")) == ["정책"]
    assert not target.with_suffix(".json.tmp").exists()
