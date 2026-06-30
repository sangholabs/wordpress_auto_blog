# .env 와 config/*.yaml 을 읽어 설정·카테고리를 제공하는 로더
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if not (ROOT / ".env").exists():
    print("[안내] .env 가 없습니다. `copy .env.example .env` 후 값을 채우세요. (SETUP.md 참고)")
load_dotenv(ROOT / ".env")


def env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _load_yaml(name: str) -> dict:
    path = ROOT / "config" / name
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_settings() -> dict:
    return _load_yaml("settings.yaml")


def get_categories() -> dict:
    return _load_yaml("categories.yaml")


# 데이터/로그 디렉터리 (gitignore 대상, 없으면 생성)
DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "logs"
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
