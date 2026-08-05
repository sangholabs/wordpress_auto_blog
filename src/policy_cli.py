"""정책·티스토리 작업실의 터미널 인터페이스."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import (
    affiliate, banner_setup, policy_package, policy_pages, policy_runner,
    policy_schedule_task, policy_seo, policy_service, policy_settings, policy_store,
)
from .config import ROOT, env


def _is_windows() -> bool:
    return os.name == "nt"


def _print_candidates(status: str | None = "ready", limit: int = 30) -> list[dict]:
    if status == "ready":
        policy_service.prune_expired_candidates()
    items = policy_store.list_candidates(status=status, limit=limit)
    if not items:
        print("정책 후보가 없습니다. collect 또는 import-url을 먼저 실행하세요.")
        return []
    if status == "ready":
        print(f"30~50대 주부·직장인 자동 추천 {len(items)}건 (점수 높은 순)")
    print("ID           점수  지역   카테고리 / 제목")
    for item in items:
        print(
            f"{item['id']:<12} {item['score']:>4}  "
            f"{item['region']:<6} {item['category']} / {item['title'][:60]}"
        )
        reasons = item.get("facts", {}).get("_curation", {}).get("reasons", [])
        if reasons:
            print(" " * 15 + "↳ " + " · ".join(reasons[:2]))
    return items


def _print_packages() -> list[dict]:
    items = policy_store.list_packages()
    if not items:
        print("생성된 티스토리 패키지가 없습니다.")
        return []
    print("글 ID                              상태                 제목")
    for item in items:
        print(f"{item['id']:<36} {item['status']:<20} {item['title'][:70]}")
    return items


def _workspace_status() -> None:
    settings = policy_settings.get()
    ready = len(policy_store.list_candidates(status="ready", limit=200))
    incomplete = len(policy_store.list_packages(status="needs_image_retry", limit=200))
    last_collect = str(policy_store.get_workspace_setting("last_full_collection_at", "없음"))[:16]
    on = lambda value: "켜짐" if value else "꺼짐"
    print("── 티스토리 작업실 설정 ───────────────────")
    print(
        f" 자동생성:{on(policy_schedule_task.status())} / 매일 {settings['schedule_time']} / "
        f"하루 {settings['packages_per_day']}편"
    )
    print(f" 추천후보:{ready}건 / 마지막 수집:{last_collect} / 이미지 재시도:{incomplete}건")
    print(
        f" 쿠팡:{on(settings['coupang_enabled'])}({affiliate.monetization_mode()}) / "
        f"배너:{settings['coupang_layout']}/{settings['coupang_max_blocks']}개 / "
        f"로켓전용:{on(settings['rocket_only'])}"
    )
    print(
        f" 글엔진:{env('LLM_PROVIDER', 'claude_code')} / "
        f"이미지:{settings['image_provider']}/{on(settings['images_enabled'])} / "
        f"SEO 통과:{settings['seo_pass_score']}점 이상"
    )
    print("────────────────────────────────────────────")


def _auto_settings_menu() -> None:
    print("1) 켜기  2) 끄기  3) 시각 변경  4) 하루 편수  5) 상태")
    choice = input("선택: ").strip()
    if choice == "1":
        policy_schedule_task.on()
    elif choice == "2":
        policy_schedule_task.off()
    elif choice == "3":
        value = policy_settings.set_value("schedule_time", input("시각(HH:MM): ").strip())
        print(f"티스토리 자동생성 시각 변경: {value}")
        if policy_schedule_task.status():
            policy_schedule_task.on()
    elif choice == "4":
        value = policy_settings.set_value("packages_per_day", input("하루 편수(1~5): ").strip())
        print(f"티스토리 하루 자동생성: {value}편")
    elif choice == "5":
        print("켜짐" if policy_schedule_task.status() else "꺼짐")


def _affiliate_settings_menu() -> None:
    print("1) 광고 켜기/끄기  2) 레이아웃  3) 배너 개수  4) 로켓 전용")
    print("5) 생성 패키지의 쿠팡 파트너스 광고 소재 입력/교체")
    choice = input("선택: ").strip()
    if choice == "1":
        enabled = input("1) 켜기  2) 끄기: ").strip() == "1"
        policy_settings.set_value("coupang_enabled", enabled)
    elif choice == "2":
        layout = {"1": "per_h2", "2": "grouped", "3": "grouped_h2"}.get(
            input("1) 소제목 분산  2) 한 자리 모음  3) 혼합: ").strip(), "per_h2"
        )
        policy_settings.set_value("coupang_layout", layout)
    elif choice == "3":
        policy_settings.set_value("coupang_max_blocks", input("배너 개수(1~3): ").strip())
    elif choice == "4":
        policy_settings.set_value("rocket_only", input("1) 켜기  2) 끄기: ").strip() == "1")
    elif choice == "5":
        _print_packages()
        package_id = input("글 ID: ").strip()
        assets = _prompt_coupang_assets()
        entries = policy_package.set_coupang_assets(package_id, assets)
        if entries:
            print(f"쿠팡 광고 소재 {len(entries)}개 저장 및 본문 HTML 재빌드 완료")
        else:
            print("직접 입력한 광고 소재를 삭제하고 기본 쿠팡 연결 방식으로 재빌드했습니다.")


def _open_policy_dashboard() -> None:
    args = [sys.executable, "-m", "src.dashboard", "--path", "/policy"]
    if _is_windows():
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        subprocess.Popen(args, cwd=str(ROOT), creationflags=flags)
    else:
        log = ROOT / "logs" / "policy_dashboard.log"
        log.parent.mkdir(exist_ok=True)
        with open(log, "a", encoding="utf-8") as output:
            subprocess.Popen(
                args, cwd=str(ROOT), stdout=output, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
    print("티스토리 정책 작업실 대시보드를 열었습니다. 잠시 후 브라우저를 확인하세요.")


def _claude_login() -> None:
    exe = shutil.which("claude")
    if not exe:
        print("claude가 설치돼 있지 않습니다. macOS/Windows 공통: npm install -g @anthropic-ai/claude-code")
        return
    if _is_windows():
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        subprocess.Popen(["cmd", "/c", exe], cwd=str(ROOT), creationflags=flags)
        print("새 창에서 Claude 로그인을 진행하세요.")
    else:
        print("현재 터미널에서 Claude를 실행합니다. 로그인을 마치고 종료하면 작업실로 돌아옵니다.")
        subprocess.run([exe], cwd=str(ROOT))
    print("Claude 인증은 같은 PC의 WordPress와 티스토리 글 생성 엔진이 공유합니다.")


def _image_settings_menu() -> None:
    enabled = input("대표 1장·본문 2장 생성  1) 켜기  2) 끄기: ").strip() == "1"
    policy_settings.set_value("images_enabled", enabled)
    print(f"티스토리 이미지 생성: {'켜짐' if enabled else '꺼짐'}")


def _clipboard_text() -> str:
    if sys.platform == "darwin":
        command = ["pbpaste"]
    elif _is_windows():
        command = ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"]
    else:
        raise RuntimeError("클립보드 소재 입력은 macOS와 Windows에서 지원합니다.")
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=True)
    if not result.stdout.strip():
        raise ValueError("클립보드가 비어 있습니다.")
    return result.stdout.strip()


def _prompt_coupang_assets() -> list[str]:
    limit = max(1, min(int(policy_settings.get().get("coupang_max_blocks", 2)), 3))
    assets: list[str] = []
    print("쿠팡 소재는 글별로 선택 사항입니다. 입력 순서대로 본문 광고 위치에 배치됩니다.")
    print("지원: 상품 URL / 링크+이미지 HTML / iframe / PartnersCoupang script")
    while len(assets) < limit:
        choice = input(
            f"쿠팡 소재 {len(assets) + 1}/{limit}  1) URL  2) 클립보드 코드  3) 코드 파일  0) 입력 완료: "
        ).strip()
        if choice in {"", "0"}:
            break
        if choice == "1":
            source = input("쿠팡 파트너스 상품 URL: ").strip()
        elif choice == "2":
            source = _clipboard_text()
        elif choice == "3":
            path = Path(input("HTML/텍스트 파일 경로: ").strip()).expanduser()
            source = path.read_text(encoding="utf-8-sig")
        elif choice.startswith("https://"):
            source = choice
        else:
            print("1, 2, 3, 0 중에서 선택하세요.")
            continue
        try:
            parsed = affiliate.parse_coupang_asset(source)
        except Exception as exc:
            print(f"[오류] 이 소재는 추가하지 않았습니다: {exc}")
            continue
        assets.append(source)
        print(f"  추가됨: {affiliate.coupang_asset_label(parsed)}")
    return assets


def interactive() -> None:
    while True:
        print("""
