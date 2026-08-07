from io import BytesIO

from src import policy_web


class Handler:
    def __init__(self, path: str, body: bytes):
        self.path = path
        self.headers = {"Content-Length": str(len(body))}
        self.rfile = BytesIO(body)
        self.wfile = BytesIO()
        self.status = None

    def send_response(self, status):
        self.status = status

    def send_header(self, *_args):
        pass

    def end_headers(self):
        pass


def test_policy_dashboard_rejects_unknown_schedule_action(monkeypatch):
    called = []
    monkeypatch.setattr(policy_web.policy_schedule_task, "on", lambda: called.append("on"))
    monkeypatch.setattr(policy_web.policy_schedule_task, "off", lambda: called.append("off"))
    handler = Handler("/policy/schedule", b"action=delete")

    assert policy_web.handle_post(handler) is True
    assert handler.status == 400
    assert called == []


def test_policy_dashboard_limits_post_body_size():
    handler = Handler("/policy/settings", b"")
    handler.headers["Content-Length"] = "1000001"

    assert policy_web.handle_post(handler) is True
    assert handler.status == 400
