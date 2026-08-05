# 생성된 마크다운을 가독성 높은 HTML로 변환한다 — 목차·쿠팡 고지/링크·반응형 스타일 삽입
import re

import markdown as md

from .config import ROOT, get_settings
from . import affiliate

OUTPUT_DIR = ROOT / "output"

# 본문 가독성 스타일 (모바일 우선). 색·폭·폰트는 settings.yaml 의 design 에서 읽는다.
def _style() -> str:
    d = get_settings().get("design", {})
    mw = d.get("max_width_px", 720)
    fs = d.get("font_size_px", 18)
    lh = d.get("line_height", 1.8)
    pc = d.get("primary_color", "#2d6cdf")
    price = d.get("price_color", "#d6293e")
    ff = d.get("font_family", "-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif")
    return f"""<style>
.post{{max-width:{mw}px;margin:0 auto;padding:16px;font-size:{fs}px;line-height:{lh};
color:#222;font-family:{ff};}}
.post h1{{font-size:30px;line-height:1.35;margin:.6em 0;}}
.post h2{{font-size:24px;margin:1.4em 0 .5em;border-left:5px solid {pc};padding-left:10px;}}
.post img{{max-width:100%;height:auto;border-radius:8px;}}
.post table{{width:100%;border-collapse:collapse;margin:1em 0;}}
.post th,.post td{{border:1px solid #ddd;padding:10px;text-align:left;}}
.post th{{background:#f5f7fb;}}
.disclosure{{background:#fff7e6;border:1px solid #ffd591;border-radius:8px;
padding:10px 14px;font-size:14px;color:#8a6d3b;margin-bottom:20px;}}
.toc{{background:#f7f9fc;border:1px solid #e3e8f0;border-radius:8px;padding:14px 18px;margin:18px 0;}}
.toc a{{color:{pc};text-decoration:none;display:block;margin:4px 0;}}
.coupang-cta{{display:block;text-align:center;background:{pc};color:#fff;
padding:14px;border-radius:8px;font-weight:bold;text-decoration:none;margin:24px 0;}}
.products{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:14px;margin:24px 0;}}
.pcard{{border:1px solid #e3e8f0;border-radius:10px;overflow:hidden;text-align:center;}}
.pcard a{{text-decoration:none;color:#222;display:block;}}
.pcard img{{width:100%;aspect-ratio:1/1;object-fit:cover;}}
.pname{{font-size:14px;line-height:1.4;padding:8px 8px 0;height:3.9em;overflow:hidden;}}
.pprice{{font-weight:bold;color:{price};padding:4px 8px;}}
.pbtn{{display:block;background:{pc};color:#fff;padding:8px;font-size:14px;font-weight:bold;}}
.coupang-widget{{text-align:center;margin:24px 0;}}
.coupang-group{{display:flex;flex-wrap:wrap;gap:12px;justify-content:center;margin:24px 0;}}
.coupang-group .coupang-widget{{margin:0;}}
.faq{{background:#f7f9fc;border-left:4px solid {pc};border-radius:8px;padding:12px 16px;margin:10px 0;}}
.faq-q{{font-weight:bold;margin:0 0 6px;color:#222;}}
.faq-a{{margin:0;color:#444;}}
</style>"""


def _build_toc(html: str) -> str:
    # _anchor_headings 로 id 가 붙은 뒤의 <h2 id="N"> 를 파싱한다.
    headings = re.findall(r'<h2 id="(\d+)">(.*?)</h2>', html)
    if not headings:
        return ""
    items = "".join(f'<a href="#{i}">{h}</a>' for i, h in headings)
    return f'<nav class="toc"><strong>목차</strong>{items}</nav>'


def _anchor_headings(html: str) -> str:
    idx = [0]

    def repl(m):
        i = idx[0]
        idx[0] += 1
        return f'<h2 id="{i}">{m.group(1)}</h2>'

    return re.sub(r"<h2>(.*?)</h2>", repl, html)


def _coupang_cta(keyword: str) -> str:
    return affiliate.coupang_cta(keyword).replace('style="display:block;', 'class="coupang-cta" style="display:block;')


def _load_widgets() -> list[str]:
    return affiliate.load_widgets()


def _wp_widgets(for_wordpress: bool) -> list[str]:
    # WP 발행 시 script 배너가 방화벽에 막히면 숏코드 1개로 대체(설정 시).
    if for_wordpress:
        sc = (get_settings().get("coupang") or {}).get("wp_banner_shortcode")
        if sc:
            return [f'<div class="coupang-widget">{sc}</div>']
    return _load_widgets()


def _cards_html(products: list[dict]) -> str:
    return affiliate.cards_html(products)


def _from_cache(keyword: str) -> list[dict]:
    return affiliate.from_cache(keyword)


def _insert_banners(html: str, banners: list[str], max_n: int) -> str:
    # 소제목 바로 밑이 아니라 각 섹션의 '첫 문단 뒤'에 배너를 넣어 더 자연스럽게 한다.
    # 서로 다른 배너를 1개씩, 최대 min(max_n, 보유 배너 수)개.
    limit = min(max_n, len(banners))
    parts = html.split("</h2>")
    out, n = parts[0], 0
    for seg in parts[1:]:
        if n < limit:
            pos = seg.find("</p>")
            if pos != -1:  # 첫 문단 뒤
                pos += len("</p>")
                seg = seg[:pos] + banners[n] + seg[pos:]
            else:  # 문단이 없으면 소제목 바로 뒤
                seg = banners[n] + seg
            n += 1
        out += "</h2>" + seg
    return out