================ 정책·티스토리 작업실 ================
 [정책 후보 준비]
 1. 보조금24 후보 새로 수집
 2. 공식 정책 URL을 후보로 추가
 3. 추천 후보 목록 보기
 4. 대상 지역 설정 (변경 후 1번 재수집)

 [수동 글 생성]
 5. 선택 후보 수동 생성 (ID 1개 이상)
 6. 추천 상위 후보 수동 일괄 생성 (자동 선택)

 [생성 패키지 관리 — 수동·자동 공통]
 7. 전체 패키지 목록
 8. 패키지 미리보기 (글 ID)
 9. 제목·본문·태그 복사 (글 ID)
10. 패키지 폴더 열기 (글 ID)
11. 패키지 ZIP 만들기 (글 ID)
12. 티스토리 게시 완료 기록 (글 ID)
13. 기존 패키지 HTML·SEO 파일 재빌드 (글 재생성 아님)

 [자동 글 생성]
14. 오늘 할당량 지금 즉시 생성
15. 매일 자동생성 예약·시각·하루 편수 설정

 [이미지]
16. 이미지 1장 선택 재생성 (글 ID, 기존 이미지도 가능)
17. 누락·실패 이미지 전체 재시도 (글 ID)
18. 새 글의 대표·본문 이미지 생성 켜기/끄기

 [SEO]
