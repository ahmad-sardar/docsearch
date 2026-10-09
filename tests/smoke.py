"""End-to-end check on a fresh machine (the Windows CI runs this): index a small folder of
docs, search it through the server (by name, typo, meaning and with AI), read a stored
page, then remove the docs while the server still runs. One page is nested thousands of
tags deep, as some sites are.

    uv run python tests/smoke.py

Then a small local website whose download stops half way and continues; whose vectors
stop and are made by the same command alone; and whose new copy (search upgrade) stops,
keeping the copy you have, and goes on the next time.

Everything goes to a temporary folder (DOCSEARCH_DATA, and a packages.toml there). The
models are downloaded into it the first time, unless DOCSEARCH_DATA already has them.
"""
from __future__ import annotations

import http.server
import json
import os
import re
import signal
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

os.environ["DOCSEARCH_ALLOW_HTTP"] = "1"          # the local website has no certificate
if "DOCSEARCH_DATA" not in os.environ:
    os.environ["DOCSEARCH_DATA"] = tempfile.mkdtemp(prefix="docsearch-smoke-")

from docsearch import cli, rerank, web  # noqa: E402

PAGES = {
    "index.html": ("Mini docs", "Welcome to the mini library. It shows how docs are searched."),
    "api/frames.html": ("frames.drop_duplicates",
                        "Return a table with duplicate rows removed. Rows that repeat an earlier row are "
                        "dropped, so every row is unique. Use keep to choose which copy stays."),
    "api/arrays.html": ("arrays.svd",
                        "Singular value decomposition of a matrix: factors it into U, S and V."),
    "con.html": ("Console output", "How the library prints to the console. A device name on Windows."),
    "aux/notes.html": ("Notes", "Extra notes, stored under a folder whose name Windows reserves."),
}


def check(ok: bool, what: str) -> None:
    print(("ok    " if ok else "FAIL  ") + what, flush=True)
    if not ok:
        web.stop()
        sys.exit(1)


def server_log() -> None:
    if web.LOG.exists():
        print("--- server.log\n" + web.LOG.read_text(encoding="utf-8", errors="replace")[-4000:])


def get(port: int, path: str, **params) -> dict:
    url = f"http://127.0.0.1:{port}{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=600) as r:
        return json.loads(r.read())


ASKED: list[str] = []                           # what the local website was asked for


def pages_asked() -> int:
    return sum(1 for path in ASKED if re.fullmatch(r"/docs/\d*", path))
SLOW = {"seconds": 0.0}                         # how long each of its pages takes


class Chain(http.server.BaseHTTPRequestHandler):
    """A website of 40 pages, each linking to the next."""

    def log_message(self, *args) -> None:
        pass

    def do_GET(self) -> None:
        ASKED.append(self.path)
        time.sleep(SLOW["seconds"])
        m = re.fullmatch(r"/docs/(\d*)", self.path)
        i = int(m.group(1) or 0) if m else -1
        body = (f"<html><body><main><h1>Chapter {i}</h1><p>{f'What chapter {i} explains. ' * 10}</p>"
                f"{f'<a href=/docs/{i + 1}>next</a>' if i < 39 else ''}</main></body></html>").encode()
        self.send_response(200 if m else 404)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def stop_and_continue() -> None:
    """A website download stopped half way (as by ctrl+c; here: after 5 pages) is kept and
    searchable, and `search add NAME` continues it to the end."""
    import contextlib
    import io
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Chain)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/docs/"

    def meta() -> dict:
        return json.loads((cli.HOME / "book" / "meta.json").read_text(encoding="utf-8"))
    cli.main(["add", f"book={url}", "--max-pages", "5", "--yes"])
    listed = io.StringIO()
    with contextlib.redirect_stdout(listed):
        cli.main(["list"])
    check(meta()["count"] == 5 and meta().get("partial") and not (cli.HOME / "book" / "emb.npy").exists()
          and "partial: 5 pages so far" in listed.getvalue(),
          "stopped after 5 pages: kept, listed as partial; its vectors wait for the rest (no wait at a stop)")
    cli.main(["upgrade", "book"])
    check(meta()["count"] == 5, "search upgrade leaves a stopped download to search add")
    cli.main(["add", "book"])
    check(meta()["count"] == 40 and not meta().get("partial") and not (cli.HOME / "book" / "crawl").exists(),
          "search add NAME continues it to the end")
    cli.main(["sync"])
    cli.main(["upgrade", "book"])
    check(meta()["count"] == 40, "then sync and upgrade as for any docs (and ask nothing again)")
    cli.main(["remove", "book"])
    server.shutdown()


