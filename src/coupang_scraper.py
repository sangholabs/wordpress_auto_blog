# 쿠팡 파트너스에 로그인 세션을 유지하며 상품 직링크를 추출한다 (Playwright, 0토큰)
# 1단계(현재): 로그인 유지 + 페이지 구조 분석(inspect). 2단계: 분석 결과로 추출 로직 완성.
import json
import re
import sys
from urllib.parse import parse_qs, quote

from playwright.sync_api import sync_playwright

from .config import DATA_DIR, get_settings

LINKS_FILE = DATA_DIR / "product_links.json"
ROCKET_ALTS = ["rocket"]  # 로켓배송만(프레시/직구는 품목이 적어 켜면 결과가 0이 되기 쉬움)
SEARCH_HASH = "https://partners.coupang.com/#affiliate/ws/link/0/{kw}"

PROFILE_DIR = DATA_DIR / ".pw_profile"  # 로그인 세션 저장(.gitignore 대상 data/ 하위)
PARTNERS_URL = "https://partners.coupang.com/"


def _cdp_port() -> int:
    return get_settings().get("coupang", {}).get("scraper_port", 9222)


_STEALTH = "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"


def _open():
    # 실제 Chrome + 자동화 흔적 제거로 봇 차단(Akamai)을 우회 시도한다.
    # 세션은 디스크에 저장돼 한 번 로그인하면 재부팅 후에도 유지된다.
    p = sync_playwright().start()
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        channel="chrome",
        headless=False,
        args=["--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
    )
    ctx.add_init_script(_STEALTH)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    return p, ctx, page


def _open_cdp(port: int | None = None):
    # SH님이 직접 띄운 실제 Chrome 에 연결한다(가장 확실한 봇 우회).
    # 사전: chrome.exe --remote-debugging-port=<port> --user-data-dir="...data\chrome-profile" 로 실행 후 수동 로그인.
    p = sync_playwright().start()
    browser = p.chromium.connect_over_cdp(f"http://localhost:{port or _cdp_port()}")
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    return p, ctx, page


def ensure_login(cdp: bool = False):
    # 파트너스에 접속해 로그인 상태를 확인한다. 미로그인이면 수동 로그인을 기다린다.
    # CDP 모드에서는 Playwright 가 페이지를 열지 않는다(봇 차단 회피). 사람이 직접 접속/로그인한다.
    p, ctx, page = _open_cdp() if cdp else _open()
    if not cdp:
        page.goto(PARTNERS_URL, wait_until="domcontentloaded")
        if "login" in page.url or "member" in page.url:
            input("브라우저에서 수동으로 로그인한 뒤, 이 창에서 Enter 를 누르세요... ")
    print(f"현재 URL: {page.url}")
    return p, ctx, page


def inspect(url: str, cdp: bool = False):
    # 주어진 페이지의 HTML/스크린샷을 저장해 셀렉터를 분석할 수 있게 한다.
    # CDP 모드에서는 사람이 이미 띄운 현재 페이지를 그대로 덤프한다(navigate 안 함).
    p, ctx, page = ensure_login(cdp=cdp)
    if not cdp:
        page.goto(url, wait_until="networkidle")
    (DATA_DIR / "inspect.html").write_text(page.content(), encoding="utf-8")
    page.screenshot(path=str(DATA_DIR / "inspect.png"), full_page=True)
    print(f"저장 완료 → {DATA_DIR / 'inspect.html'} , {DATA_DIR / 'inspect.png'}")
    ctx.close()
    p.stop()


