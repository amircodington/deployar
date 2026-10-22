"""Fault lab (B-15): a tiny shop page whose failure mode is chosen by FAULT, for the SRE demo.

FAULT=none (default) healthy · error: /api/products returns 500 with a traceback in the log ·
slow: /api/products sleeps 4 s · memory: every request keeps 40 MB until the container is OOM-killed.
Stdlib only, so the build is seconds and costs nothing to reason about.
"""

import json
import os
import sys
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

FAULT = os.environ.get("FAULT", "none")
PORT = int(os.environ.get("PORT", "8000"))
LEAK: list[bytes] = []
PAGE = """<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><title>فروشگاه آزمایشی</title>
<body style="font-family:system-ui;max-width:40rem;margin:3rem auto"><h1>فروشگاه آزمایشی دیپلویار</h1>
<p>حالت خطا: <b>{fault}</b></p><p><a href="/api/products">/api/products</a></p></body></html>"""


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, file=sys.stderr if "ERROR" in msg else sys.stdout, flush=True)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: str, kind: str = "application/json") -> None:
        data = body.encode()
        self.send_response(code)
        self.send_header("content-type", f"{kind}; charset=utf-8")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        started = time.monotonic()
        if self.path == "/api/health":
            self._send(200, '{"ok": true}')
        elif self.path.startswith("/api/products"):
            self.products()
        else:
            self._send(200, PAGE.format(fault=FAULT), "text/html")
        log(f"GET {self.path} {int((time.monotonic() - started) * 1000)}ms")

    def products(self) -> None:
        if FAULT == "memory":
            LEAK.append(b"x" * 40 * 1024 * 1024)
            log(f"cache size {len(LEAK) * 40} MB")
        if FAULT == "slow":
            time.sleep(4)
        if FAULT == "error":
            try:
                {"items": []}["products"]  # the bug: wrong key
            except KeyError:
                log("ERROR Internal Server Error: /api/products\n" + traceback.format_exc())
                self._send(500, '{"error": "internal"}')
                return
        self._send(200, json.dumps({"products": [{"name": "گوشی نمونه", "price_toman": 12_500_000}]}))

    def log_message(self, *args: object) -> None:
        pass  # one line per request comes from log() above


if __name__ == "__main__":
    log(f"fault lab listening on :{PORT} (FAULT={FAULT})")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
