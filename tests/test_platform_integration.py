import subprocess

from src import dashboard, menu, policy_cli


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


def test_tistory_claude_login_runs_in_current_terminal(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(policy_cli, "ROOT", tmp_path)
    monkeypatch.setattr(policy_cli, "_is_windows", lambda: False)
    monkeypatch.setattr(policy_cli.shutil, "which", lambda name: "/usr/local/bin/claude")
    monkeypatch.setattr(
        policy_cli.subprocess, "run",
        lambda args, **kwargs: calls.append((args, kwargs)) or subprocess.CompletedProcess(args, 0),
    )
    policy_cli._claude_login()
    assert calls == [(["/usr/local/bin/claude"], {"cwd": str(tmp_path)})]


def test_dashboard_can_start_at_policy_page(monkeypatch):
    opened = []

    class ImmediateTimer:
        def __init__(self, _delay, callback):
            self.callback = callback

        def start(self):
            self.callback()

    class FakeServer:
        def __init__(self, address, handler):
            self.address = address

        def serve_forever(self):
            return None

    monkeypatch.setattr(dashboard, "_pick_port", lambda port: 5012)
    monkeypatch.setattr(dashboard.threading, "Timer", ImmediateTimer)
    monkeypatch.setattr(dashboard.webbrowser, "open", opened.append)
    monkeypatch.setattr(dashboard, "HTTPServer", FakeServer)

    dashboard.main(["--path", "/policy"])
    assert opened == ["http://localhost:5012/policy"]
