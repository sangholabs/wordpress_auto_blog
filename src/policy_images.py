"""정책 글용 대표/본문 이미지를 로컬 파일로 생성한다."""

from __future__ import annotations

import base64
import re
from pathlib import Path
from urllib.parse import quote

import requests

from .config import env, get_settings

SLOT_ORDER = {"featured": 1, "body1": 2, "body2": 3}
SLOT_KO = {"featured": "대표", "body1": "본문", "body2": "본문"}


def safe_name(text: str, max_length: int = 36) -> str:
    value = re.sub(r"[\\/:*?\"<>|\r\n]+", "-", text).strip(" .-")
    value = re.sub(r"\s+", "-", value)
    return (value[:max_length].rstrip("-_") or "정책혜택")


def image_prompt(brief: dict) -> str:
    return (
        "Warm editorial illustration for a Korean lifestyle and public-benefit article. "
        "Show ordinary Korean adults in their 30s to 50s in a relatable everyday setting. "
        f"Scene: {brief.get('prompt', '')}. "
        "Friendly natural colors, clean composition, trustworthy magazine illustration, ample breathing room. "
        "No text, no letters, no numbers, no currency, no logos, no government seals, no official emblems, "
        "no identifiable real person, no watermark, do not imply a real beneficiary or official government advertisement."
    )


def _version(images_dir: Path, slot: str) -> int:
    prefix = f"{SLOT_ORDER[slot]:02d}_"
    versions = [1]
    for path in images_dir.glob(prefix + "*"):
        match = re.search(r"_v(\d+)\.[^.]+$", path.name)
        if match:
            versions.append(int(match.group(1)))
        elif path.is_file():
            versions.append(1)
    return max(versions) + 1 if len(versions) > 1 else 1


def _openai_bytes(prompt: str, size: str, quality: str) -> tuple[bytes, str, str]:
    if not env("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY가 비어 있어 GPT Image 이미지를 생성할 수 없습니다. .env에 키를 넣으세요.")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai 패키지가 없습니다. requirements.txt를 다시 설치하세요.") from exc
    model = get_settings().get("policy_workspace", {}).get("image_model", "gpt-image-2")
    client = OpenAI(api_key=env("OPENAI_API_KEY"))
    result = client.images.generate(
        model=model,
        prompt=prompt,
        size=size,
        quality=quality,
        output_format="jpeg",
        output_compression=88,
    )
    encoded = result.data[0].b64_json
    if not encoded:
        raise RuntimeError("OpenAI 이미지 응답에 b64_json이 없습니다.")
    return base64.b64decode(encoded), "jpg", model


def _pollinations_bytes(prompt: str, size: str) -> tuple[bytes, str, str]:
    width, height = size.split("x", 1)
    url = (
        "https://image.pollinations.ai/prompt/"
        f"{quote(prompt)}?width={width}&height={height}&nologo=true&enhance=true"
    )
    response = requests.get(url, timeout=120)
    if response.status_code >= 400 or not response.content:
        raise RuntimeError(f"Pollinations 이미지 생성 실패: HTTP {response.status_code}")
    content_type = response.headers.get("content-type", "").lower()
    if "image" not in content_type:
        raise RuntimeError(f"Pollinations가 이미지가 아닌 응답을 반환했습니다: {content_type or 'unknown'}")
    ext = "png" if "png" in content_type else "webp" if "webp" in content_type else "jpg"
    return response.content, ext, "pollinations"


def generate_image(
    package_dir: Path, brief: dict, *, provider: str = "openai", version: int | None = None
) -> dict:
    slot = brief.get("slot", "")
    if slot not in SLOT_ORDER:
        raise ValueError(f"알 수 없는 이미지 슬롯: {slot}")
    images_dir = package_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    version = version or _version(images_dir, slot)
    size = "1200x640" if slot == "featured" else "1200x800"
    quality = get_settings().get("policy_workspace", {}).get("image_quality", "medium")
    prompt = image_prompt(brief)
    if provider == "openai":
        content, ext, model = _openai_bytes(prompt, size, quality)
    elif provider == "pollinations":
        content, ext, model = _pollinations_bytes(prompt, size)
    else:
        raise ValueError("이미지 provider는 openai 또는 pollinations여야 합니다.")
    suffix = "" if version == 1 else f"_v{version}"
    section = brief.get("section") or brief.get("caption") or SLOT_KO[slot]
    filename = f"{SLOT_ORDER[slot]:02d}_{SLOT_KO[slot]}_{safe_name(section)}{suffix}.{ext}"
    output = images_dir / filename
    output.write_bytes(content)
    return {
        "slot": slot,
        "path": str(output.relative_to(package_dir)),
        "filename": filename,
        "provider": provider,
        "model": model,
        "quality": quality if provider == "openai" else "service-default",
        "size": size,
        "version": version,
        "prompt": prompt,
        "alt": brief.get("alt", ""),
        "caption": brief.get("caption", ""),
        "section": brief.get("section", ""),
        "error": "",
    }


def failed_asset(brief: dict, error: Exception, provider: str) -> dict:
    slot = brief.get("slot", "")
    return {
        "slot": slot,
        "path": "",
        "filename": "",
        "provider": provider,
        "model": "",
        "quality": "",
        "size": "1200x640" if slot == "featured" else "1200x800",
        "version": 0,
        "prompt": image_prompt(brief),
        "alt": brief.get("alt", ""),
        "caption": brief.get("caption", ""),
        "section": brief.get("section", ""),
        "error": str(error),
    }
