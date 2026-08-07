"""정책 초안을 티스토리 수동 게시용 자체 완결 패키지로 만든다."""

from __future__ import annotations

import html
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import markdown as md
from bs4 import BeautifulSoup

from . import affiliate, policy_storage, policy_store
from .config import ROOT, get_settings
from .policy_images import failed_asset, generate_image, safe_name
from .policy_prompts import unsupported_fact_warnings

OUTPUT_ROOT = ROOT / "output" / "tistory"
ZIP_ROOT = OUTPUT_ROOT / "zips"
PACKAGE_SCHEMA_VERSION = 8
ARTICLE_STYLE = (
    "max-width:720px;margin:0 auto;padding:8px 4px;font-family:-apple-system,"
    "BlinkMacSystemFont,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:#222;"
    "word-break:keep-all;overflow-wrap:break-word"
)


def _write(path: Path, content: str, *, bom: bool = False) -> None:
    """파일을 저장한다. 사람이 복사할 산출물은 UTF-8 BOM으로 인코딩 추정을 고정한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8-sig" if bom else "utf-8")


def load_manifest(package_dir: Path) -> dict:
    return json.loads((package_dir / "06_manifest.json").read_text(encoding="utf-8"))


def save_manifest(package_dir: Path, manifest: dict) -> None:
    manifest["updated_at"] = policy_store.now_iso()
    target = package_dir / "06_manifest.json"
    temp = package_dir / "06_manifest.json.tmp"
    _write(temp, json.dumps(manifest, ensure_ascii=False, indent=2))
    temp.replace(target)


def _portable_html(markdown: str) -> str:
    source = re.sub(r"^#\s+.*$", "", markdown, count=1, flags=re.MULTILINE)
    fragment = md.markdown(source, extensions=["tables", "fenced_code", "sane_lists"])
    soup = BeautifulSoup(fragment, "html.parser")
    styles = {
        "h2": "font-size:24px;line-height:1.4;margin:42px 0 16px;border-left:5px solid #2d6cdf;padding-left:12px;color:#17233c;word-break:keep-all;overflow-wrap:break-word",
        "h3": "font-size:20px;line-height:1.45;margin:30px 0 12px;color:#263b63;word-break:keep-all;overflow-wrap:break-word",
        "p": "font-size:17px;line-height:1.85;margin:12px 0;color:#222;word-break:keep-all;overflow-wrap:break-word",
        "ul": "font-size:17px;line-height:1.8;margin:12px 0;padding-left:24px;word-break:keep-all;overflow-wrap:break-word",
        "ol": "font-size:17px;line-height:1.8;margin:12px 0;padding-left:24px;word-break:keep-all;overflow-wrap:break-word",
        "li": "margin:5px 0;word-break:keep-all;overflow-wrap:break-word",
        "blockquote": "margin:18px 0;padding:14px 18px;background:#f6f8fc;border-left:4px solid #7893c7;color:#34415b",
        "table": "width:100%;min-width:640px;border-collapse:collapse;font-size:15px;line-height:1.65;table-layout:auto",
        "th": "border:1px solid #dfe4ec;padding:11px 12px;background:#f5f7fb;text-align:left;vertical-align:top;word-break:keep-all;overflow-wrap:break-word",
        "td": "border:1px solid #dfe4ec;padding:11px 12px;text-align:left;vertical-align:top;word-break:keep-all;overflow-wrap:break-word",
        "a": "color:#245ec7;text-decoration:underline;text-underline-offset:2px;overflow-wrap:anywhere",
    }
    for tag, style in styles.items():
        for node in soup.find_all(tag):
            node["style"] = style
    def normalize_checklist_item(item, *, require_marker: bool = False) -> bool:
        first_text = next((node for node in item.descendants if isinstance(node, str)), None)
        if first_text is None:
            return False
        match = re.match(r"^(\s*)\[\s*([xX]?)\s*\]\s+", str(first_text))
        if require_marker and not match:
            return False
        symbol = "☑" if match and match.group(2) else "☐"
        content = str(first_text)[match.end():] if match else str(first_text).lstrip()
        leading = match.group(1) if match else ""
        first_text.replace_with(leading + symbol + " " + content)
        item["data-policy-checklist-item"] = "true"
        if "list-style:none" not in item.get("style", ""):
            item["style"] = item.get("style", "") + ";list-style:none;margin-left:-18px"
        return True

    # LLM이 만든 Markdown 작업 목록 `- [ ] 항목`은 티스토리에서 문자 그대로 보인다.
    # 문서 어디에 있든 작업 목록이면 단일 체크 기호로 먼저 정규화한다.
    for item in soup.find_all("li"):
        normalize_checklist_item(item, require_marker=True)

    # LLM이 일반 `- 항목`으로 작성하더라도 최종 체크리스트 구간은 같은 모양을 유지한다.
    for heading in soup.find_all("h2"):
        if "최종 체크리스트" not in heading.get_text(" ", strip=True):
            continue
        for sibling in heading.find_next_siblings():
            if sibling.name == "h2":
                break
            for item in sibling.find_all("li") if sibling.name != "li" else [sibling]:
                if item.get("data-policy-checklist-item") != "true":
                    normalize_checklist_item(item)
    for table in list(soup.find_all("table")):
        table["data-policy-responsive-table"] = "true"
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            if cells:
                cells[0]["style"] = cells[0].get("style", "") + ";min-width:110px;width:24%;white-space:nowrap"
        wrapper = soup.new_tag("div")
        wrapper["style"] = (
            "width:100%;max-width:100%;overflow-x:auto;margin:20px 0;"
            "-webkit-overflow-scrolling:touch;border-radius:4px"
        )
        wrapper["role"] = "region"
        wrapper["aria-label"] = "표를 좌우로 스크롤할 수 있습니다"
        table.wrap(wrapper)

    # Markdown의 Q/A 사이 한 줄바꿈은 HTML에서 공백으로 합쳐지므로 FAQ만 명시적으로 분리한다.
    for paragraph in soup.find_all("p"):
        strong = paragraph.find("strong", recursive=False)
        if strong and re.match(r"\s*Q[.．:]", strong.get_text(" ", strip=True), flags=re.IGNORECASE):
            next_node = strong.next_sibling
            if next_node is not None and getattr(next_node, "name", None) != "br":
                strong.insert_after(soup.new_tag("br"))
    return str(soup)


def _image_placeholders(body: str, manifest: dict) -> str:
    if not manifest.get("generation", {}).get("images_enabled", True):
        return body
    soup = BeautifulSoup(body, "html.parser")
    headings = soup.find_all("h2")
    current = manifest.get("current_images", {})
    remote = manifest.get("supabase", {}).get("images", {})
    # 대표 이미지는 티스토리 편집기에서 별도로 업로드·지정한다. 파일과 Supabase
    # 보관 정보는 유지하되 게시용 본문 HTML에는 본문 이미지 두 장만 삽입한다.
    for offset, slot in enumerate(("body1", "body2"), start=1):
        brief = next((b for b in manifest["draft"]["image_briefs"] if b["slot"] == slot), {})
        section = brief.get("section", "")
        heading = next((h for h in headings if section and (section in h.get_text() or h.get_text() in section)), None)
        if heading is None and headings:
            heading = headings[min(offset, len(headings) - 1)]
        remote_asset = remote.get(slot, {})
        if remote_asset.get("public_url") and remote_asset.get("local_path") == current.get(slot):
            marker = soup.new_tag("figure")
            marker["data-policy-image-slot"] = slot
            marker["data-policy-image-source"] = "supabase"
            marker["style"] = "margin:24px 0;text-align:center"
            image = soup.new_tag("img")
            image["src"] = remote_asset["public_url"]
            image["alt"] = brief.get("alt", "")
            image["width"] = "1200"
            image["height"] = "800"
            image["loading"] = "lazy"
            image["style"] = "display:block;width:100%;height:auto;border-radius:10px"
            marker.append(image)
            if brief.get("caption"):
                caption = soup.new_tag("figcaption")
                caption["style"] = "font-size:13px;color:#667;margin-top:8px"
                caption.string = brief["caption"]
                marker.append(caption)
        else:
            marker = soup.new_tag("div")
            marker["data-policy-image-slot"] = slot
            marker["style"] = (
                "margin:22px 0;padding:18px;border:2px dashed #8aa4d6;border-radius:10px;"
                "background:#f7f9fd;text-align:center;color:#40577f;font-size:14px"
            )
            filename = Path(current.get(slot, "")).name or f"{offset + 1:02d}_본문_이미지없음.jpg"
            marker.string = f"이미지 업로드 위치: {filename} · 대체텍스트: {brief.get('alt', '')}"
        if heading:
            heading.insert_after(marker)
        else:
            soup.append(marker)
    return str(soup)


def _coupang_asset_entries(draft: dict, values: list[dict] | list[str] | tuple[str, ...]) -> list[dict]:
    queries = draft.get("coupang_queries") or ["추천 상품"]
    entries: list[dict] = []
    for index, value in enumerate(values):
        if isinstance(value, dict):
            source = value.get("source_code") or value.get("url") or ""
        else:
            source = str(value)
        if not str(source).strip():
            continue
        asset = affiliate.parse_coupang_asset(str(source))
        asset["keyword"] = str(queries[index % len(queries)])
        entries.append(asset)
    return entries


def _affiliate_blocks(
    draft: dict, fallback_keyword: str, coupang_assets: list[dict] | list[str] | None = None,
) -> tuple[list[str], list[str], str]:
    cfg = get_settings().get("policy_workspace", {})
    if not cfg.get("coupang_enabled", True):
        return [], [], "disabled"
    limit = max(1, min(int(cfg.get("coupang_max_blocks", 2)), 3))
    queries = draft.get("coupang_queries") or [fallback_keyword]
    mode, blocks, warnings = affiliate.monetization_mode(), [], []
    if coupang_assets:
        entries = _coupang_asset_entries(draft, coupang_assets)
        blocks = [
            affiliate.render_coupang_asset(entry, entry["keyword"])
            for entry in entries[:limit]
        ]
        mode = "manual-coupang-asset"
        if any(not entry["partners_tracking"] for entry in entries[:limit]):
            warnings.append(
                "일반 쿠팡 상품 URL이 포함됨. 수익 추적을 위해 쿠팡 파트너스에서 발급한 "
                "link.coupang.com 또는 coupa.ng 주소 사용을 권장함."
            )
        if cfg.get("rocket_only", True):
            warnings.append("직접 입력한 쿠팡 소재의 로켓 상품 여부는 자동 확인할 수 없음.")
        if any("script" in entry["type"] or "iframe" in entry["type"] for entry in entries[:limit]):
            warnings.append(
                "티스토리 편집기나 스킨이 iframe/script 광고를 제거할 수 있으므로 비공개 글에서 표시 여부 확인 필요."
            )
    if not blocks and mode == "api":
        for query in queries:
            products = affiliate.products_for(query, options=cfg)
            if products:
                blocks.append(affiliate.cards_html([products[0]]))
            if len(blocks) >= limit:
                break
    if not blocks:
        blocks = affiliate.load_widgets()[:limit]
        if blocks:
            mode = "widget"
            if cfg.get("rocket_only", True):
                warnings.append("다이나믹 배너 상품의 로켓 여부는 자동 확인할 수 없습니다.")
    if not blocks:
        blocks = [affiliate.coupang_cta(query) for query in queries[:limit]]
        warnings.append("쿠팡 API 상품카드/배너가 없어 검색 링크로 대체됨(수익 추적을 보장하지 않음).")
        mode = "search-link"
    return blocks[:limit], warnings, mode


def _insert_after_sections(body: str, blocks: list[str]) -> str:
    parts = body.split("</h2>")
    if len(parts) == 1:
        return body + "".join(blocks)
    out, block_index = parts[0], 0
    for section in parts[1:]:
        out += "</h2>"
        if block_index < len(blocks):
            pos = section.find("</p>")
            if pos >= 0:
                pos += len("</p>")
                section = section[:pos] + blocks[block_index] + section[pos:]
            else:
                section = blocks[block_index] + section
            block_index += 1
        out += section
    return out


def _place_affiliates(body: str, blocks: list[str], layout: str) -> str:
    if not blocks:
        return body
    if layout == "grouped":
        group = '<div data-policy-affiliate-group="true">' + "".join(blocks) + "</div>"
        return _insert_after_sections(body, [group])
    if layout == "grouped_h2":
        grouped_count = max(1, len(blocks) - 1)
        group = (
            '<div data-policy-affiliate-group="true">'
            + "".join(blocks[:grouped_count]) + "</div>"
        )
        return _insert_after_sections(body, [group, *blocks[grouped_count:]])
    return _insert_after_sections(body, blocks)


def _source_footer(manifest: dict) -> str:
    source = manifest["source"]
    checked = source.get("checked_at", "")[:10]
    url = html.escape(source["source_url"], quote=True)
    title = html.escape(source["official_title"])
    agency = html.escape(source.get("agency", ""))
    return (
        '<section style="margin:38px 0 16px;padding:18px;background:#f7f9fc;border:1px solid #dfe6f1;border-radius:10px">'
        '<strong style="display:block;margin-bottom:8px">공식 출처와 확인 기준</strong>'
        f'<p style="font-size:14px;line-height:1.7;margin:0;word-break:keep-all;overflow-wrap:break-word">{agency} · '
        f'<a href="{url}" target="_blank" rel="noopener">{title}</a><br>'
        f'{checked} 기준으로 확인했습니다. 신청 전 공식 페이지에서 최신 내용과 본인 자격을 다시 확인하세요.</p></section>'
    )


def _disclosure() -> str:
    text = html.escape(get_settings()["content"]["coupang_disclosure"])
    return (
        '<div style="background:#fff7e6;border:1px solid #ffd591;border-radius:8px;'
        f'padding:10px 14px;font-size:13px;color:#795b23;margin:18px 0">{text}</div>'
    )


def apply_readiness(manifest: dict) -> str:
    """독립된 검증 상태를 패키지의 대표 상태 하나로 정리한다."""
    if manifest.get("status") == "published":
        return "published"
    current = manifest.get("current_images", {})
    images_enabled = manifest.get("generation", {}).get("images_enabled", True)
    images_ready = all(current.get(slot) for slot in ("featured", "body1", "body2"))
    readiness = manifest.setdefault("readiness", {})
    readiness["images"] = "disabled" if not images_enabled else "ready" if images_ready else "retry"
    readiness["facts"] = "warning" if manifest.get("verification_warnings") else "ready"
    seo_status = manifest.get("seo", {}).get("status", readiness.get("seo", "review"))
    readiness["seo"] = seo_status
    if images_enabled and not images_ready:
        status = "needs_image_retry"
    elif seo_status != "pass":
        status = "seo_review"
    elif manifest.get("verification_warnings"):
        status = "ready_with_warnings"
    else:
        status = "ready"
    manifest["status"] = status
    return status


def _split_segments(full_html: str) -> list[str]:
    soup = BeautifulSoup(full_html, "html.parser")
    container = soup.find("article")
    if container:
        content = "".join(str(node) for node in container.contents)
        segment_style = container.get("style", ARTICLE_STYLE)
    else:
        content = full_html
        segment_style = ARTICLE_STYLE
    pattern = (
        r'(<figure data-policy-image-slot="body[12]"[^>]*>.*?</figure>|'
        r'<div data-policy-image-slot="body[12]"[^>]*>.*?</div>)'
    )
    parts = re.split(pattern, content, flags=re.DOTALL)
    if len(parts) >= 5:
        first_asset = parts[1] if parts[1].startswith("<figure") else ""
        second_asset = parts[3] if parts[3].startswith("<figure") else ""
        segments = [parts[0] + first_asset, parts[2] + second_asset, "".join(parts[4:])]
    else:
        segments = [content, "", ""]
    escaped_style = html.escape(segment_style, quote=True)
    return [
        f'<section data-policy-segment="{index}" style="{escaped_style}">{part.strip()}</section>'
        for index, part in enumerate(segments, start=1)
    ]


def _preview_html(tistory_html: str, manifest: dict) -> str:
    rendered = tistory_html
    assets = {item["slot"]: item for item in manifest.get("images", []) if item.get("path") and not item.get("error")}
    for slot in ("body1", "body2"):
        asset = assets.get(slot)
        if not asset:
            continue
        figure = (
            f'<figure style="margin:24px 0;text-align:center"><img src="{html.escape(asset["path"], quote=True)}" '
            f'alt="{html.escape(asset.get("alt", ""), quote=True)}" style="max-width:100%;height:auto;border-radius:10px">'
            f'<figcaption style="font-size:13px;color:#667;margin-top:8px">{html.escape(asset.get("caption", ""))}</figcaption></figure>'
        )
        rendered = re.sub(
            rf'<div data-policy-image-slot="{slot}"[^>]*>.*?</div>', figure, rendered, count=1, flags=re.DOTALL
        )
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{html.escape(manifest["title"])}</title>'
        f'<meta name="description" content="{html.escape(manifest.get("meta_description", ""), quote=True)}">'
        '</head><body style="margin:0;background:#eef1f6">'
        '<main style="max-width:760px;margin:24px auto;padding:24px;background:#fff">'
        f'<h1 style="font-size:31px;line-height:1.35">{html.escape(manifest["title"])}</h1>{rendered}</main></body></html>'
    )


def _seo_text(seo: dict) -> str:
    issues = "\n".join(f"- {item}" for item in seo["issues"]) or "- 자동 점검 이슈 없음"
    headings = "\n".join(f"- {item}" for item in seo["heading_outline"])
    alts = "\n".join(f"- {slot}: {alt}" for slot, alt in seo["image_alt_texts"].items())
    manual = "\n".join(f"- {item}" for item in seo["manual_checks"])
    return f"""티스토리 SEO 게시 정보

