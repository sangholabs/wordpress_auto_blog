# 글 생성 LLM 추상화 — provider 교체(claude_code/gemini/anthropic)와 사용량 가드를 담당
import json
import os
import shutil
import subprocess
from datetime import date

from .config import DATA_DIR, env, get_settings

USAGE_FILE = DATA_DIR / "usage.json"


def _llm_cfg() -> dict:
    return get_settings().get("llm", {})


def _record_call(provider: str):
    today = str(date.today())
    data = {}
    if USAGE_FILE.exists():
        data = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
    day = data.setdefault(today, {})
    day[provider] = day.get(provider, 0) + 1
    USAGE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _via_claude_code(prompt: str, system: str | None) -> str:
    # 로컬 Claude Code CLI 를 헤드리스(-p)로 호출. 구독 로그인 인증을 사용한다.
    # 사전조건: PC에 Claude Code 설치 + `claude` 로그인 완료.
    # 플래그 버전 차이를 피하려고 system 을 본문에 합쳐 stdin 으로 전달한다.
    # Windows 에선 claude 가 .cmd/.ps1 셸이라 cmd /c 로 감싸 실행한다.
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError(
            "claude 명령을 찾을 수 없습니다. Claude Code 설치/로그인이 필요합니다. "
            "SETUP.md 3단계(npm i -g @anthropic-ai/claude-code → claude 로그인)를 참고하세요. "
            "또는 .env 에서 LLM_PROVIDER=gemini 로 바꾸세요."
        )
    full = f"{system}\n\n---\n\n{prompt}" if system else prompt
    cmd = ["cmd", "/c", exe, "-p"] if os.name == "nt" else [exe, "-p"]
    # 구독 로그인이 우선되도록 ANTHROPIC_API_KEY 를 자식 프로세스 환경에서 제거한다.
    child_env = os.environ.copy()
    child_env.pop("ANTHROPIC_API_KEY", None)
    result = subprocess.run(
        cmd, input=full, capture_output=True, text=True, encoding="utf-8", env=child_env
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude -p 실패: {result.stderr.strip()}")
    return result.stdout.strip()


def _via_gemini(prompt: str, system: str | None) -> str:
    import google.generativeai as genai

    if not env("GEMINI_API_KEY"):
        raise RuntimeError(
            "GEMINI_API_KEY 가 비어 있습니다. .env 에 키를 넣거나 LLM_PROVIDER 를 바꾸세요. (SETUP.md 참고)"
        )
    genai.configure(api_key=env("GEMINI_API_KEY"))
    name = _llm_cfg().get("gemini_model", "gemini-1.5-flash")
    model = genai.GenerativeModel(name, system_instruction=system)
    return model.generate_content(prompt).text.strip()


def _via_anthropic(prompt: str, system: str | None) -> str:
    import anthropic

    if not env("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY 가 비어 있습니다. .env 에 키를 넣거나 LLM_PROVIDER 를 바꾸세요. (SETUP.md 참고)"
        )
    client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
    cfg = _llm_cfg()
    msg = client.messages.create(
        model=cfg.get("anthropic_model", "claude-sonnet-4-6"),
        max_tokens=cfg.get("max_tokens", 4096),
        system=system or "",
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def generate(prompt: str, system: str | None = None) -> str:
    provider = env("LLM_PROVIDER", "claude_code")
    fn = {
        "claude_code": _via_claude_code,
        "gemini": _via_gemini,
        "anthropic": _via_anthropic,
    }.get(provider)
    if fn is None:
        raise ValueError(
            f"알 수 없는 LLM_PROVIDER: '{provider}'. "
            "claude_code | gemini | anthropic 중 하나여야 합니다. (.env 확인)"
        )
    text = fn(prompt, system)
    _record_call(provider)
    return text
