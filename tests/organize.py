"""Docs organized by purpose (docsearch/organize.py) on a small local Sphinx site: no models,
no internet, a few seconds.

    uv run python tests/organize.py

- every entry gets a purpose from the docs' own words: a page's title ("Mini quickstart":
  learn), else the page whose contents list it ("How to sort", under "Mini user guide": do),
  else its folder; API objects are look up
- loose names count only on a page that starts a part ("Mini reference manual"), not on a page
  inside one ("imp — Access the import internals"; "doctest — Test interactive Python
  examples"); "What's new or different" and "Development Tools" are not about the project
- release notes and contributing pages are never downloaded (the inventory's titles say what
  they are); a page under them is removed after the download; pages that document API objects
  are always kept
- parts listed apart from the entry that holds them are folded: a Sphinx section that repeats
  its page's title, a page that repeats its API object (mini.sum's page), cppreference's
  "Parameters", "See also" (each in its page's entry), an empty section; "Example" is kept
- the search page lists, before you type, each package's learn, do, look up and understand
  entries, each in reading order; results say their purpose; the home view has the contents
  by purpose (each part with the pages its contents list)
- search list NAME: how many entries of each purpose, what was left out, the source code
- docs from before: organized once, with nothing downloaded; their vectors keep the rows of the
  entries kept
"""
from __future__ import annotations

import contextlib
import http.server
import io
import json
import os
import sys
import tempfile
import threading
import zlib

os.environ["DOCSEARCH_ALLOW_HTTP"] = "1"          # the local site has no certificate
if "DOCSEARCH_DATA" not in os.environ:
    os.environ["DOCSEARCH_DATA"] = tempfile.mkdtemp(prefix="docsearch-organize-")

from docsearch import cli, organize, web  # noqa: E402

WORDS = "Words about arrays, sorting and the sums of their rows. " * 6


def page(title: str, body: str = "", toc: list[str] = ()) -> bytes:
    """A Sphinx page: its contents (toctree) list the pages under it."""
    links = "".join(f'<li><a href="/mini/{h}">{h}</a></li>' for h in toc)
    tree = f'<div class="toctree-wrapper"><ul>{links}</ul></div>' if toc else ""
    nav = ('<nav class="bd-sidebar"><a href="user/index.html">User guide</a> <a href="reference/index.html">'
           'Reference</a> <a href="dev/index.html">Contributing</a> <a href="whatsnew/index.html">Release notes</a></nav>')
    return (f"<html><head><title>{title}</title></head><body>{nav}<div role='main'><h1>{title}</h1>"
            f"<p>{WORDS}</p>{body}{tree}</div></body></html>").encode()


PAGES = {
    "index.html": ("Mini documentation", "", ["user/index.html", "reference/index.html", "dev/index.html",
                                              "whatsnew/index.html"]),
    "user/index.html": ("Mini user guide", "", ["user/quickstart.html", "user/howto.html", "user/basics.html",
                                                "user/devtools.html"]),
    "user/quickstart.html": ("Mini quickstart", "<section id='first-steps-here'><h2>Making arrays</h2>"
                             "<p>Make one.</p></section>", []),
    "user/howto.html": ("How to sort", "<section id='how-to-sort'><h2>How to sort</h2><p>Sort it.</p></section>"
                        "<section id='sorting-by-key'><h2>Sorting by key</h2><p>By a key.</p></section>", []),
    "user/basics.html": ("Mini fundamentals", "<section id='views'><h2>Views</h2><p>A view.</p></section>", []),
    "user/devtools.html": ("Development Tools", "", []),
    "reference/index.html": ("Mini reference", "", ["reference/mini.sum.html"]),
    "reference/mini.sum.html": ("mini.sum", "<dl class='py function'><dt id='mini.sum'>mini.sum(a)</dt>"
                                "<dd><p>Sums the rows.</p></dd></dl>", []),
    "dev/index.html": ("Contributing to Mini", "", ["dev/internals.html"]),
    "dev/internals.html": ("Internals", "", []),
    "whatsnew/index.html": ("Release notes", "", ["whatsnew/v1.0.html"]),
    "whatsnew/v1.0.html": ("Version 1.0 (January 1, 2026)", "", []),
}
INVENTORY = "".join(f"{p[:-5]} std:doc -1 {p} {t}\n" for p, (t, _, _) in PAGES.items())
INVENTORY += ("mini.sum py:function 1 reference/mini.sum.html#$ -\n"
              "how-to-sort std:label -1 user/howto.html#how-to-sort How to sort\n"
              "sorting-by-key std:label -1 user/howto.html#sorting-by-key Sorting by key\n"
              "first-steps std:label -1 user/quickstart.html#first-steps-here Making arrays\n"
              "views std:label -1 user/basics.html#views Views\n")
SITE = {f"/mini/{p}": page(t, b, toc) for p, (t, b, toc) in PAGES.items()}
SITE["/mini/"] = SITE["/mini/index.html"]
SITE["/mini/objects.inv"] = (b"# Sphinx inventory version 2\n# Project: Mini\n# Version: 1.0\n"
                             b"# The remainder of this file is compressed using zlib.\n" + zlib.compress(INVENTORY.encode()))