SEO 점수: {seo.get('score', 0)}점 / 상태: {seo.get('status', 'review')}
핵심 키워드: {seo['primary_keyword']}
제목({seo['title_length']}자): {seo['title']}
메타 설명({seo['meta_description_length']}자): {seo['meta_description']}
추천 슬러그: {seo['suggested_slug']}
카테고리: {seo['category']}
태그: {', '.join(seo['tags'])}
본문 H1: {'있음(확인 필요)' if seo['h1_in_body'] else '없음(티스토리 제목이 페이지 제목 역할)'}
H2 개수: {len(seo['heading_outline'])}
표 개수: {seo['table_count']}

[소제목 구조]
{headings}

[이미지 대체텍스트]
{alts}

[자동 점검]
{issues}

[게시 후 수동 확인]
{manual}

참고: 티스토리 본문 HTML에는 <head> 메타 태그를 넣지 않습니다. 검색 스니펫은 티스토리 스킨과 검색엔진이 최종 결정하므로 메타 설명과 첫 문단을 모두 명확하게 유지하세요.
"""


def render_package_files(
    package_dir: Path, manifest: dict, *, sync_storage: bool = True,
) -> None:
    from . import policy_seo

    if sync_storage:
        storage_warnings = policy_storage.sync_manifest_images(package_dir, manifest)
    else:
        storage = manifest.get("supabase", {})
        remote = storage.get("images", {})
        current = manifest.get("current_images", {})
        cached_ready = bool(current) and all(
            remote.get(slot, {}).get("public_url")
            and remote.get(slot, {}).get("local_path") == current.get(slot)
            for slot in current
        )
        if cached_ready:
            storage["last_error"] = ""
            storage_warnings = []
        else:
            last_error = str(storage.get("last_error", "")).strip()
            storage_warnings = [last_error] if last_error else []
    body = _portable_html(manifest["draft"]["markdown"])
    body = _image_placeholders(body, manifest)
    blocks, ad_warnings, mode = _affiliate_blocks(
        manifest["draft"], manifest["source"]["official_title"],
        manifest.get("coupang_assets") or manifest.get("coupang_product_links"),
    )
    layout = get_settings().get("policy_workspace", {}).get("coupang_layout", "per_h2")
    body = _place_affiliates(body, blocks, layout)
    disclosure = _disclosure() if blocks and mode != "disabled" else ""
    full = f'<article style="{ARTICLE_STYLE}">' + disclosure + body + _source_footer(manifest) + "</article>"
    segments = _split_segments(full)
    manifest["schema_version"] = max(
        PACKAGE_SCHEMA_VERSION, int(manifest.get("schema_version", 1))
    )
    publication = manifest.setdefault("publication", {})
    publication["featured_image_in_body"] = False
    publication["body_image_slots"] = ["body1", "body2"]
    manifest["tags"] = list(manifest["draft"].get("tags", []))
    warnings = unsupported_fact_warnings(manifest["draft"]["markdown"], {
        "facts": manifest["source"].get("facts", {}),
        "source_updated_at": manifest["source"].get("source_updated_at", ""),
        "checked_at": manifest["source"].get("checked_at", ""),
    })
    core_labels = {
        "eligibility": "지원 대상", "benefit": "지원 내용", "application_period": "신청기간",
        "application_method": "신청방법", "documents": "구비서류", "contact": "문의처",
    }
    source_facts = manifest["source"].get("facts", {})
    warnings.extend(
        f"공식 출처에서 {label} 항목을 구조화하지 못함. 게시 전 원문 확인 필요."
        for key, label in core_labels.items() if not source_facts.get(key)
    )
    warnings.extend(ad_warnings)
    warnings.extend(storage_warnings)
    current = manifest.get("current_images", {})
    warnings.extend(
        item["error"] for item in manifest.get("images", [])
        if item.get("error") and not current.get(item.get("slot", ""))
    )
    manifest["verification_warnings"] = sorted(set(w for w in warnings if w))
    manifest["coupang_mode"] = mode
    manifest["coupang_settings"] = {
        "enabled": mode != "disabled", "layout": layout,
        "max_blocks": len(blocks),
        "manual_assets": len(manifest.get("coupang_assets") or manifest.get("coupang_product_links", [])),
        "rocket_only": bool(get_settings().get("policy_workspace", {}).get("rocket_only", True)),
    }
    manifest["seo"] = policy_seo.audit_local(
        manifest, full, duplicate_title=bool(manifest.get("_duplicate_title", False))
    )
    manifest.setdefault("seo_audits", {})["local"] = manifest["seo"]
    apply_readiness(manifest)
    _write(package_dir / "01_제목.txt", manifest["title"] + "\n", bom=True)
    _write(package_dir / "02_본문_티스토리.html", full, bom=True)
    _write(package_dir / "02_본문_HTML블록용.txt", full, bom=True)
    plain = BeautifulSoup(full, "html.parser").get_text("\n", strip=True)
    _write(package_dir / "03_본문_일반텍스트.txt", plain + "\n", bom=True)
    _write(package_dir / "04_태그.txt", ", ".join(manifest["draft"]["tags"]) + "\n", bom=True)
    _write(package_dir / "07_SEO_게시정보.txt", _seo_text(manifest["seo"]), bom=True)
    _write(
        package_dir / "seo" / "게시전_검사.json",
        json.dumps(manifest["seo"], ensure_ascii=False, indent=2),
    )
    for index, (name, content) in enumerate(zip(("시작", "중간", "마무리"), segments), start=1):
        _write(package_dir / "segments" / f"{index:02d}_본문_{name}.html", content, bom=True)
        _write(package_dir / "segments" / f"{index:02d}_본문_{name}_HTML블록용.txt", content, bom=True)
    checks = "\n".join(f"- {warning}" for warning in manifest["verification_warnings"]) or "- 자동 검증 경고 없음"
    source = manifest["source"]
    verification = f"""# 출처 및 검증 기록

