import json
from pathlib import Path

import yaml

from src import config, dashboard, menu, policy_package, secret_scan, settings_editor


ROOT = Path(__file__).resolve().parent.parent


def test_repository_defaults_and_local_override_are_separate(monkeypatch, tmp_path):
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "settings.yaml").write_text("publish:\n  posts_per_day: 3\npolicy_workspace:\n  packages_per_day: 1\n", encoding="utf-8")
    (cfg / "settings.local.yaml").write_text("policy_workspace:\n  packages_per_day: 5\n", encoding="utf-8")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    values = config.get_settings()
    assert values["publish"]["posts_per_day"] == 3
    assert values["policy_workspace"]["packages_per_day"] == 5


def test_menu_now_one_passes_explicit_count(monkeypatch):
    calls = []
    monkeypatch.setattr(menu.pipeline, "run", lambda **kwargs: calls.append(kwargs))
    assert menu._dispatch("1") is True
    assert calls == [{"refresh_keywords": False, "count": 1}]


def test_dashboard_post_command_requests_exactly_one(monkeypatch, tmp_path):
    calls = []
    handler = object.__new__(dashboard.Handler)
    handler.path = "/run"
    handler.headers = {"Host": "localhost:5000", "Cookie": f"dashboard_token={dashboard.DASHBOARD_TOKEN}"}
    handler.send_response = lambda *args: None
    handler.send_header = lambda *args: None
    handler.end_headers = lambda: None
    handler.wfile = SimpleWriter()
    monkeypatch.setattr(dashboard, "_bg", calls.append)
    handler.do_POST()
    assert calls == [[dashboard.PY, "-m", "src.pipeline", "--count", "1"]]


class SimpleWriter:
    def write(self, value):
        return len(value)


def test_dashboard_rejects_cross_origin_even_with_cookie():
    handler = object.__new__(dashboard.Handler)
    handler.headers = {
        "Host": "localhost:5000", "Origin": "https://evil.example",
        "Cookie": f"dashboard_token={dashboard.DASHBOARD_TOKEN}",
    }
    assert handler._same_local_origin() is False


def test_settings_editor_creates_atomic_local_yaml(tmp_path):
    path = tmp_path / "settings.local.yaml"
    settings_editor.set_section_option("publish", "posts_per_day", 5, path)
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == {"publish": {"posts_per_day": 5}}
    assert not path.with_suffix(".yaml.tmp").exists()


def test_secret_scan_reports_location_without_secret_value(tmp_path):
    fake = b"OPENAI_API_KEY=" + b"sk" + b"-" + b"abcdefghijklmnopqrstuvwxyz123456\n"
    finding = secret_scan._find(fake, "sample.env")
    assert finding == [{"kind": "OpenAI API key", "path": "sample.env", "line": 1}]
    assert "sk-" not in json.dumps(finding)


def test_windows_entrypoints_create_logs_and_policy_changes_directory():
    run = (ROOT / "run.bat").read_text(encoding="utf-8")
    policy = (ROOT / "policy_run.bat").read_text(encoding="utf-8")
    assert "if not exist logs mkdir logs" in run
    assert "cd /d %~dp0" in policy and "src.policy_runner" in policy


def test_tracked_defaults_use_blog_image_and_current_gemini():
    settings = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert settings["publish"] == {
        "status": "publish", "posts_per_day": 3, "schedule_time": "09:00",
    }
    assert settings["policy_workspace"]["auto_generate"] is False
    assert settings["policy_workspace"]["packages_per_day"] == 1
    assert settings["policy_workspace"]["schedule_time"] == "09:30"
    assert settings["llm"]["gemini_model"] == "gemini-3.6-flash"
    assert "SUPABASE_STORAGE_BUCKET=blog_image" in env_example
    assert "google-genai" in requirements and "google-generativeai" not in requirements


def test_public_documents_match_current_bucket_defaults_and_commands():
    names = (
        "README.md", "SETUP.md", "CONTINUE-ON-NEW-PC.md", "HANDOFF.md",
        "checklist.md", "context-notes.md",
    )
    documents = {name: (ROOT / name).read_text(encoding="utf-8") for name in names}
    combined = "\n".join(documents.values())
    assert "tistory-images" not in combined
    assert "WordPress.com OAuth" not in combined
    assert "blog_image" in documents["README.md"] and "blog_image" in documents["SETUP.md"]
    assert "python -m src.doctor --live" in documents["README.md"]
    assert "python -m src.pipeline --count 1" in documents["README.md"]
    assert "python -m src.policy_schedule_task" in documents["SETUP.md"]
    assert "하루 1편" in documents["README.md"]


def test_failed_package_build_removes_temporary_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(policy_package, "OUTPUT_ROOT", tmp_path / "output")
    monkeypatch.setattr(policy_package, "get_settings", lambda: {"policy_workspace": {"images_enabled": False}})
    monkeypatch.setattr(policy_package.policy_store, "list_packages", lambda **kwargs: [])
    monkeypatch.setattr(
        policy_package, "render_package_files",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("render failed")),
    )
    candidate = {
        "id": "candidate", "title": "정책", "category": "생활비·세금·환급",
        "source_url": "https://www.gov.kr/test", "checked_at": "2026-08-05T00:00:00+09:00",
    }
    draft = {
        "title": "정책 제목", "category": "생활비·세금·환급", "meta_description": "설명",
        "image_briefs": [], "coupang_queries": [], "markdown": "본문", "tags": [],
    }
    try:
        policy_package.create_package(candidate, draft)
    except RuntimeError:
        pass
    else:
        raise AssertionError("render failure expected")
    assert not list((tmp_path / "output").rglob("*.tmp-*"))
