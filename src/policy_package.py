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

from . import affiliate, policy_store
from .config import ROOT, get_settings
from .policy_images import failed_asset, generate_image, safe_name
from .policy_prompts import unsupported_fact_warnings

OUTPUT_ROOT = ROOT / "output" / "tistory"
ZIP_ROOT = OUTPUT_ROOT / "zips"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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
    fragment = md.markdown(source, extensions=["tables", "fenced_code"])
    soup = BeautifulSoup(fragment, "html.parser")
    styles = {
        "h2": "font-size:24px;line-height:1.4;margin:42px 0 16px;border-left:5px solid #2d6cdf;padding-left:12px;color:#17233c",
        "h3": "font-size:20px;line-height:1.45;margin:30px 0 12px;color:#263b63",
        "p": "font-size:17px;line-height:1.85;margin:12px 0;color:#222",
        "ul": "font-size:17px;line-height:1.8;margin:12px 0;padding-left:24px",
        "ol": "font-size:17px;line-height:1.8;margin:12px 0;padding-left:24px",
        "blockquote": "margin:18px 0;padding:14px 18px;background:#f6f8fc;border-left:4px solid #7893c7;color:#34415b",
        "table": "width:100%;border-collapse:collapse;font-size:15px;line-height:1.6",
        "th": "border:1px solid #dfe4ec;padding:10px;background:#f5f7fb;text-align:left",
        "td": "border:1px solid #dfe4ec;padding:10px;text-align:left;vertical-align:top",
    }
    for tag, style in styles.items():
        for node in soup.find_all(tag):
            node["style"] = style
    for table in list(soup.find_all("table")):
        wrapper = soup.new_tag("div")
        wrapper["style"] = "overflow-x:auto;margin:20px 0;-webkit-overflow-scrolling:touch"
        table.wrap(wrapper)
    return str(soup)


def _image_placeholders(body: str, manifest: dict) -> str:
    soup = BeautifulSoup(body, "html.parser")
    headings = soup.find_all("h2")
    current = manifest.get("current_images", {})
    for offset, slot in enumerate(("body1", "body2"), start=1):
        brief = next((b for b in manifest["draft"]["image_briefs"] if b["slot"] == slot), {})
        section = brief.get("section", "")
        heading = next((h for h in headings if section and (section in h.get_text() or h.get_text() in section)), None)
        if heading is None and headings:
            heading = headings[min(offset, len(headings) - 1)]
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


def _affiliate_blocks(draft: dict, fallback_keyword: str) -> tuple[list[str], list[str], str]:
    cfg = get_settings().get("policy_workspace", {})
    limit = max(1, min(int(cfg.get("coupang_max_blocks", 2)), 3))
    queries = draft.get("coupang_queries") or [fallback_keyword]
    mode, blocks, warnings = affiliate.monetization_mode(), [], []
    if mode == "api":
        for query in queries:
            products = affiliate.products_for(query)
            if products:
                blocks.append(affiliate.cards_html([products[0]]))
            if len(blocks) >= limit:
                break
    elif mode == "widget":
        blocks = affiliate.load_widgets()[:limit]
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


def _source_footer(manifest: dict) -> str:
    source = manifest["source"]
    checked = source.get("checked_at", "")[:10]
    url = html.escape(source["source_url"], quote=True)
    title = html.escape(source["official_title"])
    agency = html.escape(source.get("agency", ""))
    return (
        '<section style="margin:38px 0 16px;padding:18px;background:#f7f9fc;border:1px solid #dfe6f1;border-radius:10px">'
        '<strong style="display:block;margin-bottom:8px">공식 출처와 확인 기준</strong>'
        f'<p style="font-size:14px;line-height:1.7;margin:0">{agency} · '
        f'<a href="{url}" target="_blank" rel="noopener">{title}</a><br>'
        f'{checked} 기준으로 확인했습니다. 신청 전 공식 페이지에서 최신 내용과 본인 자격을 다시 확인하세요.</p></section>'
    )


def _disclosure() -> str:
    text = html.escape(get_settings()["content"]["coupang_disclosure"])
    return (
        '<div style="background:#fff7e6;border:1px solid #ffd591;border-radius:8px;'
        f'padding:10px 14px;font-size:13px;color:#795b23;margin:18px 0">{text}</div>'
    )


def _split_segments(full_html: str) -> list[str]:
    pattern = r'<div data-policy-image-slot="body[12]"[^>]*>.*?</div>'
    parts = re.split(pattern, full_html, flags=re.DOTALL)
    while len(parts) < 3:
        parts.append("")
    return parts[:3]


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
        f'<title>{html.escape(manifest["title"])}</title></head><body style="margin:0;background:#eef1f6">'
        '<main style="max-width:760px;margin:24px auto;padding:24px;background:#fff">'
        f'<h1 style="font-size:31px;line-height:1.35">{html.escape(manifest["title"])}</h1>{rendered}</main></body></html>'
    )