- 공식 정책명: {source['official_title']}
- 담당 기관: {source.get('agency', '')}
- 공식 URL: {source['source_url']}
- 출처 확인 시각: {source.get('checked_at', '')}
- 원문 수정일: {source.get('source_updated_at', '') or '확인 필요'}
- 지역: {source.get('region', '전국')}
- 쿠팡 삽입 방식: {mode}

## 자동 검증 경고

{checks}

게시 직전에 공식 URL에서 대상, 금액, 신청기간, 신청방법을 다시 확인하세요.
"""
    _write(package_dir / "05_출처_검증.md", verification, bom=True)
    image_lines = []
    for slot in ("featured", "body1", "body2"):
        path = manifest.get("current_images", {}).get(slot, "생성 실패 - 작업실에서 재생성")
        image_lines.append(f"- {slot}: {path}")
    images_enabled = manifest.get("generation", {}).get("images_enabled", True)
    remote_images = manifest.get("supabase", {}).get("images", {})
    body_remote_ready = images_enabled and all(
        remote_images.get(slot, {}).get("public_url")
        and remote_images.get(slot, {}).get("local_path") == manifest.get("current_images", {}).get(slot)
        for slot in ("body1", "body2")
    )
    manual_assets = manifest.get("coupang_assets") or manifest.get("coupang_product_links", [])
    asset_lines = [
        f"- {index}: {affiliate.coupang_asset_label(asset)}"
        for index, asset in enumerate(manual_assets, start=1) if isinstance(asset, dict)
    ] or ["- 직접 입력 소재 없음(API·공용 배너·검색 링크 설정에 따라 자동 처리)"]
    image_steps = """2. images/01_대표 파일을 티스토리에 직접 업로드하고 대표 이미지로 지정합니다.
