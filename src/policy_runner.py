"""티스토리 정책 패키지를 일일 한도 안에서 자동 생성한다."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from . import policy_service, policy_store
from .policy_settings import get as get_policy_settings


def _needs_refresh(ready_count: int, needed: int, refresh_hours: int) -> bool:
    if ready_count < needed:
        return True
    value = policy_store.get_workspace_setting("last_full_collection_at", "")
    try:
        checked = datetime.fromisoformat(str(value))
        if checked.tzinfo is None:
            checked = checked.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return True
    return datetime.now(timezone.utc) - checked.astimezone(timezone.utc) >= timedelta(hours=refresh_hours)


def run(
    count: int | None = None, *, force_refresh: bool = False,
    trigger_type: str = "scheduled",
) -> dict:
    settings = get_policy_settings()
    if trigger_type == "scheduled" and not settings.get("auto_generate", False):
        print("티스토리 자동생성 설정이 꺼져 있어 예약 실행을 건너뜁니다.")
        return {"status": "disabled", "generated": 0, "skipped": 0, "failed": 0, "errors": []}
    daily_limit = max(1, min(int(settings.get("packages_per_day", 1)), 5))
    requested = daily_limit if count is None else max(1, min(int(count), daily_limit))
    today = datetime.now().astimezone().date().isoformat()
    already = policy_store.auto_packages_on(today)
    target = max(0, min(requested, daily_limit - already))
    if target == 0:
        print(f"오늘 티스토리 자동 생성 한도 {daily_limit}편을 이미 채웠습니다.")
        return {"status": "quota_reached", "generated": 0, "skipped": 0, "failed": 0, "errors": []}

    run_id = policy_store.begin_automation_run(target, trigger_type)
    if run_id is None:
        print("다른 티스토리 자동 생성 작업이 실행 중이어서 이번 실행을 건너뜁니다.")
        return {"status": "locked", "generated": 0, "skipped": 0, "failed": 0, "errors": []}

    generated, failed, skipped, errors = 0, 0, 0, []
    final_status = "completed"
    try:
        policy_service.prune_expired_candidates()
        ready_count = len(policy_store.list_candidates(status="ready", limit=200))
        refresh_hours = max(1, int(settings.get("candidate_refresh_hours", 24)))
        if force_refresh or _needs_refresh(ready_count, target, refresh_hours):
            try:
                policy_service.collect()
            except Exception as exc:
                message = f"정책 후보 재수집 실패: {exc}"
                errors.append(message)
                print(f"[안내] {message}")

        maximum_attempts = target * 3
        candidates = policy_service.recommended_candidates(maximum_attempts)
        if not candidates:
            errors.append("생성 가능한 추천 정책 후보가 없습니다.")
        provider = str(settings.get("image_provider", "openai"))
        for candidate in candidates:
            if generated >= target:
                break
            try:
                package = policy_service.generate_candidate(
                    candidate["id"], provider, generation_mode="auto",
                    automation_run_id=run_id,
                )
                generated += 1
                print(f"자동 생성 {generated}/{target}: {package['title']}")
            except Exception as exc:
                message = f"{candidate['id']} {candidate['title']}: {exc}"
                errors.append(message)
                if "신청기간이" in str(exc) and "종료" in str(exc):
                    skipped += 1
                    print(f"[건너뜀] 종료된 정책: {message}")
                else:
                    failed += 1
                    print(f"[오류] {message}")
        if generated < target:
            final_status = "partial" if generated else "failed"
            errors.append(f"요청 {target}편 중 {generated}편만 생성했습니다.")
    except Exception as exc:
        final_status = "failed"
        errors.append(str(exc))
        raise
    finally:
        policy_store.finish_automation_run(
            run_id, generated_count=generated, failed_count=failed,
            errors=errors, status=final_status,
        )
    print(f"티스토리 자동 생성 완료: 생성 {generated}편, 건너뜀 {skipped}건, 실패 {failed}건")
    return {
        "status": final_status, "run_id": run_id, "generated": generated,
        "skipped": skipped, "failed": failed, "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="티스토리 정책 패키지 일일 자동 생성")
    parser.add_argument("--count", type=int)
    parser.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args(argv)
    result = run(args.count, force_refresh=args.force_refresh, trigger_type="scheduled")
    return 0 if result["status"] in {"completed", "quota_reached", "locked", "disabled"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
