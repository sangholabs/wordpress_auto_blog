import plistlib
import subprocess

from src import schedule_task


def _completed(args, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args, returncode, stdout, stderr)


def _mac_paths(monkeypatch, tmp_path):
    root = tmp_path / "project"
    python = root / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")
    python.chmod(0o755)
    agents = tmp_path / "Library" / "LaunchAgents"
    plist = agents / f"{schedule_task.LAUNCHD_LABEL}.plist"
    monkeypatch.setattr(schedule_task, "ROOT", root)
    monkeypatch.setattr(schedule_task, "LAUNCH_AGENTS_DIR", agents)
    monkeypatch.setattr(schedule_task, "PLIST_PATH", plist)
    monkeypatch.setattr(schedule_task.os, "getuid", lambda: 501, raising=False)  # Windows에는 os.getuid가 없다
    return root, python, plist


def test_windows_on_keeps_existing_schtasks_contract(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(schedule_task, "ROOT", tmp_path)
    monkeypatch.setattr(schedule_task, "_system", lambda: "Windows")
    monkeypatch.setattr(
        schedule_task, "get_settings", lambda: {"publish": {"schedule_time": "09:30"}}
    )

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return _completed(args)

    monkeypatch.setattr(schedule_task.subprocess, "run", fake_run)

    assert schedule_task.on() is True
    assert calls[0][0] == [
        "schtasks", "/create", "/tn", "blog-auto", "/tr", str(tmp_path / "run.bat"),
        "/sc", "daily", "/st", "09:30", "/f",
    ]


def test_windows_off_reports_delete_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(schedule_task, "_system", lambda: "Windows")

    def fake_run(args, **kwargs):
        calls.append(args)
        return _completed(args, returncode=0 if "/query" in args else 1, stderr="denied")

    monkeypatch.setattr(schedule_task.subprocess, "run", fake_run)

    assert schedule_task.off() is False
    assert calls == [
        ["schtasks", "/query", "/tn", "blog-auto"],
        ["schtasks", "/delete", "/tn", "blog-auto", "/f"],
    ]


def test_macos_on_writes_plist_and_bootstraps(monkeypatch, tmp_path):
    root, python, plist = _mac_paths(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setenv("PATH", "/test/node/bin:/usr/bin:/bin")
    monkeypatch.setattr(schedule_task, "_system", lambda: "Darwin")
    monkeypatch.setattr(schedule_task, "_launchd_status", lambda: False)
    monkeypatch.setattr(
        schedule_task, "get_settings", lambda: {"publish": {"schedule_time": "07:05"}}
    )

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return _completed(args)

    monkeypatch.setattr(schedule_task.subprocess, "run", fake_run)

    assert schedule_task.on() is True
    with open(plist, "rb") as file:
        payload = plistlib.load(file)

    assert payload["ProgramArguments"] == [str(python), "-m", "src.pipeline"]
    assert payload["WorkingDirectory"] == str(root)
    assert payload["StartCalendarInterval"] == {"Hour": 7, "Minute": 5}
    assert payload["StandardOutPath"] == str(root / "logs" / "pipeline.log")
    assert payload["StandardErrorPath"] == str(root / "logs" / "pipeline.log")
    assert payload["EnvironmentVariables"] == {
        "PATH": "/test/node/bin:/usr/bin:/bin",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    assert "RunAtLoad" not in payload
    assert calls[0][0] == ["launchctl", "bootstrap", "gui/501", str(plist)]


def test_macos_on_replaces_loaded_job(monkeypatch, tmp_path):
    _mac_paths(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setattr(schedule_task, "_system", lambda: "Darwin")
    monkeypatch.setattr(schedule_task, "_launchd_status", lambda: True)
    monkeypatch.setattr(
        schedule_task, "get_settings", lambda: {"publish": {"schedule_time": "18:45"}}
    )

    def fake_run(args, **kwargs):
        calls.append(args)
        return _completed(args)

    monkeypatch.setattr(schedule_task.subprocess, "run", fake_run)

    assert schedule_task.on() is True
    assert calls[0] == [
        "launchctl", "bootout", f"gui/501/{schedule_task.LAUNCHD_LABEL}"
    ]
    assert calls[1][0:3] == ["launchctl", "bootstrap", "gui/501"]


def test_macos_off_unloads_and_removes_plist(monkeypatch, tmp_path):
    _, _, plist = _mac_paths(monkeypatch, tmp_path)
    plist.parent.mkdir(parents=True)
    plist.write_text("stale", encoding="utf-8")
    calls = []
    monkeypatch.setattr(schedule_task, "_system", lambda: "Darwin")
    monkeypatch.setattr(schedule_task, "_launchd_status", lambda: True)

    def fake_run(args, **kwargs):
        calls.append(args)
        return _completed(args)

    monkeypatch.setattr(schedule_task.subprocess, "run", fake_run)

    assert schedule_task.off() is True
    assert calls == [[
        "launchctl", "bootout", f"gui/501/{schedule_task.LAUNCHD_LABEL}"
    ]]
    assert not plist.exists()


def test_invalid_time_is_rejected_before_platform_command(monkeypatch):
    monkeypatch.setattr(
        schedule_task, "get_settings", lambda: {"publish": {"schedule_time": "29:00"}}
    )
    monkeypatch.setattr(
        schedule_task.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("command must not run")),
    )
    assert schedule_task.on() is False


def test_unsupported_platform_is_explicit(monkeypatch, capsys):
    monkeypatch.setattr(schedule_task, "_system", lambda: "Linux")
    monkeypatch.setattr(
        schedule_task, "get_settings", lambda: {"publish": {"schedule_time": "09:00"}}
    )
    assert schedule_task.on() is False
    assert "지원하지 않는 운영체제" in capsys.readouterr().out
