"""주석을 보존하면서 settings.yaml의 지정 섹션 값만 변경한다."""

from __future__ import annotations

import re
from pathlib import Path

from .config import ROOT

SETTINGS = ROOT / "config" / "settings.yaml"


def _yaml_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if re.fullmatch(r"[A-Za-z0-9_.·가-힣-]+", text):
        return text
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def set_section_option(section: str, key: str, value: object, path: Path | None = None) -> None:
    """최상위 ``section`` 안의 2칸 들여쓰기 키 하나만 안전하게 갱신한다."""
    target = path or SETTINGS
    text = target.read_text(encoding="utf-8")
    section_match = re.search(rf"(?m)^{re.escape(section)}:\s*(?:#.*)?$", text)
    if not section_match:
        raise KeyError(f"설정 섹션을 찾을 수 없습니다: {section}")
    body_start = section_match.end()
    next_section = re.search(r"(?m)^\S[^\n]*:\s*(?:#.*)?$", text[body_start:])
    body_end = body_start + next_section.start() if next_section else len(text)
    body = text[body_start:body_end]
    scalar = _yaml_scalar(value)
    pattern = re.compile(rf"(?m)^(\s{{2}}{re.escape(key)}:\s*)([^#\n]*?)(\s*(?:#.*)?)$")
    if pattern.search(body):
        body = pattern.sub(rf"\g<1>{scalar}\g<3>", body, count=1)
    else:
        insertion = f"\n  {key}: {scalar}"
        body = body.rstrip("\n") + insertion + "\n"
    target.write_text(text[:body_start] + body + text[body_end:], encoding="utf-8")