_STATIC = (".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".woff", ".woff2", ".ico")


def netlog(cdp: bool = True):
    # 모든 비정적 요청을 캡처한다. 연결된 탭도 출력해 올바른 창에 붙었는지 확인한다.
    p = sync_playwright().start()
    browser = p.chromium.connect_over_cdp(f"http://localhost:{_cdp_port()}")
    captured = []

    def on_response(resp):
        u = resp.url
        if any(u.lower().split("?")[0].endswith(e) for e in _STATIC):
            return
        try:
            ct = resp.headers.get("content-type", "")
        except Exception:
            ct = ""
        body = None
        if "json" in ct:
            try:
                body = resp.json()
            except Exception:
                body = None
        captured.append({"url": u, "status": resp.status, "content_type": ct, "json": body})

    def wire(pg):
        pg.on("response", on_response)

    tabs = []
    for c in browser.contexts:
        for pg in c.pages:
            wire(pg)
            tabs.append(pg.url)
        c.on("page", wire)
    print(f"연결된 탭 {len(tabs)}개: {tabs}")
    input("이 창을 둔 채(위 탭 중 파트너스 창에서) 상품 검색 → 상품 클릭(링크 생성) 후 Enter... ")
    (DATA_DIR / "netlog.json").write_text(
        json.dumps(captured, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"캡처 {len(captured)}건 → {DATA_DIR / 'netlog.json'}")
    p.stop()


_STRIP = ["추천순위", "추천", "순위", "비교", "후기", "가성비", "best", "top", "vs", "단점", "브랜드", "2025", "2026"]


def _search_term(keyword: str) -> str:
    # SEO 키워드(에어프라이어 추천 순위)에서 핵심 상품어(에어프라이어)만 남겨 쿠팡 검색에 쓴다.
    t = keyword
    for w in _STRIP:
        t = re.sub(w, "", t, flags=re.IGNORECASE)
    return " ".join(t.split()) or keyword


def _parse_linkgen(url: str) -> dict:
    # 링크생성 URL 의 product[...] 파라미터에서 제목·이미지·가격을 뽑는다.
    q = url.split("?", 1)[1] if "?" in url else ""
    d = parse_qs(q)
    g = lambda k: d.get(k, [""])[0]
    return {
        "name": g("product[title]"),
        "image": g("product[image]"),
        "price": g("product[salesPrice]") or g("product[originPrice]"),
    }


def _apply_rocket_filter(page):
    # 신선 페이지 진입 시 필터는 꺼진 상태라, 각 로켓 체크박스를 한 번씩 켠다(best-effort).
    for alt in ROCKET_ALTS:
        sel = f'label.ant-checkbox-wrapper:has(img[alt="{alt}"])'
        try:
            if page.query_selector(sel):
                page.click(sel)
        except Exception:
            pass
    page.wait_for_timeout(800)  # 목록 재렌더 대기


def collect_links(page, keyword: str, limit: int = 5, rocket_only: bool = True) -> list[dict]:
    # 검색 결과의 상품을 차례로 클릭해 추적링크를 읽는다(SPA 내부 이동). 중복 상품은 건너뛴다.
    out, seen = [], set()
    idx, max_tries = 0, limit * 5
    while len(out) < limit and idx < max_tries:
        page.goto(SEARCH_HASH.format(kw=quote(keyword)), wait_until="domcontentloaded")
        try:
            page.wait_for_selector(".product-item", timeout=15000)
        except Exception:
            break
        if rocket_only:
            _apply_rocket_filter(page)
        items = page.query_selector_all(".product-item")
        if not items:
            # 필터로 0개가 되면 필터 없이 재시도(해당 키워드에 로켓 상품이 없는 경우)
            page.goto(SEARCH_HASH.format(kw=quote(keyword)), wait_until="domcontentloaded")
            try:
                page.wait_for_selector(".product-item", timeout=15000)
            except Exception:
                break
            items = page.query_selector_all(".product-item")
        if idx >= len(items):
            break
        items[idx].click()
        idx += 1
        try:
            page.wait_for_selector(".shorten-url-input", timeout=15000)
        except Exception:
            continue
        page.wait_for_timeout(400)
        link = page.inner_text(".shorten-url-input").strip()
        info = _parse_linkgen(page.url)
        if not link.startswith("http") or info["name"] in seen:
            continue
        seen.add(info["name"])
        info["url"] = link
        out.append(info)
    return out


def run(keywords: list[str], limit: int | None = None, cdp: bool = True):
    # 키워드별 추적링크를 모아 product_links.json 캐시에 병합 저장한다.
    cfg = get_settings().get("coupang", {})
    limit = limit or cfg.get("products_per_post", 5)
    rocket_only = cfg.get("rocket_only", True)
    p, ctx, page = _open_cdp() if cdp else _open()
    cache = json.loads(LINKS_FILE.read_text(encoding="utf-8")) if LINKS_FILE.exists() else {}
    for kw in keywords:
        term = _search_term(kw)
        links = collect_links(page, term, limit, rocket_only)
        if links:
            cache[kw] = links  # 저장은 원래 주제 키워드로(포맷터가 이 키로 조회)
            print(f"[{kw}] (검색어 '{term}') {len(links)}개 직링크 수집")
        else:
            print(f"[{kw}] (검색어 '{term}') 수집 실패(0개)")
    LINKS_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장 → {LINKS_FILE}")
    p.stop()


def _queue_keywords(n: int) -> list[str]:
    q = DATA_DIR / "topic_queue.json"
    if not q.exists():
        return []
    return [t["keyword"] for t in json.loads(q.read_text(encoding="utf-8"))[:n]]


if __name__ == "__main__":
    # 사용:
    #   python -m src.coupang_scraper --login            # 실제 Chrome 로 로그인 세션 만들기
    #   python -m src.coupang_scraper --inspect <URL>    # 페이지 구조 분석용 덤프
    #   python -m src.coupang_scraper --netlog --cdp     # 내부 API 캡처(검색/링크생성)
    #   python -m src.coupang_scraper --run --cdp [키워드...]  # 직링크 수집(없으면 주제큐 상위 5개)
    #   봇 차단되면 --cdp 추가 (SH님이 직접 띄운 Chrome 에 연결)
    cdp = "--cdp" in sys.argv
    if "--run" in sys.argv:
        kws = [a for a in sys.argv[1:] if not a.startswith("--")] or _queue_keywords(5)
        run(kws, cdp=cdp)
        sys.exit(0)
    if "--netlog" in sys.argv:
        netlog(cdp=cdp)
        sys.exit(0)
    if "--inspect" in sys.argv:
        idx = sys.argv.index("--inspect")
        nxt = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
        url = "" if nxt.startswith("--") else nxt  # cdp 모드에선 URL 불필요(현재 페이지 덤프)
        inspect(url, cdp=cdp)
    else:
        p, ctx, page = ensure_login(cdp=cdp)
        input("분석할 준비가 되면 Enter 로 종료... ")
        if not cdp:
            ctx.close()
        p.stop()