3. 02_본문_HTML블록용.txt 전체를 티스토리 HTML 블록 또는 HTML 모드에 붙여넣습니다.
4. 게시용 본문 HTML에는 대표 이미지가 없고, Supabase 본문 이미지 2장만 포함되어 있습니다.
5. 비공개 저장 후 대표 이미지 지정 상태와 본문 이미지 2장이 모두 표시되는지 확인합니다.""" if body_remote_ready else """2. 대표 이미지를 글 상단에 업로드하고 티스토리 대표 이미지로 지정합니다.
3. 기본모드에서 'HTML 블록'을 추가하고 segments/01_본문_시작_HTML블록용.txt 내용을 붙여넣습니다.
4. images/02_본문 파일을 업로드하고 대체텍스트·캡션을 manifest대로 입력합니다.
5. 다음 'HTML 블록'에 segments/02_본문_중간_HTML블록용.txt를 붙여넣은 뒤 images/03_본문 파일을 업로드합니다.
6. 마지막 'HTML 블록'에 segments/03_본문_마무리_HTML블록용.txt를 붙여넣습니다.""" if images_enabled else """2. 기본모드에서 'HTML 블록'을 추가합니다.
3. 02_본문_HTML블록용.txt 전체를 붙여넣습니다. 이미지 생성이 꺼져 있어 이미지 업로드 단계는 없습니다."""
    followup_step = 6 if body_remote_ready else 7 if images_enabled else 4
    guide = f"""티스토리 수동 게시 순서

