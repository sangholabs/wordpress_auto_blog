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
    keyword = "직장인 돌봄 지원"
    headings = [
        "내가 대상인지 빠른 체크", "받을 수 있는 혜택", "제외 조건과 중복 지원 주의사항",
        "신청기간과 놓치면 안 되는 날짜", "온라인·오프라인 신청 순서", "구비서류와 문의처",
        "30~50대 주부·직장인이 자주 놓치는 경우", "자주 묻는 질문", "신청 전 최종 체크리스트",
    ]
    sections = "\n\n".join(
        f"## {heading}\n\n" + ("공식 자료를 기준으로 대상과 신청 절차를 확인하고, 불명확한 내용은 공식 안내에서 확인해야 합니다. " * 7)
        for heading in headings
    )
    return {
        "primary_keyword": keyword,
        "secondary_keywords": ["돌봄 혜택", "맞벌이 지원", "정부 지원", "자녀 돌봄"],
        "search_intent": "신청방법", "suggested_slug": "직장인-돌봄-지원-신청방법",
        "title": "직장인 돌봄 지원 대상과 신청방법, 놓치기 쉬운 혜택 총정리",
        "meta_description": "직장인 돌봄 지원 대상과 받을 수 있는 혜택, 신청기간, 온라인·오프라인 신청방법과 구비서류를 공식 자료 기준으로 한눈에 확인할 수 있도록 정리했습니다.",
        "category": "자녀·교육·돌봄",
        "tags": ["돌봄", "직장인", "정부지원", "맞벌이", "자녀돌봄", "생활혜택", "신청방법", "복지정책"],
        "markdown": f"{keyword}의 대상과 혜택, 신청방법을 공식 자료 기준으로 빠르게 확인합니다. 기준일 현재 본인 조건을 먼저 점검하세요.\n\n{sections}",
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
    def fake_generate(prompt, system, **kwargs):
        calls.append(prompt)
        assert kwargs["json_schema"] == policy_prompts.POLICY_DRAFT_SCHEMA
        return "not-json" if len(calls) == 1 else valid
    monkeypatch.setattr(policy_prompts, "generate", fake_generate)
    draft = policy_prompts.generate_policy_draft(_candidate())
    assert draft["category"] == "자녀·교육·돌봄"
    assert len(calls) == 2
    assert "이전 응답 오류" in calls[1]


def test_unsupported_amount_is_flagged():
    warnings = policy_prompts.unsupported_fact_warnings("지원금은 30만원입니다.", {"facts": {"benefit": "20만원"}})
    assert warnings == ["출처 원문에서 같은 표기를 찾지 못함: 30만원"]
