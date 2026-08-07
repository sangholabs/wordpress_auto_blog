"""티스토리 정책 패키지의 게시 전·게시 후 SEO를 점검한다."""

from __future__ import annotations

import ipaddress
import json
import re
import socket
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from . import policy_store
from .policy_settings import get as get_policy_settings

MAX_PAGE_BYTES = 5 * 1024 * 1024


def _result(score: int, checks: list[dict], phase: str, **extra) -> dict:
    settings = get_policy_settings()
    score = max(0, min(100, int(score)))
    if score >= int(settings.get("seo_pass_score", 80)):
        status = "pass"
    elif score >= int(settings.get("seo_review_score", 60)):
        status = "review"
    else:
        status = "fail"
    issues = [item["message"] for item in checks if not item["passed"]]
    return {
        "phase": phase, "score": score, "status": status,
        "checked_at": policy_store.now_iso(), "checks": checks,
        "issues": issues, **extra,
    }


def _check(checks: list[dict], passed: bool, code: str, message: str, points: int) -> int:
    checks.append({
        "code": code, "passed": bool(passed), "points": points,
        "message": message,
    })
    return 0 if passed else points


def _rel_tokens(node) -> set[str]:
    value = node.get("rel", [])
    if isinstance(value, str):
        return set(value.lower().split())
    return {str(item).lower() for item in value}


def _appears_before(soup: BeautifulSoup, earlier, later_nodes: list) -> bool:
    """파서가 속성 순서를 바꿔도 DOM 순서만으로 앞뒤를 판단한다."""
    targets = {id(earlier): "earlier", **{id(node): "later" for node in later_nodes}}
    for node in soup.descendants:
        kind = targets.get(id(node))
        if kind == "earlier":
            return True
        if kind == "later":
            return False
    return False


