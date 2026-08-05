from datetime import datetime, timezone

import pytest

from src import policy_service


def test_recommended_candidates_balances_categories(monkeypatch):
    candidates = [
        {"id": "a", "score": 100, "category": "직장·고용·휴직"},
        {"id": "b", "score": 95, "category": "직장·고용·휴직"},
        {"id": "c", "score": 85, "category": "자녀·교육·돌봄"},
    ]
    monkeypatch.setattr(
        policy_service.policy_store, "list_candidates",
        lambda **kwargs: [dict(item) for item in candidates],
    )
    monkeypatch.setattr(policy_service.policy_store, "set_candidate_status", lambda *args: None)
    assert [item["id"] for item in policy_service.recommended_candidates(2)] == ["a", "c"]


def test_expired_candidate_is_removed_from_ready_queue(monkeypatch):
    candidate = {
        "id": "expired", "source_type": "gov24", "external_id": "OLD",
        "title": "종료 정책", "official": True,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "facts": {"summary": "지원", "application_period": "2023-01-01 ~ 2023-11-23"},
    }
    statuses = []
    monkeypatch.setattr(policy_service.policy_store, "get_candidate", lambda candidate_id: candidate)
    monkeypatch.setattr(policy_service.policy_sources, "refresh_candidate", lambda candidate_id: candidate)
    monkeypatch.setattr(
        policy_service.policy_store, "set_candidate_status",
        lambda candidate_id, status, error="": statuses.append((candidate_id, status, error)),
    )

    with pytest.raises(RuntimeError, match="신청기간이 2023-11-23에 종료"):
        policy_service.generate_candidate("expired")

    assert statuses and statuses[-1][0:2] == ("expired", "expired")


def test_prune_expired_candidates_updates_cached_ready_items(monkeypatch):
    current = datetime.now(timezone.utc).isoformat()
    items = [
        {"id": "old", "checked_at": current, "facts": {"application_period": "2023-11-23"}},
        {"id": "open", "checked_at": current, "facts": {"application_period": "상시 신청"}},
    ]
    statuses = []
    monkeypatch.setattr(policy_service.policy_store, "list_candidates", lambda **kwargs: items)
    monkeypatch.setattr(policy_service.policy_store, "set_candidate_status", lambda *args: statuses.append(args))
    assert policy_service.prune_expired_candidates() == 1
    assert statuses[0][0:2] == ("old", "expired")


def test_generate_candidate_prints_progress_before_slow_steps(monkeypatch, capsys):
    candidate = {
        "id": "candidate", "title": "직장인 생활 지원", "official": True,
        "checked_at": datetime.now(timezone.utc).isoformat(), "facts": {},
    }
    draft = {"title": "직장인 생활 지원 신청 방법"}
    monkeypatch.setattr(policy_service.policy_store, "get_candidate", lambda _id: candidate)
    monkeypatch.setattr(policy_service.policy_store, "set_candidate_status", lambda *args: None)
    monkeypatch.setattr(policy_service.policy_sources, "refresh_candidate", lambda _id: candidate)
    monkeypatch.setattr(policy_service.policy_sources, "validate_for_generation", lambda _candidate: [])
    monkeypatch.setattr(policy_service, "generate_policy_draft", lambda _candidate: draft)
    monkeypatch.setattr(
        policy_service.policy_package, "create_package",
        lambda *args, **kwargs: {"id": "post", "title": draft["title"], "path": "/tmp/post"},
    )

    policy_service.generate_candidate("candidate", coupang_assets=[])

    output = capsys.readouterr().out
    assert "[진행 1/6] 공식 정책 최신 정보 확인" in output
    assert "[진행 2/6] '직장인 생활 지원' 글 초안 생성 요청" in output
    assert "LLM 응답 대기" in output
    assert "[진행 3/6] 초안 검증 완료" in output
