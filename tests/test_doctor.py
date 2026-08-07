from src import doctor


def test_doctor_default_never_runs_live_checks(monkeypatch):
    calls = []
    monkeypatch.setattr(doctor, "_offline", lambda report: calls.append("offline"))
    monkeypatch.setattr(
        doctor, "_live",
        lambda report: (_ for _ in ()).throw(AssertionError("live check must be opt-in")),
    )
    assert doctor.main([]) == 0
    assert calls == ["offline"]


def test_doctor_live_uses_read_only_get_checks(monkeypatch):
    calls = []
    monkeypatch.setattr(doctor, "_gov24_get", lambda *args: calls.append("gov24-get") or [{}])
    monkeypatch.setattr(
        doctor, "verify_status",
        lambda: {"verified": True, "public": True, "bucket": "blog_image", "error": ""},
    )
    monkeypatch.setattr(
        doctor, "env",
        lambda key, default="": {
            "WP_SITE_URL": "https://blog.example",
            "WP_USERNAME": "user",
            "WP_APP_PASSWORD": "password",
        }.get(key, default),
    )
    monkeypatch.setattr(
        doctor.requests, "get",
        lambda *args, **kwargs: calls.append("wordpress-get") or type("Response", (), {"status_code": 200})(),
    )
    report = doctor.Report()
    doctor._live(report)
    assert report.failed == 0
    assert calls == ["gov24-get", "wordpress-get"]