def vectors_and_new_copies() -> None:
    """The vectors stop (ctrl+c): searchable by words; the same command makes them alone.
    A new copy (search upgrade) stops: yours is kept; the next upgrade goes on with it."""
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Chain)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/docs/"

    def meta() -> dict:
        return json.loads((cli.HOME / "vbook" / "meta.json").read_text(encoding="utf-8"))
    real = cli.embed_source

    def ctrl_c_in_vectors(_sid: str) -> None:
        raise KeyboardInterrupt
    cli.embed_source = ctrl_c_in_vectors
    try:
        cli.main(["add", f"vbook={url}", "--yes"])
        check(False, "the vectors stopped")
    except SystemExit:
        pass
    finally:
        cli.embed_source = real
    check(meta().get("partial") == {"step": "vectors"} and not (cli.HOME / "vbook" / "emb.npy").exists(),
          "ctrl+c while the vectors are made: the docs kept, marked as missing them")
    ASKED.clear()
    cli.main(["add", "vbook"])
    check(not meta().get("partial") and (cli.HOME / "vbook" / "emb.npy").exists() and not ASKED,
          "search add NAME made the vectors, and downloaded nothing")

    SLOW["seconds"] = 0.15
    ASKED.clear()

    def ctrl_c_in_new_copy() -> None:
        while signal.getsignal(signal.SIGINT) is signal.default_int_handler or pages_asked() < 8:
            time.sleep(0.05)
        signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
    threading.Thread(target=ctrl_c_in_new_copy, daemon=True).start()
    cli.main(["upgrade", "vbook"])
    staged = cli.STAGING / "vbook"
    check(meta()["count"] == 40 and not meta().get("partial") and (staged / "crawl" / "plan.json").exists(),
          "ctrl+c in search upgrade: the copy you have stays; the new one is kept, stopped")
    SLOW["seconds"] = 0.0
    ASKED.clear()
    cli.main(["upgrade", "vbook"])
    check(meta()["count"] == 40 and not staged.exists() and 0 < pages_asked() < 40,
          f"search upgrade went on with it ({pages_asked()} pages, not 40) and put it in place")
    cli.main(["remove", "vbook"])
    server.shutdown()


def main() -> None:
    data = Path(os.environ["DOCSEARCH_DATA"])
    cli.CONFIG = data / "packages.toml"
    docs = data / "mini-docs"
    for rel, (title, text) in PAGES.items():
        f = docs / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f"<html><head><title>{title}</title></head><body><main><h1>{title}</h1>"
                     f"<p>{text}</p></main></body></html>", encoding="utf-8")
    deep = "<div><span>" * 3000 + "Nested pages: thousands of unclosed tags deep." + "</span></div>" * 3000
    (docs / "deep.html").write_text(f"<html><head><title>Nested pages</title></head><body><main>"
                                    f"<h1>Nested pages</h1>{deep}</main></body></html>", encoding="utf-8")
    print(f"data in {data}; models on the {'GPU (MLX)' if cli.use_mlx() else 'processor (numpy)'}")
    if rerank.model_dir() is None:
        rerank.download()
    cli.main(["add", f"mini={docs}"])
    check((cli.HOME / "mini" / "emb.npy").exists(), "indexed, with vectors")
    plain = data / "plain-docs"                  # docs added without vectors (embed = false): they
    plain.mkdir(parents=True, exist_ok=True)     # must not turn search by meaning off for the rest
    (plain / "index.html").write_text("<html><head><title>Plain notes</title></head><body><main><h1>Plain notes"
                                      "</h1><p>Kept without vectors: found by their words.</p></main></body></html>",
                                      encoding="utf-8")
    cli.main(["add", f"plain={plain}", "--no-embed"])

    port = web.start()
    try:
        def top(q: str, **kw) -> list[str]:
            return [it["name"] for it in get(port, "/api/search", q=q, src="mini", **kw)["items"]]
        check(top("drop_duplicates")[:1] == ["frames.drop_duplicates"], "search by name")
        check(top("drop_duplciates")[:1] == ["frames.drop_duplicates"], "search with a typo")
        check(top("remove repeated rows")[:1] == ["frames.drop_duplicates"], "search by meaning")
        r = get(port, "/api/search", q="how do i factor a matrix", src="mini", ai="1")
        check(r["ai"] == "ranked" and r["items"][0]["name"] == "arrays.svd", "search ai")
        check(top("Nested pages")[:1] == ["Nested pages"], "a page nested 6,000 tags deep")
        check(get(port, "/api/info")["mode"] == "hybrid"
              and [it["name"] for it in get(port, "/api/search", q="kept without vectors", src="plain")["items"]][:1]
              == ["Plain notes"], "docs without vectors: found by their words; search by meaning stays on")
        for q in ("Console output", "Notes"):
            hit = get(port, "/api/search", q=q, src="mini")["items"][0]
            entry = get(port, f"/api/entry/{hit['id']}")
            check(q in json.dumps(entry), f"stored page of '{q}' (a name Windows reserves)")
        cli.main(["remove", "plain"])
        cli.main(["remove", "mini"])                 # while the server still runs
        check(not (cli.HOME / "mini").exists(), "removed while the server runs")
    finally:
        web.stop()
    stop_and_continue()
    vectors_and_new_copies()
    print("all good")


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        server_log()
        raise
