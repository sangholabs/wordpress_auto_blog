"""Git에서 제외된 로컬 설정 파일의 지정 섹션 값만 변경한다."""

from __future__ import annotations

from pathlib import Path

import yaml

from .config import ROOT

SETTINGS = ROOT / "config" / "settings.local.yaml"


def set_section_option(section: str, key: str, value: object, path: Path | None = None) -> None:
    """최상위 ``section``의 키를 로컬 YAML에 원자적으로 저장한다."""
    target = path or SETTINGS
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        with open(target, encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
    else:
        data = {}
    if not isinstance(data, dict):
        raise RuntimeError(f"로컬 설정 형식이 올바르지 않습니다: {target}")
    current = data.setdefault(section, {})
    if not isinstance(current, dict):
        raise RuntimeError(f"로컬 설정 섹션이 객체가 아닙니다: {section}")
    current[key] = value
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    temporary.replace(target)
