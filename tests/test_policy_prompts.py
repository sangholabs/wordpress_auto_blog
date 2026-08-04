import json

from src import policy_prompts
from src.policy_store import now_iso


def _candidate():
    return {
        "id": "abc", "title": "직장인 돌봄 지원", "agency": "고용노동부",
        "region": "전국", "category": "자녀·교육·돌봄",
        "source_url": "https://www.gov.kr/test", "checked_at": now_iso(),
        "source_updated_at": "2026-08-01", "facts": {"benefit": "돌봄 비용 지원"},
    }


def _valid_draft():
    return {
        "title": "직장인 부모가 놓치기 쉬운 돌봄 지원 신청법",
        "meta_description": "직장인 부모를 위한 돌봄 지원 대상과 신청 방법을 공식 자료 기준으로 정리합니다.",
        "category": "자녀·교육·돌봄", "tags": ["돌봄", "직장인", "정부지원"],
        "markdown": "## 내가 대상인지 빠른 체크\n\n" + ("공식 자료를 확인하세요. " * 100),
        "image_briefs": [
            {"slot": "featured", "section": "대표", "prompt": "가족", "alt": "가족", "caption": "가족"},
            {"slot": "body1", "section": "대상", "prompt": "확인", "alt": "확인", "caption": "확인"},
            {"slot": "body2", "section": "신청", "prompt": "신청", "alt": "신청", "caption": "신청"},
        ],
        "coupang_queries": ["수납함", "보온병"],
    }


def test_generation_repairs_invalid_json_once(monkeypatch):
    calls = []
    valid = json.dumps(_valid_draft(), ensure_ascii=False)
    def fake_generate(prompt, system):
        calls.append(prompt)
        return "not-json" if len(calls) == 1 else valid
    monkeypatch.setattr(policy_prompts, "generate", fake_generate)
    draft = policy_prompts.generate_policy_draft(_candidate())
    assert draft["category"] == "자녀·교육·돌봄"
    assert len(calls) == 2
    assert "이전 응답 오류" in calls[1]


def test_unsupported_amount_is_flagged():
    warnings = policy_prompts.unsupported_fact_warnings("지원금은 30만원입니다.", {"facts": {"benefit": "20만원"}})
    assert warnings == ["출처 원문에서 같은 표기를 찾지 못함: 30만원"]

