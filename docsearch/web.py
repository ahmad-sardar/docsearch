"""docsearch in the browser: a small server on this computer, shown in Safari (on a Mac)
or the default browser.

    search pandas mean      (in the terminal)  →  the browser shows the results and the docs

The server is a process on this computer, listening on 127.0.0.1 only (that address never
leaves the machine; nothing else can reach it). The browser is only the renderer. The server
keeps the search index in memory, so every search after the first is instant, and serves
the stored copies of the docs pages and their images (see pages.py).

100% offline: the server process blocks every connection that is not to this
computer (cli.offline_only), and the pages contain no links that could go online.

Safety: the docs HTML is allowlist-filtered when it is stored; every response also sends
a strict Content-Security-Policy (only this server's own script and styles may run or
load), and requests whose Host is not 127.0.0.1/localhost are refused, which blocks
DNS-rebinding tricks from web pages.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from bs4 import BeautifulSoup
from markdown_it import MarkdownIt

from docsearch import cli
from docsearch import pages as offline

STATIC = Path(__file__).parent / "static"
STATIC_TYPES = {"index.html": "text/html; charset=utf-8", "app.css": "text/css; charset=utf-8",
                "app.js": "text/javascript; charset=utf-8", "icon.svg": "image/svg+xml", "icon.png": "image/png"}
STATE = cli.DATA / "server.json"            # {"pid": ..., "port": ...} of the running server
LOG = cli.DATA / "server.log"
PORT = int(os.environ.get("DOCSEARCH_PORT", "8765"))
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
       "font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; "
       "frame-ancestors 'none'")
# Images (an SVG can carry script): no script at all, and sandboxed if opened on its own.
ASSET_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; sandbox"
MD = MarkdownIt("commonmark", {"html": False}).enable("table")   # raw HTML in Markdown is escaped


def pygments_css() -> str:
    """Colours for the code blocks Sphinx already marked up: light and dark."""
    from pygments.formatters import HtmlFormatter
    light = HtmlFormatter(style="default").get_style_defs(".highlight")
    dark = HtmlFormatter(style="github-dark").get_style_defs(".highlight")
    return f"{light}\n@media (prefers-color-scheme: dark) {{\n{dark}\n}}\n"


# --------------------------------------------------------------------------- the library

class Library:
    """Everything that is indexed, searchable, with its offline pages."""

    def __init__(self) -> None:
        sids = sorted(d.name for d in cli.HOME.iterdir() if (d / "meta.json").exists()) \
            if cli.HOME.exists() else []
        if not sids:
            raise SystemExit("search: nothing is indexed yet. Run: search sync")
        vectors = any((cli.HOME / s / "emb.npy").exists() for s in sids) and cli.model_cached()   # (a source
        # without vectors, embed = false or not made yet, is left out of search by meaning only)
        self.index = cli.Index(sids, "hybrid" if vectors else "spell")
        self.lock = threading.Lock()                 # one search at a time (the model)
        self.meta = {s: json.loads((cli.HOME / s / "meta.json").read_text(encoding="utf-8"))
                     for s in sids}
        self.sites = {s: (m["root"], cli.HOME / s / "pages") for s, m in self.meta.items()
                      if str(m.get("root", "")).startswith("http")}
        self.sid_of = [cli.source_id(e.source) for e in self.index.entries]
        # one version per package unless asked: the latest (numpy), else a pinned one (numpy@1.26)
        groups: dict[str, list[str]] = {}
        for s in self.meta:
            groups.setdefault(s.split("@")[0], []).append(s)
        self.default = {min(v, key=lambda s: ("@" in s, s)) for v in groups.values()}
        self.summaries: dict[int, str] = {}
        self.image_types: dict[str, dict[str, str]] = {}
        self._browse_pos: dict[int, int] = {}
        self.pygments = pygments_css()
        self.index.search("warm up")                 # load caches before the first request

    def info(self) -> dict:
        counts: dict[str, int] = {}
        for s in self.sid_of:
            counts[s] = counts.get(s, 0) + 1
        return {"app": "docsearch", "mode": self.index.mode,
                "sources": [{"id": s, "name": m.get("name", s), "version": self.label(s),
                             "dated": not m.get("version"),
                             "count": counts.get(s, 0), "offline": bool(m.get("pages")),
                             "about": m.get("about") or m.get("project") or "", "root": m.get("root", ""),
                             "group": s.split("@")[0], "default": s in self.default,
                             "kind": m.get("kind", ""), "added": m.get("created", "")}
                            for s, m in self.meta.items()]}

    def label(self, sid: str) -> str:
        """The docs version to show next to the name; for docs that publish no version
        number (cppreference, MDN), the day they were downloaded."""
        m = self.meta[sid]
        return m.get("version") or str(m.get("created", ""))[:10]

    def item(self, i: int, q: str) -> dict:
        e = self.index.entries[i]
        is_api = e.kind not in cli.PAGE_KINDS
        if i not in self.summaries:
            self.summaries[i] = cli.summary(e) if is_api or not q else cli.snippet(e, q)
        return {"id": i, "name": cli.api_name(e.title) if is_api else e.title, "kind": e.kind,
                "source": self.sid_of[i], "api": is_api, "summary": self.summaries[i]}

    def search(self, q: str, srcs: set[str], offset: int, limit: int, ai: bool = False) -> dict:
        q = q.strip()
        srcs = srcs or self.default                  # never two versions of one package at once
        rest, phrases, patterns = cli.parse_strict(q)
        plain_q = " ".join([rest] + phrases).strip()     # what ranks the results (and the AI reads)
        if not q:                                    # no query: all the docs, in reading order
            ids = [i for i in self.index.browse if not srcs or self.sid_of[i] in srcs]
        elif phrases or patterns:                    # strict: every match, the best first
            with self.lock:
                try:
                    found = self.index.strict(phrases, patterns, self.full_text)
                except ValueError as e:
                    return {"q": q, "total": 0, "ai": None, "items": [], "error": str(e)}
                hits = self.index.search(plain_q, limit=3000) if plain_q else []
            allowed = {i for i in found if (not srcs or self.sid_of[i] in srcs) and not self.index.duplicate(i)}
            ranked = [i for i, _, _ in hits if i in allowed]
            if not self._browse_pos:
                self._browse_pos = {i: k for k, i in enumerate(self.index.browse)}
            seen = set(ranked)
            ids = ranked + sorted((i for i in allowed if i not in seen),
                                  key=lambda i: self._browse_pos.get(i, len(self._browse_pos)))
        else:
            with self.lock:
                hits = self.index.search(q, limit=3000 if srcs else cli.SHOW)
            ids = [i for i, _, _ in hits if not srcs or self.sid_of[i] in srcs][:cli.SHOW]
        state = None
        if ai and plain_q:                           # the model reorders the top results
            from docsearch import rerank
            model = rerank.get()
            if model is None:
                state = "not installed"
            else:
                s = model.scores(plain_q, [self.rerank_text(i) for i in ids[:rerank.TOP]])
                with self.lock:
                    exact = set(self.index.rank_name(plain_q)[0])
                ids = rerank.reorder(ids, s, exact)
                state = "ranked"
        with self.lock:
            fixed = self.index.correction(plain_q) if plain_q else None
        return {"q": q, "total": len(ids), "ai": state, "corrected": fixed,
                "items": [self.item(i, q) for i in ids[offset:offset + limit]]}

    def rerank_text(self, i: int) -> str:
        e = self.index.entries[i]
        return f"{cli.api_name(e.title)} ({e.kind}, {e.source})\n{cli.plain(e.text)[:1200]}"

    def entry(self, i: int) -> dict:
        e = self.index.entries[i]
        sid = self.sid_of[i]
        is_api = e.kind not in cli.PAGE_KINDS
        name = cli.api_name(e.title) if is_api else e.title
        html_text, page = None, None
        site = self.sites.get(sid)
        if site and e.location.startswith(site[0]):
            rel, _, anchor = e.location[len(site[0]):].partition("#")
            rel = rel or "index.html"
            stored = offline.load_page(site[1], rel)
            if stored is not None:
                html_text = fragment(stored, anchor, e.kind)
                page = {"path": f"{sid}/{rel}", "at": anchor}
        if html_text is None:                        # no offline page: draw the indexed text
            base = e.location if cli.safe_url(e.location) else "https://invalid.invalid/"
            html_text = offline.sanitize(MD.render(self.full_text(i)), base)
        return {"id": i, "name": name, "kind": e.kind, "source": sid, "api": is_api,
                "version": self.label(sid),
                "html": offline.localize_links(html_text, self.sites), "page": page,
                "web": e.location if cli.safe_url(e.location) else None,
                "import": import_line(name, e.kind) if is_api else None}

    def asset(self, sid: str, name: str) -> tuple[bytes, str] | None:
        """A stored image of a docs page, and its type."""
        site = self.sites.get(sid)
        if site is None or not re.fullmatch(r"[0-9a-f]{40}", name):
            return None
        folder = site[1] / "_images"
        if sid not in self.image_types:
            try:
                self.image_types[sid] = json.loads((folder / "images.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.image_types[sid] = {}
        ctype = self.image_types[sid].get(name)
        f = folder / name
        return (f.read_bytes(), ctype) if ctype and f.is_file() else None

    def full_text(self, i: int) -> str:
        """An entry's whole text (memory keeps only its start; see cli.KEEP_CHARS)."""
        return self.index.full_text(i)

    def page(self, path: str) -> dict | None:
        sid, _, rel = path.partition("/")
        site = self.sites.get(sid)
        if site is None:
            return None
        stored = offline.load_page(site[1], rel)
        if stored is None:
            return None
        title = BeautifulSoup(stored, "lxml").find("h1")
        return {"path": path, "source": sid, "version": self.label(sid),
                "title": title.get_text(" ", strip=True) if title else rel,
                "html": offline.localize_links(stored, self.sites), "web": site[0] + rel}


HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")


def fragment(page_html: str, anchor: str, kind: str) -> str:
    """The part of a stored page that documents one entry (a class, a function, a section)."""
    if not anchor or kind == "doc":
        return page_html
    soup = BeautifulSoup(page_html, "lxml")
    el = soup.find(id=anchor)
    if el is None:
        return page_html
    if el.name == "dt":
        dl = el.find_parent("dl")
        if dl is None:
            return str(el)
        if len(dl.find_all("dd", recursive=False)) <= 1:   # an API object (Sphinx): its whole <dl>
            return str(dl)
        group = [el]                                      # one item of a list (git: an option):
        for sib in el.find_next_siblings():               # its terms and their description
            group.append(sib)
            if sib.name == "dd":
                break
        return "<dl>" + "".join(str(x) for x in group) + "</dl>"
    pre = el.find_parent("pre") if el.name in ("span", "a", "code") else None
    if pre is not None:                                   # a signature (OCaml: <pre><span id=VALx>val x
        nxt = pre.find_next_sibling()                     # ...</pre><div class="info">): it and its text
        return str(pre) + (str(nxt) if nxt is not None and nxt.name in ("div", "p", "dl") else "")
    if el.name not in HEADINGS and el.find_parent(HEADINGS) is not None:
        el = el.find_parent(HEADINGS)                     # MediaWiki: <h3><span id=...>Title</span>
    if el.name in ("span", "a") and not el.get_text(strip=True):
        heading = None
        if heading is None:
            nxt = el.find_next(["section", "div", "dl", "p"] + list(HEADINGS))
            if nxt is None:
                return page_html
            if nxt.name not in HEADINGS:
                return str(nxt)
            heading = nxt
        el = heading
    if el.name in HEADINGS:                               # a heading: it and the text under it
        parent, level = el.parent, int(el.name[1])
        if parent is not None and parent.name in ("section", "div") and parent.find(HEADINGS) is el:
            body = [str(parent)]                          # the section the heading starts, and
            if len(parent.get_text(strip=True)) <= len(el.get_text(strip=True)) + 20:
                for sib in parent.next_siblings:          # if it is only the heading (MDN), the
                    name = getattr(sib, "name", None)                  # subsections after it
                    first = sib if name in HEADINGS else sib.find(HEADINGS) if name else None
                    if first is not None and int(first.name[1]) <= level:
                        break
                    body.append(str(sib))
            return "".join(body)
        body = [str(el)]
        for sib in el.next_siblings:
            if getattr(sib, "name", None) in HEADINGS and int(sib.name[1]) <= level:
                break
            body.append(str(sib))
        return "".join(body)
    return str(el)


