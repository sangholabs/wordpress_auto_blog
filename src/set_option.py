# settings.yaml 의 허용된 키 하나를 값으로 바꾼다 (bat/대시보드 공용, 주석 보존)
import re
import sys

from .settings_editor import set_section_option

SECTIONS = {
    "status": "publish", "posts_per_day": "publish", "schedule_time": "publish",
    "banner_layout": "content", "max_banners": "content", "featured_image": "content",
    "rocket_only": "coupang",
}
ALLOWED = set(SECTIONS)


def _bool(value: object) -> bool:
    lowered = str(value).strip().lower()
    if lowered in {"1", "true", "yes", "on", "켜기", "켜짐"}:
        return True
    if lowered in {"0", "false", "no", "off", "끄기", "꺼짐"}:
        return False
    raise ValueError("true 또는 false 값을 입력하세요.")


def normalize(key: str, value: object) -> object:
    if key not in ALLOWED:
        raise KeyError(f"허용되지 않은 키: {key} (가능: {', '.join(sorted(ALLOWED))})")
    text = str(value).strip()
    if key == "status":
        if text not in {"publish", "draft"}:
            raise ValueError("발행 상태는 publish 또는 draft여야 합니다.")
        return text
    if key == "schedule_time":
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", text):
            raise ValueError("시각은 HH:MM 형식이어야 합니다.")
        return text
    if key in {"posts_per_day", "max_banners"}:
        number = int(text)
        low, high = (1, 5) if key == "posts_per_day" else (1, 3)
        if not low <= number <= high:
            raise ValueError(f"{key}는 {low}~{high} 범위여야 합니다.")
        return number
    if key == "banner_layout":
        if text not in {"per_h2", "grouped", "grouped_h2"}:
            raise ValueError("배너 레이아웃이 올바르지 않습니다.")
        return text
    if key in {"featured_image", "rocket_only"}:
        return _bool(value)
    return text


def set_option(key: str, val: str):
    parsed = normalize(key, val)
    set_section_option(SECTIONS[key], key, parsed)
    print(f"로컬 설정 변경됨: {key} = {parsed}")
    return parsed


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        set_option(sys.argv[1], sys.argv[2])
    else:
        print("사용: python -m src.set_option <key> <value>")
