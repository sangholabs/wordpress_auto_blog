import re
from pathlib import Path

import pytest

from src import policy_cli


INPUTS = {
    "0": [],
    "1": [],
    "2": ["https://www.gov.kr/policy"],
    "3": [],
    "4": ["서울, 성남"],
    "5": ["candidate-1", "1", "0"],
    "6": ["1", "1"],
    "7": [],
    "8": ["post-1"],
    "9": ["post-1", "html"],
    "10": ["post-1"],
    "11": ["post-1"],
    "12": ["post-1", ""],
    "13": ["post-1"],
    "14": [],
    "15": [],
    "16": ["post-1", "대표", "1"],
    "17": ["post-1", "1"],
    "18": [],
    "19": ["post-1", ""],
    "20": [],
    "21": [],
    "22": [],
    "23": [],
    "24": [],
}

EXPECTED = {
    "0": "exit",
    "1": "collect",
    "2": "import-url",
    "3": "candidates",
    "4": "regions",
    "5": "generate",
    "6": "recommended",
    "7": "packages",
    "8": "preview",
    "9": "copy",
    "10": "open",
    "11": "zip",
    "12": "published",
    "13": "rebuild",
    "14": "auto-run",
    "15": "auto-settings",
    "16": "regenerate",
    "17": "retry-images",
    "18": "image-settings",
    "19": "seo-local",
    "20": "affiliate-settings",
    "21": "banner-setup",
    "22": "dashboard",
    "23": "claude-login",
    "24": "required-pages",
}


def _install_safe_actions(monkeypatch, events):
    monkeypatch.setattr(policy_cli, "_workspace_status", lambda: None)
    monkeypatch.setattr(policy_cli, "_print_candidates", lambda *args, **kwargs: events.append("candidates") or [])
    monkeypatch.setattr(policy_cli, "_print_packages", lambda *args, **kwargs: events.append("packages") or [])
    monkeypatch.setattr(policy_cli.policy_service, "collect", lambda: events.append("collect"))
    monkeypatch.setattr(policy_cli.policy_service, "import_url", lambda *args: events.append("import-url"))
    monkeypatch.setattr(
        policy_cli.policy_service, "generate_candidate",
        lambda *args, **kwargs: events.append("generate"),
    )
    monkeypatch.setattr(policy_cli.policy_service, "open_package", lambda *args, **kwargs: events.append("preview" if kwargs.get("preview") else "open"))
    monkeypatch.setattr(policy_cli.policy_service, "copy_content", lambda *args: events.append("copy"))
    monkeypatch.setattr(policy_cli.policy_service, "set_regions", lambda *args: events.append("regions"))
    monkeypatch.setattr(policy_cli.policy_service, "generate_recommended", lambda *args: events.append("recommended"))
    monkeypatch.setattr(policy_cli.policy_package, "regenerate_image", lambda *args: events.append("regenerate") or {"path": "image.jpg"})
    monkeypatch.setattr(policy_cli.policy_package, "create_zip", lambda *args: events.append("zip") or Path("post.zip"))
    monkeypatch.setattr(policy_cli.policy_package, "mark_manifest_published", lambda *args: events.append("published"))
    monkeypatch.setattr(policy_cli.policy_package, "rebuild_package", lambda *args: events.append("rebuild") or {"path": "package"})
    monkeypatch.setattr(policy_cli.policy_package, "retry_failed_images", lambda *args: events.append("retry-images") or [])
    monkeypatch.setattr(policy_cli.policy_runner, "run", lambda **kwargs: events.append("auto-run") or {"status": "completed"})
    monkeypatch.setattr(policy_cli, "_auto_settings_menu", lambda: events.append("auto-settings"))
    monkeypatch.setattr(policy_cli, "_affiliate_settings_menu", lambda: events.append("affiliate-settings"))
    monkeypatch.setattr(policy_cli.policy_seo, "run_local_for_package", lambda *args: events.append("seo-local") or {"score": 100, "status": "pass", "issues": []})
    monkeypatch.setattr(policy_cli.policy_seo, "run_published_for_package", lambda *args: events.append("seo-url") or {"score": 100, "status": "pass", "issues": []})
    monkeypatch.setattr(policy_cli, "_open_policy_dashboard", lambda: events.append("dashboard"))
    monkeypatch.setattr(policy_cli, "_claude_login", lambda: events.append("claude-login"))
    monkeypatch.setattr(policy_cli.banner_setup, "setup_banner", lambda: events.append("banner-setup"))
    monkeypatch.setattr(policy_cli.policy_pages, "create_required_pages_package", lambda: events.append("required-pages"))
    monkeypatch.setattr(policy_cli, "_image_settings_menu", lambda: events.append("image-settings"))


