# 로컬 웹 대시보드 — 브라우저 버튼으로 발행·자동발행을 제어한다 (외부 의존성 없음, stdlib)
import argparse
import html as htmlmod
import os
import socket
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from . import policy_web, schedule_task
from .config import env, get_settings
from .set_option import set_option as _set_yaml

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
LOG = ROOT / "logs" / "pipeline.log"
PORT = int(env("DASHBOARD_PORT", "5000"))  # .env 로 변경 가능


def _pick_port(start: int) -> int:
    # start 부터 빈 포트를 찾는다(이미 쓰이면 자동으로 다음 번호).
    for p in range(start, start + 30):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return start

def _btn(key, val, label, cls="b1"):
    return (f'<form method="post" action="/set">'
            f'<input type="hidden" name="key" value="{key}">'
            f'<input type="hidden" name="val" value="{val}">'
            f'<button class="{cls}">{label}</button></form>')


PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="8"><title>WordPress 자동화 대시보드</title>
<style>
body{font-family:-apple-system,'Malgun Gothic',sans-serif;max-width:820px;margin:24px auto;padding:0 16px;color:#222;}
h1{font-size:22px;} h3{margin:20px 0 4px;font-size:14px;color:#555;}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:4px 0 8px;}
button{font-size:14px;padding:9px 14px;border:0;border-radius:8px;color:#fff;cursor:pointer;}
input[type=text]{padding:9px;border:1px solid #ccc;border-radius:8px;width:74px;}
.b1{background:#2d6cdf;}.b2{background:#3aa76d;}.b3{background:#e0a800;}.b4{background:#999;}.b5{background:#7048e8;}
.status{padding:12px 14px;background:#f5f7fb;border:1px solid #e3e8f0;border-radius:8px;line-height:2;}
.cur{color:#2d6cdf;font-weight:bold;}
pre{background:#0e1116;color:#d6deeb;padding:14px;border-radius:8px;overflow:auto;max-height:320px;font-size:13px;}
small{color:#777;}form{display:inline;}
</style></head><body>
<h1>WordPress 블로그 자동화 대시보드</h1>
<p><a href="/policy" style="display:inline-block;background:#2f9e6f;color:#fff;padding:10px 14px;border-radius:8px;text-decoration:none;font-weight:bold">국가정책·티스토리 작업실 열기</a></p>
<div class="status">
자동발행: <span class="cur">%%SCHED%%</span> (매일 %%TIME%%) &nbsp;·&nbsp;
발행모드: <span class="cur">%%MODE%%</span> &nbsp;·&nbsp;
하루 편수: <span class="cur">%%PPD%%</span> &nbsp;·&nbsp;
배너: <span class="cur">%%LAYOUT%% / %%MAXB%%개</span> &nbsp;·&nbsp;
로켓전용: <span class="cur">%%ROCKET%%</span>
</div>

<h3>발행</h3><div class="row">
<form method="post" action="/run"><button class="b1">지금 1편 발행</button></form>
<form method="post" action="/run-refresh"><button class="b2">키워드 새로 수집 후 발행</button></form>
</div>

<h3>자동발행</h3><div class="row">
<form method="post" action="/sched-on"><button class="b3">켜기</button></form>
<form method="post" action="/sched-off"><button class="b4">끄기</button></form>
<form method="post" action="/set"><input type="hidden" name="key" value="schedule_time"><input type="text" name="val" value="%%TIME%%"><button class="b5">시각 저장</button></form>
<small>시각 변경 후 '켜기'를 다시 누르세요</small>
</div>

<h3>발행모드</h3><div class="row">%%MODE_BTNS%%</div>
<h3>하루 편수</h3><div class="row">%%PPD_BTNS%%</div>
<h3>배너 레이아웃</h3><div class="row">%%LAYOUT_BTNS%%</div>
<h3>배너 개수</h3><div class="row">%%MAXB_BTNS%%</div>
<h3>로켓 전용</h3><div class="row">%%ROCKET_BTNS%%</div>

<h3>실행 로그 (8초마다 갱신)</h3><pre>%%LOG%%</pre>
</body></html>"""


def _bg(args):
    (ROOT / "logs").mkdir(exist_ok=True)
    env2 = os.environ.copy()
    env2["PYTHONUTF8"] = "1"          # 자식 프로세스 출력을 UTF-8 로 (로그 한글 깨짐 방지)
    env2["PYTHONIOENCODING"] = "utf-8"
    with open(LOG, "a", encoding="utf-8") as f:
        subprocess.Popen(args, cwd=str(ROOT), stdout=f, stderr=subprocess.STDOUT, env=env2)


def _tail(n=50):
    if not LOG.exists():
        return "(아직 로그 없음)"
    lines = LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    return htmlmod.escape("\n".join(lines[-n:]))


def _sched_status():
    return "켜짐" if schedule_task.status() else "꺼짐"


def _mode():
    try:
        return get_settings()["publish"]["status"]
    except Exception:
        return "?"


def _get(section, key, default):
    return get_settings().get(section, {}).get(key, default)


def _sched_time():
    return str(_get("publish", "schedule_time", "09:00"))


def _mode_btns():
    return _btn("status", "publish", "공개(publish)", "b1") + _btn("status", "draft", "초안(draft)", "b4")


def _ppd_btns():
    return "".join(_btn("posts_per_day", str(n), f"{n}편", "b1") for n in (1, 2, 3, 5))


def _layout_btns():
    opts = [("per_h2", "소제목 분산"), ("grouped", "한 자리 모아"), ("grouped_h2", "혼합")]
    return "".join(_btn("banner_layout", v, l, "b1") for v, l in opts)


def _maxb_btns():
    return "".join(_btn("max_banners", str(n), str(n), "b1") for n in (1, 2, 3))


def _rocket_btns():
    return _btn("rocket_only", "true", "켜기", "b2") + _btn("rocket_only", "false", "끄기", "b4")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if policy_web.handle_get(self):
            return
        repl = {
            "%%SCHED%%": _sched_status(), "%%TIME%%": _sched_time(), "%%MODE%%": _mode(),
            "%%PPD%%": str(_get("publish", "posts_per_day", 1)),
            "%%LAYOUT%%": _get("content", "banner_layout", "per_h2"),
            "%%MAXB%%": str(_get("content", "max_banners", 3)),
            "%%ROCKET%%": "켜짐" if _get("coupang", "rocket_only", True) else "꺼짐",
            "%%MODE_BTNS%%": _mode_btns(), "%%PPD_BTNS%%": _ppd_btns(),
            "%%LAYOUT_BTNS%%": _layout_btns(), "%%MAXB_BTNS%%": _maxb_btns(),
            "%%ROCKET_BTNS%%": _rocket_btns(), "%%LOG%%": _tail(),
        }
        body = PAGE
        for k, v in repl.items():
            body = body.replace(k, v)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_POST(self):
        if policy_web.handle_post(self):
            return
        if self.path == "/run":
            _bg([PY, "-m", "src.pipeline"])
        elif self.path == "/run-refresh":
            _bg([PY, "-m", "src.pipeline", "--refresh"])
        elif self.path == "/set":
            length = int(self.headers.get("Content-Length", 0))
            data = parse_qs(self.rfile.read(length).decode("utf-8"))
            key, val = data.get("key", [""])[0], data.get("val", [""])[0]
            if key and val:
                _set_yaml(key, val)
        elif self.path == "/sched-on":
            schedule_task.on()
        elif self.path == "/sched-off":
            schedule_task.off()
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def log_message(self, *a):
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description="WordPress·티스토리 로컬 대시보드")
    parser.add_argument("--path", choices=("/", "/policy"), default="/")
    args = parser.parse_args(argv)
    port = _pick_port(PORT)
    start_url = f"http://localhost:{port}{args.path if args.path != '/' else ''}"
    threading.Timer(1.0, lambda: webbrowser.open(start_url)).start()
    print(f"대시보드 실행 중 → {start_url}  (종료하려면 이 창에서 Ctrl+C)")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