ASKED: list[str] = []


class Site(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass

    def do_GET(self) -> None:
        ASKED.append(self.path)
        body = SITE.get(self.path)
        self.send_response(200 if body else 404)
        body = body or b"<html><body>Not Found</body></html>"
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def check(ok: bool, what: str) -> None:
    print(("ok    " if ok else "FAIL  ") + what, flush=True)
    if not ok:
        sys.exit(1)


def run(*argv: str) -> str:
    said = io.StringIO()
    try:
        with contextlib.redirect_stderr(said), contextlib.redirect_stdout(said):
            cli.main(list(argv))
    except SystemExit:
        pass
    return said.getvalue()


def main() -> None:
    cli.CONFIG = cli.DATA / "packages.toml"
    labels()
    folding()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Site)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    site = f"http://127.0.0.1:{server.server_address[1]}"
    said = run("add", f"mini={site}/mini/", "--yes", "--no-embed")
    pages = [p for p in ASKED if p.endswith(".html")]
    check(not any(p.startswith("/mini/whatsnew/") or p == "/mini/dev/index.html" for p in pages)
          and "/mini/reference/mini.sum.html" in pages and "pages about the project left out" in said,
          f"release notes and contributing pages are never downloaded ({sorted(pages)})")
    entries = {e.title: e for e in cli.iter_entries("mini")}
    purpose = {t: e.purpose for t, e in entries.items()}
    check(purpose.get("Mini quickstart (page)") == "learn" and purpose.get("Making arrays (section)") == "learn"
          and purpose.get("How to sort (page)") == "do" and purpose.get("Sorting by key (section)") == "do"
          and purpose.get("Mini fundamentals (page)") == "understand" and purpose.get("Views (section)") == "understand"
          and purpose.get("Mini reference (page)") == "lookup" and purpose.get("mini.sum (function)") == "lookup"
          and purpose.get("Development Tools (page)") == "do",
          f"each entry's purpose: its page's title, else the page above it; API objects: look up ({purpose})")
    check(not any(t.startswith(("Internals", "Contributing", "Release notes", "Version 1.0")) for t in entries)
          and not (cli.HOME / "mini" / "pages" / "dev" / "internals.html.gz").exists(),
          f"a page under contributing (downloaded: its folder's index was not) is removed, its stored page too ({list(entries)})")
    check("How to sort (section)" not in entries and "mini.sum (page)" not in entries and "mini.sum (function)" in entries,
          "folded: a section that repeats its page's title; a page that repeats its API object")
    meta = cli.load_meta("mini")
    check(meta.get("organized") == organize.VERSION and meta["count"] == len(entries)
          and meta["left_out"]["pages"] >= 4, f"what was left out is kept in meta ({meta.get('left_out')})")

    lib = web.Library()
    items = lib.search("", {"mini"}, 0, 200)["items"]
    order = [it["purpose"] for it in items]
    groups = [p for k, p in enumerate(order) if k == 0 or order[k - 1] != p]
    names = [it["name"] for it in items]
    check(groups == ["learn", "do", "lookup", "understand"] and names.index("How to sort (page)") < names.index("Sorting by key (section)"),
          f"before you type: learn, do, look up, understand, each in reading order ({groups}, {names})")
    found = lib.search("sorting by key", {"mini"}, 0, 5)["items"]
    check(found and found[0]["purpose"] == "do", f"results say their purpose ({found[:1]})")
    contents = {g["purpose"]: g for g in lib.contents({"mini"})[0]["groups"]}
    do = contents["do"]["parts"][0]
    check([p["title"] for p in contents["learn"]["parts"]] == ["Mini quickstart"] and do["title"] == "Mini user guide"
          and [p["title"] for p in do["pages"]] == ["How to sort", "Development Tools"]
          and contents["lookup"]["parts"][0]["title"] == "Mini reference" and contents["do"]["count"] >= 3
          and (cli.HOME / "mini" / "contents.json").exists(),
          f"the contents, by purpose: each part with the pages its contents list ({contents})")
    meta["repo"] = "github.com/mini/mini"
    cli.write_atomic(cli.HOME / "mini" / "meta.json", json.dumps(meta).encode())
    said = run("list", "mini")
    check("learn 2" in said and "do 4" in said and "understand 2" in said and "pages about the project left out" in said
          and "source code: github.com/mini/mini" in said,
          f"search list NAME: each purpose's count, what was left out, the source code ({said!r})")
    migrate()
    print("all good")


