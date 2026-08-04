"""정책·티스토리 작업실의 터미널 인터페이스."""

from __future__ import annotations

import argparse
import sys

from . import policy_package, policy_service, policy_store


def _print_candidates(status: str | None = "ready", limit: int = 30) -> list[dict]:
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


def interactive() -> None:
    while True:
        print("""
================ 정책·티스토리 작업실 ================
 1. 보조금24 정책 후보 수집      2. 공식 정책 URL 추가
 3. 후보 목록                    4. 선택 후보 글 생성
 5. 생성 패키지 목록             6. 패키지 미리보기
 7. 제목/본문/태그 복사           8. 이미지 개별 재생성
9. 패키지 폴더 열기             10. ZIP 만들기
11. 티스토리 게시 완료 표시      12. 선택 지역 설정
13. 추천 상위 정책 자동 생성
 0. 이전 메뉴
========================================================""")
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
                _print_candidates(status="ready")
                ids = input("생성할 후보 ID(여러 개는 공백 구분): ").split()
                provider = input("이미지 엔진 1) OpenAI  2) Pollinations : ").strip()
                for candidate_id in ids:
                    try:
                        policy_service.generate_candidate(candidate_id, "pollinations" if provider == "2" else "openai")
                    except Exception as exc:
                        print(f"[오류] {candidate_id}: {exc}")
            elif choice == "5":
                _print_packages()
            elif choice == "6":
                _print_packages()
                policy_service.open_package(input("글 ID: ").strip(), preview=True)
            elif choice == "7":
                _print_packages()
                package_id = input("글 ID: ").strip()
                part = input("title/html/segment1/segment2/segment3/tags: ").strip()
                policy_service.copy_content(package_id, part)
                print("클립보드에 복사했습니다.")
            elif choice == "8":
                _print_packages()
                package_id = input("글 ID: ").strip()
                slot = {"대표": "featured", "본문1": "body1", "본문2": "body2"}.get(
                    input("대표/본문1/본문2: ").strip(), ""
                )
                provider = "pollinations" if input("1) OpenAI  2) Pollinations : ").strip() == "2" else "openai"
                asset = policy_package.regenerate_image(package_id, slot, provider)
                print(f"이미지 생성 완료: {asset['path']}")
            elif choice == "9":
                _print_packages()
                policy_service.open_package(input("글 ID: ").strip())
            elif choice == "10":
                _print_packages()
                archive = policy_package.create_zip(input("글 ID: ").strip())
                print(f"ZIP 생성: {archive}")
            elif choice == "11":
                _print_packages()
                package_id = input("글 ID: ").strip()
                url = input("티스토리 게시 URL(선택): ").strip()
                policy_package.mark_manifest_published(package_id, url)
                print("게시 완료로 표시했습니다.")
            elif choice == "12":
                regions = [x.strip() for x in input("시·도/시·군·구(쉼표 구분, 비우면 전국만): ").split(",") if x.strip()]
                policy_service.set_regions(regions)
            elif choice == "13":
                _print_candidates(limit=10)
                count = max(1, min(int(input("자동 생성할 편수(기본 1): ").strip() or "1"), 10))
                provider = "pollinations" if input("이미지 1) OpenAI  2) Pollinations : ").strip() == "2" else "openai"
                policy_service.generate_recommended(count, provider)
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
    auto = sub.add_parser("generate-recommended")
    auto.add_argument("--count", type=int, default=1)
    auto.add_argument("--provider", choices=("openai", "pollinations"), default="openai")
    image = sub.add_parser("regenerate-image")
    image.add_argument("package_id")
    image.add_argument("slot", choices=("대표", "본문1", "본문2", "featured", "body1", "body2"))
    image.add_argument("--provider", choices=("openai", "pollinations"), default="openai")
    for name in ("preview", "open", "zip"):
        cmd = sub.add_parser(name)
        cmd.add_argument("package_id")
    copy = sub.add_parser("copy")
    copy.add_argument("package_id")
    copy.add_argument("part", choices=("title", "html", "segment1", "segment2", "segment3", "tags"))
    published = sub.add_parser("mark-published")
    published.add_argument("package_id")
    published.add_argument("--url", default="")
    regions = sub.add_parser("regions")
    regions.add_argument("values", nargs="*")
    sub.add_parser("packages")
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
    elif args.command == "generate":
        failures = []
        for candidate_id in args.candidate_ids:
            try:
                policy_service.generate_candidate(candidate_id, args.provider)
            except Exception as exc:
                failures.append(f"{candidate_id}: {exc}")
                print(f"[오류] {candidate_id}: {exc}", file=sys.stderr)
        if failures:
            raise RuntimeError(f"{len(failures)}건 생성 실패")
    elif args.command == "generate-recommended":
        policy_service.generate_recommended(max(1, min(args.count, 10)), args.provider)
    elif args.command == "regenerate-image":
        slot = {"대표": "featured", "본문1": "body1", "본문2": "body2"}.get(args.slot, args.slot)
        asset = policy_package.regenerate_image(args.package_id, slot, args.provider)
        print(asset["path"])
    elif args.command == "preview":
        policy_service.open_package(args.package_id, preview=True)
    elif args.command == "open":
        policy_service.open_package(args.package_id)
    elif args.command == "copy":
        policy_service.copy_content(args.package_id, args.part)
        print("클립보드에 복사했습니다.")
    elif args.command == "zip":
        print(policy_package.create_zip(args.package_id))
    elif args.command == "mark-published":
        policy_package.mark_manifest_published(args.package_id, args.url)
        print("게시 완료로 표시했습니다.")
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