1. 01_제목.txt 내용을 티스토리 제목에 붙여넣습니다.
{image_steps}
{followup_step}. 04_태그.txt의 태그를 입력하고 05_출처_검증.md의 경고를 확인합니다.
{followup_step + 1}. 07_SEO_게시정보.txt에서 제목·설명·소제목·ALT 자동 점검과 게시 후 확인사항을 확인합니다.
{followup_step + 2}. 먼저 비공개로 저장해 모바일 표 가로 스크롤·문단·이미지·쿠팡 링크·고지문구를 확인한 뒤 공개합니다.
{followup_step + 3}. 작업실에서 게시 완료를 표시하고 티스토리 URL을 기록합니다.

[중요]
- 티스토리 '코드블록'은 HTML 코드를 글에 그대로 보여주는 기능이므로 본문 작성에는 사용하지 않습니다.
- 반드시 'HTML 블록' 또는 편집기의 'HTML 모드'에 붙여넣으세요.
- 한 번에 붙여넣을 때는 02_본문_HTML블록용.txt를 사용합니다. 02_본문_티스토리.html과 내용은 같고 두 파일 모두 UTF-8 BOM으로 저장됩니다.
- 이미지 사이에 본문을 나눠 넣을 때는 segments 폴더의 *_HTML블록용.txt 3개를 순서대로 사용합니다.
- 대표 이미지는 게시용 본문 HTML에 포함되지 않습니다. images/01_대표 파일을 티스토리에서 별도로 업로드·지정하세요.

이미지 파일
{chr(10).join(image_lines)}