@pytest.mark.parametrize("choice", [str(number) for number in range(25)])
def test_all_policy_menu_numbers_dispatch_to_the_displayed_feature(monkeypatch, choice):
    events = []
    _install_safe_actions(monkeypatch, events)
    if choice == "0":
        answers = iter(["0"])
    else:
        answers = iter([choice, *INPUTS[choice], "", "0"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    policy_cli.interactive()

    if choice == "0":
        assert events == []
    else:
        assert EXPECTED[choice] in events


def test_policy_menu_prints_every_number_once(capsys, monkeypatch):
    monkeypatch.setattr(policy_cli, "_workspace_status", lambda: None)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "0")
    policy_cli.interactive()
    output = capsys.readouterr().out
    numbers = [int(value) for value in re.findall(r"(?<!\d)(\d{1,2})\.", output)]
    assert sorted(numbers) == list(range(25))
    assert len(numbers) == 25
    for heading in (
        "[정책 후보 준비]", "[수동 글 생성]", "[생성 패키지 관리 — 수동·자동 공통]",
        "[자동 글 생성]", "[이미지]", "[SEO]", "[쿠팡 파트너스]", "[기타]",
    ):
        assert heading in output
    assert "SEO 검사 (게시 전/게시 URL, 글 재작성 안 함)" in output


@pytest.mark.parametrize(
    ("answers", "expected"),
    [
        (["1"], ("schedule", "on")),
        (["2"], ("schedule", "off")),
        (["3", "10:30"], ("setting", "schedule_time", "10:30")),
        (["4", "2"], ("setting", "packages_per_day", "2")),
        (["5"], ("schedule", "status")),
    ],
)
def test_auto_settings_submenu_routes_all_actions(monkeypatch, answers, expected):
    events = []
    values = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(values))
    monkeypatch.setattr(policy_cli.policy_schedule_task, "on", lambda: events.append(("schedule", "on")) or True)
    monkeypatch.setattr(policy_cli.policy_schedule_task, "off", lambda: events.append(("schedule", "off")) or True)
    monkeypatch.setattr(policy_cli.policy_schedule_task, "status", lambda: events.append(("schedule", "status")) or False)
    monkeypatch.setattr(
        policy_cli.policy_settings, "set_value",
        lambda key, value: events.append(("setting", key, value)) or value,
    )
    policy_cli._auto_settings_menu()
    assert expected in events


@pytest.mark.parametrize(
    ("answers", "expected"),
    [
        (["1", "1"], ("coupang_enabled", True)),
        (["2", "2"], ("coupang_layout", "grouped")),
        (["3", "3"], ("coupang_max_blocks", "3")),
        (["4", "2"], ("rocket_only", False)),
    ],
)
def test_affiliate_settings_submenu_routes_all_actions(monkeypatch, answers, expected):
    events = []
    values = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(values))
    monkeypatch.setattr(
        policy_cli.policy_settings, "set_value",
        lambda key, value: events.append((key, value)) or value,
    )
    policy_cli._affiliate_settings_menu()
    assert events == [expected]


def test_affiliate_settings_can_replace_package_product_links(monkeypatch):
    events = []
    values = iter([
        "5", "post-1",
        "1", "https://link.coupang.com/a/one",
        "1", "https://link.coupang.com/a/two",
    ])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(values))
    monkeypatch.setattr(policy_cli, "_print_packages", lambda: [])
    monkeypatch.setattr(
        policy_cli.policy_package, "set_coupang_assets",
        lambda package_id, assets: events.append((package_id, assets)) or [{"url": url} for url in assets],
    )
    policy_cli._affiliate_settings_menu()
    assert events == [("post-1", ["https://link.coupang.com/a/one", "https://link.coupang.com/a/two"])]


def test_coupang_prompt_accepts_single_line_html_directly(monkeypatch):
    iframe = '<iframe src="https://coupa.ng/cox0qY" width="120" height="240"></iframe>'
    values = iter([iframe, "0"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(values))
    monkeypatch.setattr(
        policy_cli.policy_settings, "get", lambda: {"coupang_max_blocks": 2},
    )
    assert policy_cli._prompt_coupang_assets() == [iframe]


def test_coupang_prompt_blank_reprompts_instead_of_skipping_next_article(monkeypatch, capsys):
    values = iter(["", "0"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(values))
    monkeypatch.setattr(policy_cli.policy_settings, "get", lambda: {"coupang_max_blocks": 2})
    assert policy_cli._prompt_coupang_assets() == []
    assert "빈 입력은 완료가 아닙니다" in capsys.readouterr().out


def test_coupang_prompt_shows_article_and_asset_progress(monkeypatch):
    prompts = []
    answers = iter(["0"])

    def answer(prompt=""):
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr("builtins.input", answer)
    monkeypatch.setattr(policy_cli.policy_settings, "get", lambda: {"coupang_max_blocks": 2})
    assert policy_cli._prompt_coupang_assets(3, 5) == []
    assert any("글 3/5 · 쿠팡 소재 1/2" in prompt for prompt in prompts)


@pytest.mark.parametrize(("answer", "enabled"), [("1", True), ("2", False)])
def test_image_settings_submenu_is_tistory_scoped(monkeypatch, answer, enabled):
    events = []
    monkeypatch.setattr("builtins.input", lambda _prompt="": answer)
    monkeypatch.setattr(
        policy_cli.policy_settings, "set_value",
        lambda key, value: events.append((key, value)),
    )
    policy_cli._image_settings_menu()
    assert events == [("images_enabled", enabled)]


def test_image_settings_can_remove_featured_from_all_existing_bodies(monkeypatch):
    events = []
    answers = iter(["6", "all"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    monkeypatch.setattr(policy_cli, "_print_packages", lambda: [])
    monkeypatch.setattr(
        policy_cli.policy_package,
        "remove_featured_from_body",
        lambda package_id=None: events.append(package_id) or {"total": 3, "rebuilt": 3, "errors": []},
    )
    policy_cli._image_settings_menu()
    assert events == [None]