19. SEO 검사 (게시 전/게시 URL, 글 재작성 안 함)

 [쿠팡 파트너스]
20. 티스토리 광고·레이아웃·개수·로켓·광고 소재 설정
21. 티스토리 쿠팡 배너 설정 도우미

 [기타]
22. 티스토리 대시보드 열기
23. Claude 로그인 (티스토리 글 생성 엔진)
24. 티스토리 애드센스 필수 페이지 패키지
 0. 이전 메뉴
========================================================""")
        _workspace_status()
        choice = input("번호 선택: ").strip()
        try:
            if choice == "1":
                policy_service.collect()
            elif choice == "2":
                url = input("공식 정책 URL(https://): ").strip()
                policy_service.import_url(url)
            elif choice == "3":
                _print_candidates()
            elif choice == "4":
                regions = [x.strip() for x in input("시·도/시·군·구(쉼표 구분, 비우면 전국만): ").split(",") if x.strip()]
                policy_service.set_regions(regions)
            elif choice == "5":
                _print_candidates(status="ready")
                ids = input("생성할 후보 ID(여러 개는 공백 구분): ").split()
                provider = input("이미지 엔진 1) OpenAI  2) Pollinations : ").strip()
                for candidate_id in ids:
                    try:
                        print(f"[{candidate_id}] 글에 넣을 쿠팡 파트너스 소재를 선택하세요.")
                        coupang_assets = _prompt_coupang_assets()
                        policy_service.generate_candidate(
                            candidate_id, "pollinations" if provider == "2" else "openai",
                            coupang_assets=coupang_assets,
                        )
                    except Exception as exc:
                        print(f"[오류] {candidate_id}: {exc}")
            elif choice == "6":
                _print_candidates(limit=10)
                count = max(1, min(int(input("자동 생성할 편수(기본 1): ").strip() or "1"), 10))
                provider = "pollinations" if input("이미지 1) OpenAI  2) Pollinations : ").strip() == "2" else "openai"
                policy_service.generate_recommended(count, provider)
            elif choice == "7":
                _print_packages()
            elif choice == "8":
                _print_packages()
                policy_service.open_package(input("글 ID: ").strip(), preview=True)
            elif choice == "9":
                _print_packages()
                package_id = input("글 ID: ").strip()
                part = input("title/html/segment1/segment2/segment3/tags: ").strip()
                policy_service.copy_content(package_id, part)
                print("클립보드에 복사했습니다.")
            elif choice == "10":
                _print_packages()
                policy_service.open_package(input("글 ID: ").strip())
            elif choice == "11":
                _print_packages()
                archive = policy_package.create_zip(input("글 ID: ").strip())
                print(f"ZIP 생성: {archive}")
            elif choice == "12":
                _print_packages()
                package_id = input("글 ID: ").strip()
                url = input("티스토리 게시 URL(선택): ").strip()
                policy_package.mark_manifest_published(package_id, url)
                print("게시 완료로 표시했습니다.")
            elif choice == "13":
                _print_packages()
                package = policy_package.rebuild_package(input("글 ID: ").strip())
                print(f"패키지 재빌드 완료: {package['path']}")
            elif choice == "14":
                result = policy_runner.run(trigger_type="manual")
                print(f"자동 생성 상태: {result['status']}")
            elif choice == "15":
                _auto_settings_menu()
            elif choice == "16":
                _print_packages()
                package_id = input("글 ID: ").strip()
                slot = {"대표": "featured", "본문1": "body1", "본문2": "body2"}.get(
                    input("대표/본문1/본문2: ").strip(), ""
                )
                provider = "pollinations" if input("1) OpenAI  2) Pollinations : ").strip() == "2" else "openai"
                asset = policy_package.regenerate_image(package_id, slot, provider)
                print(f"이미지 생성 완료: {asset['path']}")
            elif choice == "17":
                _print_packages()
                package_id = input("글 ID: ").strip()
                provider = "pollinations" if input("1) OpenAI  2) Pollinations: ").strip() == "2" else "openai"
                assets = policy_package.retry_failed_images(package_id, provider)
                success = sum(1 for asset in assets if asset.get("path"))
                print(f"실패 이미지 재시도 완료: 성공 {success}/{len(assets)}")
            elif choice == "18":
                _image_settings_menu()
            elif choice == "19":
                _print_packages()
                package_id = input("글 ID: ").strip()
                url = input("게시 URL(게시 전 검사만 하려면 Enter): ").strip()
                result = policy_seo.run_published_for_package(package_id, url) if url else policy_seo.run_local_for_package(package_id)
                print(f"SEO 검사: {result['score']}점 / {result['status']}")
                for issue in result["issues"]:
                    print(f"- {issue}")
            elif choice == "20":
                _affiliate_settings_menu()
            elif choice == "21":
                print("[티스토리] 아래 배너는 티스토리 정책 패키지와 WordPress가 공유하는 쿠팡 연결 파일에 저장됩니다.")
                banner_setup.setup_banner()
            elif choice == "22":
                _open_policy_dashboard()
            elif choice == "23":
                _claude_login()
            elif choice == "24":
                policy_pages.create_required_pages_package()
            elif choice == "0":
                return
            else:
                print("잘못된 번호입니다.")
        except Exception as exc:
            print(f"[오류] {exc}")
        input("\n[Enter] 작업실 메뉴로 돌아가기...")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="국가정책·티스토리 콘텐츠 작업실")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("collect")
    imp = sub.add_parser("import-url")
    imp.add_argument("url")
    imp.add_argument("--text", default="")
    listing = sub.add_parser("list")
    listing.add_argument("--status")
    listing.add_argument("--all", action="store_true", help="자동 선별에서 제외된 기존 후보도 표시")
    listing.add_argument("--limit", type=int, default=30)
    gen = sub.add_parser("generate")
    gen.add_argument("candidate_ids", nargs="+")
    gen.add_argument("--provider", choices=("openai", "pollinations"), default="openai")
    gen.add_argument(
        "--coupang-url", action="append", default=[],
        help="쿠팡 파트너스 제품 URL. 여러 개면 옵션을 반복합니다.",
    )
    gen.add_argument(
        "--coupang-asset-file", action="append", default=[],
        help="쿠팡 HTML/iframe/script 소재 파일. 여러 개면 옵션을 반복합니다.",
    )
    gen.add_argument("--coupang-asset", action="append", default=[], help=argparse.SUPPRESS)
    auto = sub.add_parser("generate-recommended")
    auto.add_argument("--count", type=int, default=1)
    auto.add_argument("--provider", choices=("openai", "pollinations"), default="openai")
    auto_run = sub.add_parser("auto-run")
    auto_run.add_argument("--count", type=int)
    auto_run.add_argument("--force-refresh", action="store_true")
    image = sub.add_parser("regenerate-image")
    image.add_argument("package_id")
    image.add_argument("slot", choices=("대표", "본문1", "본문2", "featured", "body1", "body2"))
    image.add_argument("--provider", choices=("openai", "pollinations"), default="openai")
    retry = sub.add_parser("retry-images")
    retry.add_argument("package_id")
    retry.add_argument("slot", choices=("대표", "본문1", "본문2", "featured", "body1", "body2", "all"))
    retry.add_argument("--provider", choices=("openai", "pollinations"), default="openai")
    seo = sub.add_parser("seo-check")
    seo.add_argument("package_id")
    seo.add_argument("--url", default="")
    settings = sub.add_parser("settings")
    settings.add_argument("action", choices=("show", "set"))
    settings.add_argument("key", nargs="?")
    settings.add_argument("value", nargs="?")
    for name in ("preview", "open", "zip", "rebuild"):
        cmd = sub.add_parser(name)
        cmd.add_argument("package_id")
    copy = sub.add_parser("copy")
    copy.add_argument("package_id")
    copy.add_argument("part", choices=("title", "html", "segment1", "segment2", "segment3", "tags"))
    published = sub.add_parser("mark-published")
    published.add_argument("package_id")
    published.add_argument("--url", default="")
    coupang_links = sub.add_parser("coupang-links")
    coupang_links.add_argument("package_id")
    coupang_links.add_argument("urls", nargs="*")
    coupang_links.add_argument("--clear", action="store_true")
    coupang_assets = sub.add_parser("coupang-assets")
    coupang_assets.add_argument("package_id")
    coupang_assets.add_argument("--url", action="append", default=[])
    coupang_assets.add_argument("--file", action="append", default=[])
    coupang_assets.add_argument("--clear", action="store_true")
    regions = sub.add_parser("regions")
    regions.add_argument("values", nargs="*")
    sub.add_parser("packages")
    sub.add_parser("dashboard")
    sub.add_parser("claude-login")
    sub.add_parser("banner-setup")
    sub.add_parser("required-pages")
    sub.add_parser("reindex")
    sub.add_parser("interactive")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "collect":
        policy_service.collect()
    elif args.command == "import-url":
        policy_service.import_url(args.url, args.text)
    elif args.command == "list":
        status = None if args.all else (args.status or "ready")
        _print_candidates(status, max(1, min(args.limit, 200)))
    elif args.command == "packages":
        _print_packages()
    elif args.command == "dashboard":
        _open_policy_dashboard()
    elif args.command == "claude-login":
        _claude_login()
    elif args.command == "banner-setup":
        banner_setup.setup_banner()
    elif args.command == "required-pages":
        policy_pages.create_required_pages_package()
    elif args.command == "generate":
        failures = []
        for candidate_id in args.candidate_ids:
            try:
                policy_service.generate_candidate(
                    candidate_id, args.provider,
                    coupang_assets=[
                        *(Path(path).expanduser().read_text(encoding="utf-8-sig") for path in args.coupang_asset_file),
                        *args.coupang_asset,
                        *args.coupang_url,
                    ],
                )
            except Exception as exc:
                failures.append(f"{candidate_id}: {exc}")
                print(f"[오류] {candidate_id}: {exc}", file=sys.stderr)
        if failures:
            raise RuntimeError(f"{len(failures)}건 생성 실패")
    elif args.command == "generate-recommended":
        policy_service.generate_recommended(max(1, min(args.count, 10)), args.provider)
    elif args.command == "auto-run":
        result = policy_runner.run(args.count, force_refresh=args.force_refresh, trigger_type="manual")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "regenerate-image":
        slot = {"대표": "featured", "본문1": "body1", "본문2": "body2"}.get(args.slot, args.slot)
        asset = policy_package.regenerate_image(args.package_id, slot, args.provider)
        print(asset["path"])
    elif args.command == "retry-images":
        if args.slot == "all":
            assets = policy_package.retry_failed_images(args.package_id, args.provider)
            print(json.dumps(assets, ensure_ascii=False, indent=2))
        else:
            slot = {"대표": "featured", "본문1": "body1", "본문2": "body2"}.get(args.slot, args.slot)
            print(policy_package.regenerate_image(args.package_id, slot, args.provider)["path"])
    elif args.command == "seo-check":
        result = policy_seo.run_published_for_package(args.package_id, args.url) if args.url else policy_seo.run_local_for_package(args.package_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "settings":
        if args.action == "show":
            print(json.dumps(policy_settings.get(), ensure_ascii=False, indent=2))
        else:
            if not args.key or args.value is None:
                raise ValueError("settings set에는 항목과 값이 필요합니다.")
            if args.key == "auto_generate":
                enabled = policy_settings.normalize(args.key, args.value)
                ok = policy_schedule_task.on() if enabled else policy_schedule_task.off()
                if not ok:
                    raise RuntimeError("티스토리 자동생성 예약 변경에 실패했습니다.")
                value = enabled
            else:
                was_registered = policy_schedule_task.status() if args.key == "schedule_time" else False
                value = policy_settings.set_value(args.key, args.value)
                if was_registered and not policy_schedule_task.on():
                    raise RuntimeError("변경한 시각으로 티스토리 예약을 재등록하지 못했습니다.")
            print(f"{args.key} = {value}")
    elif args.command == "preview":
        policy_service.open_package(args.package_id, preview=True)
    elif args.command == "open":
        policy_service.open_package(args.package_id)
    elif args.command == "copy":
        policy_service.copy_content(args.package_id, args.part)
        print("클립보드에 복사했습니다.")
    elif args.command == "zip":
        print(policy_package.create_zip(args.package_id))
    elif args.command == "rebuild":
        print(policy_package.rebuild_package(args.package_id)["path"])
    elif args.command == "mark-published":
        policy_package.mark_manifest_published(args.package_id, args.url)
        print("게시 완료로 표시했습니다.")
    elif args.command == "coupang-links":
        if not args.urls and not args.clear:
            raise ValueError("제품 URL을 입력하거나 삭제하려면 --clear를 사용하세요.")
        entries = policy_package.set_coupang_product_links(
            args.package_id, [] if args.clear else args.urls,
        )
        print(f"쿠팡 제품 링크 {len(entries)}개 저장 및 패키지 재빌드 완료")
    elif args.command == "coupang-assets":
        sources = [
            *(Path(path).expanduser().read_text(encoding="utf-8-sig") for path in args.file),
            *args.url,
        ]
        if not sources and not args.clear:
            raise ValueError("--url 또는 --file을 입력하거나 삭제하려면 --clear를 사용하세요.")
        entries = policy_package.set_coupang_assets(args.package_id, [] if args.clear else sources)
        print(f"쿠팡 광고 소재 {len(entries)}개 저장 및 패키지 재빌드 완료")
    elif args.command == "regions":
        policy_service.set_regions(args.values)
    elif args.command == "interactive":
        interactive()
    elif args.command == "reindex":
        print(f"manifest에서 {policy_package.reindex_packages()}건 복원했습니다.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        raise SystemExit(1)
