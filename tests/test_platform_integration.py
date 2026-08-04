import subprocess

from src import dashboard, menu


def test_dashboard_reads_common_scheduler_status(monkeypatch):
    monkeypatch.setattr(dashboard.schedule_task, "status", lambda: True)
    assert dashboard._sched_status() == "켜짐"
    monkeypatch.setattr(dashboard.schedule_task, "status", lambda: False)
    assert dashboard._sched_status() == "꺼짐"


def test_dashboard_links_policy_workspace():
    assert 'href="/policy"' in dashboard.PAGE


def test_claude_login_runs_in_current_terminal_on_macos(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(menu, "ROOT", tmp_path)
    monkeypatch.setattr(menu, "_is_windows", lambda: False)
    monkeypatch.setattr(menu.shutil, "which", lambda name: "/usr/local/bin/claude")

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(menu.subprocess, "run", fake_run)
    menu._claude_login()
    assert calls == [(["/usr/local/bin/claude"], {"cwd": str(tmp_path)})]
