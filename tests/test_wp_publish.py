from types import SimpleNamespace

import pytest
import requests

from src import images, wp_publish


class Response:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code = status
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


def _prepare(monkeypatch):
    monkeypatch.setattr(wp_publish, "env", lambda key, default="": {
        "WP_SITE_URL": "https://example.test", "WP_USERNAME": "user", "WP_APP_PASSWORD": "pass",
    }.get(key, default))
    monkeypatch.setattr(wp_publish, "_category_name", lambda slug: None)
    monkeypatch.setattr(images, "generate_featured_media", lambda keyword: None)


def _post():
    return {"keyword": "정책 혜택", "title": "제목", "markdown": "본문", "meta_description": "설명", "category": ""}


def test_existing_slug_skips_duplicate_post(monkeypatch):
    _prepare(monkeypatch)
    monkeypatch.setattr(wp_publish, "_find_existing_post", lambda slug: {"id": 7, "link": "https://example.test/existing"})
    monkeypatch.setattr(wp_publish.requests, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not post")))
    result = wp_publish.publish_post(_post(), status="draft")
    assert result["id"] == 7 and result["_duplicate_skipped"] is True


def test_rank_math_meta_error_retries_once_without_meta(monkeypatch):
    _prepare(monkeypatch)
    monkeypatch.setattr(wp_publish, "_find_existing_post", lambda slug: None)
    payloads = []

    def post(url, json, **kwargs):
        payloads.append(dict(json))
        if len(payloads) == 1:
            return Response(400, {"code": "rest_invalid_param", "message": "Invalid meta", "data": {"params": {"meta": "bad"}}}, "bad meta")
        return Response(201, {"id": 8, "link": "https://example.test/new"})

    monkeypatch.setattr(wp_publish.requests, "post", post)
    result = wp_publish.publish_post(_post(), status="draft")
    assert result["id"] == 8
    assert "meta" in payloads[0] and "meta" not in payloads[1]


def test_server_error_is_not_retried(monkeypatch):
    _prepare(monkeypatch)
    monkeypatch.setattr(wp_publish, "_find_existing_post", lambda slug: None)
    calls = []
    monkeypatch.setattr(
        wp_publish.requests, "post",
        lambda *args, **kwargs: calls.append(1) or Response(500, {"code": "server"}, "server error"),
    )
    with pytest.raises(RuntimeError, match="게시 실패 500"):
        wp_publish.publish_post(_post(), status="draft")
    assert len(calls) == 1


def test_ambiguous_timeout_checks_slug_before_failing(monkeypatch):
    _prepare(monkeypatch)
    existing = iter([None, {"id": 9, "link": "https://example.test/recovered"}])
    monkeypatch.setattr(wp_publish, "_find_existing_post", lambda slug: next(existing))
    monkeypatch.setattr(
        wp_publish.requests, "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(requests.Timeout("timeout")),
    )
    assert wp_publish.publish_post(_post(), status="draft")["id"] == 9
