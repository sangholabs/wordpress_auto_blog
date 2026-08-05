from datetime import datetime, timedelta, timezone

import pytest
import requests

from src import policy_sources


def test_service_key_accepts_portal_display_and_legacy_decoding_values():
    decoded = "abc+def/ghi="
    encoded = "abc%2Bdef%2Fghi%3D"
    assert policy_sources._normalize_service_key(encoded) == decoded
    assert policy_sources._normalize_service_key(decoded) == decoded


def test_gov24_connection_error_does_not_expose_service_key(monkeypatch):
    secret = "secret%2Bkey%3D"
    monkeypatch.setattr(policy_sources, "env", lambda name: secret)

    def fail(*args, **kwargs):
        raise requests.ConnectionError(f"failed URL serviceKey={secret}")

    monkeypatch.setattr(policy_sources.requests, "get", fail)
    with pytest.raises(RuntimeError) as caught:
        policy_sources._gov24_get(policy_sources.GOV24_LIST_URL, {"page": 1})
    assert secret not in str(caught.value)
    assert "api.odcloud.kr" in str(caught.value)


def test_normalize_gov24_classifies_audience_and_region():
    item = policy_sources.normalize_gov24({
        "서비스ID": "SVC100", "서비스명": "직장인 자녀 돌봄 지원",
        "소관기관명": "고용노동부", "지원대상": "근로자 부모",
        "지원내용": "돌봄 비용 일부 지원", "신청방법": "온라인 신청",
    })
    assert item["id"] == policy_sources.stable_id("gov24", "SVC100")
    assert item["category"] == "자녀·교육·돌봄"
    assert item["region"] == "전국"
    assert item["official"] is True
    assert item["score"] > 0
    assert item["status"] == "ready"


def test_detect_region_normalizes_formal_province_and_local_agency():
    assert policy_sources.detect_region({"소관기관명": "충청남도 공주시"}) == "충남 공주시"
    assert policy_sources.detect_region({"소관기관명": "보건복지부"}) == "전국"


def test_curation_excludes_specialized_industry_and_keeps_family_benefit():
    fishery = policy_sources.normalize_gov24({
        "서비스ID": "FISH1", "서비스명": "양식장 친환경에너지 보급",
        "소관기관명": "해양수산부", "지원대상": "양식 어업인",
        "지원내용": "설비 비용 지원",
    })
    family = policy_sources.normalize_gov24({
        "서비스ID": "FAMILY1", "서비스명": "맞벌이 가정 아이돌봄 비용 지원",
        "소관기관명": "여성가족부", "지원대상": "근로자 부모 가구",
        "지원내용": "아이돌봄 이용 비용 지원",
    }, conditions={"JA0326": "Y", "JA0411": "Y", "JA0110": 30, "JA0111": 59})
    assert fishery["status"] == "filtered_out"
    assert "농림·수산업 전용" in fishery["facts"]["_curation"]["exclusions"]
    assert family["status"] == "ready"
    assert family["score"] > fishery["score"]
    assert any("근로자" in reason for reason in family["facts"]["_curation"]["reasons"])


def test_collect_filters_unselected_regions_and_fetches_details(monkeypatch):
    stored = []
    raw = [
        {"서비스ID": "N1", "서비스명": "전국 근로자 환급", "소관기관명": "국세청", "지원내용": "환급"},
        {"서비스ID": "B1", "서비스명": "부산 육아 지원", "소관기관명": "부산광역시", "지원내용": "지원금"},
    ]
    monkeypatch.setattr(policy_sources, "_gov24_get", lambda url, params: raw)
    monkeypatch.setattr(policy_sources, "fetch_gov24_detail", lambda service_id: next(x for x in raw if x["서비스ID"] == service_id))
    monkeypatch.setattr(policy_sources.policy_store, "get_regions", lambda: [])
    monkeypatch.setattr(policy_sources.policy_store, "upsert_candidate", stored.append)
    monkeypatch.setattr(policy_sources.policy_store, "hide_gov24_candidates", lambda: None)
    monkeypatch.setattr(policy_sources, "get_settings", lambda: {"policy_workspace": {
        "scan_page_size": 10, "scan_limit": 10, "detail_limit": 10,
        "recommended_limit": 10, "minimum_score": 0,
    }})
    result = policy_sources.collect_gov24()
    assert [item["external_id"] for item in result] == ["N1"]
    assert stored[0]["region"] == "전국"


def test_fetch_detail_uses_official_condition_parameter(monkeypatch):
    captured = {}

    def fake_get(url, params):
        captured.update(params)
        return [{"서비스ID": "SVC1"}]

    monkeypatch.setattr(policy_sources, "_gov24_get", fake_get)
    assert policy_sources.fetch_gov24_detail("SVC1")["서비스ID"] == "SVC1"
    assert captured["cond[서비스ID::EQ]"] == "SVC1"


def test_import_url_requires_official_source(monkeypatch):
    class Response:
        status_code = 200
        text = "<html><head><title>생활비 지원 정책</title></head><body><main>직장인 가구 지원금 신청 안내</main></body></html>"
        def raise_for_status(self):
            return None

    saved = []
    monkeypatch.setattr(policy_sources.requests, "get", lambda *a, **k: Response())
    monkeypatch.setattr(policy_sources.policy_store, "upsert_candidate", saved.append)
    official = policy_sources.import_policy_url("https://www.bokjiro.go.kr/test")
    unofficial = policy_sources.import_policy_url("https://example.com/test")
    assert official["status"] == "ready"
    assert unofficial["status"] == "needs_official_source"


def test_stale_and_expired_candidate_is_rejected():
    candidate = {
        "official": True,
        "checked_at": (datetime.now(timezone.utc) - timedelta(days=9)).isoformat(),
        "facts": {"summary": "지원", "application_period": "2024-01-01 ~ 2024-12-31"},
    }
    errors = policy_sources.validate_for_generation(candidate)
    assert any("9일" in error for error in errors)
    assert any("종료" in error for error in errors)


def test_normalize_gov24_marks_finished_policy_expired():
    item = policy_sources.normalize_gov24({
        "서비스ID": "OLD1", "서비스명": "직장인 난방비 지원",
        "소관기관명": "산업통상자원부", "지원대상": "근로자 가구",
        "지원내용": "난방비 지원", "신청기간": "2023-10-01 ~ 2023-11-23",
    }, minimum_score=0)
    assert item["status"] == "expired"
    assert "2023-11-23" in item["last_error"]