def import_line(name: str, kind: str) -> str | None:
    parts = name.split(".")
    if len(parts) < 2:
        return f"import {name}" if kind == "module" else None
    if kind == "module":
        return f"import {name}"
    if kind in ("method", "attribute", "property", "classmethod", "staticmethod") and len(parts) > 2:
        parts = parts[:-1]                           # import the class, not the method
    return f"from {'.'.join(parts[:-1])} import {parts[-1]}"


# --------------------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    server_version = "docsearch"
    sys_version = ""
    library: Library
    hosts: set[str]

    def log_message(self, fmt: str, *args) -> None:  # quiet; errors go to the log below
        pass

    def send(self, code: int, body: bytes, ctype: str, csp: str = CSP, cache: str = "no-store") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Security-Policy", csp)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Cache-Control", cache)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def json(self, data, code: int = 200) -> None:
        self.send(code, json.dumps(data).encode(), "application/json; charset=utf-8")

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        if self.headers.get("Host", "") not in self.hosts:
            return self.send(403, b"forbidden", "text/plain")
        url = urllib.parse.urlsplit(self.path)
        qs = {k: v[-1] for k, v in urllib.parse.parse_qs(url.query).items()}
        lib = self.library
        try:
            if url.path == "/":
                return self.send(200, (STATIC / "index.html").read_bytes(), STATIC_TYPES["index.html"])
            if url.path == "/static/pygments.css":
                return self.send(200, lib.pygments.encode(), "text/css; charset=utf-8")
            if url.path.startswith("/static/"):
                name = url.path[len("/static/"):]
                if name not in STATIC_TYPES:
                    return self.send(404, b"not found", "text/plain")
                return self.send(200, (STATIC / name).read_bytes(), STATIC_TYPES[name])
            m = re.fullmatch(r"/asset/([\w.@\-]{1,100})/([0-9a-f]{40})", url.path)
            if m:
                found = lib.asset(m.group(1), m.group(2))
                if found is None:
                    return self.send(404, b"not found", "text/plain")
                return self.send(200, found[0], found[1], ASSET_CSP, "max-age=86400")
            if url.path in ("/favicon.ico", "/apple-touch-icon.png"):     # asked for without the page
                return self.send(200, (STATIC / "icon.png").read_bytes(), "image/png")
            if url.path == "/api/info":
                return self.json(lib.info())
            if url.path == "/api/search":
                srcs = {s for s in qs.get("src", "").split(",") if s}
                offset = max(0, int(qs.get("offset", "0") or 0))
                limit = min(200, max(1, int(qs.get("limit", "60") or 60)))
                return self.json(lib.search(qs.get("q", "")[:300], srcs, offset, limit, qs.get("ai") == "1"))
            m = re.fullmatch(r"/api/entry/(\d+)", url.path)
            if m:
                i = int(m.group(1))
                if not 0 <= i < len(lib.index.entries):
                    return self.json({"error": "no such entry"}, 404)
                return self.json(lib.entry(i))
            if url.path == "/api/page":
                data = lib.page(qs.get("path", ""))
                return self.json(data) if data else self.json({"error": "page not stored"}, 404)
            return self.send(404, b"not found", "text/plain")
        except Exception as ex:  # noqa: BLE001 - keep serving; the log has the details
            print(f"{time.strftime('%H:%M:%S')} error on {self.path}: {ex!r}", file=sys.stderr, flush=True)
            return self.json({"error": "internal error"}, 500)

    def do_POST(self) -> None:
        """The one thing the page can change: remove a source (wrong docs were matched).
        Only from the docsearch page itself: the Origin must be this server, and the
        request must carry a custom header, which other sites cannot send without asking
        this server first (CORS preflight), and it never says yes."""
        host = self.headers.get("Host", "")
        if (host not in self.hosts or self.headers.get("Origin") != f"http://{host}"
                or self.headers.get("X-Docsearch") != "1"):
            return self.send(403, b"forbidden", "text/plain")
        if self.path != "/api/remove":
            return self.send(404, b"not found", "text/plain")
        try:
            size = int(self.headers.get("Content-Length", "0"))
            sid = json.loads(self.rfile.read(min(size, 1000)) or b"{}").get("source", "")
        except (ValueError, AttributeError):
            return self.json({"error": "bad request"}, 400)
        lib = self.library
        if sid not in lib.meta:
            return self.json({"error": "no such source"}, 404)
        cli.forget(sid)
        reload_library()
        return self.json({"ok": True, "removed": sid})


