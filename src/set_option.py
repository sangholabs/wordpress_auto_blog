# settings.yaml 의 허용된 키 하나를 값으로 바꾼다 (bat/대시보드 공용, 주석 보존)
import re
import sys

from .config import ROOT

SETTINGS = ROOT / "config" / "settings.yaml"
ALLOWED = {"status", "posts_per_day", "banner_layout", "max_banners", "rocket_only", "schedule_time", "featured_image"}


def set_option(key: str, val: str):
    if key not in ALLOWED:
        print(f"허용되지 않은 키: {key} (가능: {', '.join(sorted(ALLOWED))})")
        return
    if key == "schedule_time":
        val = f'"{val}"'  # 시간은 따옴표로 감싸야 YAML 이 문자열로 인식
    txt = SETTINGS.read_text(encoding="utf-8")
    new = re.sub(rf"(?m)^(\s*{re.escape(key)}:\s*)(\S+)", rf"\g<1>{val}", txt, count=1)
    SETTINGS.write_text(new, encoding="utf-8")
    print(f"설정 변경됨: {key} = {val}")


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        set_option(sys.argv[1], sys.argv[2])
    else:
        print("사용: python -m src.set_option <key> <value>")
