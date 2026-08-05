"""정책 패키지 이미지를 Supabase Storage 공개 버킷에 동기화한다."""

from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from urllib.parse import quote, urlsplit

import requests

from .config import env
from .policy_settings import get as get_policy_settings
from .policy_store import now_iso


def _config() -> dict:
    base_url = env("SUPABASE_URL").strip().rstrip("/")
    key = (
        env("SUPABASE_SECRET_KEY").strip()
        or env("SUPABASE_SERVICE_ROLE_KEY").strip()
        or env("SUPABASE_PUBLISHABLE_KEY").strip()
        or env("SUPABASE_ANON_KEY").strip()
    )
    return {
        "enabled": bool(get_policy_settings().get("supabase_upload_enabled", True)),
        "base_url": base_url,
        "key": key,
        "bucket": env("SUPABASE_STORAGE_BUCKET", "tistory-images").strip(),
        "prefix": env("SUPABASE_STORAGE_PREFIX", "policy-tistory").strip().strip("/"),
    }


def _validated_config() -> dict:
    cfg = _config()
    missing = [
        name for name, value in (
            ("SUPABASE_URL", cfg["base_url"]),
            ("SUPABASE_SECRET_KEY 또는 Supabase API 키", cfg["key"]),
            ("SUPABASE_STORAGE_BUCKET", cfg["bucket"]),
        ) if not value
    ]
    if missing:
        raise RuntimeError("Supabase 이미지 업로드 설정 누락: " + ", ".join(missing))
    parsed = urlsplit(cfg["base_url"])
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host.endswith(".supabase.co"):
        raise ValueError("SUPABASE_URL은 https://프로젝트ID.supabase.co 형식이어야 합니다.")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", cfg["bucket"]):
        raise ValueError("SUPABASE_STORAGE_BUCKET 이름이 올바르지 않습니다.")
    if cfg["prefix"] and not re.fullmatch(r"[A-Za-z0-9._/-]+", cfg["prefix"]):
        raise ValueError("SUPABASE_STORAGE_PREFIX에는 영문, 숫자, 점, 밑줄, 빗금만 사용할 수 있습니다.")
    return cfg


def status() -> dict:
    cfg = _config()
    return {
        "enabled": cfg["enabled"],
        "configured": bool(cfg["base_url"] and cfg["key"] and cfg["bucket"]),
        "project": (urlsplit(cfg["base_url"]).hostname or ""),
        "bucket": cfg["bucket"],
        "prefix": cfg["prefix"],
    }


def verify_status() -> dict:
    """환경변수뿐 아니라 실제 버킷 존재 여부와 공개 상태까지 확인한다."""
    state = status()
    try:
        cfg = _validated_config()
        _check_public_bucket(cfg)
    except Exception as exc:
        return {**state, "verified": False, "public": False, "error": str(exc)}
    return {**state, "verified": True, "public": True, "error": ""}


def _headers(cfg: dict, content_type: str = "application/json") -> dict:
    headers = {
        "apikey": cfg["key"],
        "Content-Type": content_type,
    }
    if not str(cfg["key"]).startswith(("sb_secret_", "sb_publishable_")):
        headers["Authorization"] = f"Bearer {cfg['key']}"
    return headers


def _check_public_bucket(cfg: dict) -> None:
    url = f"{cfg['base_url']}/storage/v1/bucket/{quote(cfg['bucket'], safe='')}"
    response = requests.get(url, headers=_headers(cfg), timeout=15)
    if response.status_code == 404:
        raise RuntimeError(
            f"Supabase Storage 버킷 '{cfg['bucket']}'이 없습니다. 공개 버킷으로 먼저 생성하세요."
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Supabase 버킷 확인 실패 HTTP {response.status_code}: {response.text[:300]}")
    try:
        bucket = response.json()
    except ValueError as exc:
        raise RuntimeError("Supabase 버킷 확인 응답이 JSON이 아닙니다.") from exc
    if not bucket.get("public"):
        raise RuntimeError(
            f"Supabase 버킷 '{cfg['bucket']}'이 비공개입니다. 블로그 이미지용 공개 버킷으로 변경하세요."
        )


def _upload(cfg: dict, local_file: Path, object_path: str) -> str:
    encoded = quote(object_path, safe="/")
    url = f"{cfg['base_url']}/storage/v1/object/{quote(cfg['bucket'], safe='')}/{encoded}"
    content_type = mimetypes.guess_type(local_file.name)[0] or "application/octet-stream"
    headers = _headers(cfg, content_type)
    headers.update({"x-upsert": "true", "cache-control": "31536000"})
    response = requests.post(url, headers=headers, data=local_file.read_bytes(), timeout=60)
    if response.status_code not in {200, 201}:
        raise RuntimeError(f"Supabase 이미지 업로드 실패 HTTP {response.status_code}: {response.text[:300]}")
    return (
        f"{cfg['base_url']}/storage/v1/object/public/"
        f"{quote(cfg['bucket'], safe='')}/{encoded}"
    )


def sync_manifest_images(package_dir: Path, manifest: dict) -> list[str]:
    """현재 이미지 버전을 업로드하고 manifest에 공개 URL을 기록한다."""
    cfg = _config()
    state = manifest.setdefault("supabase", {})
    state.setdefault("images", {})
    state.update({"enabled": cfg["enabled"], "bucket": cfg["bucket"], "prefix": cfg["prefix"]})
    if not cfg["enabled"]:
        return []
    try:
        cfg = _validated_config()
        _check_public_bucket(cfg)
    except Exception as exc:
        state["configured"] = False
        state["last_error"] = str(exc)
        print(f"[안내] Supabase 이미지 업로드 건너뜀: {exc}", flush=True)
        return [str(exc)]
    state["configured"] = True
    state["last_error"] = ""
    warnings: list[str] = []
    base = package_dir.resolve()
    created = str(manifest.get("created_at", ""))[:10].replace("-", "/") or "undated"
    package_id = re.sub(r"[^A-Za-z0-9._-]+", "-", str(manifest.get("id", "package")))
    for slot, relative in manifest.get("current_images", {}).items():
        local_file = (package_dir / relative).resolve()
        if base not in local_file.parents or not local_file.is_file():
            warnings.append(f"Supabase 업로드할 로컬 이미지가 없음: {relative}")
            continue
        previous = state["images"].get(slot, {})
        if previous.get("local_path") == relative and previous.get("public_url"):
            continue
        suffix = local_file.suffix.lower() or ".jpg"
        object_path = "/".join(
            part for part in (cfg["prefix"], created, package_id, f"{slot}{suffix}") if part
        )
        try:
            public_url = _upload(cfg, local_file, object_path)
        except Exception as exc:
            warnings.append(f"{slot} Supabase 업로드 실패: {exc}")
            continue
        state["images"][slot] = {
            "local_path": relative,
            "object_path": object_path,
            "public_url": public_url,
            "uploaded_at": now_iso(),
        }
        print(f"    Supabase 업로드 완료: {slot} → {public_url}", flush=True)
    state["last_sync_at"] = now_iso()
    return warnings