def audit_local(manifest: dict, full_html: str, *, duplicate_title: bool = False) -> dict:
    settings = get_policy_settings()
    soup = BeautifulSoup(full_html, "html.parser")
    draft = manifest.get("draft", {})
    markdown = str(draft.get("markdown", ""))
    title = str(manifest.get("title", "")).strip()
    description = str(manifest.get("meta_description", "")).strip()
    keyword = str(draft.get("primary_keyword") or manifest.get("source", {}).get("official_title", "")).strip()
    secondary = [str(item).strip() for item in draft.get("secondary_keywords", []) if str(item).strip()]
    tags = [str(item).strip().lstrip("#") for item in draft.get("tags", []) if str(item).strip()]
    headings = [node.get_text(" ", strip=True) for node in soup.find_all("h2")]
    briefs = draft.get("image_briefs", []) if isinstance(draft.get("image_briefs"), list) else []
    intro_md = markdown.split("##", 1)[0]
    intro = re.sub(r"[*_`>#\[\]()-]", " ", intro_md)
    intro = re.sub(r"\s+", " ", intro).strip()
    checks, score = [], 100

    title_min, title_max = int(settings["seo_title_min"]), int(settings["seo_title_max"])
    desc_min, desc_max = int(settings["seo_description_min"]), int(settings["seo_description_max"])
    score -= _check(checks, title_min <= len(title) <= title_max, "title_length",
                    f"제목은 {title_min}~{title_max}자를 권장합니다. 현재 {len(title)}자입니다.", 8)
    score -= _check(checks, bool(keyword and keyword in title), "keyword_title",
                    "핵심 키워드가 제목에 포함되지 않았습니다.", 10)
    score -= _check(checks, not keyword or title.find(keyword) <= max(0, len(title) // 2), "keyword_title_front",
                    "핵심 키워드를 제목 앞부분에 배치하세요.", 4)
    score -= _check(checks, desc_min <= len(description) <= desc_max, "description_length",
                    f"메타 설명은 {desc_min}~{desc_max}자를 권장합니다. 현재 {len(description)}자입니다.", 8)
    score -= _check(checks, bool(keyword and keyword in description), "keyword_description",
                    "메타 설명에 핵심 키워드가 없습니다.", 4)
    score -= _check(checks, len(markdown) >= int(settings["seo_min_body_chars"]), "body_length",
                    f"본문이 {settings['seo_min_body_chars']}자보다 짧습니다.", 10)
    score -= _check(checks, soup.find("h1") is None, "body_h1",
                    "본문 H1은 티스토리 제목과 중복되므로 제거하세요.", 10)
    score -= _check(checks, len(headings) >= 8, "heading_count",
                    f"H2가 {len(headings)}개입니다. 검색 의도별 H2를 8개 이상 구성하세요.", 8)
    score -= _check(checks, bool(keyword and keyword in intro[:150]), "keyword_intro",
                    "도입부 150자 안에 핵심 키워드가 없습니다.", 6)
    score -= _check(checks, 8 <= len(tags) <= 12, "tag_count",
                    f"태그는 8~12개를 권장합니다. 현재 {len(tags)}개입니다.", 4)
    image_meta_ok = len(briefs) == 3 and all(isinstance(item, dict) for item in briefs) and all(
        str(item.get("alt", "")).strip() and str(item.get("caption", "")).strip()
        for item in briefs if isinstance(item, dict)
    )
    score -= _check(checks, image_meta_ok, "image_metadata",
                    "대표·본문 이미지 3장의 ALT와 캡션이 모두 필요합니다.", 8)
    current_images = manifest.get("current_images", {})
    score -= _check(checks, all(current_images.get(slot) for slot in ("featured", "body1", "body2")),
                    "image_files", "생성되지 않은 대표 또는 본문 이미지가 있습니다.", 8)
    storage = manifest.get("supabase", {})
    if storage.get("enabled") and storage.get("configured"):
        remote_images = storage.get("images", {})
        remote_stored = all(
            remote_images.get(slot, {}).get("public_url")
            and remote_images.get(slot, {}).get("local_path") == current_images.get(slot)
            for slot in ("featured", "body1", "body2")
        )
        body_images_embedded = all(
            remote_images.get(slot, {}).get("public_url")
            and soup.find("img", src=remote_images[slot]["public_url"])
            for slot in ("body1", "body2")
        )
        featured_not_embedded = not (
            remote_images.get("featured", {}).get("public_url")
            and soup.find("img", src=remote_images["featured"]["public_url"])
        )
        score -= _check(
            checks, remote_stored and body_images_embedded and featured_not_embedded,
            "supabase_images",
            "Supabase 이미지 보관 상태 또는 본문 이미지 2장 삽입 상태를 확인하세요. "
            "대표 이미지는 게시 HTML에서 제외되어야 합니다.", 8,
        )
    tables = soup.find_all("table")
    responsive = all(table.get("data-policy-responsive-table") == "true" and table.parent.get("role") == "region" for table in tables)
    score -= _check(checks, responsive, "responsive_tables",
                    "모든 표를 모바일 가로 스크롤 래퍼로 감싸야 합니다.", 6)
    korean_wrap = all("word-break:keep-all" in str(node.get("style", "")) for node in soup.find_all(["p", "li", "th", "td"]))
    score -= _check(checks, korean_wrap, "korean_wrapping",
                    "일부 문단·목록·표에 한국어 단어 단위 줄바꿈 설정이 없습니다.", 4)
    source = manifest.get("source", {})
    source_ok = bool(source.get("source_url") and source.get("checked_at") and "공식 출처와 확인 기준" in full_html)
    score -= _check(checks, source_ok, "official_source",
                    "공식 출처 링크와 확인 기준일이 필요합니다.", 6)
    affiliate_links = [
        a for a in soup.find_all("a", href=True)
        if "coupang" in a["href"].lower() or "coupa.ng" in a["href"].lower()
    ]
    affiliate_assets = soup.select("[data-policy-coupang-asset]")
    affiliate_present = bool(affiliate_links or affiliate_assets)
    sponsored = all({"nofollow", "sponsored"}.issubset(_rel_tokens(a)) for a in affiliate_links)
    disclosure_ok = not affiliate_present or "쿠팡 파트너스 활동" in full_html
    disclosure_before = True
    if affiliate_present and disclosure_ok:
        disclosure_text = soup.find(string=lambda value: value and "쿠팡 파트너스 활동" in value)
        disclosure_before = bool(disclosure_text) and _appears_before(
            soup, disclosure_text, [*affiliate_links, *affiliate_assets]
        )
    score -= _check(checks, sponsored and disclosure_ok and disclosure_before, "affiliate_disclosure",
                    "쿠팡 링크의 sponsored 속성 또는 첫 광고 앞 제휴 고지문구를 확인하세요.", 8)
    empty_links = [a for a in soup.find_all("a") if not str(a.get("href", "")).strip()]
    score -= _check(checks, not empty_links, "empty_links", "주소가 비어 있는 링크가 있습니다.", 4)
    unsafe_local = any(
        str(node.get(attr, "")).startswith(("file:", "/Users/", "C:\\"))
        for node in soup.find_all(True) for attr in ("href", "src")
    )
    score -= _check(checks, not unsafe_local, "local_path",
                    "게시 HTML에 로컬 파일 경로가 포함되어 있습니다.", 8)
    score -= _check(checks, not duplicate_title, "duplicate_title",
                    "동일한 티스토리 제목의 패키지가 이미 있습니다.", 6)
    if keyword:
        score -= _check(checks, markdown.count(keyword) <= 10, "keyword_stuffing",
                        "핵심 키워드가 10회를 초과해 반복됩니다.", 4)

    suggested_slug = str(draft.get("suggested_slug", "")).strip() or re.sub(
        r"-+", "-", re.sub(r"[^0-9A-Za-z가-힣]+", "-", title)
    ).strip("-")
    return _result(
        score, checks, "local", primary_keyword=keyword,
        secondary_keywords=secondary, search_intent=str(draft.get("search_intent", "")),
        title=title, title_length=len(title), meta_description=description,
        meta_description_length=len(description), suggested_slug=suggested_slug[:70].rstrip("-") or "정책혜택",
        category=manifest.get("category", ""), tags=tags, heading_outline=headings,
        h1_in_body=bool(soup.find("h1")), table_count=len(tables),
        image_alt_texts={item.get("slot", ""): str(item.get("alt", "")).strip() for item in briefs if isinstance(item, dict)},
        manual_checks=[
            "티스토리 제목 입력란에 01_제목.txt를 사용하고 본문에는 H1을 추가하지 않기",
            "대표 이미지를 지정하고 본문 이미지의 ALT·캡션 입력하기",
            "비공개 미리보기에서 모바일 표·문단·이미지·광고 확인하기",
            "게시 URL을 기록한 뒤 게시 후 SEO 검사를 다시 실행하기",
        ],
    )


def _public_https_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("게시 URL은 인증정보가 없는 공개 HTTPS 주소여야 합니다.")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443)}
    except socket.gaierror as exc:
        raise ValueError(f"게시 URL 호스트를 확인할 수 없습니다: {parsed.hostname}") from exc
    for value in addresses:
        address = ipaddress.ip_address(value)
        if not address.is_global:
            raise ValueError("내부·로컬 네트워크 주소는 SEO 검사에 사용할 수 없습니다.")
    return url