def reload_library() -> None:
    """Load the index again in the background (after a source was removed); the old one
    answers until the new one is ready."""
    def run() -> None:
        try:
            Handler.library = Library()
        except SystemExit:                           # nothing indexed any more
            pass
    threading.Thread(target=run, daemon=True).start()


def serve(port: int = PORT) -> None:
    """Run the server in this process until it is stopped. It cannot reach the internet."""
    cli.offline_only()
    library = Library()

    def warm_up() -> None:                           # the first "search ai" is then quick
        from docsearch import rerank
        model = rerank.get()
        if model is not None:
            model.scores("warm up", ["warm up"])
    threading.Thread(target=warm_up, daemon=True).start()
    for p in (port, 0):                              # the usual port, else any free one
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", p), Handler)
            break
        except OSError:
            continue
    real = httpd.server_address[1]
    Handler.library = library
    Handler.hosts = {f"127.0.0.1:{real}", f"localhost:{real}"}
    STATE.write_text(json.dumps({"pid": os.getpid(), "port": real}), encoding="utf-8")
    print(f"docsearch: serving on http://127.0.0.1:{real}", flush=True)
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=httpd.shutdown).start())
    try:
        httpd.serve_forever()
    finally:
        try:
            if json.loads(STATE.read_text(encoding="utf-8")).get("pid") == os.getpid():
                STATE.unlink()
        except (OSError, ValueError):
            pass