쿠팡 광고 소재
{chr(10).join(asset_lines)}
- iframe/script 소재는 티스토리에서 제거될 수 있으므로 비공개 저장 후 실제 표시를 확인하세요.
"""
    _write(package_dir / "00_게시가이드.txt", guide, bom=True)
    _write(package_dir / "preview.html", _preview_html(full, manifest), bom=True)
    save_manifest(package_dir, manifest)


def _package_dir(candidate_id: str, title: str, created: datetime) -> Path:
    base = OUTPUT_ROOT / created.strftime("%Y") / created.strftime("%m") / created.strftime("%d")
    desired = base / f"{candidate_id}_{safe_name(title, 42)}"
    if not desired.exists():
        return desired
    suffix = 2
    while (base / f"{desired.name}_{suffix}").exists():
        suffix += 1
    return base / f"{desired.name}_{suffix}"


def create_package(
    candidate: dict, draft: dict, *, image_provider: str = "openai",
    generation_mode: str = "manual", automation_run_id: int | None = None,
    coupang_product_urls: list[str] | tuple[str, ...] | None = None,
    coupang_assets: list[str] | tuple[str, ...] | None = None,
) -> dict:
    created = datetime.now().astimezone()
    package_id = f"{candidate['id']}-{created.strftime('%Y%m%d%H%M%S%f')}"
    final_dir = _package_dir(candidate["id"], draft["title"], created)
    package_dir = final_dir.parent / f".{final_dir.name}.tmp-{package_id}"
    package_dir.mkdir(parents=True, exist_ok=False)
    policy_cfg = get_settings().get("policy_workspace", {})
    images_enabled = bool(policy_cfg.get("images_enabled", True))
    try:
        manifest = {
            "schema_version": PACKAGE_SCHEMA_VERSION,
            "id": package_id,
            "candidate_id": candidate["id"],
            "title": draft["title"],
            "category": draft["category"],
            "meta_description": draft["meta_description"],
            "created_at": created.isoformat(timespec="seconds"),
            "updated_at": created.isoformat(timespec="seconds"),
            "status": "ready",
            "published_at": "",
            "tistory_url": "",
            "source": {
                "source_type": candidate.get("source_type", "manifest"),
                "external_id": candidate.get("external_id", ""),
                "official": bool(candidate.get("official", True)),
                "official_title": candidate["title"],
                "agency": candidate.get("agency", ""),
                "region": candidate.get("region", "전국"),
                "source_url": candidate["source_url"],
                "source_updated_at": candidate.get("source_updated_at", ""),
                "checked_at": candidate["checked_at"],
                "facts": candidate.get("facts", {}),
            },
            "draft": draft,
            "coupang_assets": _coupang_asset_entries(
                draft, [*(coupang_assets or []), *(coupang_product_urls or [])],
            ),
            "images": [],
            "current_images": {},
            "verification_warnings": [],
            "generation": {
                "mode": generation_mode, "automation_run_id": automation_run_id,
                "image_provider": image_provider, "images_enabled": images_enabled,
            },
            "readiness": {},
            "seo_audits": {},
            "_duplicate_title": any(
                item["title"] == draft["title"] for item in policy_store.list_packages(limit=500)
            ),
        }
        if images_enabled:
            print("[진행 4/6] 대표·본문 이미지 3장 생성 시작", flush=True)
            for index, brief in enumerate(draft["image_briefs"], start=1):
                print(
                    f"  - 이미지 {index}/3 ({brief.get('slot', '')}) 생성 중 · "
                    f"엔진 {image_provider}", flush=True,
                )
                try:
                    asset = generate_image(package_dir, brief, provider=image_provider)
                except Exception as exc:
                    asset = failed_asset(brief, exc, image_provider)
                    print(f"    실패: {exc}", flush=True)
                else:
                    print(f"    완료: {asset.get('filename', '')}", flush=True)
                manifest["images"].append(asset)
                if asset.get("path"):
                    manifest["current_images"][asset["slot"]] = asset["path"]
        else:
            print("[진행 4/6] 이미지 생성 꺼짐 · 글 패키지만 생성", flush=True)
        print("[진행 5/6] 티스토리 HTML·분할 본문·SEO 검사 파일 생성", flush=True)
        render_package_files(package_dir, manifest)
        manifest.pop("_duplicate_title", None)
        save_manifest(package_dir, manifest)
        if final_dir.exists():
            raise FileExistsError(f"최종 패키지 폴더가 이미 있습니다: {final_dir}")
        package_dir.rename(final_dir)
    except BaseException:
        shutil.rmtree(package_dir, ignore_errors=True)
        raise
    package = {
        "id": package_id,
        "candidate_id": candidate["id"],
        "title": draft["title"],
        "category": draft["category"],
        "path": str(final_dir),
        "status": manifest["status"],
        "created_at": manifest["created_at"],
        "updated_at": manifest["updated_at"],
        "generation_mode": generation_mode,
        "automation_run_id": automation_run_id,
    }
    policy_store.save_package(package)
    policy_store.save_seo_audit(package_id, "local", manifest["seo"])
    policy_store.set_candidate_status(candidate["id"], "generated")
    print(f"[진행 6/6] 패키지 저장 완료 · SEO {manifest['seo']['score']}점", flush=True)
    return package


def set_coupang_assets(
    package_id: str, values: list[str] | tuple[str, ...],
) -> list[dict]:
    """기존 패키지의 쿠팡 소재를 교체하고 HTML·SEO 산출물을 다시 만든다."""
    package = policy_store.get_package(package_id)
    if not package:
        raise KeyError(f"패키지를 찾을 수 없습니다: {package_id}")
    package_dir = Path(package["path"])
    manifest = load_manifest(package_dir)
    entries = _coupang_asset_entries(manifest["draft"], values)
    manifest["coupang_assets"] = entries
    manifest.pop("coupang_product_links", None)
    render_package_files(package_dir, manifest)
    package["status"] = manifest["status"]
    package["updated_at"] = manifest["updated_at"]
    policy_store.save_package(package)
    policy_store.save_seo_audit(package_id, "local", manifest["seo"])
    return entries


def set_coupang_product_links(
    package_id: str, urls: list[str] | tuple[str, ...],
) -> list[dict]:
    """이전 URL 전용 인터페이스를 새 쿠팡 소재 인터페이스로 연결한다."""
    return set_coupang_assets(package_id, urls)


def rebuild_package(package_id: str) -> dict:
    """LLM·이미지 API 재호출 없이 manifest에서 HTML·가이드·SEO 파일을 다시 만든다."""
    package = policy_store.get_package(package_id)
    if not package:
        raise KeyError(f"패키지를 찾을 수 없습니다: {package_id}")
    package_dir = Path(package["path"])
    manifest = load_manifest(package_dir)
    render_package_files(package_dir, manifest)
    package["status"] = manifest["status"]
    package["updated_at"] = manifest["updated_at"]
    policy_store.save_package(package)
    policy_store.save_seo_audit(package_id, "local", manifest["seo"])
    return package


def outdated_packages(limit: int = 500) -> list[dict]:
    """현재 렌더러보다 오래된 manifest를 사용하는 패키지를 반환한다."""
    outdated: list[dict] = []
    for package in policy_store.list_packages(limit=limit):
        manifest_path = Path(package["path"]) / "06_manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            version = int(manifest.get("schema_version", 1))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
        if version < PACKAGE_SCHEMA_VERSION:
            item = dict(package)
            item["schema_version"] = version
            outdated.append(item)
    return outdated


def rebuild_outdated_packages() -> dict:
    """구형 패키지를 외부 LLM·이미지 생성 없이 최신 형식으로 일괄 재빌드한다."""
    targets = outdated_packages()
    rebuilt, errors = [], []
    for index, package in enumerate(targets, start=1):
        print(
            f"[재빌드 {index}/{len(targets)}] {package['title']} "
            f"(schema {package['schema_version']} → {PACKAGE_SCHEMA_VERSION})",
            flush=True,
        )
        try:
            rebuilt.append(rebuild_package(package["id"]))
        except Exception as exc:
            errors.append(f"{package['id']}: {exc}")
            print(f"[오류] {errors[-1]}", flush=True)
    return {"total": len(targets), "rebuilt": len(rebuilt), "errors": errors}


def rebuild_all_packages() -> dict:
    """모든 기존 패키지에 최신 HTML·SEO 렌더러를 다시 적용한다."""
    targets = policy_store.list_packages(limit=500)
    rebuilt, errors = [], []
    for index, package in enumerate(targets, start=1):
        print(f"[전체 재빌드 {index}/{len(targets)}] {package['title']}", flush=True)
        try:
            rebuilt.append(rebuild_package(package["id"]))
        except Exception as exc:
            errors.append(f"{package['id']}: {exc}")
            print(f"[오류] {errors[-1]}", flush=True)
    return {"total": len(targets), "rebuilt": len(rebuilt), "errors": errors}


def _featured_body_files(package_dir: Path, manifest: dict) -> list[str]:
    """게시용 본문 산출물 중 대표 이미지 참조가 남은 파일명을 반환한다."""
    featured_url = (
        manifest.get("supabase", {}).get("images", {}).get("featured", {}).get("public_url", "")
    )
    paths = [
        package_dir / "02_본문_티스토리.html",
        package_dir / "02_본문_HTML블록용.txt",
        *(package_dir / "segments").glob("*.html"),
        *(package_dir / "segments").glob("*_HTML블록용.txt"),
    ]
    found: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        soup = BeautifulSoup(path.read_text(encoding="utf-8-sig"), "html.parser")
        has_slot = soup.find(attrs={"data-policy-image-slot": "featured"}) is not None
        has_url = bool(featured_url and soup.find("img", src=featured_url))
        if has_slot or has_url:
            found.append(str(path.relative_to(package_dir)))
    return sorted(set(found))


def remove_featured_from_body(package_id: str | None = None) -> dict:
    """대표 이미지 파일은 보존하고 게시용 본문에서만 제거해 패키지를 재빌드한다."""
    if package_id:
        package = policy_store.get_package(package_id)
        if not package:
            raise KeyError(f"패키지를 찾을 수 없습니다: {package_id}")
        targets = [package]
    else:
        targets = policy_store.list_packages(limit=500)
    rebuilt, errors = [], []
    for index, package in enumerate(targets, start=1):
        print(
            f"[대표이미지 본문 제거 {index}/{len(targets)}] {package['title']}",
            flush=True,
        )
        try:
            package_dir = Path(package["path"])
            manifest = load_manifest(package_dir)
            render_package_files(package_dir, manifest, sync_storage=False)
            package["status"] = manifest["status"]
            package["updated_at"] = manifest["updated_at"]
            policy_store.save_package(package)
            policy_store.save_seo_audit(package["id"], "local", manifest["seo"])
            rebuilt_package = package
            manifest = load_manifest(package_dir)
            remaining = _featured_body_files(package_dir, manifest)
            if remaining:
                raise RuntimeError("대표 이미지 참조가 남은 파일: " + ", ".join(remaining))
            rebuilt.append(rebuilt_package)
        except Exception as exc:
            message = f"{package['id']}: {exc}"
            errors.append(message)
            print(f"[오류] {message}", flush=True)
    return {"total": len(targets), "rebuilt": len(rebuilt), "errors": errors}


def upload_package_images(package_id: str) -> dict:
    """기존 패키지의 현재 이미지 3장을 Supabase에 올리고 게시 HTML을 다시 만든다."""
    package = policy_store.get_package(package_id)
    if not package:
        raise KeyError(f"패키지를 찾을 수 없습니다: {package_id}")
    package_dir = Path(package["path"])
    manifest = load_manifest(package_dir)
    render_package_files(package_dir, manifest)
    remote = manifest.get("supabase", {}).get("images", {})
    missing = [
        slot for slot in ("featured", "body1", "body2")
        if not remote.get(slot, {}).get("public_url")
        or remote.get(slot, {}).get("local_path") != manifest.get("current_images", {}).get(slot)
    ]
    package["status"] = manifest["status"]
    package["updated_at"] = manifest["updated_at"]
    policy_store.save_package(package)
    policy_store.save_seo_audit(package_id, "local", manifest["seo"])
    if missing:
        error = manifest.get("supabase", {}).get("last_error", "")
        raise RuntimeError(
            "Supabase에 올리지 못한 이미지: " + ", ".join(missing)
            + (f" · {error}" if error else "")
        )
    return manifest


def regenerate_image(package_id: str, slot: str, provider: str) -> dict:
    package = policy_store.get_package(package_id)
    if not package:
        raise KeyError(f"패키지를 찾을 수 없습니다: {package_id}")
    package_dir = Path(package["path"])
    manifest = load_manifest(package_dir)
    brief = next((item for item in manifest["draft"]["image_briefs"] if item["slot"] == slot), None)
    if not brief:
        raise KeyError(f"이미지 슬롯을 찾을 수 없습니다: {slot}")
    asset = generate_image(package_dir, brief, provider=provider)
    manifest.setdefault("generation", {})["images_enabled"] = True
    manifest["images"].append(asset)
    manifest["current_images"][slot] = asset["path"]
    if package.get("status") == "published":
        manifest["status"] = "published"
    render_package_files(package_dir, manifest)
    package["status"] = manifest["status"]
    package["updated_at"] = manifest["updated_at"]
    policy_store.save_package(package)
    policy_store.save_seo_audit(package_id, "local", manifest["seo"])
    return asset


def retry_failed_images(package_id: str, provider: str = "openai") -> list[dict]:
    """현재 이미지가 없는 슬롯만 재시도하고 성공·실패 이력을 모두 보존한다."""
    package = policy_store.get_package(package_id)
    if not package:
        raise KeyError(f"패키지를 찾을 수 없습니다: {package_id}")
    package_dir = Path(package["path"])
    manifest = load_manifest(package_dir)
    manifest.setdefault("generation", {})["images_enabled"] = True
    generated = []
    for brief in manifest["draft"]["image_briefs"]:
        slot = brief["slot"]
        if manifest.get("current_images", {}).get(slot):
            continue
        try:
            asset = generate_image(package_dir, brief, provider=provider)
        except Exception as exc:
            asset = failed_asset(brief, exc, provider)
        manifest["images"].append(asset)
        generated.append(asset)
        if asset.get("path"):
            manifest.setdefault("current_images", {})[slot] = asset["path"]
    render_package_files(package_dir, manifest)
    package["status"] = manifest["status"]
    package["updated_at"] = manifest["updated_at"]
    policy_store.save_package(package)
    policy_store.save_seo_audit(package_id, "local", manifest["seo"])
    return generated


def mark_manifest_published(package_id: str, url: str = "") -> dict:
    from . import policy_seo

    package = policy_store.mark_published(package_id, url)
    package_dir = Path(package["path"])
    manifest = load_manifest(package_dir)
    manifest["status"] = "published"
    manifest["published_at"] = package["published_at"]
    manifest["tistory_url"] = url
    save_manifest(package_dir, manifest)
    if url:
        try:
            policy_seo.run_published_for_package(package_id, url)
        except Exception as exc:
            policy_seo.failed_published_audit(package_id, url, exc)
            print(f"[안내] 게시 후 SEO 검사는 실패했지만 게시 완료 기록은 저장했습니다: {exc}")
    return package


def create_zip(package_id: str) -> Path:
    package = policy_store.get_package(package_id)
    if not package:
        raise KeyError(f"패키지를 찾을 수 없습니다: {package_id}")
    ZIP_ROOT.mkdir(parents=True, exist_ok=True)
    target = ZIP_ROOT / safe_name(package_id, 80)
    archive = shutil.make_archive(str(target), "zip", root_dir=package["path"])
    return Path(archive)


def reindex_packages() -> int:
    """SQLite가 유실돼도 글별 manifest에서 후보와 패키지 색인을 복원한다."""
    count = 0
    for manifest_path in OUTPUT_ROOT.glob("*/*/*/*/06_manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            source = manifest["source"]
            candidate = {
                "id": manifest["candidate_id"],
                "source_type": source.get("source_type", "manifest"),
                "external_id": source.get("external_id", ""),
                "title": source["official_title"],
                "category": manifest["category"],
                "agency": source.get("agency", ""),
                "region": source.get("region", "전국"),
                "source_url": source["source_url"],
                "official": bool(source.get("official", True)),
                "facts": source.get("facts", {}),
                "source_updated_at": source.get("source_updated_at", ""),
                "checked_at": source.get("checked_at", manifest["created_at"]),
                "score": 0,
                "status": "generated",
            }
            policy_store.upsert_candidate(candidate)
            policy_store.save_package({
                "id": manifest["id"], "candidate_id": manifest["candidate_id"],
                "title": manifest["title"], "category": manifest["category"],
                "path": str(manifest_path.parent), "status": manifest.get("status", "ready"),
                "created_at": manifest["created_at"], "updated_at": manifest.get("updated_at", manifest["created_at"]),
                "published_at": manifest.get("published_at", ""), "tistory_url": manifest.get("tistory_url", ""),
                "generation_mode": manifest.get("generation", {}).get("mode", "manual"),
                "automation_run_id": manifest.get("generation", {}).get("automation_run_id"),
            })
            count += 1
        except (KeyError, ValueError, json.JSONDecodeError, OSError):
            continue
    return count