def fetch_published(url: str) -> tuple[str, str, int]:
    current = _public_https_url(url)
    headers = {"User-Agent": "Mozilla/5.0 PolicyTistorySEOAudit/1.0"}
    for _ in range(6):
        response = requests.get(current, timeout=15, allow_redirects=False, headers=headers)
        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("location", "")
            if not location:
                raise RuntimeError("게시 URL 리디렉션 위치가 비어 있습니다.")
            current = _public_https_url(urljoin(current, location))
            continue
        content = response.content
        if len(content) > MAX_PAGE_BYTES:
            raise RuntimeError("게시 페이지가 5MB를 초과해 SEO 검사를 중단했습니다.")
        response.encoding = response.encoding or "utf-8"
        return content.decode(response.encoding, errors="replace"), current, response.status_code
    raise RuntimeError("게시 URL 리디렉션이 너무 많습니다.")


def audit_published_html(
    page_html: str, url: str, status_code: int = 200, *,
    expected_title: str = "", primary_keyword: str = "",
    expected_coupang_assets: list[dict] | None = None,
) -> dict:
    soup = BeautifulSoup(page_html, "html.parser")
    content = (
        soup.select_one("article, .tt_article_useless_p_margin, .entry-content, .contents_style")
        or soup.body or soup
    )
    checks, score = [], 100
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    description_node = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    description = str(description_node.get("content", "")).strip() if description_node else ""
    canonical = soup.find("link", rel=lambda value: value and "canonical" in value)
    robots = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    robots_value = str(robots.get("content", "")).lower() if robots else ""
    viewport = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
    og_title = soup.find("meta", property="og:title")
    og_description = soup.find("meta", property="og:description")
    og_image = soup.find("meta", property="og:image")
    score -= _check(checks, 200 <= status_code < 300, "http_status", f"HTTP 상태가 {status_code}입니다.", 20)
    score -= _check(checks, bool(title), "page_title", "게시 페이지 title 태그가 없습니다.", 12)
    if expected_title:
        score -= _check(checks, expected_title in title, "expected_title",
                        "게시 페이지 title에 저장된 글 제목이 그대로 포함되지 않았습니다.", 8)
    score -= _check(checks, bool(description), "page_description", "게시 페이지 meta description이 없습니다.", 10)
    if primary_keyword:
        score -= _check(checks, primary_keyword in title or primary_keyword in description,
                        "published_keyword", "게시 페이지 제목·설명에서 핵심 키워드를 찾지 못했습니다.", 6)
    score -= _check(checks, bool(canonical and canonical.get("href")), "canonical", "canonical 링크가 없습니다.", 8)
    score -= _check(checks, "noindex" not in robots_value, "robots", "게시 페이지에 noindex가 설정되어 있습니다.", 15)
    score -= _check(checks, bool(viewport), "viewport", "모바일 viewport 메타 태그가 없습니다.", 5)
    score -= _check(checks, all(node and node.get("content") for node in (og_title, og_description, og_image)),
                    "open_graph", "Open Graph 제목·설명·대표 이미지 중 누락된 값이 있습니다.", 8)
    score -= _check(checks, bool(content.find(["h1", "h2"])), "page_heading", "게시 페이지에서 제목 heading을 찾지 못했습니다.", 6)
    content_images = [img for img in content.find_all("img") if not str(img.get("src", "")).startswith("data:")]
    score -= _check(checks, not content_images or all(str(img.get("alt", "")).strip() for img in content_images),
                    "published_image_alt", "ALT가 비어 있는 게시 이미지가 있습니다.", 8)
    remaining_placeholders = content.select(
        "div[data-policy-image-slot]:not([data-policy-image-source='supabase'])"
    )
    score -= _check(checks, not remaining_placeholders, "image_placeholders",
                    "게시 본문에 이미지 업로드 자리 표시가 남아 있습니다.", 8)
    affiliate_links = [
        a for a in content.find_all("a", href=True)
        if "coupang" in a["href"].lower() or "coupa.ng" in a["href"].lower()
    ]
    affiliate_ok = all({"nofollow", "sponsored"}.issubset(_rel_tokens(a)) for a in affiliate_links)
    score -= _check(checks, affiliate_ok, "published_affiliate_rel",
                    "게시된 쿠팡 링크에 nofollow sponsored가 없습니다.", 8)
    expected_embed = any(
        "iframe" in str(asset.get("type", "")) or "script" in str(asset.get("type", ""))
        or asset.get("type") == "dynamic-banner"
        for asset in (expected_coupang_assets or []) if isinstance(asset, dict)
    )
    embedded = bool(
        content.find("iframe", src=lambda value: value and ("coupang" in value or "coupa.ng" in value))
        or content.find("script", src=lambda value: value and "ads-partners.coupang.com" in value)
        or content.select_one("[data-policy-coupang-asset]")
    )
    score -= _check(
        checks, not expected_embed or embedded, "published_coupang_embed",
        "티스토리 게시 과정에서 쿠팡 iframe/script 광고가 제거된 것으로 보입니다.", 8,
    )
    return _result(score, checks, "published", url=url, title=title, meta_description=description)


