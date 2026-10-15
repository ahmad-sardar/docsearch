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
- plain search is the reference (look up, understand; names first); search how IDEA (and the
  page's How) the tutorials, guides and how-tos (learn, do)
- search list NAME: how many entries of each purpose, what was left out, the source code
- docs from before: organized once, with nothing downloaded; their vectors keep the rows of the
  entries kept
- examples (examples.py): an API entry's "Examples" part, and cppreference's Example section,
  are example entries of search how, at their entry's place (plain search finds the entry);
  whether one is complete is read from its code: names it uses and never defines or imports
  ("df (from earlier)", "import polars as pl", "from itertools import batched"; numpy's and
  pandas' np and pd are taken as their docs say), a C++ program with its includes and main
- official guides (guides.py): the docs' header links a "User guide" on their own site (its
  folder holds the docs: only the guide's pages are read, from its sitemap) and "Tutorials" on
  a site that links to the package's repository: both read with the docs, as parts of the copy,
  their pages under pages/guide/ and pages/guide2/, organized with them (its "Getting started":
  learn; development/: left out); a "Learn more" on a site that is not the package's is not
  taken; a guide's entries say "as of" the day; links between the docs and the guide stay in
  the copy; a copy you have gets its guides on search add, without its docs read again;
  --guide URL: taken when official (kept in packages.toml), refused when not
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
                                "<dd><p>Sums the rows.</p><p class='rubric'>Examples</p><div class='highlight'><pre>"
                                "&gt;&gt;&gt; mini.sum([1, 2])\n3</pre></div></dd></dl>", []),
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
    completeness()
    examples_kept()
    sections_whole()
    one_per_thing()
    yours_first()
    sections_kept()
    by_structure()
    under_contents()
    markdown_api()
    replaced_by_coverage()
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
    found = lib.search("sorting by key", {"mini"}, 0, 5, mode="how")["items"]
    check(found and found[0]["purpose"] == "do", f"results say their purpose ({found[:1]})")
    contents = {g["purpose"]: g for g in lib.contents({"mini"})[0]["groups"]}
    do = contents["do"]["parts"][0]
    check([p["title"] for p in contents["learn"]["parts"]] == ["Mini quickstart"] and do["title"] == "Mini user guide"
          and [p["title"] for p in do["pages"]] == ["How to sort", "Development Tools"]
          and contents["lookup"]["parts"][0]["title"] == "Mini reference" and contents["do"]["count"] >= 3
          and (cli.HOME / "mini" / "contents.json").exists(),
          f"the contents, by purpose: each part with the pages its contents list ({contents})")
    what = lib.search("mini.sum sorting by key", {"mini"}, 0, 50)["items"]
    how = lib.search("mini.sum sorting by key", {"mini"}, 0, 50, mode="how")["items"]
    empty_how = lib.search("", {"mini"}, 0, 200, mode="how")["items"]
    check(what and what[0]["name"] == "mini.sum" and {it["purpose"] for it in what} <= {"lookup", "understand"}
          and how and how[0]["name"] == "Sorting by key (section)" and "mini.sum" in [it["name"] for it in how]
          and {it["purpose"] for it in empty_how} == {"learn", "do"},
          f"plain search: the reference (names first); how: the tutorials and guides first, the function "
          f"that does it too ({what[:2]}, {how[:2]})")
    learn = lib.search("sorting by key", {"mini"}, 0, 50, purpose="learn")
    lookup = lib.search("sorting by key", {"mini"}, 0, 50, mode="how", purpose="lookup")
    browse_do = lib.search("", {"mini"}, 0, 200, purpose="do")
    have = browse_do["purposes"]
    check(learn["items"] and {it["purpose"] for it in learn["items"]} == {"learn"}
          and lookup["items"] and {it["purpose"] for it in lookup["items"]} == {"lookup"} and lookup["mode"] == "how"
          and browse_do["purpose"] == "do" and {it["purpose"] for it in browse_do["items"]} == {"do"}
          and have == lib.search("sorting by key", {"mini"}, 0, 5)["purposes"]
          and have["do"] == browse_do["total"] and have["lookup"] == order.count("lookup") and set(have) == set(organize.PURPOSES),
          f"one purpose: only its entries, searched among themselves (in how mode too), and before you type; "
          f"each purpose's count of entries ({learn['items'][:1]}, {lookup['items'][:1]}, {have})")
    typed = lib.search("how sorting by key", {"mini"}, 0, 20)
    check(typed["mode"] == "how" and typed["q"] == "sorting by key" and typed["items"]
          and typed["items"][0]["name"] == "Sorting by key (section)",
          f"\"how\" first in the page's search box: how, as search how ({typed['q']!r}, {typed['mode']})")
    cli.save("refonly", [cli.Entry("refonly.join (function)", "function", "https://ref.example/join.html#refonly.join",
                                   "Joins two tables.", "refonly", "lookup")],
             {"name": "refonly", "spec": "refonly", "kind": "sphinx", "root": "https://ref.example/", "count": 1,
              "organized": organize.VERSION, "created": "2026-10-12 10:00", "model": None})
    with contextlib.redirect_stderr(io.StringIO()):
        cli.make_search_caches("refonly")
    none = web.Library().search("how join two tables", {"refonly"}, 0, 20)
    run("remove", "refonly")
    check(none["mode"] == "how" and none["items"] and none["items"][0]["name"] == "refonly.join",
          f"how, where no tutorial, guide or example matches: the function that does it ({none['items'][:1]})")
    opened = []
    real_open, web.open_browser = web.open_browser, opened.append
    try:
        run("how", "mini", "sort", "by", "key")
        run("mini", "sum")
        run("ai", "how", "mini", "sort", "by", "key")
    finally:
        web.open_browser = real_open
    check(opened[0]["mode"] == "how" and opened[0]["q"] == "sort by key" and opened[0]["src"] == "mini"
          and opened[1]["mode"] == "what"
          and (opened[2]["mode"], opened[2]["q"], opened[2]["src"]) == ("how", "sort by key", "mini"),
          f"search how IDEA: the page searches the guides; plain search, the reference; search ai how IDEA: "
          f"the guides, ranked with AI ({opened})")
    ex = lib.search("sums rows mini.sum examples", {"mini"}, 0, 20, mode="how")["items"]
    ex = next((it for it in ex if it["kind"] == "example"), None)
    shown = lib.entry(ex["id"]) if ex else {}
    check(ex is not None and ex["name"] == "mini.sum › Examples" and ex["complete"] == {"needs": ["import mini"]}
          and "mini.sum([1, 2])" in shown.get("html", "") and shown.get("html", "").count("Sums the rows") == 1
          and shown["page"]["path"] == "mini/reference/mini.sum.html" and shown["page"]["at"] == "mini.sum"
          and "mini.sum › Examples" not in [it["name"] for it in lib.search("mini.sum", {"mini"}, 0, 20)["items"]],
          f"an API entry's examples: an entry of search how, at its entry's place, what the entry is said once; "
          f"complete or what it needs (here: import mini); plain search finds the entry itself ({ex})")
    meta["repo"] = "github.com/mini/mini"
    cli.write_atomic(cli.HOME / "mini" / "meta.json", json.dumps(meta).encode())
    said = run("list", "mini")
    check("learn 2" in said and "do 5" in said and "understand 2" in said and "pages about the project left out" in said
          and "source code: github.com/mini/mini" in said,
          f"search list NAME: each purpose's count, what was left out, the source code ({said!r})")
    migrate()
    guides()
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
    numbered = {t: organize.label_of(t, {"cuda"}, part=k < 3) for k, t in enumerate((
        "1. Introduction to CUDA", "5. Technical Appendices", "3. Tutorials", "2.1. Intro to CUDA C++",
        "4.2. CUDA Graphs", "2.3. Writing SIMT Kernels"))}
    check(numbered == {"1. Introduction to CUDA": "learn", "5. Technical Appendices": "lookup", "3. Tutorials": "learn",
                       "2.1. Intro to CUDA C++": "learn", "4.2. CUDA Graphs": None, "2.3. Writing SIMT Kernels": None},
          f"numbered titles (CUDA's): read without their number; an introduction is to learn from, "
          f"appendices to look up ({numbered})")
    titles = {"whatsnew/index.html": "Release notes", "whatsnew/v1.0.html": "Version 1.0 (January 1, 2026)",
              "whatsnew/api.html": "Version 1.1", "dev/index.html": "Contributing to Mini",
              "dev/internals.html": "Internals", "user/index.html": "User guide"}
    skip = organize.unread(titles, {"whatsnew/api.html"}, {"mini"})
    check(skip == {"whatsnew/index.html", "whatsnew/v1.0.html", "dev/index.html"},
          f"not downloaded: release notes (their folder too) and contributing pages; never a page of API objects ({skip})")


def completeness() -> None:
    from docsearch import examples as X
    ok = {
        "pandas": X.needs("```\n>>> df = pd.DataFrame({'a': [1]})\n>>> df.a.sum()\n1\n```", package="pandas"),
        "later": X.needs("```\n>>> df.merge(other)\n```", package="pandas"),
        "polars": X.needs("```\n>>> pl.DataFrame({'a': [1]})\n```", package="polars"),
        "stdlib": X.needs("```\n>>> list(batched('ABCDEFG', 3))\n```", name="itertools.batched"),
        "program": X.needs("```cpp\n#include <print>\nint main() { std::println(\"hi\"); }\n```"),
        "fragment": X.needs("```cpp\nstd::vector<int> v;\nv.push_back(1);\n```"),
        "prose": X.needs("No code here."),
        "ipython": X.needs("```\nIn [1]: df1 = pd.DataFrame({'a': [1]})\n\nIn [2]: pd.merge(df1, df2)\nOut[2]: 1\n```",
                           package="pandas")}
    check(ok == {"pandas": {"complete": True}, "later": {"needs": ["df (from earlier)", "other (from earlier)"]},
                 "polars": {"needs": ["import polars as pl"]}, "stdlib": {"needs": ["from itertools import batched"]},
                 "program": {"complete": True}, "fragment": {"needs": ["#include and main"]}, "prose": None,
                 "ipython": {"needs": ["df2 (from earlier)"]}},
          f"an example's code: complete, or what it needs, read from the code ({ok})")
    entry = cli.Entry("numpy.sum (function)", "function", "https://x/numpy.sum.html#numpy.sum",
                      "```python\nnumpy.sum(a)\n```\n\nSums. Of all.\n\nMore.\n\nExamples\n\nTry it in your browser!\n\n"
                      "```\n>>> np.sum([1, 2])\n3\n```\n\nGo BackOpen In Tab", "numpy", "lookup")
    made = X.entries_of([entry])
    check(len(made) == 1 and made[0].title == "numpy.sum › Examples" and made[0].kind == "example"
          and made[0].purpose == "do" and made[0].location == entry.location and made[0].text.startswith("Sums.\n\n")
          and "More." not in made[0].text and "browser" not in made[0].text and ">>> np.sum" in made[0].text,
          f"an API entry's Examples part, what the entry is first, without the page's buttons: an example entry "
          f"at its place ({made})")


def examples_kept() -> None:
    """Examples: only code the docs present as one; re-organizing keeps their purpose, and the
    examples it would make again the same, with their vectors; placeholders are not examples."""
    from docsearch import examples as X
    said = {"described": X.unit(cli.Entry("f (function)", "function", "https://x/f", "Sorts.\n\n```python\n"
                                          "x = [3, 1]\nx.sort()\n```", "x")),
            "presented": X.unit(cli.Entry("g (function)", "function", "https://x/g", "Sorts.\n\nFor example:\n\n"
                                          "```python\nsorted([3, 1])\nsorted('ba')\n```", "x"))}
    check(said["described"] is None and said["presented"] and said["presented"].startswith("For example:"),
          f"code in a description is not an example; code the docs present as one is ({said})")
    root = "https://numpy.example/"
    at = root + "reference/generated/numpy.sum.html#numpy.sum"
    sums = "```\n>>> np.sum([1, 2])\n3\n```"
    entries = [cli.Entry("numpy.sum (function)", "function", at, f"Sums.\n\nExamples\n\n{sums}", "np"),
               cli.Entry("numpy.sum › Examples", "example", at, f"Sums.\n\n{sums}", "np", "lookup"),  # (relabeled)
               cli.Entry("numpy.dot (function)", "function", root + "reference/generated/numpy.dot.html#numpy.dot",
                         "Dots.\n\n```c\nstruct dot {\n  int a;\n};\n```", "np"),
               cli.Entry("numpy.dot › Examples", "example", root + "reference/generated/numpy.dot.html#numpy.dot",
                         "```c\nstruct dot {\n  int a;\n};\n```", "np", "do")]          # (any code, before)
    kept, keep = organize.organize("examples", entries, {"name": "np", "kind": "sphinx", "root": root})
    got = [(e.title, e.purpose, i) for e, i in zip(kept, keep)]
    check(got == [("numpy.sum (function)", "lookup", 0), ("numpy.sum › Examples", "do", 1),
                  ("numpy.dot (function)", "lookup", 2)],
          f"re-organized: an example keeps its purpose and its row; one made from any code goes ({got})")
    root = "https://en.cppreference.com/"
    entries = [cli.Entry("std::f", "api", root + "cpp/f", "std::f does f.", "cpp"),
               cli.Entry("std::f › Example", "section", root + "cpp/f#Example",
                         "## Example\n\nThis section is incomplete\nReason: no example", "cpp")]
    kept, _ = organize.organize("placeholder", entries, {"name": "cpp", "kind": "known", "root": root})
    check([e.title for e in kept] == ["std::f"], f"an Example section that has none yet: left out ({kept})")


def sections_whole() -> None:
    """A section reached by its label is the whole section (Sphinx puts the label's anchor first
    in it), not its first paragraph; copies cut before are cut again from their stored pages."""
    import gzip
    page = ("<html><body><div role='main'><section id='reading'><span id='tut-files'></span><h2>Reading</h2>"
            "<p>open() returns a file object.</p><pre>for line in f:\n    print(line)</pre>"
            "<section id='methods'><span id='tut-methods'></span><h3>Methods</h3><p>Read lines.</p></section>"
            "</section><section id='other'><h2>Other</h2><p>a</p><span id='mid'></span><p>b</p><p>c</p></section>"
            "</div></body></html>")
    soup = cli.make_soup(page.encode())
    cut = {a: cli.html_to_md("".join(str(n) for n in cli.sphinx_fragment(soup, a))) for a in ("tut-files", "mid")}
    check("for line in f" in cut["tut-files"] and "Read lines." in cut["tut-files"] and cut["mid"].strip() == "b",
          f"a label first in its section: the whole section; a label inside one: what it marks ({cut})")
    root = "https://tut.example/"
    entries = [cli.Entry("Input and output (page)", "doc", root + "tutorial/io.html", "Input and output.", "tut"),
               cli.Entry("Reading (section)", "label", root + "tutorial/io.html#tut-files",
                         "open() returns a file object.", "tut"),
               cli.Entry("b (section)", "label", root + "tutorial/io.html#mid", "b", "tut")]
    cli.save("tut", entries, {"name": "tut", "spec": "tut", "kind": "sphinx", "root": root, "pages": True,
                              "created": "2026-10-01 10:00", "model": cli.MODEL_NAME, "count": 3, "organized": 2})
    (cli.HOME / "tut" / "pages" / "tutorial").mkdir(parents=True, exist_ok=True)
    (cli.HOME / "tut" / "pages" / "tutorial" / "io.html.gz").write_bytes(gzip.compress(page.encode()))
    organize.organize_copy("tut")
    got = {e.title: e.text for e in cli.iter_entries("tut")}
    check("for line in f" in got.get("Reading (section)", "") and got.get("b (section)") == "b"
          and cli.load_meta("tut")["organized"] == organize.VERSION,
          f"organized again (version 3): a section cut as its first paragraph is cut whole from its stored page, "
          f"nothing downloaded ({got})")


def one_per_thing() -> None:
    """One section reached by two labels is one entry; results of one name say where each is."""
    root = "https://twins.example/"
    sec = "## Pure Python\n\nApply a function row-wise."
    entries = [cli.Entry("Enhancing performance (page)", "doc", root + "perf.html", "Speed.", "twins"),
               cli.Entry("Pure Python (section)", "label", root + "perf.html#pure-python", sec, "twins"),
               cli.Entry("Pure Python (section)", "label", root + "perf.html#enhancingperf-pure", sec, "twins"),
               cli.Entry("Comparison with R (page)", "doc", root + "compare/r.html", "R.", "twins"),
               cli.Entry("Sorting (section)", "label", root + "compare/r.html#sorting", "Sort in R.", "twins"),
               cli.Entry("Basics (page)", "doc", root + "basics.html", "Basics.", "twins"),
               cli.Entry("Sorting (section)", "label", root + "basics.html#sorting", "Sort it.", "twins"),
               cli.Entry("GroupBy (page)", "doc", root + "reference/dataframe/group_by.html", "Group a frame.", "twins"),
               cli.Entry("GroupBy (page)", "doc", root + "reference/lazyframe/group_by.html", "Group lazily.", "twins")]
    kept, _ = organize.organize("twins", entries, {"name": "twins", "kind": "sphinx", "root": root})
    check([e.location.split("#")[-1] for e in kept if e.title == "Pure Python (section)"] == ["enhancingperf-pure"],
          f"one section reached by two labels: one entry, at the docs' own label ({[e.location for e in kept]})")
    cli.save("twins", kept, {"name": "twins", "spec": "twins", "kind": "sphinx", "root": root, "count": len(kept),
                             "organized": organize.VERSION, "created": "2026-10-12 10:00", "model": None})
    with contextlib.redirect_stderr(io.StringIO()):
        cli.make_search_caches("twins")
    where = {}
    for q in ("sorting", "groupby"):
        for it in web.Library().search(q, {"twins"}, 0, 20)["items"] + web.Library().search(q, {"twins"}, 0, 20, mode="how")["items"]:
            where.setdefault(it["name"], set()).add(it.get("where"))
    run("remove", "twins")
    check(where.get("Sorting (section)") == {"Comparison with R", "Basics"}
          and where.get("GroupBy (page)") == {"reference/dataframe", "reference/lazyframe"},
          f"two results of one name: each says where it is, its page or its folder ({where})")


def yours_first() -> None:
    """Every package searched from a project: what is named as asked, then the project's own
    packages, then its languages' other docs, then the rest. One package searched: as it was."""
    made = {"cpp": [cli.Entry("std::list::sort", "api", "https://cpp.example/list/sort",
                              "Sorts a list. Sort a list of elements in a list.", "cpp")],
            "pyx": [cli.Entry("Sorting how to (page)", "doc", "https://pyx.example/sorting.html",
                              "How to sort: sorted() returns a new list.", "pyx", "do")],
            "pyz": [cli.Entry("pyz.sort_list (function)", "function", "https://pyz.example/sort.html#pyz.sort_list",
                              "Sort a list, in place.", "pyz")]}
    for name, es in made.items():
        cli.save(name, es, {"name": name, "spec": name, "kind": "sphinx", "root": es[0].location.rsplit("/", 1)[0] + "/",
                            "count": 1, "organized": organize.VERSION, "created": "2026-10-12 10:00", "model": None})
        with contextlib.redirect_stderr(io.StringIO()):
            cli.make_search_caches(name)
    lib = web.Library()
    order = lambda q, **kw: [it["source"] for it in lib.search(q, set(), 0, 50, **kw)["items"]
                             if it["source"] in made]                                       # noqa: E731
    yours = order("sort a list", mode="how", project={"pyx": "1.0"})
    exact = order("std::list::sort", project={"pyx": "1.0"})
    one = [it["source"] for it in lib.search("sort a list", {"cpp"}, 0, 50, project={"pyx": "1.0"})["items"]]
    for name in made:
        run("remove", name)
    check(yours == ["pyx", "pyz", "cpp"] and exact[0] == "cpp" and one == ["cpp"],
          f"every package from a Python project: its package, Python's others, then C++; a name asked "
          f"exactly first; one package as it was ({yours}, {exact}, {one})")


def sections_kept() -> None:
    """The sections chosen of each docs site of a package, kept per site in packages.toml with
    what was chosen before (the docs' own, from before, kept), and read back for each site."""
    cli.config_set("twosites", {"version": "latest", "sections": "default"})
    cli.remember_sections("twosites", {"https://guide.example/": ["Build", "+"]})
    kept = cli.config_values("twosites")
    got = (cli.site_sections("twosites", "https://docs.example/", main=True),
           cli.site_sections("twosites", "https://guide.example/"), cli.site_sections("twosites", "https://other.example/"))
    check(kept["sections"] == {"": "default", "https://guide.example/": ["Build", "+"]}
          and got == ("default", ["Build", "+"], None),
          f"the sections chosen, per site: the docs' (from before) and the guide's, each read back ({kept}, {got})")


def by_structure() -> None:
    """Purposes by the site's own structure (organizing version 5): a page's purpose comes from
    its title, its contents and its sections in the site's outline, not from the page above it by
    address (a first page "Getting Started" is not what the pages under it are), unless that
    page names a collection ("API reference"); a place ("Overview") names its own page only;
    changelogs and blog pages are left out; a top section holding much of the site is parted by
    its own sections; each part counts its own purpose's entries."""
    from docsearch import pages as offline
    root = "https://struct.example/"
    rels = ["", "docs/", "docs/proxy/keys", "docs/proxy/spend", "api/", "api/client", "guides/a", "guides/b",
            "guides/c", "guides/d", "guides/e", "guides/f", "overview/create-agent", "changelog/agent-server",
            "blog/post"]
    titles = {"": "Struct", "docs/": "Getting Started", "docs/proxy/keys": "Virtual keys",
              "docs/proxy/spend": "Spend tracking", "api/": "API reference", "api/client": "Client",
              "guides/a": "Build agents", "guides/b": "Use tools", "guides/c": "Add memory", "guides/d": "Stream",
              "guides/e": "Deploy it", "guides/f": "Monitor it", "overview/create-agent": "Create an agent",
              "changelog/agent-server": "Agent Server changelog", "blog/post": "A post"}
    entries = [cli.Entry(f"{titles[r]} (page)" if r else "Struct (page)", "page", root + r, f"About {titles[r]}.", "struct")
               for r in rels]
    cli.save("struct", entries, {"name": "struct", "spec": "struct", "kind": "website", "root": root, "pages": True,
                                 "count": len(entries), "created": "2026-10-14 10:00", "model": None})
    for r in rels:
        offline.save_page(cli.HOME / "struct" / "pages", r or "index.html",
                          f"<html><body><main><h1>{titles[r]}</h1><p>Text.</p></main></body></html>")
    outline = {root + r: c for r, c in {
        "guides/a": ["Lifecycle", "Build"], "guides/b": ["Lifecycle", "Build"], "guides/c": ["Lifecycle", "Build"],
        "guides/d": ["Lifecycle", "Observe"], "guides/e": ["Lifecycle", "Deploy"], "guides/f": ["Lifecycle", "Observe"],
        "overview/create-agent": ["Overview"]}.items()}
    cli.write_atomic(cli.HOME / "struct" / "outline.json", json.dumps(outline).encode())
    meta = cli.load_meta("struct")
    kept, _ = organize.organize("struct", list(cli.iter_entries("struct")), meta)
    purpose = {e.location[len(root):]: e.purpose for e in kept}
    cli.save("struct", kept, meta)
    parts = {g["purpose"]: [p["title"] for p in g["parts"]] for g in organize.contents("struct")}
    run("remove", "struct")
    check(purpose.get("docs/proxy/keys") != "learn" and purpose.get("api/client") == "lookup"
          and purpose.get("overview/create-agent") == "do" and "changelog/agent-server" not in purpose
          and "blog/post" not in purpose and {"Build", "Observe", "Deploy"} <= set(parts.get("do", [])),
          f"by the site's structure: not by address (but a collection's folder); a place names its own page; "
          f"changelogs and blogs left out; a big section parted by its own ({purpose}, {parts})")


def under_contents() -> None:
    """CUDA's guides: a "Contents" page lists the guide's first page, so that page starts a part
    and its title counts ("CUDA Programming Guide": do); its numbered parts are read without
    their numbers ("1. Introduction to CUDA": learn); a known source's parts are named as the
    publisher names them (a one-page guide whose first heading is "1. Overview")."""
    from docsearch import order, pages as offline, sources
    root = "https://gpu.example/"
    toc = lambda *hrefs: ('<div class="toctree-wrapper compound"><ul>'
                          + "".join(f'<li class="toctree-l1"><a href="{h}">{h}</a></li>' for h in hrefs) + "</ul></div>")
    pages = {"gpu-programming-guide/contents.html": ("Contents", toc("index.html")),
             "gpu-programming-guide/index.html": ("GPU Programming Guide", ""),
             "gpu-programming-guide/part1.html": ("1. Introduction to GPU", toc("01-intro/model.html")),
             "gpu-programming-guide/01-intro/model.html": ("1.1. Programming Model", ""),
             "gpu-programming-guide/part2.html": ("2. Programming GPUs", toc("02-basics/intro-cpp.html", "02-basics/kernels.html")),
             "gpu-programming-guide/02-basics/intro-cpp.html": ("2.1. Intro to GPU C++", ""),
             "gpu-programming-guide/02-basics/kernels.html": ("2.2. Writing Kernels", ""),
             "gpu-programming-guide/part5.html": ("5. Technical Appendices", toc("05-appendices/env.html")),
             "gpu-programming-guide/05-appendices/env.html": ("5.1. Environment Variables", ""),
             "practices/contents.html": ("Contents", toc("index.html")),
             "practices/index.html": ("1. Overview", ""),
             "api/index.html": ("GPU Runtime API", "")}
    entries = [cli.Entry(f"{t} (page)", "page", root + r, f"About {t}.", "gpu") for r, (t, _) in pages.items()]
    entries.append(cli.Entry("Memory transfers", "section", root + "practices/index.html#memory", "Copy less.", "gpu"))
    known = {"about": "GPU", "root": root, "parts": [
        {"kind": "sphinx", "url": root + "gpu-programming-guide/", "title": "GPU Programming Guide"},
        {"kind": "sphinx", "url": root + "practices/", "title": "GPU Best Practices Guide"},
        {"kind": "sphinx", "url": root + "api/", "title": "GPU Runtime API"}]}
    sources.KNOWN["gpu"] = known
    try:
        cli.save("gpu", entries, {"name": "gpu", "spec": "gpu", "kind": "known", "root": root, "pages": True,
                                  "count": len(entries), "created": "2026-10-15 10:00", "model": None,
                                  "nav": [root + "gpu-programming-guide/contents.html", root + "practices/contents.html"]})
        for r, (t, body) in pages.items():
            offline.save_page(cli.HOME / "gpu" / "pages", r, f"<html><body><main><h1>{t}</h1>{body}<p>Text.</p></main></body></html>")
        meta = cli.load_meta("gpu")
        listed = order.page_order("gpu", meta).parent.get("gpu-programming-guide/index.html")
        kept, _ = organize.organize("gpu", list(cli.iter_entries("gpu")), meta)
        purpose = {e.location[len(root):]: e.purpose for e in kept}
        run("remove", "gpu")
    finally:
        del sources.KNOWN["gpu"]
    want = {"gpu-programming-guide/index.html": "do", "gpu-programming-guide/01-intro/model.html": "learn", "gpu-programming-guide/02-basics/intro-cpp.html": "learn",
            "gpu-programming-guide/02-basics/kernels.html": "do", "gpu-programming-guide/05-appendices/env.html": "lookup",
            "practices/index.html": "do", "practices/index.html#memory": "do", "api/index.html": "lookup"}
    check(listed == "gpu-programming-guide/contents.html" and {r: purpose.get(r) for r in want} == want,
          f"a guide under a Contents page, numbered titles, a known source's parts named by their publisher "
          f"({ {r: purpose.get(r) for r in want} })")


def markdown_api() -> None:
    """A Markdown API reference's page (reference.langchain.com): an API entry named from its
    address, of the kind it says; its Signature and Description folded into it; its example an
    entry of its own."""
    root = "https://ref.example/python/lib/"
    page = ("# make_agent\n\n> **Function** in `lib`\n\nMakes an agent.\n\n## Signature\n\n```python\n"
            "make_agent(model)\n```\n\n## Description\n\nMakes an agent.\n\nExample:\n\n```python\n"
            "from lib.agents import make_agent\nagent = make_agent('m')\n```\n")
    loc = root + "agents/factory/make_agent"
    entries = [cli.Entry("make_agent", "page", loc, page, "lib"),
               cli.Entry("make_agent › Signature", "section", loc + "#signature",
                         "## Signature\n\n```python\nmake_agent(model)\n```", "lib"),
               cli.Entry("make_agent › Description", "section", loc + "#description",
                         "## Description\n\nMakes an agent.\n\nExample:\n\n```python\nfrom lib.agents import "
                         "make_agent\nagent = make_agent('m')\n```", "lib")]
    kept, keep = organize.organize("mdapi", entries, {"name": "lib", "kind": "website", "root": root})
    got = [(e.title, e.kind) for e in kept]
    check(got == [("lib.agents.factory.make_agent", "function"), ("lib.agents.factory.make_agent › Examples", "example")]
          and keep[0] == -1,
          f"a Markdown API reference's page: an API entry named from its address; its parts folded; its "
          f"example an entry ({got}, {keep})")


def replaced_by_coverage() -> None:
    """A download replaces the copy you have when it read nine in ten of the pages its site
    lists (with few failed), whatever its count of entries; where nothing says how many pages
    there are, when it has 70% of the entries the copy you have has."""
    import tempfile
    from pathlib import Path
    d = Path(tempfile.mkdtemp())

    def why(**meta):
        cli.write_atomic(d / "meta.json", json.dumps(meta).encode())
        return cli.incomplete(d, {"count": 28000})
    got = (why(count=9600, expected_pages=1643, read_pages=1600), why(count=9600, expected_pages=1643, read_pages=1200),
           why(count=9600), why(count=26000))
    check(got[0] is None and "1,200 of the 1,643" in (got[1] or "") and "9600 entries" in (got[2] or "") and got[3] is None,
          f"replaced by coverage: read 9 in 10 of the listed pages; else, unknown, 70% of the entries ({got})")


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
    kinds = [e.kind for e in kept]
    check(titles == ["std::format", "std::format › Example", "std::format › See also"] and keep == [0, -1, 4]
          and kinds == ["api", "example", "section"] and kept[1].purpose == "do"
          and kept[1].text.startswith("std::format formats.\n\n## Example")
          and meta["left_out"]["folded"] == 3,
          f"folded: Parameters, Return value (in the page's entry), an empty section; kept: Example (what "
          f"its page is said first: a new vector), and a See also whose text the page does not have ({titles})")


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



# --------------------------------------------------------------------------- official guides

MOCK: dict[str, dict[str, bytes]] = {}           # host -> path -> page (a made-up web, no internet)
MOCK_ASKED: list[str] = []


def answer(request):
    import httpx
    MOCK_ASKED.append(str(request.url))
    body = MOCK.get(request.url.host, {}).get(request.url.raw_path.decode())
    return httpx.Response(200 if body is not None else 404, content=body if body is not None else b"no")


def doc_page(title: str, body: str = "", head: str = "", base: str = "") -> bytes:
    hint = f'<script id="__config" type="application/json">{{"base": "{base}"}}</script>' if base else ""
    return (f"<html><head><title>{title}</title>{hint}</head><body><header>{head}</header>"
            f"<nav><a href='https://github.com/lib-org/lib'>GitHub</a></nav><main><h1>{title}</h1>"
            f"<p>{WORDS}</p>{body}</main></body></html>").encode()


def sitemap(urls: list[str]) -> bytes:
    return ("<urlset>" + "".join(f"<url><loc>{u}</loc></url>" for u in urls) + "</urlset>").encode()


def guide_sites(header: str) -> None:
    api = "https://docs.lib.example/api/stable/"
    inv = ("index std:doc -1 index.html Lib API reference\nreference std:doc -1 reference.html Reference\n"
           "lib.join py:function 1 reference.html#lib.join -\n")
    MOCK["pypi.org"] = {"/pypi/lib/json": json.dumps({"info": {"name": "lib", "summary": "A lib.", "version": "1.0",
                        "project_urls": {"Documentation": api, "Source": "https://github.com/lib-org/lib",
                                         "Homepage": "https://docs.lib.example/api/latest/"}}}).encode()}
    MOCK["docs.lib.example"] = {
        "/api/stable/objects.inv": (b"# Sphinx inventory version 2\n# Project: Lib\n# Version: 1.0\n"
                                    b"# The remainder of this file is compressed using zlib.\n" + zlib.compress(inv.encode())),
        "/api/stable/": doc_page("Lib API reference", "", header),
        "/api/stable/index.html": doc_page("Lib API reference", "", header),
        "/api/stable/reference.html": doc_page("Reference", "<dl class='py function'><dt id='lib.join'>lib.join(a, b)"
                                               "</dt><dd><p>Joins two tables.</p></dd></dl>"),
        "/": doc_page("Lib", "<a href='user-guide/getting-started/'>Start</a>", base="."),
        "/sitemap.xml": sitemap([f"https://docs.lib.example/{p}" for p in (
            "", "user-guide/getting-started/", "user-guide/concepts/", "user-guide/joins/", "development/contributing/")]),
        "/user-guide/getting-started/": doc_page("Getting started", "<pre><code>import lib</code></pre>"),
        "/user-guide/concepts/": doc_page("Concepts", "<p>Tables and rows.</p>"),
        "/user-guide/joins/": doc_page("Joins", "<p>Use <a href='https://docs.lib.example/api/stable/reference.html#lib.join'>"
                                                "lib.join</a>, as <a href='../concepts/'>Concepts</a> says.</p>"),
        "/development/contributing/": doc_page("Contributing", ""),
    }
    MOCK["learn.lib-tutorials.example"] = {
        "/": doc_page("Lib tutorials", "<a href='first-steps/'>First steps</a>", base="."),
        "/sitemap.xml": sitemap(["https://learn.lib-tutorials.example/", "https://learn.lib-tutorials.example/first-steps/"]),
        "/first-steps/": doc_page("Your first table", "<p>Make a table.</p>"),
    }
    MOCK["shop.lib.example"] = {"/": doc_page("Lib training", "<a href='courses/'>Courses</a>"),   # (only a
                                "/sitemap.xml": sitemap(["https://shop.lib.example/"] +
                                                        [f"https://shop.lib.example/courses/{n}/" for n in range(12)]),
                                "/courses/": doc_page("Paid courses", "")}                             # sitemap)
    MOCK["blog.example"] = {"/": b"<html><body><main><h1>A blog</h1><p>Posts.</p></main></body></html>",
                            "/sitemap.xml": sitemap(["https://blog.example/"])}
    MOCK["api.github.com"] = {"/repos/lib-org/lib": json.dumps({"full_name": "lib-org/lib",
                                                                "homepage": "https://docs.lib.example/"}).encode()}


def guides() -> None:
    import httpx
    real = cli._CLIENT
    cli._CLIENT = httpx.Client(transport=httpx.MockTransport(answer), follow_redirects=False)
    try:
        guides_found()
    finally:
        cli._CLIENT = real


def guides_found() -> None:
    from docsearch import guides as G
    from docsearch import pages
    header = ("<a href='/api/stable/'>API</a> <a href='https://docs.lib.example/'>User guide</a> "
              "<a href='https://learn.lib-tutorials.example/'><span>Tutorials</span> <span>Learn it step by step</span></a> "
              "<a href='https://blog.example/'>Learn more</a> <a href='https://shop.lib.example/'>Courses</a>")
    guide_sites(header)
    said = run("add", "lib", "--no-embed")
    m = cli.load_meta("lib@1.0")
    got = {g["root"]: (g["dir"], g["title"], g["purpose"]) for g in m.get("guides") or []}
    check(got == {"https://docs.lib.example/": ("guide", "User guide", "do"),
                  "https://learn.lib-tutorials.example/": ("guide2", "Tutorials", "learn")}
          and "blog.example" not in said and "official guide" in said,
          f"guides the docs' header links: named as guides (a menu's first words), on their site or linking to "
          f"their repository; not \"Learn more\" ({got})")
    check(not any("shop.lib.example" in r or "/api/latest/" in r for r in got)
          and "shop.lib.example" not in str(cli.load_meta("lib@1.0").get("guides")),
          f"not a guide: an official site with only a sitemap (no docs site), nor these docs of another version "
          f"(PyPI's /api/latest/ next to /api/stable/) ({got})")
    es = {e.title: e for e in cli.iter_entries("lib@1.0")}
    locs = [e.location for e in es.values()]
    check(len([x for x in locs if x.endswith("#lib.join")]) == 1
          and pages.page_file(cli.HOME / "lib@1.0" / "pages" / "guide", "user-guide/joins/").exists()
          and pages.page_file(cli.HOME / "lib@1.0" / "pages" / "guide2", "first-steps/").exists()
          and not any("/api/stable/" in str(u) for u in [x for x in MOCK_ASKED if "sitemap" in x]),
          f"the guides' pages, each in its folder; the docs inside the guide's site not read again ({sorted(es)})")
    purpose = {t: e.purpose for t, e in es.items()}
    check(purpose.get("Getting started") == "learn" and purpose.get("Concepts") == "understand"
          and purpose.get("Joins") == "do" and purpose.get("Your first table") == "learn" and "Contributing" not in es,
          f"a guide's pages, organized with the docs ({purpose})")
    lib = web.Library()
    joins = next(i for i, e in enumerate(lib.index.entries) if e.title == "Joins")
    entry = lib.entry(joins)
    page = lib.page(entry["page"]["path"])
    check(entry["version"].startswith("User guide, as of ") and entry["page"]["path"].startswith("lib@1.0/guide/")
          and page["web"] == "https://docs.lib.example/user-guide/joins/"
          and "page=lib%401.0%2Freference.html" in page["html"] and "page=lib%401.0%2Fguide%2Fuser-guide%2Fconcepts" in page["html"],
          f"a guide's entry: of no version, \"as of\" the day; its links to the docs and to itself stay here ({entry['version']})")
    parts = {g["purpose"]: [p["title"] for p in g["parts"]] for g in lib.contents({"lib@1.0"})[0]["groups"]}
    check("User guide" in parts.get("do", []) and "Tutorials" in parts.get("learn", []),
          f"the contents: each guide as a part, by its purpose ({parts})")

    # a copy from before guides: they come with search add, its docs are not read again
    MOCK["docs.lib.example"]["/api/stable/"] = MOCK["docs.lib.example"]["/api/stable/index.html"] = doc_page(
        "Lib API reference", "", "<a href='/api/stable/'>API</a>")
    run("remove", "lib", "--all")
    run("add", "lib", "--no-embed")
    check(not cli.load_meta("lib@1.0").get("guides"), "docs whose header links no guide: none")
    MOCK["docs.lib.example"]["/api/stable/"] = MOCK["docs.lib.example"]["/api/stable/index.html"] = doc_page(
        "Lib API reference", "", header)
    MOCK_ASKED.clear()
    said = run("add", "lib", "--no-embed")
    roots = [g["root"] for g in cli.load_meta("lib@1.0").get("guides") or []]
    check(len(roots) == 2 and "Joins" in {e.title for e in cli.iter_entries("lib@1.0")}
          and not any(u.endswith("/api/stable/reference.html") for u in MOCK_ASKED),
          f"a copy you have gets the guides its docs link, without its docs read again ({roots})")

    # --guide: taken when official, refused when not
    said = run("add", "lib", "--no-embed", "--guide", "https://blog.example/")
    check("not taken as a guide" in said and "blog.example" not in str(cli.load_meta("lib@1.0").get("guides")),
          f"--guide on a site that is not the package's: refused ({said[-200:]!r})")
    MOCK["docs.lib.example"]["/api/stable/"] = MOCK["docs.lib.example"]["/api/stable/index.html"] = doc_page(
        "Lib API reference", "", "<a href='/api/stable/'>API</a>")
    run("remove", "lib", "--all")
    said = run("add", "lib", "--no-embed", "--guide", "https://docs.lib.example/")
    toml = cli.CONFIG.read_text(encoding="utf-8")
    check([g["root"] for g in cli.load_meta("lib@1.0").get("guides") or []] == ["https://docs.lib.example/"]
          and "[guides]" in toml and "https://docs.lib.example/" in toml and G.config_guides("lib"),
          f"--guide on the docs' own site: taken, and kept in packages.toml ({toml!r})")


if __name__ == "__main__":
    main()
