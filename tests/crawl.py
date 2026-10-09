"""The website importer on a small local site that behaves as big docs sites do (each case
was seen on a real one): no models, no internet, a few seconds.

    uv run python tests/crawl.py

- the docs moved to a new release (Oracle: /23/ -> /26/): read there, not one page only
- a book whose contents are a <link rel="contents">, not a link (Oracle)
- "too many requests" (429) from Akamai (learn.microsoft.com): slow down and retry, not
  "a bot check" that gives the whole site up
- robots.txt Crawl-delay (AWS: 5 s): kept
- print copies of whole sections (Kubernetes: /_print/, 71% of its entries): not read
- one page by three addresses (c, c/, c/index.html): one entry
- a small box called "content" before the text (AWS), hidden text (Azure), and a hidden
  tab you can switch to (Docusaurus): the text is found, the hidden junk is not, the tab is
- links to missing pages (Kubernetes has hundreds): no reason to call a download incomplete
- a download stopped half way (ctrl+c, or a page budget): what it read is kept, and the
  same call continues it, to the same pages as one that never stopped
- the number of pages, from the sitemap, before the download starts, in its time budget
  also on a site that asks for a pause between pages
- a print copy is known by its link ("Print this book", as mdBook says), not by its name:
  Kotlin's print.html documents its print() function
- a site that stops answering stops the download (kept, partial) and it continues later; a
  page that keeps failing is given up after a few tries; pages are counted once
- a 429 never makes the wait between pages shorter than robots.txt asks
- ctrl+c (a real signal) while a slow page is awaited: seen at once (on Windows before Python
  3.14 a long wait cannot be interrupted, so the download waits in short slices)
"""
from __future__ import annotations

import contextlib
import http.server
import io
import os
import signal
import sys
import tempfile
import threading
import time

os.environ["DOCSEARCH_ALLOW_HTTP"] = "1"          # the local site has no certificate
if "DOCSEARCH_DATA" not in os.environ:
    os.environ["DOCSEARCH_DATA"] = tempfile.mkdtemp(prefix="docsearch-crawl-")

from docsearch import cli, importers  # noqa: E402

WORDS = "Words about tables, rows and the queries that read them. " * 8


def page(title: str, body: str, head: str = "") -> bytes:
    return (f"<html><head><title>{title}</title>{head}</head><body><main><h1>{title}</h1>"
            f"<p>{WORDS}</p>{body}</main></body></html>").encode()


SITE = {
    "/robots.txt": (200, b"User-agent: *\nCrawl-delay: 1\n"),
    "/v26/docs/": (200, page("SQL Reference", "", '<link rel="contents" href="toc.htm">')),
    "/v26/docs/toc.htm": (200, page("Contents", "".join(f'<a href="{h}">{h}</a> ' for h in (
        "a.html", "b.html", "c", "c/", "c/index.html", "_print/", "missing.html"))
        + '<a href="print.html" title="Print this book"></a> <a href="api/print.html">print</a>')),
    "/v26/docs/api/print.html": (200, page("print", "")),
    "/v26/docs/a.html": (200, b"<html><head><title>Alpha</title></head><body>"
                              b"<div class='content'>Thanks for letting us know.</div>"
                              b"<div class='body'><h1>Alpha</h1><div hidden>Access requires authorization.</div>"
                              b"<p>" + WORDS.encode() + b"</p><div role='tabpanel' hidden>Tab two text.</div>"
                              b"</div></body></html>"),
    "/v26/docs/b.html": (200, page("Beta", "")),
    "/v26/docs/c/": (200, page("Gamma", "")),
    "/v26/docs/c/index.html": (200, page("Gamma", "")),
    "/v26/docs/_print/": (200, page("Everything", WORDS * 50)),
    "/v26/docs/print.html": (200, page("Everything", WORDS * 50)),
}
REDIRECTS = {"/v23/docs/": "/v26/docs/", "/v26/docs/c": "/v26/docs/c/"}
for _n in range(12):                              # small sites for counting and failing
    SITE[f"/down/p{_n}.html"] = SITE[f"/flaky/p{_n}.html"] = (200, page(f"Page {_n}", ""))
SITE["/down/"] = (200, page("Down", "".join(f'<a href="p{n}.html">{n}</a> ' for n in range(12))))
SITE["/flaky/"] = (200, page("Flaky", "".join(f'<a href="p{n}.html">{n}</a> ' for n in range(6))))
SITE["/count/"] = (200, page("Count", '<a href="/flaky/p0.html">0</a> <a href="shell.html">app</a>'))
SITE["/count/shell.html"] = (200, b"<html><body><div id=app></div></body></html>")     # a JavaScript app
LOG: list[tuple[float, str]] = []
BUSY = {"/v26/docs/b.html": 2}                    # answers "too many requests" this many times
DROP: set[str] = set()                            # no answer at all (the connection drops)
SITE["/slow/"] = (200, page("Slow", '<a href="late.html">late</a> <a href="p0.html">0</a>'))
SITE["/slow/late.html"] = SITE["/slow/p0.html"] = (200, page("Late", ""))
LATE = {"/slow/late.html": 8.0}                   # answers after this many seconds