def _write_json(folder: Path, name: str, result: dict) -> None:
    target = folder / "seo" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def run_local_for_package(package_id: str) -> dict:
    from . import policy_package

    package = policy_store.get_package(package_id)
    if not package:
        raise KeyError(f"패키지를 찾을 수 없습니다: {package_id}")
    folder = Path(package["path"])
    manifest = policy_package.load_manifest(folder)
    duplicates = [item for item in policy_store.list_packages(limit=500) if item["id"] != package_id and item["title"] == manifest["title"]]
    full_html = (folder / "02_본문_티스토리.html").read_text(encoding="utf-8-sig")
    result = audit_local(manifest, full_html, duplicate_title=bool(duplicates))
    manifest["seo"] = result
    manifest.setdefault("seo_audits", {})["local"] = result
    manifest.setdefault("readiness", {})["seo"] = result["status"]
    policy_package.apply_readiness(manifest)
    policy_package.save_manifest(folder, manifest)
    _write_json(folder, "게시전_검사.json", result)
    package["status"] = manifest["status"]
    package["updated_at"] = manifest["updated_at"]
    policy_store.save_package(package)
    policy_store.save_seo_audit(package_id, "local", result)
    return result


def run_published_for_package(package_id: str, url: str) -> dict:
    package = policy_store.get_package(package_id)
    if not package:
        raise KeyError(f"패키지를 찾을 수 없습니다: {package_id}")
    folder = Path(package["path"])
    manifest_path = folder / "06_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    page_html, final_url, status_code = fetch_published(url)
    result = audit_published_html(
        page_html, final_url, status_code, expected_title=manifest.get("title", ""),
        primary_keyword=manifest.get("seo", {}).get("primary_keyword", ""),
        expected_coupang_assets=manifest.get("coupang_assets", []),
    )
    manifest.setdefault("seo_audits", {})["published"] = result
    manifest["updated_at"] = policy_store.now_iso()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_json(folder, "게시후_검사.json", result)
    policy_store.save_seo_audit(package_id, "published", result, final_url)
    return result


def failed_published_audit(package_id: str, url: str, error: Exception) -> dict:
    result = {
        "phase": "published", "score": 0, "status": "error", "url": url,
        "checked_at": policy_store.now_iso(), "checks": [], "issues": [str(error)],
    }
    package = policy_store.get_package(package_id)
    if package:
        folder = Path(package["path"])
        manifest_path = folder / "06_manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest.setdefault("seo_audits", {})["published"] = result
            manifest["updated_at"] = policy_store.now_iso()
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_json(folder, "게시후_검사.json", result)
        policy_store.save_seo_audit(package_id, "published", result, url)
    return result
