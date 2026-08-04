import base64
import json
from pathlib import Path
from types import SimpleNamespace

from src import policy_images, policy_package
from src.policy_store import now_iso


def _candidate():
    return {
        "id": "abc123", "title": "직장인 자녀 돌봄 지원", "agency": "고용노동부",
        "region": "전국", "category": "자녀·교육·돌봄", "official": True,
        "source_url": "https://www.gov.kr/test", "checked_at": now_iso(),
        "source_updated_at": "2026-08-01", "facts": {"summary": "돌봄 지원", "benefit": "비용 일부 지원"},
    }


def _draft():
    sections = [
        "내가 대상인지 빠른 체크", "받을 수 있는 혜택", "제외 조건과 중복 지원 주의사항",
        "신청기간과 놓치면 안 되는 날짜", "온라인·오프라인 신청 순서", "구비서류와 문의처",
        "30~50대 주부·직장인이 자주 놓치는 경우", "자주 묻는 질문", "신청 전 최종 체크리스트",
    ]
    markdown = "\n\n".join(f"## {title}\n\n공식 자료를 확인해 신청하세요. 자세한 조건은 공식 안내에서 확인 필요합니다." for title in sections)
    return {
        "title": "직장인 부모 돌봄 지원 대상과 신청 방법",
        "meta_description": "공식 정책 안내", "category": "자녀·교육·돌봄",
        "tags": ["돌봄", "직장인", "정부혜택"], "markdown": markdown,
        "image_briefs": [
            {"slot": "featured", "section": "대표", "prompt": "가족", "alt": "가족 일러스트", "caption": "가족"},
            {"slot": "body1", "section": sections[0], "prompt": "체크", "alt": "대상 확인", "caption": "대상 확인"},
            {"slot": "body2", "section": sections[4], "prompt": "신청", "alt": "온라인 신청", "caption": "신청"},
        ], "coupang_queries": ["정리함", "텀블러"],
    }


def test_image_versioning_without_network(monkeypatch, tmp_path):
    monkeypatch.setattr(policy_images, "_openai_bytes", lambda p, s, q: (b"jpeg", "jpg", "gpt-image-2"))
    monkeypatch.setattr(policy_images, "get_settings", lambda: {"policy_workspace": {"image_quality": "medium"}})
    brief = _draft()["image_briefs"][0]
    first = policy_images.generate_image(tmp_path, brief)
    second = policy_images.generate_image(tmp_path, brief)
    assert first["version"] == 1
    assert second["version"] == 2
    assert second["filename"].endswith("_v2.jpg")


def test_openai_image_contract_uses_gpt_image_settings(monkeypatch):
    captured = {}
    class Images:
        def generate(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(b"jpeg").decode())])
    class Client:
        def __init__(self, api_key):
            captured["api_key"] = api_key
            self.images = Images()
    import openai
    monkeypatch.setattr(openai, "OpenAI", Client)
    monkeypatch.setattr(policy_images, "env", lambda key: "secret" if key == "OPENAI_API_KEY" else "")
    monkeypatch.setattr(policy_images, "get_settings", lambda: {"policy_workspace": {"image_model": "gpt-image-2"}})
    content, ext, model = policy_images._openai_bytes("prompt", "1200x640", "medium")
    assert content == b"jpeg" and ext == "jpg" and model == "gpt-image-2"
    assert captured == {
        "api_key": "secret", "model": "gpt-image-2", "prompt": "prompt",
        "size": "1200x640", "quality": "medium", "output_format": "jpeg",
        "output_compression": 88,
    }


def test_tistory_package_has_copy_friendly_structure(monkeypatch, tmp_path):
    monkeypatch.setattr(policy_package, "OUTPUT_ROOT", tmp_path / "output")
    monkeypatch.setattr(policy_package.policy_store, "save_package", lambda package: None)
    monkeypatch.setattr(policy_package.policy_store, "set_candidate_status", lambda *args: None)
    monkeypatch.setattr(policy_package.affiliate, "monetization_mode", lambda: "widget")
    monkeypatch.setattr(policy_package.affiliate, "load_widgets", lambda: ["<div>배너1</div>", "<div>배너2</div>"])

    def fake_image(folder, brief, provider="openai"):
        path = folder / "images" / f"{brief['slot']}.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"image")
        return {"slot": brief["slot"], "path": str(path.relative_to(folder)), "filename": path.name,
                "provider": provider, "model": "mock", "quality": "medium", "size": "1200x800",
                "version": 1, "prompt": "p", "alt": brief["alt"], "caption": brief["caption"],
                "section": brief["section"], "error": ""}

    monkeypatch.setattr(policy_package, "generate_image", fake_image)
    package = policy_package.create_package(_candidate(), _draft())
    folder = Path(package["path"])
    expected = [
        "00_게시가이드.txt", "01_제목.txt", "02_본문_티스토리.html",
        "03_본문_일반텍스트.txt", "04_태그.txt", "05_출처_검증.md",
        "06_manifest.json", "preview.html",
    ]
    assert all((folder / name).exists() for name in expected)
    assert len(list((folder / "segments").glob("*.html"))) == 3
    tistory = (folder / "02_본문_티스토리.html").read_text(encoding="utf-8")
    assert "data-policy-image-slot=\"body1\"" in tistory
    assert "<style" not in tistory
    assert "배너1" in tistory and "배너2" in tistory
    manifest = json.loads((folder / "06_manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["current_images"]) == {"featured", "body1", "body2"}


def test_reindex_restores_sqlite_from_manifest(monkeypatch, tmp_path):
    output = tmp_path / "output"
    folder = output / "2026" / "08" / "05" / "abc_title"
    folder.mkdir(parents=True)
    manifest = {
        "id": "post-1", "candidate_id": "abc", "title": "정책 글", "category": "생활비·세금·환급",
        "created_at": now_iso(), "updated_at": now_iso(), "status": "ready", "published_at": "", "tistory_url": "",
        "source": {"source_type": "url", "external_id": "https://www.gov.kr/x", "official": True,
                   "official_title": "공식 정책", "agency": "행정안전부", "region": "전국",
                   "source_url": "https://www.gov.kr/x", "checked_at": now_iso(), "facts": {"summary": "혜택"}},
    }
    (folder / "06_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(policy_package, "OUTPUT_ROOT", output)
    monkeypatch.setattr(policy_package.policy_store, "DB_PATH", tmp_path / "restored.sqlite3")
    assert policy_package.reindex_packages() == 1
    assert policy_package.policy_store.get_package("post-1")["path"] == str(folder)