class Site(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass

    def do_GET(self) -> None:
        LOG.append((time.monotonic(), self.path))
        if self.path in REDIRECTS:
            self.send_response(301)
            self.send_header("Location", REDIRECTS[self.path])
            self.end_headers()
            return
        if self.path in DROP:
            self.connection.close()
            return
        time.sleep(LATE.get(self.path, 0))
        code, body = SITE.get(self.path, (404, b"<html><body>Not Found</body></html>"))
        if BUSY.get(self.path):
            BUSY[self.path] -= 1
            code, body = 429, b"<html><head><title>Too Many Requests</title></head></html>"
        self.send_response(code)
        self.send_header("Server", "AkamaiGHost")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def check(ok: bool, what: str) -> None:
    print(("ok    " if ok else "FAIL  ") + what, flush=True)
    if not ok:
        sys.exit(1)


def main() -> None:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Site)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    site = f"http://127.0.0.1:{server.server_address[1]}"
    start = f"{site}/v23/docs/"
    plan = {"kind": "website", "root": start, "start": start, "prefix": start}
    entries, meta = cli.build_known("db", "db", plan, 8, None)
    pages = {e.location: e for e in entries if e.kind == "page"}
    asked = [path for _, path in LOG]

    check(meta["root"] == f"{site}/v26/docs/", "moved docs are read where they went")
    check(f"{site}/v26/docs/a.html" in pages, "a book's contents found through <link rel=contents>")
    check(f"{site}/v26/docs/b.html" in pages and not cli.DEAD_HOSTS, "429 from Akamai: slowed down, retried, read")
    check("/v26/docs/print.html" not in asked and not any("/_print/" in p for p in asked)
          and f"{site}/v26/docs/api/print.html" in pages, "print copies are not read; a page named print.html is")
    check(sum(e.title == "Gamma" for e in pages.values()) == 1, "one page by three addresses: one entry")
    alpha = pages[f"{site}/v26/docs/a.html"].text
    check("queries that read them" in alpha and "Thanks for letting" not in alpha,
          "the page's text, not a small box called content")
    check("authorization" not in alpha and "Tab two text" in alpha, "hidden text dropped, hidden tabs kept")
    check(meta["failures"].keys() == {"not-found"} and cli.missed_pages(meta) == 0,
          "links to missing pages: not a reason to call the download incomplete")
    times = [t for t, path in LOG if path != "/robots.txt"]
    check(min(b - a for a, b in zip(times, times[1:])) >= 0.9, "robots.txt Crawl-delay kept")

    whole = sorted((e.title, e.location) for e in entries)
    SITE["/robots.txt"] = (200, b"User-agent: *\n")    # (no more waiting between pages: faster)
    cli.PACE.clear()
    _, meta = cli.build_known("db2", "db2", plan, 8, 2, resumable=True)        # 2 pages this time
    check(meta.get("partial", {}).get("pages") == 2 and importers.unfinished("db2") is not None,
          "stopped after 2 pages: kept, marked partial, with what is left")
    BUSY["/v26/docs/b.html"] = 1
    later, meta = cli.build_known("db2", "db2", plan, 8, None, resumable=True)
    check(not meta.get("partial") and importers.unfinished("db2") is None
          and sorted((e.title, e.location) for e in later) == whole, "continued: the same pages as in one go")

    BUSY["/v26/docs/b.html"] = 0
    def ctrl_c() -> None:                        # once the download is under way: two pages read
        while signal.getsignal(signal.SIGINT) is signal.default_int_handler or \
                sum(path.startswith("/v26/docs/") for _, path in LOG[logged:]) < 2:
            time.sleep(0.05)
        signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
    logged = len(LOG)
    threading.Thread(target=ctrl_c, daemon=True).start()
    _, meta = cli.build_known("db3", "db3", plan, 8, None, resumable=True)
    check(bool(meta.get("partial")) and signal.getsignal(signal.SIGINT) is signal.default_int_handler,
          "ctrl+c: stops after the pages under way, keeps them")
    later, meta = cli.build_known("db3", "db3", plan, 8, None, resumable=True)
    check(not meta.get("partial") and sorted((e.title, e.location) for e in later) == whole,
          "continued after ctrl+c: the same pages as in one go")

    import urllib.robotparser
    SITE["/sm.xml"] = (200, f"<sitemapindex><sitemap><loc>{site}/sm2.xml</loc></sitemap></sitemapindex>".encode())
    SITE["/sm2.xml"] = (200, "<urlset>".encode() + "".join(
        f"<url><loc>{site}/v26/docs/{p}</loc></url>" for p in ("a.html", "b.html", "c/", "x.html")).encode()
        + f"<url><loc>{site}/elsewhere.html</loc></url></urlset>".encode())
    rp = urllib.robotparser.RobotFileParser()
    rp.parse([f"Sitemap: {site}/sm.xml"])
    count = importers.count_pages(rp, f"{site}/v26/docs/", lambda u: u.startswith(f"{site}/v26/docs/"))
    check(count == 4, "the number of pages under the address, from the sitemap")

    cli.RETRY_WAITS = (0.05, 0.05, 0.05)          # (the test only: no long pauses between tries)
    said = io.StringIO()
    count_site = f"{site}/count/"
    with contextlib.redirect_stderr(said):
        _, meta = cli.build_known("db4", "db4", {"kind": "website", "root": count_site, "start": count_site,
                                                 "prefix": [count_site, f"{site}/flaky/"]}, 8, None, resumable=True)
    check("3 pages (1 failed)" in said.getvalue(), "pages are counted once (an app page is read, and failed)")
    check(cli.missed_pages(meta) == 0, "an app page is not a page another try may get")

    down = f"{site}/down/"
    DROP.update(f"/down/p{n}.html" for n in range(12))
    _, meta = cli.build_known("db5", "db5", {"kind": "website", "root": down, "start": down, "prefix": down},
                              8, None, resumable=True)
    check(meta.get("partial", {}).get("again") == 12 and not meta.get("failures") and importers.unfinished("db5"),
          "a site that stops answering: the download stops, kept, the pages to try again")
    DROP.clear()
    later, meta = cli.build_known("db5", "db5", {"kind": "website", "root": down, "start": down, "prefix": down},
                                  8, None, resumable=True)
    check(not meta.get("partial") and not meta.get("failures") and sum(e.kind == "page" for e in later) == 13
          and importers.unfinished("db5") is None, "continued when it answers again: every page")

    flaky = f"{site}/flaky/"
    DROP.add("/flaky/p3.html")
    LOG.clear()
    found, meta = cli.build_known("db6", "db6", {"kind": "website", "root": flaky, "start": flaky, "prefix": flaky},
                                  8, None, resumable=True)
    tries = sum(path == "/flaky/p3.html" for _, path in LOG)
    check(not meta.get("partial") and meta["failures"].keys() == {"dropped"} and sum(e.kind == "page" for e in found) == 6
          and tries == importers.TRIES * (len(cli.RETRY_WAITS) + 1),
          f"a page that keeps failing is given up after {importers.TRIES} tries ({tries} requests); the rest is read")
    DROP.clear()

    cli.set_crawl_delay("slow.example", 30.0)
    cli.paced("slow.example", True)
    check(cli.PACE["slow.example"]["gap"] >= 30.0, "a 429 never makes the wait shorter than robots.txt asks")

    SITE["/sm.xml"] = (200, ("<sitemapindex>" + "".join(f"<sitemap><loc>{site}/sm2.xml?{n}</loc></sitemap>"
                                                            for n in range(20)) + "</sitemapindex>").encode())
    cli.set_crawl_delay(site.split("//")[1], 2.0)
    t0 = time.monotonic()
    importers.count_pages(rp, f"{site}/v26/docs/", lambda u: True, seconds=3)
    took = time.monotonic() - t0
    check(took < 3 + 2.5, f"counting keeps its time budget on a site that asks for pauses ({took:.1f} s of 3)")
    cli.PACE.clear()

    slow = f"{site}/slow/"
    sent: dict = {}

    def ctrl_c_later() -> None:                 # the real signal, from another thread: it does not
        while signal.getsignal(signal.SIGINT) is signal.default_int_handler or \
                not any(path == "/slow/late.html" for _, path in LOG):        # wake a waiting thread
            time.sleep(0.05)
        time.sleep(0.5)                          # the download now waits for the late page
        sent["at"] = time.monotonic()
        signal.raise_signal(signal.SIGINT)
    LOG.clear()
    threading.Thread(target=ctrl_c_later, daemon=True).start()
    _, meta = cli.build_known("db7", "db7", {"kind": "website", "root": slow, "start": slow, "prefix": slow},
                              8, None, resumable=True)
    took = time.monotonic() - sent["at"]
    check(bool(meta.get("partial")) and took < 2.0,
          f"ctrl+c while a slow page is awaited: stopped {took:.1f} s later, not when the page came")
    server.shutdown()
    print("all good")


if __name__ == "__main__":
    main()
