"""End-to-end check on a fresh machine (the Windows CI runs this): index a small folder of
docs, search it through the server (by name, typo, meaning and with AI), read a stored
page, then remove the docs while the server still runs. One page is nested thousands of
tags deep, as some sites are.

    uv run python tests/smoke.py

Then a small local website whose download stops half way and continues; whose vectors
stop and are made by the same command alone; and whose new copy (search upgrade) stops,
keeping the copy you have, and goes on the next time. Then docs with versions: each version
pulled is a copy of its own, the one search uses chosen once; and a project's versions.

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


# Queries with symbols, as docsearch gets them in single quotes (the shell would refuse or
# change most of them otherwise): every one is the query's, never taken for a docs name
SYMBOLS = ["Path()", "np.sum()", "f(x, y)", "arr[0]", "dict[str, int]", "pd.DataFrame.loc[]", "Vec<T>",
           "HashMap<String, Vec<u8>>", "std::map<K,V>", "#include <vector>", "vec!", "!=", "&str", "a && b",
           "*args", "**kwargs", "x?", "?.", "??", "std::array::operator[]", "operator<<", "operator()", "~vector",
           "(+)", "( + )", "(|>)", "@property", "#define", "...", "=>", "->", "<=>", "a|b", "a;b", "$PATH",
           "`ls`", "$(ls)", "it's", '"quote', "{a,b}", "^x", "%d", "100%", "--amend", "lambda x: x+1", "a > b",
           "[x for x in y]", "re.sub(r'\\d+')", "C:\\path", '"drop_duplicates"', '"unclosed', '"', "/", "//",
           "/[/", "/(/", "/^frames\\./", '"" ""', "\\", "%", "+", "&", "#", "?", "=", " ", "\u2028", "é",
           "中文", "😀", "a" * 500, "print()", "Option<T>", "println!", "a*b", "std::vector::push_back",
           "operator+=", "@dataclass", "${x}", "git commit --amend", "a < b", "foo@bar", "x = 1", "Path", "np.sum",
           "/a/ /b/", "%%", "++", "\t"]
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


VERSION = {"now": "1.0"}                         # what the versioned site says it is


class Versioned(http.server.BaseHTTPRequestHandler):
    """Docs with versions, as a known site: /v/ (the release, its number at /v/VERSION) and
    /n/ (its nightly)."""

    def log_message(self, *args) -> None:
        pass

    def do_GET(self) -> None:
        ASKED.append(self.path)
        m = re.fullmatch(r"/(v|n)/(\w*)", self.path)
        if self.path in ("/v/VERSION", "/n/VERSION"):
            body = f"testdocs {VERSION['now'] if self.path[1] == 'v' else 'Nightly'}".encode()
        elif m:
            which = "release " + VERSION["now"] if m.group(1) == "v" else "nightly"
            page = m.group(2) or "index"
            body = (f"<html><head><title>Testdocs {page}</title></head><body><main><h1>Testdocs {page}</h1>"
                    f"<p>{f'The {page} page of the {which} docs. ' * 8}</p>"
                    f"{'<a href=a>a</a> <a href=b>b</a>' if page == 'index' else ''}</main></body></html>").encode()
        else:
            body = b"not found"
        self.send_response(200 if m or self.path.endswith("VERSION") else 404)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def versions() -> None:
    """Each version pulled is a copy of its own; one you have is not pulled again; search uses
    the one you chose (or your project's); a package with several copies is removed one copy at
    a time (or with --all)."""
    import contextlib
    import io

    from docsearch import sources
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Versioned)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    site = f"http://127.0.0.1:{server.server_address[1]}"
    sources.KNOWN["testdocs"] = {
        "about": "Test docs with versions", "kind": "website", "root": f"{site}/",
        "start": f"{site}/v/", "prefix": f"{site}/v/", "exclude": "VERSION",
        "version_from": [f"{site}/v/VERSION", r"testdocs (\d+\.\d+)"],
        "channels": {"nightly": {"start": f"{site}/n/", "prefix": f"{site}/n/",
                                 "version_from": [f"{site}/n/VERSION", r"testdocs (\w+)"]}}}

    def run(*argv: str) -> str:
        said = io.StringIO()
        with contextlib.redirect_stderr(said), contextlib.redirect_stdout(said):
            cli.main(list(argv))
        return said.getvalue()

    def pages_read() -> int:
        return sum(1 for path in ASKED if re.fullmatch(r"/[vn]/\w*", path) and not path.endswith("VERSION"))
    try:
        run("add", "testdocs", "--no-embed")
        check(cli.copies("testdocs") == ["testdocs@1.0"], "a pull is kept under its version: testdocs@1.0")
        ASKED.clear()
        said = run("add", "testdocs", "--no-embed")
        check("you have this version already" in said and pages_read() == 0,
              "the version you have is not downloaded again")
        VERSION["now"] = "1.1"
        said = run("upgrade", "testdocs")
        check(cli.copies("testdocs") == ["testdocs@1.1", "testdocs@1.0"] and "next search asks" in said,
              "search upgrade: the new version next to the old one; the next search asks which one to use")
        ASKED.clear()
        said = run("upgrade", "testdocs")
        check("you have this version already" in said and pages_read() == 0, "and again: nothing to download")
        check(cli.in_use("testdocs")[0] is None and cli.ask_copy("testdocs", cli.copies("testdocs")) == "testdocs@1.1",
              "several copies, none chosen: asked (without a terminal: the newest)")
        cli.choose("testdocs@1.0")
        listed = run("list")
        check(cli.in_use("testdocs")[0] == "testdocs@1.0" and cli.config_use().get("testdocs") == "1.0"
              and re.search(r"testdocs@1\.0 .*<- search uses this", listed) is not None,
              "the copy you chose is kept (packages.toml [use]), and search list shows it")
        uses, note = cli.in_use("testdocs", {"testdocs": "1.1.3"}), cli.in_use("testdocs", {"testdocs": "2.0"})[1]
        check(uses[0] == "testdocs@1.1" and "your project uses 2.0" in note,
              "in a project: the version it uses (1.1 for 1.1.3); one you do not have is said so")
        check(cli.split_sources(["testdocs", "x"]) == (["testdocs"], "x")
              and cli.search_copies(["testdocs"], {}) == (["testdocs@1.0"], ["testdocs@1.0"])
              and cli.search_copies(["testdocs@1.1"], {})[0] == ["testdocs@1.1"]
              and cli.search_copies([], {"testdocs": "1.1"})[1] == ["testdocs@1.1"],
              "a search names a package (its copy in use) or a copy; a project's version wins")

        lib = web.Library()
        first = "testdocs@1.0" in lib.loaded and "testdocs@1.1" not in lib.loaded
        hits = lib.search("", {"testdocs@1.1"}, 0, 50)["items"]
        check(first and "testdocs@1.1" in lib.loaded and hits and {h["source"] for h in hits} == {"testdocs@1.1"},
              "the search page loads the copy in use, and another one when a search asks for it")
        port = web.start()
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/use", data=b'{"source": "testdocs@1.1"}',
                                     headers={"Content-Type": "application/json", "X-Docsearch": "1",
                                              "Origin": f"http://127.0.0.1:{port}"}, method="POST")
        with urllib.request.urlopen(req, timeout=60) as r:
            chosen_in_page = json.loads(r.read()).get("use")
        web.stop()
        check(chosen_in_page == "testdocs@1.1" and cli.in_use("testdocs")[0] == "testdocs@1.1",
              "chosen in the page: kept as your choice")

        run("add", "testdocs==nightly", "--no-embed")
        nightly = f"testdocs@nightly-{time.strftime('%Y-%m-%d')}"
        ASKED.clear()
        said = run("add", "testdocs==nightly", "--no-embed")
        check(nightly in cli.copies("testdocs") and "you have this version already" in said and pages_read() == 0
              and cli.match_version(cli.copies("testdocs"), "nightly") is None,
              "a nightly is a copy of its day; the same day's again is not downloaded; never chosen for you")

        os.replace(cli.HOME / "testdocs@1.1", cli.HOME / "testdocs")       # as before copies had versions
        cli.migrate_copies()
        check((cli.HOME / "testdocs@1.1").exists() and not (cli.HOME / "testdocs").exists(),
              "docs from before: renamed once to their version")

        said = run("remove", "testdocs")
        check(len(cli.copies("testdocs")) == 3 and "--all" in said, "search remove NAME with several copies: listed, none removed")
        run("remove", "testdocs@1.0")
        check(cli.copies("testdocs") == ["testdocs@1.1", nightly] and cli.config_use().get("testdocs") == "1.1",
              "search remove NAME@VERSION: that copy only")
        run("remove", "testdocs", "--all")
        toml = cli.CONFIG.read_text(encoding="utf-8")
        check(not cli.copies("testdocs") and "testdocs" not in toml, "--all: every copy, and its lines in packages.toml")
    finally:
        del sources.KNOWN["testdocs"]
        server.shutdown()


def project_files() -> None:
    """The versions a project uses, read from its files (in the folder search runs in, or above)."""
    root = Path(tempfile.mkdtemp(prefix="docsearch-project-"))
    (root / ".git").mkdir()
    (root / "uv.lock").write_text('version = 1\n[[package]]\nname = "numpy"\nversion = "2.4.1"\n', encoding="utf-8")
    (root / "requirements.txt").write_text("pandas[excel]==2.2.3\nrequests>=2\n", encoding="utf-8")
    (root / ".python-version").write_text("3.12\n", encoding="utf-8")
    (root / ".venv" / "lib" / "python3.12" / "site-packages" / "scikit_learn-1.5.0.dist-info").mkdir(parents=True)
    (root / "go.mod").write_text("module x\n\ngo 1.22\n", encoding="utf-8")
    (root / "rust-toolchain.toml").write_text('[toolchain]\nchannel = "1.80.0"\n', encoding="utf-8")
    (root / "src" / "deep").mkdir(parents=True)
    found = cli.project_versions(root / "src" / "deep")
    want = {"numpy": "2.4.1", "pandas": "2.2.3", "python": "3.12", "scikit-learn": "1.5.0", "go": "1.22", "rust": "1.80.0"}
    check(all(found.get(k) == v for k, v in want.items()) and "requests" not in found,
          f"a project's versions, from its files ({ {k: found.get(k) for k in want} })")


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
        kept, answered = [], []
        for q in SYMBOLS:
            kept.append(cli.split_sources(["mini", *q.split()]) == (["mini"], " ".join(q.split())))
            answered.append(isinstance(get(port, "/api/search", q=q, src="mini").get("items"), list))
        check(all(kept) and all(answered), f"{len(SYMBOLS)} queries with symbols: each is the query, and answered "
              f"({[q for q, k, a in zip(SYMBOLS, kept, answered) if not (k and a)]} not)")
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
    versions()
    project_files()
    print("all good")


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        server_log()
        raise
