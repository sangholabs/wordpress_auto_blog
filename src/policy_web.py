"""기존 로컬 대시보드에 연결되는 정책·티스토리 작업실 화면."""

from __future__ import annotations

import html
import json
import mimetypes
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from . import policy_package, policy_service, policy_store
from .config import ROOT
from .policy_sources import POLICY_CATEGORIES

LOG = ROOT / "logs" / "policy_workspace.log"

BASE_STYLE = """
body{font-family:-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;max-width:1160px;margin:24px auto;padding:0 18px;color:#202838;background:#f5f7fb}
a{color:#2d6cdf}.top{display:flex;justify-content:space-between;align-items:center;gap:12px}.panel{background:#fff;border:1px solid #dfe5ef;border-radius:12px;padding:18px;margin:16px 0;box-shadow:0 2px 8px #12213a0d}
button,.btn{display:inline-block;border:0;border-radius:8px;padding:9px 13px;background:#2d6cdf;color:#fff;text-decoration:none;cursor:pointer;font-size:14px}.green{background:#2f9e6f}.gray{background:#718096}.orange{background:#d9822b}.red{background:#c94b4b}
input,textarea,select{border:1px solid #cbd3df;border-radius:7px;padding:9px;font:inherit;box-sizing:border-box}textarea{width:100%;min-height:100px}table{width:100%;border-collapse:collapse;font-size:14px}th,td{padding:10px;border-bottom:1px solid #e8ecf2;text-align:left;vertical-align:top}th{background:#f8fafc}.muted{color:#687387;font-size:13px}.badge{display:inline-block;padding:3px 7px;border-radius:10px;background:#e9effb;color:#2e5599;font-size:12px}.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}.copybox{position:absolute;left:-9999px}pre{white-space:pre-wrap;background:#111827;color:#d9e2f1;padding:12px;border-radius:8px;max-height:260px;overflow:auto}.image{max-width:100%;border-radius:10px;border:1px solid #dfe5ef}.warn{background:#fff7e6;border:1px solid #ffd591;padding:10px;border-radius:8px;margin:8px 0}
"""


def _send(handler, body: str, status: int = 200, content_type: str = "text/html; charset=utf-8") -> None:
    data = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _redirect(handler, location: str) -> None:
    handler.send_response(303)
    handler.send_header("Location", location)
    handler.end_headers()


def _layout(title: str, body: str) -> str:
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{BASE_STYLE}</style></head>
<body><div class="top"><h1>{html.escape(title)}</h1><div><a class="btn gray" href="/">기존 대시보드</a></div></div>{body}
<script>
async function copyFrom(id){{const el=document.getElementById(id);await navigator.clipboard.writeText(el.value);const old=event.target.textContent;event.target.textContent='복사됨';setTimeout(()=>event.target.textContent=old,1200)}}
</script></body></html>"""


def _tail() -> str:
    if not LOG.exists():
        return "아직 정책 작업 로그가 없습니다."
    return "\n".join(LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-60:])


def _bg(args: list[str]) -> None:
    LOG.parent.mkdir(exist_ok=True)
    child_env = os.environ.copy()
    child_env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    with open(LOG, "a", encoding="utf-8") as output:
        subprocess.Popen(
            args, cwd=str(ROOT), stdout=output, stderr=subprocess.STDOUT,
            env=child_env, start_new_session=True,
        )


def _candidate_rows(items: list[dict]) -> str:
    rows = []
    for item in items:
        official = "공식" if item["official"] else "확인 필요"
        disabled = "" if item["official"] and item["status"] in ("ready", "failed") else "disabled"
        reasons = item.get("facts", {}).get("_curation", {}).get("reasons", [])
        reason_html = " · ".join(html.escape(reason) for reason in reasons[:2])
        rows.append(
            f'<tr><td><input type="checkbox" name="candidate_id" value="{item["id"]}" {disabled}></td>'
            f'<td><strong>{html.escape(item["title"])}</strong><div class="muted">{html.escape(item.get("agency", ""))}</div>'
            f'<a href="{html.escape(item["source_url"], quote=True)}" target="_blank">공식 출처</a></td>'
            f'<td>{html.escape(item["category"])}<br><span class="badge">{html.escape(item["region"])}</span></td>'
            f'<td>{item["score"]}<div class="muted">{reason_html}</div></td><td>{html.escape(item["status"])}<br><span class="muted">{official}</span></td>'
            f'<td class="muted">{html.escape(item["checked_at"][:16])}<br>{html.escape(item.get("last_error", ""))}</td></tr>'
        )
    return "".join(rows) or '<tr><td colspan="6">정책 후보가 없습니다.</td></tr>'


def _package_rows(items: list[dict]) -> str:
    rows = []
    for item in items:
        rows.append(
            f'<tr><td><a href="/policy/package?id={item["id"]}"><strong>{html.escape(item["title"])}</strong></a>'
            f'<div class="muted">{html.escape(item["id"])}</div></td><td>{html.escape(item["category"])}</td>'
            f'<td><span class="badge">{html.escape(item["status"])}</span></td><td>{html.escape(item["created_at"][:16])}</td></tr>'
        )
    return "".join(rows) or '<tr><td colspan="4">생성된 패키지가 없습니다.</td></tr>'


def index_page(message: str = "") -> str:
    candidates = policy_store.list_candidates(status="ready", limit=50)
    packages = policy_store.list_packages(limit=100)
    regions = ", ".join(policy_store.get_regions())
    message_html = f'<div class="panel warn">{html.escape(message)}</div>' if message else ""
    category_options = "".join(f'<option value="{html.escape(cat)}">{html.escape(cat)}</option>' for cat in POLICY_CATEGORIES)
    body = f"""{message_html}
