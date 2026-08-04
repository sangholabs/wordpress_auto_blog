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
    assert [item["id"] for item in policy_service.recommended_candidates(2)] == ["a", "c"]
