# settings.yaml 의 허용된 키 하나를 값으로 바꾼다 (bat/대시보드 공용, 주석 보존)
import sys

from .settings_editor import set_section_option

SECTIONS = {
    "status": "publish", "posts_per_day": "publish", "schedule_time": "publish",
    "banner_layout": "content", "max_banners": "content", "featured_image": "content",
    "rocket_only": "coupang",
}
ALLOWED = set(SECTIONS)


def set_option(key: str, val: str):
    if key not in ALLOWED:
        print(f"허용되지 않은 키: {key} (가능: {', '.join(sorted(ALLOWED))})")
        return
    parsed: object = val
    if val.lower() in {"true", "false"}:
        parsed = val.lower() == "true"
    elif val.isdigit():
        parsed = int(val)
    set_section_option(SECTIONS[key], key, parsed)
    print(f"설정 변경됨: {key} = {val}")


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        set_option(sys.argv[1], sys.argv[2])
    else:
        print("사용: python -m src.set_option <key> <value>")
