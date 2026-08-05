from datetime import datetime

from src import policy_runner


def _settings():
    return {
        "auto_generate": True, "packages_per_day": 1,
        "candidate_refresh_hours": 24, "image_provider": "openai",
    }


def test_auto_runner_continues_after_candidate_failure(monkeypatch):
    finished, calls = {}, []
    monkeypatch.setattr(policy_runner, "get_policy_settings", _settings)
    monkeypatch.setattr(policy_runner.policy_service, "prune_expired_candidates", lambda: 0)
    monkeypatch.setattr(policy_runner.policy_store, "auto_packages_on", lambda day: 0)
    monkeypatch.setattr(policy_runner.policy_store, "begin_automation_run", lambda *args: 7)
    monkeypatch.setattr(policy_runner.policy_store, "finish_automation_run", lambda run_id, **kwargs: finished.update(kwargs))
    monkeypatch.setattr(policy_runner.policy_store, "list_candidates", lambda **kwargs: [{"id": "a"}])
    monkeypatch.setattr(
        policy_runner.policy_store, "get_workspace_setting",
        lambda *args: datetime.now().astimezone().isoformat(),
    )
    monkeypatch.setattr(
        policy_runner.policy_service, "recommended_candidates",
        lambda limit: [{"id": "a", "title": "실패"}, {"id": "b", "title": "성공"}],
    )

    def generate(candidate_id, provider, **kwargs):
        calls.append((candidate_id, provider, kwargs))
        if candidate_id == "a":
            raise RuntimeError("LLM 실패")
        return {"title": "성공 패키지"}

    monkeypatch.setattr(policy_runner.policy_service, "generate_candidate", generate)
    result = policy_runner.run(trigger_type="manual")
    assert result["status"] == "completed"
    assert result["generated"] == 1 and result["failed"] == 1
    assert [call[0] for call in calls] == ["a", "b"]
    assert calls[1][2] == {"generation_mode": "auto", "automation_run_id": 7}
    assert finished["generated_count"] == 1


def test_auto_runner_refreshes_stale_pool_and_respects_daily_quota(monkeypatch):
    collected = []
    monkeypatch.setattr(policy_runner, "get_policy_settings", _settings)
    monkeypatch.setattr(policy_runner.policy_service, "prune_expired_candidates", lambda: 0)
    monkeypatch.setattr(policy_runner.policy_store, "auto_packages_on", lambda day: 0)
    monkeypatch.setattr(policy_runner.policy_store, "begin_automation_run", lambda *args: 8)
    monkeypatch.setattr(policy_runner.policy_store, "finish_automation_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(policy_runner.policy_store, "list_candidates", lambda **kwargs: [{"id": "a"}])
    monkeypatch.setattr(policy_runner.policy_store, "get_workspace_setting", lambda *args: "2020-01-01T00:00:00+09:00")
    monkeypatch.setattr(policy_runner.policy_service, "collect", lambda: collected.append(True))
    monkeypatch.setattr(policy_runner.policy_service, "recommended_candidates", lambda limit: [{"id": "a", "title": "정책"}])
    monkeypatch.setattr(policy_runner.policy_service, "generate_candidate", lambda *args, **kwargs: {"title": "패키지"})
    assert policy_runner.run(trigger_type="manual")["generated"] == 1
    assert collected == [True]

    monkeypatch.setattr(policy_runner.policy_store, "auto_packages_on", lambda day: 1)
    assert policy_runner.run(trigger_type="manual")["status"] == "quota_reached"


def test_auto_runner_reports_finished_policy_as_skipped(monkeypatch, capsys):
    monkeypatch.setattr(policy_runner, "get_policy_settings", _settings)
    monkeypatch.setattr(policy_runner.policy_service, "prune_expired_candidates", lambda: 0)
    monkeypatch.setattr(policy_runner.policy_store, "auto_packages_on", lambda day: 0)
    monkeypatch.setattr(policy_runner.policy_store, "begin_automation_run", lambda *args: 9)
    monkeypatch.setattr(policy_runner.policy_store, "finish_automation_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(policy_runner.policy_store, "list_candidates", lambda **kwargs: [{"id": "old"}])
    monkeypatch.setattr(
        policy_runner.policy_store, "get_workspace_setting",
        lambda *args: datetime.now().astimezone().isoformat(),
    )
    monkeypatch.setattr(
        policy_runner.policy_service, "recommended_candidates",
        lambda limit: [{"id": "old", "title": "종료"}, {"id": "new", "title": "신규"}],
    )

    def generate(candidate_id, *args, **kwargs):
        if candidate_id == "old":
            raise RuntimeError("정책 후보를 생성할 수 없습니다: 신청기간이 2023-11-23에 종료되었습니다.")
        return {"title": "새 패키지"}

    monkeypatch.setattr(policy_runner.policy_service, "generate_candidate", generate)
    result = policy_runner.run(trigger_type="manual")
    assert result["status"] == "completed"
    assert result["generated"] == 1 and result["skipped"] == 1 and result["failed"] == 0
    assert "[건너뜀] 종료된 정책" in capsys.readouterr().out