# --------------------------------------------------------------------------- control

def running() -> int | None:
    """The port of our running server, if there is one."""
    try:
        port = int(json.loads(STATE.read_text(encoding="utf-8"))["port"])
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/info", timeout=1) as r:
            return port if json.loads(r.read()).get("app") == "docsearch" else None
    except (OSError, ValueError, KeyError):
        return None


def start() -> int:
    """Make sure the server runs (start it in the background if needed); return its port."""
    port = running()
    if port:
        return port
    cli.say("Starting docsearch (loading the index, a few seconds the first time)...")
    STATE.unlink(missing_ok=True)
    if os.name == "nt":                              # no console window, and it outlives this one
        detach = {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
    else:
        detach = {"start_new_session": True}
    with open(LOG, "ab") as log:
        subprocess.Popen([sys.executable, "-m", "docsearch.web", "serve"], stdout=log, stderr=log,
                         stdin=subprocess.DEVNULL, cwd=str(cli.ROOT), **detach)
    deadline = time.time() + 180
    while time.time() < deadline:
        time.sleep(0.25)
        port = running()
        if port:
            return port
    cli.die(f"the server did not start. See {LOG}")
    return 0


def stop() -> bool:
    try:
        pid = int(json.loads(STATE.read_text(encoding="utf-8"))["pid"])
    except (OSError, ValueError, KeyError):
        return False
    if running() is None:
        STATE.unlink(missing_ok=True)
        return False
    try:
        os.kill(pid, signal.SIGTERM)                 # (on Windows: ends the process)
    except OSError:
        return False
    for _ in range(40):
        if running() is None:
            return True
        time.sleep(0.1)
    return True


def wsl() -> bool:
    """Linux inside Windows (WSL): no browser of its own; Windows' browser can reach this
    server, since WSL passes 127.0.0.1 through to Windows."""
    import platform
    return sys.platform == "linux" and "microsoft" in platform.uname().release.lower()


def open_browser(params: dict[str, str]) -> None:
    """Open (or reuse) the docsearch page: in Safari on a Mac, Windows' default browser
    from WSL, else the default browser. If none opens, the address is printed."""
    port = start()
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v})   # no quotes left in it
    url = f"http://127.0.0.1:{port}/" + (f"?{query}" if query else "")
    if sys.platform == "darwin" and Path("/Applications/Safari.app").exists():
        subprocess.run(["open", "-a", "Safari", url], check=False)
        return
    if wsl():
        import shutil
        opener = shutil.which("wslview")
        cmd = [opener, url] if opener else ["powershell.exe", "-NoProfile", "-Command", f"Start-Process '{url}'"]
        try:
            if subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                return
        except OSError:
            pass
    else:
        import webbrowser
        if webbrowser.open(url):
            return
    cli.say(f"Open this in your browser: {url}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="docsearch.web")
    ap.add_argument("cmd", choices=["serve"])
    ap.add_argument("--port", type=int, default=PORT)
    serve(ap.parse_args().port)