def render_package_files(package_dir: Path, manifest: dict) -> None:
    body = _portable_html(manifest["draft"]["markdown"])
    body = _image_placeholders(body, manifest)
    blocks, ad_warnings, mode = _affiliate_blocks(manifest["draft"], manifest["source"]["official_title"])
    body = _insert_after_sections(body, blocks)
    full = (
        "<article style=\"max-width:720px;margin:0 auto;padding:8px 4px;font-family:-apple-system,"
        "BlinkMacSystemFont,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:#222\">"
        + _disclosure() + body + _source_footer(manifest) + "</article>"
    )
    segments = _split_segments(full)
    warnings = unsupported_fact_warnings(manifest["draft"]["markdown"], {
        "facts": manifest["source"].get("facts", {})
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
    warnings.extend(item["error"] for item in manifest.get("images", []) if item.get("error"))
    manifest["verification_warnings"] = sorted(set(w for w in warnings if w))
    manifest["coupang_mode"] = mode
    if manifest["verification_warnings"] and manifest.get("status") != "published":
        manifest["status"] = "ready_with_warnings"
    _write(package_dir / "01_제목.txt", manifest["title"] + "\n")
    _write(package_dir / "02_본문_티스토리.html", full)
    plain = BeautifulSoup(full, "html.parser").get_text("\n", strip=True)
    _write(package_dir / "03_본문_일반텍스트.txt", plain + "\n")
    _write(package_dir / "04_태그.txt", ", ".join(manifest["draft"]["tags"]) + "\n")
    for index, (name, content) in enumerate(zip(("시작", "중간", "마무리"), segments), start=1):
        _write(package_dir / "segments" / f"{index:02d}_본문_{name}.html", content)
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
    _write(package_dir / "05_출처_검증.md", verification)
    image_lines = []
    for slot in ("featured", "body1", "body2"):
        path = manifest.get("current_images", {}).get(slot, "생성 실패 - 작업실에서 재생성")
        image_lines.append(f"- {slot}: {path}")
    guide = f"""티스토리 수동 게시 순서

1. 01_제목.txt 내용을 티스토리 제목에 붙여넣습니다.
2. 대표 이미지를 글 상단에 업로드하고 티스토리 대표 이미지로 지정합니다.
3. segments/01_본문_시작.html을 HTML 모드에 붙여넣습니다.
4. images/02_본문 파일을 업로드하고 대체텍스트·캡션을 manifest대로 입력합니다.
5. segments/02_본문_중간.html을 이어 붙인 뒤 images/03_본문 파일을 업로드합니다.
6. segments/03_본문_마무리.html을 이어 붙입니다. 한 번에 작업하려면 02_본문_티스토리.html의 이미지 안내 상자를 실제 이미지로 교체합니다.
7. 04_태그.txt의 태그를 입력하고 05_출처_검증.md의 경고를 확인합니다.
8. 먼저 비공개로 저장해 표·이미지·쿠팡 링크·고지문구를 확인한 뒤 공개합니다.
9. 작업실에서 게시 완료를 표시하고 티스토리 URL을 기록합니다.

이미지 파일
{chr(10).join(image_lines)}
"""
    _write(package_dir / "00_게시가이드.txt", guide)
    _write(package_dir / "preview.html", _preview_html(full, manifest))
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


def create_package(candidate: dict, draft: dict, *, image_provider: str = "openai") -> dict:
    created = datetime.now().astimezone()
    package_id = f"{candidate['id']}-{created.strftime('%Y%m%d%H%M%S%f')}"
    package_dir = _package_dir(candidate["id"], draft["title"], created)
    package_dir.mkdir(parents=True, exist_ok=False)
    manifest = {
        "schema_version": 1,
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
        "images": [],
        "current_images": {},
        "verification_warnings": [],
    }
    for brief in draft["image_briefs"]:
        try:
            asset = generate_image(package_dir, brief, provider=image_provider)
        except Exception as exc:
            asset = failed_asset(brief, exc, image_provider)
        manifest["images"].append(asset)
        if asset.get("path"):
            manifest["current_images"][asset["slot"]] = asset["path"]
    if any(item.get("error") for item in manifest["images"]):
        manifest["status"] = "ready_with_warnings"
    render_package_files(package_dir, manifest)
    package = {
        "id": package_id,
        "candidate_id": candidate["id"],
        "title": draft["title"],
        "category": draft["category"],
        "path": str(package_dir),
        "status": manifest["status"],
        "created_at": manifest["created_at"],
        "updated_at": manifest["updated_at"],
    }
    policy_store.save_package(package)
    policy_store.set_candidate_status(candidate["id"], "generated")
    return package


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
    manifest["images"].append(asset)
    manifest["current_images"][slot] = asset["path"]
    was_published = package.get("status") == "published"
    if was_published:
        manifest["status"] = "published"
    elif all(manifest["current_images"].get(key) for key in ("featured", "body1", "body2")):
        manifest["status"] = "ready"
    render_package_files(package_dir, manifest)
    package["status"] = manifest["status"]
    package["updated_at"] = manifest["updated_at"]
    policy_store.save_package(package)
    return asset


def mark_manifest_published(package_id: str, url: str = "") -> dict:
    package = policy_store.mark_published(package_id, url)
    package_dir = Path(package["path"])
    manifest = load_manifest(package_dir)
    manifest["status"] = "published"
    manifest["published_at"] = package["published_at"]
    manifest["tistory_url"] = url
    save_manifest(package_dir, manifest)
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
            })
            count += 1
        except (KeyError, ValueError, json.JSONDecodeError, OSError):
            continue
    return count
