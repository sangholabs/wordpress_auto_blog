"""보조금24와 공식 정책 URL을 정책 후보로 정규화한다."""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup

from .config import env, get_settings
from . import policy_store

GOV24_LIST_URL = "https://api.odcloud.kr/api/gov24/v3/serviceList"
GOV24_DETAIL_URL = "https://api.odcloud.kr/api/gov24/v3/serviceDetail"
GOV24_CONDITIONS_URL = "https://api.odcloud.kr/api/gov24/v3/supportConditions"
GOV24_PAGE_URL = "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/{service_id}"

LAST_COLLECTION_STATS: dict[str, int | str] = {}

POLICY_CATEGORIES = (
    "생활비·세금·환급",
    "주거·공과금·에너지",
    "자녀·교육·돌봄",
    "직장·고용·휴직",
    "건강·의료·보험",
    "노후·부모돌봄",
)

_CATEGORY_WORDS = {
    "자녀·교육·돌봄": ("자녀", "아동", "육아", "출산", "보육", "교육", "학비", "돌봄", "부모", "방과후", "아이돌봄"),
    "직장·고용·휴직": ("근로", "직장", "고용", "취업", "휴직", "실업", "재직", "직업", "워라밸"),
    "주거·공과금·에너지": ("주거", "주택", "임대", "전세", "월세", "에너지", "전기", "가스", "난방", "공과금"),
    "건강·의료·보험": ("건강", "의료", "병원", "검진", "치료", "보험", "예방접종", "의약"),
    "노후·부모돌봄": ("노인", "노후", "연금", "부모", "장기요양", "간병", "중장년", "장년"),
    "생활비·세금·환급": ("세금", "환급", "소득", "생활비", "지원금", "바우처", "장려금", "할인", "감면", "대출"),
}

_LIFE_THEME_WORDS = {
    "직장·고용": ("근로자", "직장인", "재직", "고용", "휴직", "실업", "구직", "퇴직", "중장년"),
    "자녀·돌봄": ("자녀", "아동", "영유아", "육아", "보육", "돌봄", "출산", "임산부", "난임", "학비", "교육비", "다자녀", "한부모"),
    "주거·공과금": ("주거", "주택", "전세", "월세", "임대", "무주택", "전기요금", "가스요금", "난방비", "에너지", "공과금"),
    "생활비·세금": ("생활비", "생계", "소득", "세금", "환급", "공제", "감면", "보험료", "통신비"),
    "건강·의료": ("건강", "의료", "병원", "검진", "치료", "예방접종", "의료비", "건강보험"),
    "노후·부모돌봄": ("노후", "연금", "노인", "부모", "장기요양", "요양", "간병", "치매"),
}
_BENEFIT_WORDS = (
    "지원금", "장려금", "바우처", "환급", "감면", "공제", "수당", "급여", "무료",
    "할인", "비용 지원", "요금 지원", "보험료 지원", "의료비 지원", "학비 지원", "융자", "대출",
)
_SPECIALIZED_WORDS = {
    "농림·수산업 전용": ("어업", "어선", "수산", "양식장", "선원", "원양", "농업", "농어업", "농기계", "축산", "임업", "귀어", "귀농"),
    "기업·사업자 전용": ("중소기업", "기업 지원", "법인", "사업자", "창업기업", "경영자금", "수출", "무역", "산업체"),
    "특수 직역 전용": ("군인", "군무원", "장병", "전역예정", "국가유공자", "보훈", "특수임무", "선원"),
    "특정 피해·이주 대상 전용": ("범죄피해자", "성폭력 피해", "북한이탈주민", "특별귀화", "외국인 피해자", "이주여성"),
}
_TARGET_CONDITION_CODES = {
    "JA0301": "예비부모·난임", "JA0302": "임산부", "JA0303": "출산·입양",
    "JA0326": "근로자·직장인", "JA0327": "구직자·실업자",
    "JA0403": "한부모·조손가정", "JA0404": "1인가구", "JA0411": "다자녀가구",
    "JA0412": "무주택세대", "JA0414": "확대가족",
}
_SPECIALIZED_CONDITION_CODES = {
    "JA0313": "농업인", "JA0314": "어업인", "JA0315": "축산업인", "JA0316": "임업인",
    "JA1101": "예비창업자", "JA1102": "영업중 사업자", "JA1103": "폐업예정자",
    "JA2101": "중소기업", "JA2102": "사회복지시설", "JA2103": "기관·단체",
    "JA2201": "제조업", "JA2202": "농림어업", "JA2203": "정보통신업", "JA2299": "기타업종",
}
_PROVINCES = (
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원",
    "충북", "충남", "전북", "전남", "경북", "경남", "제주",
)
_REGION_ALIASES = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구",
    "인천광역시": "인천", "광주광역시": "광주", "대전광역시": "대전",
    "울산광역시": "울산", "세종특별자치시": "세종", "경기도": "경기",
    "강원특별자치도": "강원", "강원도": "강원", "충청북도": "충북",
    "충청남도": "충남", "전북특별자치도": "전북", "전라북도": "전북",
    "전라남도": "전남", "경상북도": "경북", "경상남도": "경남",
    "제주특별자치도": "제주", "제주도": "제주",
}
_OFFICIAL_HOSTS = (
    "gov.kr", "go.kr", "bokjiro.go.kr", "work24.go.kr", "data.go.kr", "korea.kr",
    "nps.or.kr", "nhis.or.kr", "hometax.go.kr", "nts.go.kr", "moel.go.kr",
)