<div class="grid"><section class="panel"><h2>정책 수집</h2>
<form method="post" action="/policy/collect"><button class="green">보조금24 후보 수집</button></form>
<p class="muted">DATA_GO_KR_API_KEY가 필요합니다. 전국 정책과 아래 선택 지역만 수집합니다.</p>
<form method="post" action="/policy/regions"><label>선택 지역(쉼표 구분)</label><div class="row"><input name="regions" style="flex:1" value="{html.escape(regions)}" placeholder="예: 서울, 성남"><button>저장</button></div></form></section>
<section class="panel"><h2>공식 URL 추가</h2><form method="post" action="/policy/import">
<input name="url" type="url" required style="width:100%" placeholder="https://... 공식 정책 페이지">
<details><summary class="muted">페이지를 읽지 못할 때 본문 붙여넣기</summary><textarea name="text"></textarea></details><button class="green">후보 추가</button></form></section></div>

<section class="panel"><h2>30~50대 생활밀착 자동 추천</h2>
<p class="muted">농림·수산업, 기업·특수직역 정책을 제외하고 근로자·가구·연령 조건과 실제 혜택을 기준으로 자동 선별한 목록입니다.</p>
<form method="post" action="/policy/generate-recommended"><div class="row"><label>상위 자동 선택 <input name="count" type="number" min="1" max="10" value="1" style="width:70px">편</label>
<label>이미지 엔진 <select name="provider"><option value="openai">OpenAI GPT Image</option><option value="pollinations">Pollinations</option></select></label><button class="green">추천 상위 정책 자동 생성</button></div></form>
<hr style="border:0;border-top:1px solid #e8ecf2;margin:16px 0"><form method="post" action="/policy/generate">
<div class="row"><label>이미지 엔진 <select name="provider"><option value="openai">OpenAI GPT Image</option><option value="pollinations">Pollinations</option></select></label>
<label>카테고리 참고 <select disabled><option>전체</option>{category_options}</select></label><button class="orange">선택 후보 글·이미지 생성</button></div>
<div style="overflow-x:auto"><table><thead><tr><th></th><th>정책</th><th>분류</th><th>점수</th><th>상태</th><th>확인</th></tr></thead><tbody>{_candidate_rows(candidates)}</tbody></table></div></form></section>

