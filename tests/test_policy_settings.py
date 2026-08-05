import yaml

from src import policy_settings, set_option, settings_editor


def test_section_scoped_settings_do_not_cross_wordpress_and_tistory(monkeypatch, tmp_path):
    target = tmp_path / "settings.yaml"
    target.write_text(
        "publish:\n  schedule_time: \"09:00\"\n  posts_per_day: 3\n"
        "coupang:\n  rocket_only: false\n"
        "policy_workspace:\n  schedule_time: \"09:30\"\n  packages_per_day: 1\n  rocket_only: true\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings_editor, "SETTINGS", target)

    policy_settings.set_value("schedule_time", "10:15")
    policy_settings.set_value("rocket_only", False)
    set_option.set_option("posts_per_day", "5")

    values = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert values["publish"] == {"schedule_time": "09:00", "posts_per_day": 5}
    assert values["coupang"]["rocket_only"] is False
    assert values["policy_workspace"]["schedule_time"] == "10:15"
    assert values["policy_workspace"]["rocket_only"] is False


def test_policy_settings_validate_ranges():
    assert policy_settings.normalize("packages_per_day", "5") == 5
    assert policy_settings.normalize("coupang_enabled", "false") is False
    assert policy_settings.normalize("images_enabled", "false") is False
    try:
        policy_settings.normalize("packages_per_day", "9")
    except ValueError:
        pass
    else:
        raise AssertionError("하루 편수 범위 검증이 필요합니다.")