def _value(data: dict, *keys, default=""):
    for key in keys:
        value = data.get(key)
        if value not in (None, "", []):
            if isinstance(value, (dict, list)):
                return value
            return str(value).strip()
    return default


def stable_id(source_type: str, external: str) -> str:
    raw = f"{source_type}:{external}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]


def is_official_url(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    return url.startswith("https://") and any(host == h or host.endswith("." + h) for h in _OFFICIAL_HOSTS)


def classify(text: str) -> str:
    compact = text.lower()
    best = max(
        _CATEGORY_WORDS.items(),
        key=lambda item: sum(1 for word in item[1] if word.lower() in compact),
    )
    return best[0] if any(word.lower() in compact for word in best[1]) else "생활비·세금·환급"


def detect_region(data: dict) -> str:
    explicit = _value(data, "지역", "지원지역", "region")
    agency = " ".join(str(_value(data, key)) for key in ("소관기관명", "기관명", "agency"))
    title = " ".join(str(_value(data, key)) for key in ("서비스명", "title"))
    text = f"{agency} {title} {explicit}"
    province = next((canonical for alias, canonical in _REGION_ALIASES.items() if alias in text), "")
    if not province:
        province = next((name for name in _PROVINCES if name in str(explicit)), "")

    local = ""
    for token in re.split(r"[\s,·/()]+", agency):
        token = token.strip()
        if token in _REGION_ALIASES:
            continue
        if re.fullmatch(r"[가-힣]{2,10}(?:시|군|구)", token):
            local = token
    if not local:
        match = re.match(r"\s*([가-힣]{2,10}(?:시|군|구))(?:\s|$)", title)
        if match and match.group(1) not in _REGION_ALIASES:
            local = match.group(1)
    if province or local:
        return " ".join(part for part in (province, local) if part)
    return "전국"


def _matched(text: str, words: tuple[str, ...]) -> list[str]:
    compact = text.lower()
    return [word for word in words if word.lower() in compact]


def _condition_enabled(value) -> bool:
    if value in (None, "", 0, "0", False):
        return False
    return str(value).strip().lower() not in ("n", "no", "false", "해당없음")


def curate_policy(
    *, title: str, facts: dict, agency: str = "", region: str = "전국",
    selected_regions: list[str] | None = None, conditions: dict | None = None,
    minimum_score: int = 20,
) -> dict:
    """30~50대 주부·직장인 관점에서 추천 여부와 근거를 계산한다."""
    conditions = conditions or {}
    text = " ".join(
        [title, agency, *[str(v) for k, v in facts.items() if not k.startswith("_") and isinstance(v, (str, int, float))]]
    )
    theme_hits = {label: _matched(text, words) for label, words in _LIFE_THEME_WORDS.items()}
    theme_hits = {label: hits for label, hits in theme_hits.items() if hits}
    benefit_hits = _matched(text, _BENEFIT_WORDS)
    target_conditions = [
        label for code, label in _TARGET_CONDITION_CODES.items() if _condition_enabled(conditions.get(code))
    ]
    specialized_conditions = [
        label for code, label in _SPECIALIZED_CONDITION_CODES.items() if _condition_enabled(conditions.get(code))
    ]
    exclusions = [label for label, words in _SPECIALIZED_WORDS.items() if _matched(text, words)]

    age_start = conditions.get("JA0110")
    age_end = conditions.get("JA0111")
    try:
        age_start = int(age_start) if age_start not in (None, "") else None
        age_end = int(age_end) if age_end not in (None, "") else None
    except (TypeError, ValueError):
        age_start = age_end = None
    age_overlaps = bool(
        age_start is not None and age_end is not None and age_start <= 59 and age_end >= 30
    )
    if age_end is not None and age_end < 30:
        exclusions.append("30대 미만 연령 전용")
    elif age_start is not None and age_start > 59:
        # 노후·부모돌봄 정책은 30~50대가 부모를 위해 확인할 가치가 있어 제외하지 않는다.
        if "노후·부모돌봄" not in theme_hits:
            exclusions.append("60대 이상 연령 전용")

    # 전문 업종 조건만 있고 일반 생활 대상 조건이 없다면 폭넓은 독자에게 맞지 않는다.
    if specialized_conditions and not target_conditions:
        exclusions.append("전문 업종·사업체 지원조건")
    exclusions = list(dict.fromkeys(exclusions))

    score = 0
    for hits in theme_hits.values():
        score += 8 + min(4, max(0, len(hits) - 1))
    score += min(12, len(benefit_hits) * 3)
    if facts.get("benefit"):
        score += 5
    if facts.get("eligibility"):
        score += 4
    if facts.get("application_period") or facts.get("application_method"):
        score += 3
    if target_conditions:
        score += 10
    if age_overlaps:
        score += 6
    if region == "전국":
        score += 4
    elif selected_regions and any(r in region or region in r for r in selected_regions):
        score += 5
    if exclusions:
        score -= 40 + (len(exclusions) - 1) * 5

    reasons = []
    if theme_hits:
        reasons.append("생활밀착 주제: " + ", ".join(theme_hits))
    if benefit_hits:
        reasons.append("구체적 혜택 신호: " + ", ".join(benefit_hits[:4]))
    if target_conditions:
        reasons.append("공식 대상조건: " + ", ".join(target_conditions[:4]))
    if age_overlaps:
        reasons.append(f"연령조건 {age_start}~{age_end}세가 타깃과 겹침")
    if region == "전국":
        reasons.append("전국 공통 정책")

    recommended = bool(
        not exclusions
        and (theme_hits or target_conditions or age_overlaps)
        and facts.get("benefit")
        and score >= minimum_score
    )
    return {
        "recommended": recommended,
        "score": score,
        "reasons": reasons,
        "exclusions": exclusions,
        "theme_hits": theme_hits,
        "benefit_hits": benefit_hits,
    }


def score_policy(
    facts: dict, region: str = "전국", selected_regions: list[str] | None = None,
    *, title: str = "", agency: str = "", conditions: dict | None = None,
) -> int:
    return int(curate_policy(
        title=title, facts=facts, agency=agency, region=region,
        selected_regions=selected_regions, conditions=conditions, minimum_score=-999,
    )["score"])


def _normalized_facts(data: dict, *, source_text: str = "") -> dict:
    return {
        "summary": _value(data, "서비스목적요약", "서비스목적", "서비스개요", "summary", "설명"),
        "eligibility": _value(data, "지원대상", "선정기준", "eligibility", "사용자구분"),
        "benefit": _value(data, "지원내용", "서비스내용", "benefit"),
        "exclusions": _value(data, "중복불가서비스", "제외대상", "exclusions"),
        "application_period": _value(data, "신청기한", "신청기간", "applicationPeriod"),
        "application_method": _value(data, "신청방법", "applicationMethod"),
        "documents": _value(
            data, "구비서류", "제출서류", "documents", "공무원확인구비서류", "본인확인필요구비서류"
        ),
        "contact": _value(data, "전화문의", "문의처", "contact"),
        "online_url": _value(data, "온라인신청사이트URL", "온라인신청URL", "onlineUrl"),
        "user_type": _value(data, "사용자구분", "userType"),
        "service_area": _value(data, "서비스분야", "serviceArea"),
        "support_type": _value(data, "지원유형", "supportType"),
        "source_text": source_text[:12000],
    }


def normalize_gov24(
    data: dict, *, selected_regions: list[str] | None = None,
    conditions: dict | None = None, minimum_score: int = 20,
) -> dict:
    external_id = _value(data, "서비스ID", "서비스아이디", "serviceId", "service_id")
    title = _value(data, "서비스명", "serviceName", "title", default="이름 없는 정책")
    facts = _normalized_facts(data)
    agency = _value(data, "소관기관명", "기관명", "agency")
    region = detect_region({**data, "agency": agency, "title": title})
    source_url = _value(data, "상세조회URL", "서비스상세URL", "sourceUrl")
    if not source_url and external_id:
        source_url = GOV24_PAGE_URL.format(service_id=external_id)
    source_url = source_url or "https://www.gov.kr/portal/rcvfvrSvc/main"
    text = " ".join([title, agency, *[str(v) for v in facts.values()]])
    curation = curate_policy(
        title=title, facts=facts, agency=agency, region=region,
        selected_regions=selected_regions, conditions=conditions,
        minimum_score=minimum_score,
    )
    facts["_curation"] = curation
    if conditions:
        facts["_support_conditions"] = conditions
    return {
        "id": stable_id("gov24", external_id or source_url + title),
        "source_type": "gov24",
        "external_id": external_id,
        "title": title,
        "category": classify(text),
        "agency": agency,
        "region": region,
        "source_url": source_url,
        "official": True,
        "facts": facts,
        "source_updated_at": _value(data, "수정일시", "수정일", "updatedAt"),
        "checked_at": policy_store.now_iso(),
        "score": curation["score"],
        "status": "ready" if curation["recommended"] else "filtered_out",
    }


def _response_items(payload) -> list[dict]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("data", "items", "result", "results", "response"):
        value = payload.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
        if isinstance(value, dict):
            nested = _response_items(value)
            if nested:
                return nested
            if any(k in value for k in ("서비스ID", "serviceId", "서비스명", "serviceName")):
                return [value]
    if any(k in payload for k in ("서비스ID", "serviceId", "서비스명", "serviceName")):
        return [payload]
    return []


def _normalize_service_key(key: str) -> str:
    """포털 표시 키와 기존 Decoding 키를 모두 serviceKey 원문으로 맞춘다."""
    return unquote(key.strip())


def _gov24_get(url: str, params: dict, timeout: int = 30) -> list[dict]:
    key = env("DATA_GO_KR_API_KEY")
    if not key:
        raise RuntimeError(
            "DATA_GO_KR_API_KEY가 비어 있습니다. 공공데이터포털에서 보조금24 API 활용신청 후 .env에 넣으세요."
        )
    # 공공데이터포털의 새 화면은 URL 인코딩된 일반 인증키 하나만 표시할 수 있다.
    # requests가 쿼리를 다시 인코딩하므로, 여기서 한 번 원문으로 복원해 이중 인코딩을 막는다.
    query = {"serviceKey": _normalize_service_key(key), "returnType": "JSON", **params}
    try:
        response = requests.get(url, params=query, timeout=timeout)
    except requests.RequestException as exc:
        host = urlparse(url).hostname or "공공데이터 API"
        raise RuntimeError(f"보조금24 API 연결 실패: {host}에 연결할 수 없습니다.") from exc
    if response.status_code >= 400:
        raise RuntimeError(f"보조금24 API 오류 {response.status_code}: {response.text[:300]}")
    items = _response_items(response.json())
    return items


def _fetch_paginated(url: str, *, limit: int, page_size: int, params: dict | None = None) -> list[dict]:
    result: list[dict] = []
    page = 1
    params = params or {}
    while len(result) < limit:
        size = min(page_size, limit - len(result))
        batch = _gov24_get(url, {**params, "page": page, "perPage": size})
        if not batch:
            break
        result.extend(batch[:size])
        if len(batch) < size:
            break
        page += 1
    return result[:limit]


def fetch_support_conditions(*, limit: int, page_size: int) -> dict[str, dict]:
    rows = _fetch_paginated(GOV24_CONDITIONS_URL, limit=limit, page_size=page_size)
    return {
        str(_value(row, "서비스ID", "serviceId")): row
        for row in rows if _value(row, "서비스ID", "serviceId")
    }


def fetch_gov24_detail(service_id: str) -> dict:
    if not service_id:
        return {}
    items = _gov24_get(
        GOV24_DETAIL_URL,
        {"cond[서비스ID::EQ]": service_id, "page": 1, "perPage": 1},
    )
    return items[0] if items else {}


def collect_gov24() -> list[dict]:
    global LAST_COLLECTION_STATS
    cfg = get_settings().get("policy_workspace", {})
    page_size = max(10, min(int(cfg.get("scan_page_size", cfg.get("collect_limit", 500))), 500))
    scan_limit = max(page_size, min(int(cfg.get("scan_limit", page_size)), 20000))
    recommended_limit = max(1, min(int(cfg.get("recommended_limit", 50)), 200))
    detail_limit = max(0, min(int(cfg.get("detail_limit", 30)), recommended_limit))
    minimum_score = int(cfg.get("minimum_score", 20))
    regions = policy_store.get_regions()
    raw = _fetch_paginated(GOV24_LIST_URL, limit=scan_limit, page_size=page_size)
    if not raw:
        raise RuntimeError("보조금24 정책 목록이 비어 있습니다.")

    conditions_by_id: dict[str, dict] = {}
    condition_error = ""
    if cfg.get("use_support_conditions", True):
        try:
            conditions_by_id = fetch_support_conditions(limit=scan_limit, page_size=page_size)
        except Exception as exc:
            condition_error = str(exc)

    raw_by_id = {
        str(_value(row, "서비스ID", "serviceId")): row
        for row in raw if _value(row, "서비스ID", "serviceId")
    }
    preliminary = []
    for raw_item in raw:
        external_id = str(_value(raw_item, "서비스ID", "serviceId"))
        item = normalize_gov24(
            raw_item, selected_regions=regions,
            conditions=conditions_by_id.get(external_id), minimum_score=minimum_score,
        )
        region_matches = item["region"] == "전국" or any(
            r in item["region"] or item["region"] in r for r in regions
        )
        if region_matches and item["status"] == "ready":
            preliminary.append(item)

    preliminary.sort(key=lambda item: item["score"], reverse=True)
    result = []
    for item in preliminary[:recommended_limit]:
        if len(result) < detail_limit and item["external_id"]:
            try:
                detail = fetch_gov24_detail(item["external_id"])
                if detail:
                    merged = {**raw_by_id.get(item["external_id"], {}), **detail}
                    item = normalize_gov24(
                        merged, selected_regions=regions,
                        conditions=conditions_by_id.get(item["external_id"]),
                        minimum_score=minimum_score,
                    )
            except Exception as exc:
                item["last_error"] = str(exc)
        if item["status"] == "ready":
            result.append(item)

    result.sort(key=lambda item: item["score"], reverse=True)
    result = result[:recommended_limit]
    policy_store.hide_gov24_candidates()
    for item in result:
        policy_store.upsert_candidate(item)

    LAST_COLLECTION_STATS = {
        "scanned": len(raw),
        "condition_rows": len(conditions_by_id),
        "recommended": len(result),
        "hidden": max(0, len(raw) - len(result)),
        "condition_error": condition_error,
    }
    return result


def _page_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
        tag.decompose()
    title = ""
    og = soup.find("meta", attrs={"property": "og:title"})
    if og and og.get("content"):
        title = og["content"].strip()
    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", soup.get_text("\n", strip=True))
    return title, text[:20000]


def import_policy_url(url: str, pasted_text: str = "") -> dict:
    if not url.startswith("https://"):
        raise ValueError("정책 URL은 https:// 주소여야 합니다.")
    title, text = "", pasted_text.strip()
    if not text:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        response.raise_for_status()
        title, text = _page_text(response.text)
    if not text:
        raise RuntimeError("페이지 본문을 읽지 못했습니다. 공식 페이지 내용을 함께 붙여넣어 주세요.")
    if not title:
        title = next((line.strip() for line in text.splitlines() if line.strip()), "이름 없는 정책")[:150]
    facts = _normalized_facts({}, source_text=text)
    facts["summary"] = text[:1000]
    category = classify(title + " " + text[:5000])
    official = is_official_url(url)
    candidate = {
        "id": stable_id("url", url),
        "source_type": "url",
        "external_id": url,
        "title": title[:200],
        "category": category,
        "agency": urlparse(url).hostname or "",
        "region": "전국",
        "source_url": url,
        "official": official,
        "facts": facts,
        "source_updated_at": "",
        "checked_at": policy_store.now_iso(),
        "score": score_policy(facts) + (5 if official else 0),
        "status": "ready" if official else "needs_official_source",
        "last_error": "" if official else "공식 출처가 확인되지 않았습니다.",
    }
    policy_store.upsert_candidate(candidate)
    return candidate


def _parse_expiry(text: str) -> date | None:
    matches = re.findall(r"(20\d{2})[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})", text or "")
    dates = []
    for year, month, day in matches:
        try:
            dates.append(date(int(year), int(month), int(day)))
        except ValueError:
            pass
    return max(dates) if dates else None


def validate_for_generation(candidate: dict, max_cache_days: int | None = None) -> list[str]:
    if max_cache_days is None:
        max_cache_days = int(get_settings().get("policy_workspace", {}).get("source_cache_days", 7))
    errors = []
    if not candidate.get("official"):
        errors.append("공식 출처가 필요합니다.")
    checked = datetime.fromisoformat(candidate["checked_at"])
    age = datetime.now(checked.tzinfo) - checked
    if age.days > max_cache_days:
        errors.append(f"출처 확인 후 {age.days}일이 지나 다시 확인해야 합니다.")
    facts = candidate.get("facts", {})
    expiry = _parse_expiry(str(facts.get("application_period", "")))
    if expiry and expiry < date.today():
        errors.append(f"신청기간이 {expiry.isoformat()}에 종료되었습니다.")
    if not (facts.get("summary") or facts.get("source_text")):
        errors.append("정책 설명을 읽지 못했습니다.")
    return errors


def refresh_candidate(candidate_id: str) -> dict:
    candidate = policy_store.get_candidate(candidate_id)
    if not candidate:
        raise KeyError(f"정책 후보를 찾을 수 없습니다: {candidate_id}")
    if candidate["source_type"] == "gov24" and candidate.get("external_id"):
        detail = fetch_gov24_detail(candidate["external_id"])
        if detail:
            previous_facts = candidate.get("facts", {})
            detail.setdefault("사용자구분", previous_facts.get("user_type", ""))
            detail.setdefault("서비스분야", previous_facts.get("service_area", ""))
            detail.setdefault("지원유형", previous_facts.get("support_type", ""))
            refreshed = normalize_gov24(
                detail, selected_regions=policy_store.get_regions(),
                conditions=previous_facts.get("_support_conditions"),
                minimum_score=int(get_settings().get("policy_workspace", {}).get("minimum_score", 20)),
            )
            policy_store.upsert_candidate(refreshed)
            return refreshed
    if candidate["source_type"] == "url":
        return import_policy_url(candidate["source_url"])
    return candidate