<section class="panel"><h2>티스토리 패키지</h2><div style="overflow-x:auto"><table><thead><tr><th>제목</th><th>카테고리</th><th>상태</th><th>생성일</th></tr></thead><tbody>{_package_rows(packages)}</tbody></table></div></section>
<section class="panel"><h2>작업 로그</h2><pre>{html.escape(_tail())}</pre><p class="muted">생성 중이면 새로고침해 상태를 확인하세요.</p></section>"""
    return _layout("국가정책·티스토리 작업실", body)


def package_page(package_id: str) -> str:
    package = policy_store.get_package(package_id)
    if not package:
        return _layout("패키지 없음", '<div class="panel">패키지를 찾을 수 없습니다.</div>')
    folder = Path(package["path"])
    manifest = policy_package.load_manifest(folder)
    fields = {
        "copy-title": ("제목", (folder / "01_제목.txt").read_text(encoding="utf-8")),
        "copy-html": ("전체 HTML", (folder / "02_본문_티스토리.html").read_text(encoding="utf-8")),
        "copy-seg1": ("본문 시작", (folder / "segments/01_본문_시작.html").read_text(encoding="utf-8")),
        "copy-seg2": ("본문 중간", (folder / "segments/02_본문_중간.html").read_text(encoding="utf-8")),
        "copy-seg3": ("본문 마무리", (folder / "segments/03_본문_마무리.html").read_text(encoding="utf-8")),
        "copy-tags": ("태그", (folder / "04_태그.txt").read_text(encoding="utf-8")),
    }
    copy_buttons = "".join(
        f'<textarea class="copybox" id="{key}">{html.escape(value)}</textarea><button onclick="copyFrom(\'{key}\')">{label} 복사</button>'
        for key, (label, value) in fields.items()
    )
    images = []
    current = manifest.get("current_images", {})
    for brief in manifest["draft"]["image_briefs"]:
        slot = brief["slot"]
        path = current.get(slot, "")
        picture = (
            f'<img class="image" src="/policy/asset?id={package_id}&path={html.escape(path, quote=True)}">'
            f'<p><a class="btn gray" href="/policy/download?id={package_id}&path={html.escape(path, quote=True)}">다운로드</a></p>'
            if path else '<div class="warn">이미지가 없습니다. 아래에서 재생성하세요.</div>'
        )
        images.append(
            f'<div class="panel"><h3>{html.escape(slot)} · {html.escape(brief.get("section", ""))}</h3>{picture}'
            f'<p class="muted">ALT: {html.escape(brief.get("alt", ""))}<br>캡션: {html.escape(brief.get("caption", ""))}</p>'
            f'<form method="post" action="/policy/regenerate"><input type="hidden" name="package_id" value="{package_id}">'
            f'<input type="hidden" name="slot" value="{slot}"><select name="provider"><option value="openai">OpenAI</option><option value="pollinations">Pollinations</option></select> '
            '<button class="orange">이 이미지만 재생성</button></form></div>'
        )
    warnings = "".join(f'<div class="warn">{html.escape(w)}</div>' for w in manifest.get("verification_warnings", [])) or '<p>자동 검증 경고 없음</p>'
    body = f"""<section class="panel"><h2>{html.escape(manifest['title'])}</h2><p><span class="badge">{html.escape(manifest['status'])}</span> · {html.escape(manifest['category'])}</p>
