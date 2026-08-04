"""공식 정책 사실만 근거로 티스토리용 글 초안을 생성한다."""

from __future__ import annotations

import json
import re

from .llm_provider import generate
from .policy_sources import POLICY_CATEGORIES

POLICY_SYSTEM = """너는 대한민국 정부 혜택을 쉽게 설명하는 한국어 편집자다.
독자는 30~50대 주부와 직장인으로 고정한다. 제공된 공식 출처 사실만 사용한다.
출처에 없는 금액, 비율, 날짜, 자격, 예외, 기관, 신청 경로를 추측하거나 보충하지 않는다.
불명확한 값은 반드시 '공식 안내에서 확인 필요'라고 쓴다.
광고 상품이 정책 혜택을 보장하거나 신청에 필수인 것처럼 표현하지 않는다.
응답은 설명이나 코드펜스 없이 유효한 JSON 객체 하나만 출력한다."""


def build_policy_prompt(candidate: dict, validation_error: str = "") -> str:
    official_facts = {
        key: value for key, value in candidate.get("facts", {}).items()
        if not key.startswith("_")
    }
    source = {
        "policy_id": candidate["id"],
        "official_title": candidate["title"],
        "agency": candidate.get("agency", ""),
        "region": candidate.get("region", "전국"),
        "category": candidate["category"],
        "source_url": candidate["source_url"],
        "source_updated_at": candidate.get("source_updated_at", ""),
        "checked_at": candidate["checked_at"],
        "facts": official_facts,
    }
    repair = f"\n이전 응답 오류: {validation_error}\n오류를 바로잡아 전체 JSON을 다시 출력한다.\n" if validation_error else ""
    return f"""다음 공식 정책 자료를 바탕으로 티스토리 게시용 글을 작성한다.

[공식 자료]
{json.dumps(source, ensure_ascii=False, indent=2)}

[출력 JSON 스키마]
{{
  "title": "검색 의도와 실제 혜택이 드러나는 28~45자 제목",
  "meta_description": "공백 포함 155자 이내 요약",
  "category": "{candidate['category']}",
  "tags": ["해시 기호 없는 태그 8~12개"],
  "markdown": "H1 없이 ## 소제목부터 시작하는 본문",
  "image_briefs": [
    {{"slot":"featured","section":"대표","prompt":"장면 설명","alt":"대체텍스트","caption":"캡션"}},
    {{"slot":"body1","section":"본문 소제목 하나","prompt":"서로 다른 장면 설명","alt":"대체텍스트","caption":"캡션"}},
    {{"slot":"body2","section":"본문의 다른 소제목","prompt":"서로 다른 장면 설명","alt":"대체텍스트","caption":"캡션"}}
  ],
  "coupang_queries": ["정책과 자연스럽게 연관된 실제 생활용품 검색어 1", "검색어 2"]
}}

[본문 필수 순서]
1. 짧은 도입과 기준일 안내.
2. ## 내가 대상인지 빠른 체크.
3. ## 받을 수 있는 혜택.
4. ## 제외 조건과 중복 지원 주의사항.
5. ## 신청기간과 놓치면 안 되는 날짜.
6. ## 온라인·오프라인 신청 순서.
7. ## 구비서류와 문의처.
8. ## 30~50대 주부·직장인이 자주 놓치는 경우.
9. ## 자주 묻는 질문.
10. ## 신청 전 최종 체크리스트.

[작성 규칙]
- 표와 짧은 목록을 사용하고 한 문단은 2~4문장으로 제한한다.
- 공식 자료의 빈 항목은 지어내지 말고 '공식 안내에서 확인 필요'로 표시한다.
- 공식 출처 링크와 기준일은 패키징 단계에서 자동 추가되므로 본문에 중복 삽입하지 않는다.
- 이미지, 제휴 광고, 내부 처리 토큰은 본문에 직접 쓰지 않는다.
- 쿠팡 검색어는 정책 신청과 무관한 선택적 생활용품이어야 하며 상품명·가격은 만들지 않는다.
- category는 반드시 다음 중 하나다: {', '.join(POLICY_CATEGORIES)}.
{repair}"""


def _json_object(text: str) -> dict:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("JSON 객체를 찾을 수 없습니다.")
        data = json.loads(cleaned[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("최상위 응답은 JSON 객체여야 합니다.")
    return data


def validate_draft(draft: dict) -> list[str]:
    errors = []
    for key in ("title", "meta_description", "category", "markdown"):
        if not isinstance(draft.get(key), str) or not draft[key].strip():
            errors.append(f"{key}가 비어 있습니다.")
    if draft.get("category") not in POLICY_CATEGORIES:
        errors.append("category가 허용된 정책 카테고리가 아닙니다.")
    tags = draft.get("tags")
    if not isinstance(tags, list) or not 3 <= len(tags) <= 15 or not all(isinstance(x, str) for x in tags):
        errors.append("tags는 문자열 3~15개의 배열이어야 합니다.")
    briefs = draft.get("image_briefs")
    if not isinstance(briefs, list) or len(briefs) != 3:
        errors.append("image_briefs는 대표 1개와 본문 2개여야 합니다.")
    else:
        expected = {"featured", "body1", "body2"}
        slots = {b.get("slot") for b in briefs if isinstance(b, dict)}
        if slots != expected:
            errors.append("image_briefs 슬롯은 featured, body1, body2여야 합니다.")
        for brief in briefs:
            if not isinstance(brief, dict) or not all(str(brief.get(k, "")).strip() for k in ("prompt", "alt", "caption")):
                errors.append("모든 이미지 설명에 prompt, alt, caption이 필요합니다.")
                break
    queries = draft.get("coupang_queries", [])
    if not isinstance(queries, list) or not all(isinstance(x, str) for x in queries):
        errors.append("coupang_queries는 문자열 배열이어야 합니다.")
    if draft.get("markdown") and len(draft["markdown"]) < 1200:
        errors.append("본문이 1200자보다 짧습니다.")
    return errors


def generate_policy_draft(candidate: dict) -> dict:
    last_error = ""
    for attempt in range(2):
        raw = generate(build_policy_prompt(candidate, last_error), system=POLICY_SYSTEM)
        try:
            draft = _json_object(raw)
            errors = validate_draft(draft)
            if errors:
                raise ValueError(" ".join(errors))
            draft["tags"] = [tag.lstrip("#").strip() for tag in draft["tags"] if tag.strip()]
            draft["coupang_queries"] = [q.strip() for q in draft.get("coupang_queries", []) if q.strip()][:3]
            return draft
        except (ValueError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            if attempt == 1:
                raise RuntimeError(f"정책 글 JSON 검증 실패: {last_error}") from exc
    raise RuntimeError("정책 글 생성에 실패했습니다.")


def unsupported_fact_warnings(markdown: str, candidate: dict) -> list[str]:
    """출처에 없는 명시적 금액/날짜를 빠르게 찾아 검증 파일에 표시한다."""
    source = json.dumps(candidate.get("facts", {}), ensure_ascii=False)
    patterns = (
        r"\d[\d,]*(?:만|천)?\s*원",
        r"20\d{2}[.\-/년]\s*\d{1,2}(?:[.\-/월]\s*\d{1,2})?",
        r"\d+(?:\.\d+)?\s*%",
    )
    warnings = []
    for pattern in patterns:
        for value in set(re.findall(pattern, markdown)):
            compact = re.sub(r"\s+", "", value)
            if compact not in re.sub(r"\s+", "", source):
                warnings.append(f"출처 원문에서 같은 표기를 찾지 못함: {value}")
    return sorted(set(warnings))
