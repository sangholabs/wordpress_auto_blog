"""정책 작업실의 수집, 생성, 복사, 열기 동작을 조정한다."""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

from . import policy_package, policy_sources, policy_store
from .policy_prompts import generate_policy_draft


def collect() -> list[dict]:
    items = policy_sources.collect_gov24()
    stats = policy_sources.LAST_COLLECTION_STATS
    print(
        f"보조금24 {stats.get('scanned', len(items))}건 검사 → "
        f"30~50대 생활밀착 추천 {len(items)}건 자동 선별 완료"
    )
    if stats.get("condition_error"):
        print("[안내] 세부 대상조건 조회 실패로 정책 본문 기준 선별만 적용했습니다.")
    return items


def recommended_candidates(limit: int = 20) -> list[dict]:
    count = max(1, min(limit, 200))
    pool = policy_store.list_candidates(status="ready", limit=200)
    selected: list[dict] = []
    category_counts: dict[str, int] = {}
    while pool and len(selected) < count:
        best = max(
            pool,
            key=lambda item: item["score"] - category_counts.get(item["category"], 0) * 18,
        )
        pool.remove(best)
        selected.append(best)
        category_counts[best["category"]] = category_counts.get(best["category"], 0) + 1
    return selected


def generate_recommended(count: int = 1, image_provider: str = "openai") -> list[dict]:
    candidates = recommended_candidates(count)
    if not candidates:
        raise RuntimeError("생성 가능한 추천 정책이 없습니다. collect를 먼저 실행하세요.")
    print("자동 선택: " + ", ".join(f"{item['id']}({item['title']})" for item in candidates))
    return [generate_candidate(item["id"], image_provider) for item in candidates]


def import_url(url: str, pasted_text: str = "") -> dict:
    candidate = policy_sources.import_policy_url(url, pasted_text)
    label = "공식 출처" if candidate["official"] else "공식 출처 확인 필요"
    print(f"정책 후보 추가: {candidate['id']} · {candidate['title']} ({label})")
    return candidate


def generate_candidate(candidate_id: str, image_provider: str = "openai") -> dict:
    candidate = policy_store.get_candidate(candidate_id)
    if not candidate:
        raise KeyError(f"정책 후보를 찾을 수 없습니다: {candidate_id}")
    try:
        candidate = policy_sources.refresh_candidate(candidate_id)
    except Exception as exc:
        print(f"[안내] 공식 출처 재확인 실패, 캐시 검증을 진행합니다: {exc}")
        candidate = policy_store.get_candidate(candidate_id) or candidate
    errors = policy_sources.validate_for_generation(candidate)
    if errors:
        raise RuntimeError("정책 후보를 생성할 수 없습니다: " + " ".join(errors))
    policy_store.set_candidate_status(candidate_id, "generating")
    try:
        draft = generate_policy_draft(candidate)
        package = policy_package.create_package(candidate, draft, image_provider=image_provider)
    except Exception as exc:
        policy_store.set_candidate_status(candidate_id, "failed", str(exc))
        raise
    print(f"티스토리 패키지 생성 완료: {package['id']} → {package['path']}")
    return package


def _package(package_id: str) -> tuple[dict, Path]:
    package = policy_store.get_package(package_id)
    if not package:
        raise KeyError(f"패키지를 찾을 수 없습니다: {package_id}")
    path = Path(package["path"]).resolve()
    if not path.exists():
        raise FileNotFoundError(f"패키지 폴더가 없습니다: {path}")
    return package, path


def copy_content(package_id: str, part: str) -> str:
    _, folder = _package(package_id)
    files = {
        "title": folder / "01_제목.txt",
        "html": folder / "02_본문_티스토리.html",
        "segment1": folder / "segments" / "01_본문_시작.html",
        "segment2": folder / "segments" / "02_본문_중간.html",
        "segment3": folder / "segments" / "03_본문_마무리.html",
        "tags": folder / "04_태그.txt",
    }
    if part not in files:
        raise ValueError(f"복사 대상이 올바르지 않습니다: {part}")
    text = files[part].read_text(encoding="utf-8")
    system = platform.system()
    command = ["pbcopy"] if system == "Darwin" else ["clip"] if system == "Windows" else None
    if command is None:
        raise RuntimeError("클립보드 복사는 macOS와 Windows에서 지원합니다.")
    subprocess.run(command, input=text, text=True, encoding="utf-8", check=True)
    return text


def open_package(package_id: str, preview: bool = False) -> Path:
    _, folder = _package(package_id)
    target = folder / "preview.html" if preview else folder
    system = platform.system()
    if system == "Darwin":
        command = ["open", str(target)]
    elif system == "Windows":
        command = ["cmd", "/c", "start", "", str(target)] if preview else ["explorer", str(target)]
    else:
        raise RuntimeError("폴더/미리보기 열기는 macOS와 Windows에서 지원합니다.")
    subprocess.Popen(command, cwd=str(folder), start_new_session=system != "Windows")
    return target


def set_regions(regions: list[str]) -> None:
    policy_store.set_regions(regions)
    print("선택 지역 저장: " + (", ".join(regions) if regions else "전국 정책만"))
