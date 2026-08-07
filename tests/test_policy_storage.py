from pathlib import Path

from src import policy_storage


class _Response:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def test_supabase_sync_uploads_current_images_and_records_public_urls(monkeypatch, tmp_path):
    image = tmp_path / "images" / "featured.jpg"
    image.parent.mkdir()
    image.write_bytes(b"jpeg")
    manifest = {
        "id": "candidate-20260805120000", "created_at": "2026-08-05T12:00:00+09:00",
        "current_images": {"featured": "images/featured.jpg"},
    }
    cfg = {
        "enabled": True, "base_url": "https://project.supabase.co", "key": "secret",
        "bucket": "blog_image", "prefix": "policy-tistory",
    }
    uploads = []
    monkeypatch.setattr(policy_storage, "_config", lambda: dict(cfg))
    monkeypatch.setattr(policy_storage, "_validated_config", lambda: dict(cfg))
    monkeypatch.setattr(
        policy_storage.requests, "get",
        lambda *args, **kwargs: _Response(payload={"public": True}),
    )
    monkeypatch.setattr(
        policy_storage.requests, "post",
        lambda url, **kwargs: uploads.append((url, kwargs)) or _Response(status_code=200),
    )

    assert policy_storage.sync_manifest_images(tmp_path, manifest) == []
    remote = manifest["supabase"]["images"]["featured"]
    assert remote["local_path"] == "images/featured.jpg"
    assert remote["public_url"].startswith(
        "https://project.supabase.co/storage/v1/object/public/blog_image/"
    )
    assert uploads[0][1]["headers"]["x-upsert"] == "true"
    assert uploads[0][1]["headers"]["Content-Type"] == "image/jpeg"
    assert uploads[0][1]["data"] == b"jpeg"


def test_supabase_sync_keeps_local_package_when_configuration_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(policy_storage, "_config", lambda: {
        "enabled": True, "base_url": "", "key": "", "bucket": "blog_image", "prefix": "policy",
    })
    monkeypatch.setattr(
        policy_storage, "_validated_config",
        lambda: (_ for _ in ()).throw(RuntimeError("Supabase 이미지 업로드 설정 누락")),
    )
    manifest = {"current_images": {}}
    warnings = policy_storage.sync_manifest_images(tmp_path, manifest)
    assert warnings == ["Supabase 이미지 업로드 설정 누락"]
    assert manifest["supabase"]["configured"] is False


def test_verify_status_checks_real_public_bucket(monkeypatch):
    state = {"enabled": True, "configured": True, "project": "project.supabase.co", "bucket": "blog_image", "prefix": "policy"}
    monkeypatch.setattr(policy_storage, "status", lambda: dict(state))
    monkeypatch.setattr(policy_storage, "_validated_config", lambda: {"bucket": "blog_image"})
    monkeypatch.setattr(policy_storage, "_check_public_bucket", lambda cfg: None)
    assert policy_storage.verify_status()["verified"] is True


def test_supabase_sync_reuses_complete_public_urls_without_bucket_request(monkeypatch, tmp_path):
    image = tmp_path / "images" / "body1.jpg"
    image.parent.mkdir()
    image.write_bytes(b"jpeg")
    manifest = {
        "current_images": {"body1": "images/body1.jpg"},
        "supabase": {
            "images": {
                "body1": {
                    "local_path": "images/body1.jpg",
                    "public_url": "https://project.supabase.co/storage/v1/object/public/blog_image/body1.jpg",
                }
            }
        },
    }
    monkeypatch.setattr(
        policy_storage,
        "_config",
        lambda: {
            "enabled": True,
            "base_url": "https://project.supabase.co",
            "key": "secret",
            "bucket": "blog_image",
            "prefix": "policy-tistory",
        },
    )
    monkeypatch.setattr(
        policy_storage,
        "_validated_config",
        lambda: (_ for _ in ()).throw(AssertionError("설정 검증을 다시 호출하면 안 됩니다.")),
    )

    assert policy_storage.sync_manifest_images(tmp_path, manifest) == []
