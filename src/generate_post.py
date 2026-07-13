# 주제 큐에서 글감을 골라 LLM으로 SEO 구조 글(마크다운)을 생성한다
import json
import re

from .config import DATA_DIR, ROOT
from .llm_provider import generate
from .prompts import POST_SYSTEM, build_post_prompt

QUEUE_FILE = DATA_DIR / "topic_queue.json"
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def _slug(keyword: str) -> str:
    return re.sub(r"\s+", "-", keyword.strip())


def generate_post(topic: dict) -> dict:
    prompt = build_post_prompt(topic)
    print(f"'{topic['keyword']}' 글 생성 중... (Claude 응답 대기, 1~3분 소요)", flush=True)
    markdown = generate(prompt, system=POST_SYSTEM)

    title_match = re.search(r"^#\s+(.+)$", markdown, re.MULTILINE)
    meta_match = re.search(r"^>\s*메타설명:\s*(.+)$", markdown, re.MULTILINE)
    post = {
        "keyword": topic["keyword"],
        "category": topic["category"],
        "title": title_match.group(1).strip() if title_match else topic["keyword"],
        "meta_description": meta_match.group(1).strip() if meta_match else "",
        "markdown": markdown,
    }
    out = OUTPUT_DIR / f"draft_{_slug(topic['keyword'])}.md"
    out.write_text(markdown, encoding="utf-8")
    print(f"초안 생성({len(markdown)}자) → {out}")
    return post


def top_topic() -> dict:
    queue = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    if not queue:
        raise RuntimeError("주제 큐가 비어있다. topic_queue 를 먼저 실행해라.")
    return queue[0]


if __name__ == "__main__":
    from .formatter import save_preview

    post = generate_post(top_topic())
    save_preview(post)