<div class="row">{copy_buttons}<a class="btn green" href="/policy/open?id={package_id}&preview=1">미리보기 열기</a><a class="btn gray" href="/policy/open?id={package_id}">폴더 열기</a><a class="btn orange" href="/policy/zip?id={package_id}">ZIP 다운로드</a></div></section>
<section class="grid">{''.join(images)}</section><section class="panel"><h2>검증 경고</h2>{warnings}</section>
<section class="panel"><h2>티스토리 게시 완료 기록</h2><form method="post" action="/policy/published"><input type="hidden" name="package_id" value="{package_id}"><div class="row"><input name="url" type="url" style="flex:1" placeholder="https://내블로그.tistory.com/..." value="{html.escape(manifest.get('tistory_url',''))}"><button class="green">게시 완료 표시</button></div></form></section>"""
    return _layout("티스토리 패키지", body)


def _safe_file(package_id: str, relative: str) -> Path:
    package = policy_store.get_package(package_id)
    if not package:
        raise KeyError("패키지를 찾을 수 없습니다.")
    base = Path(package["path"]).resolve()
    target = (base / relative).resolve()
    if target != base and base not in target.parents:
        raise ValueError("패키지 밖의 파일은 열 수 없습니다.")
    if not target.is_file():
        raise FileNotFoundError(target)
    return target


def _serve_file(handler, path: Path, download: bool = False) -> None:
    data = path.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
    handler.send_header("Content-Length", str(len(data)))
    if download:
        handler.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(path.name)}")
    handler.end_headers()
    handler.wfile.write(data)


def handle_get(handler) -> bool:
    parsed = urlparse(handler.path)
    if not parsed.path.startswith("/policy"):
        return False
    query = parse_qs(parsed.query)
    try:
        if parsed.path == "/policy":
            _send(handler, index_page(query.get("message", [""])[0]))
        elif parsed.path == "/policy/package":
            _send(handler, package_page(query.get("id", [""])[0]))
        elif parsed.path in ("/policy/asset", "/policy/download"):
            path = _safe_file(query.get("id", [""])[0], query.get("path", [""])[0])
            _serve_file(handler, path, download=parsed.path.endswith("download"))
        elif parsed.path == "/policy/open":
            policy_service.open_package(query.get("id", [""])[0], query.get("preview", [""])[0] == "1")
            _redirect(handler, "/policy/package?id=" + query.get("id", [""])[0])
        elif parsed.path == "/policy/zip":
            archive = policy_package.create_zip(query.get("id", [""])[0])
            _serve_file(handler, archive, download=True)
        else:
            _send(handler, "찾을 수 없습니다.", 404, "text/plain; charset=utf-8")
    except Exception as exc:
        _send(handler, index_page(f"오류: {exc}"), 400)
    return True


def _form(handler) -> dict[str, list[str]]:
    length = int(handler.headers.get("Content-Length", 0))
    return parse_qs(handler.rfile.read(length).decode("utf-8"), keep_blank_values=True)


def handle_post(handler) -> bool:
    parsed = urlparse(handler.path)
    if not parsed.path.startswith("/policy"):
        return False
    data = _form(handler)
    try:
        if parsed.path == "/policy/collect":
            _bg([sys.executable, "-m", "src.policy_cli", "collect"])
        elif parsed.path == "/policy/import":
            policy_service.import_url(data.get("url", [""])[0], data.get("text", [""])[0])
        elif parsed.path == "/policy/generate":
            ids = data.get("candidate_id", [])
            if not ids:
                raise ValueError("생성할 정책 후보를 선택하세요.")
            provider = data.get("provider", ["openai"])[0]
            _bg([sys.executable, "-m", "src.policy_cli", "generate", *ids, "--provider", provider])
        elif parsed.path == "/policy/generate-recommended":
            count = max(1, min(int(data.get("count", ["1"])[0]), 10))
            provider = data.get("provider", ["openai"])[0]
            _bg([
                sys.executable, "-m", "src.policy_cli", "generate-recommended",
                "--count", str(count), "--provider", provider,
            ])
        elif parsed.path == "/policy/regenerate":
            package_id = data.get("package_id", [""])[0]
            _bg([
                sys.executable, "-m", "src.policy_cli", "regenerate-image", package_id,
                data.get("slot", [""])[0], "--provider", data.get("provider", ["openai"])[0],
            ])
            _redirect(handler, f"/policy/package?id={package_id}")
            return True
        elif parsed.path == "/policy/published":
            package_id = data.get("package_id", [""])[0]
            policy_package.mark_manifest_published(package_id, data.get("url", [""])[0])
            _redirect(handler, f"/policy/package?id={package_id}")
            return True
        elif parsed.path == "/policy/regions":
            regions = [r.strip() for r in data.get("regions", [""])[0].split(",") if r.strip()]
            policy_service.set_regions(regions)
        else:
            raise ValueError("알 수 없는 작업입니다.")
        _redirect(handler, "/policy")
    except Exception as exc:
        _send(handler, index_page(f"오류: {exc}"), 400)
    return True
