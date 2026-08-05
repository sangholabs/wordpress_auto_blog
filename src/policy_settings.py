"""정책·티스토리 작업실 전용 설정 조회와 변경."""

from __future__ import annotations

import re

from .config import get_settings
from .settings_editor import set_section_option

DEFAULTS = {
    "auto_generate": False,
    "schedule_time": "09:30",
    "packages_per_day": 1,
    "candidate_refresh_hours": 24,
    "generation_stale_minutes": 60,
    "image_provider": "openai",
    "image_model": "gpt-image-2",
    "image_quality": "medium",
    "images_enabled": True,
    "supabase_upload_enabled": True,
    "coupang_enabled": True,
    "coupang_layout": "per_h2",
    "coupang_max_blocks": 2,
    "rocket_only": True,
    "seo_title_min": 28,
    "seo_title_max": 45,
    "seo_description_min": 80,
    "seo_description_max": 155,
    "seo_min_body_chars": 1800,
    "seo_pass_score": 80,
    "seo_review_score": 60,
}


def get() -> dict:
    values = dict(DEFAULTS)
    values.update(get_settings().get("policy_workspace", {}))
    return values


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    lowered = str(value).strip().lower()
    if lowered in {"1", "true", "yes", "on", "켜기", "켜짐"}:
        return True
    if lowered in {"0", "false", "no", "off", "끄기", "꺼짐"}:
        return False
    raise ValueError("true 또는 false 값을 입력하세요.")


def normalize(key: str, value: object) -> object:
    if key not in DEFAULTS:
        raise KeyError(f"허용되지 않은 티스토리 설정: {key}")
    if isinstance(DEFAULTS[key], bool):
        return _as_bool(value)
    if key == "schedule_time":
        text = str(value).strip()
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", text):
            raise ValueError("시각은 HH:MM 형식이어야 합니다.")
        return text
    if key == "image_provider":
        text = str(value).strip().lower()
        if text not in {"openai", "pollinations"}:
            raise ValueError("이미지 엔진은 openai 또는 pollinations여야 합니다.")
        return text
    if key == "image_quality":
        text = str(value).strip().lower()
        if text not in {"low", "medium", "high"}:
            raise ValueError("이미지 품질은 low, medium, high 중 하나여야 합니다.")
        return text
    if key == "coupang_layout":
        text = str(value).strip()
        if text not in {"per_h2", "grouped", "grouped_h2"}:
            raise ValueError("배너 레이아웃이 올바르지 않습니다.")
        return text
    if isinstance(DEFAULTS[key], int):
        number = int(value)
        ranges = {
            "packages_per_day": (1, 5), "candidate_refresh_hours": (1, 168),
            "generation_stale_minutes": (15, 720),
            "coupang_max_blocks": (1, 3), "seo_title_min": (10, 60),
            "seo_title_max": (20, 80), "seo_description_min": (30, 180),
            "seo_description_max": (60, 250), "seo_min_body_chars": (800, 10000),
            "seo_pass_score": (60, 100), "seo_review_score": (0, 99),
        }
        low, high = ranges.get(key, (0, 10000))
        if not low <= number <= high:
            raise ValueError(f"{key}는 {low}~{high} 범위여야 합니다.")
        return number
    return str(value).strip()


def set_value(key: str, value: object) -> object:
    normalized = normalize(key, value)
    set_section_option("policy_workspace", key, normalized)
    return normalized
