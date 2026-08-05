import plistlib
import subprocess

from src import policy_schedule_task


def _root(monkeypatch, tmp_path):
    root = tmp_path / "project"
    python = root / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")
    python.chmod(0o755)
    windows_python = root / ".venv" / "Scripts" / "python.exe"
    windows_python.parent.mkdir(parents=True)
    windows_python.write_text("", encoding="utf-8")
    agents = tmp_path / "LaunchAgents"
    monkeypatch.setattr(policy_schedule_task, "ROOT", root)
    monkeypatch.setattr(policy_schedule_task, "LAUNCH_AGENTS_DIR", agents)
    monkeypatch.setattr(policy_schedule_task, "PLIST_PATH", agents / "policy.plist")
    monkeypatch.setattr(policy_schedule_task.policy_settings, "get", lambda: {"schedule_time": "09:30"})
    monkeypatch.setattr(policy_schedule_task, "_set_enabled", lambda enabled: None)
    return root


def test_policy_macos_plist_is_independent(monkeypatch, tmp_path):
    root = _root(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setattr(policy_schedule_task, "_system", lambda: "Darwin")
    monkeypatch.setattr(policy_schedule_task, "_launchd_status", lambda: False)
    monkeypatch.setattr(policy_schedule_task.os, "getuid", lambda: 501)

    def fake_run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(policy_schedule_task.subprocess, "run", fake_run)
    assert policy_schedule_task.on() is True
    payload = plistlib.loads(policy_schedule_task.PLIST_PATH.read_bytes())
    assert payload["Label"] == "com.wordpress-auto-blog.policy-tistory"
    assert payload["ProgramArguments"] == [str(root / ".venv/bin/python"), "-m", "src.policy_runner"]
    assert payload["StartCalendarInterval"] == {"Hour": 9, "Minute": 30}
    assert payload["StandardOutPath"].endswith("logs/policy_pipeline.log")
    assert "RunAtLoad" not in payload
    assert calls[-1][:2] == ["launchctl", "bootstrap"]


def test_policy_windows_task_uses_separate_name(monkeypatch, tmp_path):
    root = _root(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setattr(policy_schedule_task, "_system", lambda: "Windows")

    def fake_run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(policy_schedule_task.subprocess, "run", fake_run)
    assert policy_schedule_task.on() is True
    command = calls[0]
    assert command[command.index("/tn") + 1] == "blog-policy-tistory-auto"
    assert "src.policy_runner" in command[command.index("/tr") + 1]
    assert str(root / ".venv/Scripts/python.exe") in command[command.index("/tr") + 1]