def labels() -> None:
    names = {"numpy", "python", "pandas", "c++"}
    leaf = {t: organize.label_of(t, names, part=False) for t in (
        "Logging HOWTO", "Argparse Tutorial", "imp — Access the import internals",
        "doctest — Test interactive Python examples", "What’s new or different", "Development Tools",
        "NumPy 2.5.0 Release Notes", "What’s New In Python 3.12", "Contributing to NumPy", "NumPy internals",
        "Concepts library (since C++20)", "Glossary", "Installation")}
    check(leaf == {"Logging HOWTO": "do", "Argparse Tutorial": "learn", "imp — Access the import internals": None,
                   "doctest — Test interactive Python examples": None, "What’s new or different": None,
                   "Development Tools": None, "NumPy 2.5.0 Release Notes": "removed",
                   "What’s New In Python 3.12": "removed", "Contributing to NumPy": "removed",
                   "NumPy internals": "understand", "Concepts library (since C++20)": None, "Glossary": "lookup",
                   "Installation": "do"},
          f"a page inside a part: named by what it is, not by what it is about ({leaf})")
    part = {t: organize.label_of(t, names) for t in (
        "F2PY reference manual", "The Python Language Reference", "Python HOWTOs", "NumPy user guide",
        "Development", "Building from source", "pandas documentation")}
    check(part == {"F2PY reference manual": "lookup", "The Python Language Reference": "lookup", "Python HOWTOs": "do",
                   "NumPy user guide": "do", "Development": "removed", "Building from source": "removed",
                   "pandas documentation": None},
          f"a page that starts a part: its loose names count too ({part})")
    titles = {"whatsnew/index.html": "Release notes", "whatsnew/v1.0.html": "Version 1.0 (January 1, 2026)",
              "whatsnew/api.html": "Version 1.1", "dev/index.html": "Contributing to Mini",
              "dev/internals.html": "Internals", "user/index.html": "User guide"}
    skip = organize.unread(titles, {"whatsnew/api.html"}, {"mini"})
    check(skip == {"whatsnew/index.html", "whatsnew/v1.0.html", "dev/index.html"},
          f"not downloaded: release notes (their folder too) and contributing pages; never a page of API objects ({skip})")


def folding() -> None:
    """cppreference's sections: folded when the page's entry holds them, word for word."""
    root = "https://en.cppreference.com/"
    page_md = ("std::format formats.\n\n## Parameters\n\n| fmt | the format |\n\n## Return value\n\nA string.\n\n"
               "## Example\n\n```cpp\nint main() {}\n```\n\n## See also\n\nstd::print")
    entries = [cli.Entry("std::format", "api", root + "cpp/utility/format/format", page_md, "cpp"),
               cli.Entry("std::format › Parameters", "section", root + "cpp/utility/format/format#Parameters",
                         "## Parameters\n\n| fmt | the format |", "cpp"),
               cli.Entry("std::format › Return value", "section", root + "cpp/utility/format/format#Return_value",
                         "## Return value\n\nA string.", "cpp"),
               cli.Entry("std::format › Example", "section", root + "cpp/utility/format/format#Example",
                         "## Example\n\n```cpp\nint main() {}\n```", "cpp"),
               cli.Entry("std::format › See also", "section", root + "cpp/utility/format/format#See_also",
                         "## See also\n\nstd::print (a newer text)", "cpp"),
               cli.Entry("std::format › Classes", "section", root + "cpp/utility/format/format#Classes",
                         "## Classes", "cpp")]
    meta = {"name": "cpp", "kind": "known", "root": root}
    kept, keep = organize.organize("folding", entries, meta)
    titles = [e.title for e in kept]
    check(titles == ["std::format", "std::format › Example", "std::format › See also"] and keep == [0, 3, 4]
          and meta["left_out"]["folded"] == 3,
          f"folded: Parameters, Return value (in the page's entry), an empty section; kept: Example, and a "
          f"See also whose text the page does not have ({titles})")


def migrate() -> None:
    """Docs saved before they were organized: organized once, nothing downloaded."""
    import numpy as np
    root = "https://old.example.org/"
    entries = [cli.Entry("Old documentation (page)", "doc", root + "index.html", "Start here.", "old"),
               cli.Entry("Old tutorial (page)", "doc", root + "tutorial/index.html", "Learn it.", "old"),
               cli.Entry("Release notes (page)", "doc", root + "whatsnew/index.html", "1.0: first.", "old"),
               cli.Entry("old.f (function)", "function", root + "reference/old.f.html#old.f", "Does f.", "old")]
    cli.save("old", entries, {"name": "old", "spec": "old", "kind": "sphinx", "root": root, "pages": True,
                              "created": "2026-10-01 10:00", "model": cli.MODEL_NAME, "count": len(entries)})
    np.save(cli.HOME / "old" / "emb.npy", np.arange(16, dtype=np.float32).reshape(4, 4))
    with contextlib.redirect_stderr(io.StringIO()):
        cli.make_search_caches("old")
    said = run("list")
    kept = [(e.title, e.purpose) for e in cli.iter_entries("old")]
    emb = np.load(cli.HOME / "old" / "emb.npy")
    check("old: organizing its docs" in said and kept == [("Old documentation (page)", "lookup"),
                                                           ("Old tutorial (page)", "learn"), ("old.f (function)", "lookup")]
          and emb[:, 0].tolist() == [0.0, 4.0, 12.0] and cli.load_meta("old")["organized"] == organize.VERSION,
          f"docs from before: organized once; their vectors keep the kept entries' rows ({kept}, {emb[:, 0]})")
    said = run("list")
    check("organizing" not in said, "and only once")


if __name__ == "__main__":
    main()