def _insert_block_after_h2(html: str, block: str, n: int) -> str:
    # 같은 블록(배너 그룹)을 앞쪽 n 개 </h2> 뒤에 삽입한다.
    parts = html.split("</h2>")
    out, cnt = parts[0], 0
    for seg in parts[1:]:
        out += "</h2>"
        if cnt < n:
            out += block
            cnt += 1
        out += seg
    return out


def _place(html: str, block: str) -> str:
    # 첫 [[PRODUCTS]] 토큰 자리에만 넣고, 없으면 본문 끝에 붙인다. (남은 토큰은 to_html 말미에서 제거)
    if "[[PRODUCTS]]" in html:
        return html.replace("[[PRODUCTS]]", block, 1)
    return html + block


def to_html(post: dict, for_wordpress: bool = False) -> str:
    s = get_settings()["content"]
    body_md = re.sub(r"^>\s*메타설명:.*$", "", post["markdown"], flags=re.MULTILINE)
    body_md = re.sub(r"^#\s+.+$", "", body_md, count=1, flags=re.MULTILINE)  # 첫 H1(제목)은 WP 제목과 중복이라 제거
    body_md = re.sub(r"(?m)^(\s*[-*])\s*\[[ xX]\]\s*", r"\1 ", body_md)  # 체크박스 문법 '- [ ]' → 일반 불릿
    body_md = re.sub(r"(?m)^(?!\s*[-*]\s)(.+)\n([ \t]*[-*]\s)", r"\1\n\n\2", body_md)  # 목록 앞 빈 줄 보장(장단점 등)
    body_md = re.sub(r"(?m)^([ \t]*[-*]\s.+)\n(?!\s*[-*]\s)(?=\S)", r"\1\n\n", body_md)  # 목록 뒤 빈 줄 보장
    html = md.markdown(body_md, extensions=["tables", "fenced_code"])
    html = _anchor_headings(html)
    # FAQ 를 카드(질문/답변) 형태로 감싼다
    html = re.sub(
        r"<p><strong>(Q\.\s*.*?)</strong>\s*(A\.\s*.*?)</p>",
        r'<div class="faq"><p class="faq-q">\1</p><p class="faq-a">\2</p></div>',
        html, flags=re.DOTALL,
    )
    layout = s.get("banner_layout", "per_h2")
    products = affiliate.products_for(post["keyword"], options=get_settings().get("coupang", {}))
    if products and layout == "per_h2":
        # 소제목마다 서로 다른 상품 카드 1개씩 + '추천 상품' 자리(토큰)엔 전체 그리드
        cards = [_cards_html([p]) for p in products]
        html = _insert_banners(html, cards, s.get("max_banners", 3))
        html = html.replace("[[PRODUCTS]]", _cards_html(products), 1)
    elif products:
        html = _place(html, _cards_html(products))  # 한 자리 그리드
    else:
        banners = _wp_widgets(for_wordpress)
        group = f'<div class="coupang-group">{"".join(banners[: s.get("max_banners", 3)])}</div>'
        if banners and layout == "grouped":
            # 한 자리(토큰)에 배너 그룹 1개
            html = _place(html, group)
        elif banners and layout == "grouped_h2":
            # 한 자리(토큰) + 앞쪽 소제목들 아래에 각각 배너 그룹
            html = _insert_block_after_h2(html, group, s.get("h2_groups", 3))
            html = _place(html, group)
        elif banners and layout == "per_h2":
            # 총 max_banners 개: '추천 상품' 자리 1개 + 나머지는 소제목마다 분산(서로 다른 배너)
            n = s.get("max_banners", 2)
            if "[[PRODUCTS]]" in html:
                html = html.replace("[[PRODUCTS]]", banners[0], 1)
                html = _insert_banners(html, banners[1:], max(n - 1, 0))
            else:
                html = _insert_banners(html, banners, n)
        elif banners:
            html = _place(html, banners[0])
        else:
            print(
                "[안내] 쿠팡 상품이 설정되지 않아 검색 링크로 대체합니다(수수료 미적용). "
                "다이나믹 배너(SETUP 5-A) 또는 스크래퍼/ API 를 설정하세요."
            )
            html = _place(html, _coupang_cta(post["keyword"]))
    html = html.replace("[[PRODUCTS]]", "")  # 남은 토큰(본문 문장 속 중복 언급 등) 제거
    # 레거시 [[COUPANG]] 토큰 정리(구버전 초안 호환)
    html = re.sub(r"\[\[COUPANG(:[^\]]*)?\]\]", _coupang_cta(post["keyword"]), html)
    disclosure = f'<div class="disclosure">{s["coupang_disclosure"]}</div>'
    toc = _build_toc(html) if s.get("toc") else ""
    full = f'{_style()}<article class="post">{disclosure}{toc}{html}</article>'
    return full


def save_preview(post: dict) -> str:
    from .generate_post import _slug

    out = OUTPUT_DIR / f"preview_{_slug(post['keyword'])}.html"
    out.write_text(to_html(post), encoding="utf-8")
    print(f"미리보기 저장 → {out}")
    return str(out)


if __name__ == "__main__":
    # 기존 초안 md 를 LLM 호출 없이 다시 렌더한다. 사용: python -m src.formatter output/draft_xxx.md
    import sys
    from pathlib import Path

    md_path = Path(sys.argv[1])
    keyword = md_path.stem.replace("draft_", "").replace("-", " ")
    save_preview({"keyword": keyword, "markdown": md_path.read_text(encoding="utf-8")})
