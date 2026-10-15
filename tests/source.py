"""Finding a package's docs through its source code, on made-up sites answered in this
process (httpx's MockTransport: real-looking addresses, nothing goes online), a few seconds.

    uv run python tests/source.py

- docs and repository that point at each other: taken, no question, the repository kept,
  GitHub not asked (the docs' own link says it); a page that says where its docs begin
  (Sphinx's data-content_root) costs one question for them
- a home page that links to its docs on the same site (sympy.org: docs.sympy.org); on a site
  many packages share (Google's), the link that names the package (google-cloud-bigquery)
- docs added by their address: read as they are; their repository (for the link to their
  source) is the one their pages link to that names their site back
- PyPI's docs link points at an umbrella site; the repository names the real docs: those; the
  named address sends HTTPS to plain HTTP elsewhere (wsproto.readthedocs.io to
  python-hyper.org/projects/wsproto/): followed over HTTPS, and checked by where it started
- docs on a site under the one the repository names (docs.scipy.org under scipy.org): checked
- a package PyPI names only its repository for: found at the website the repository names,
  whose first page only says "go to /main/" (triton)
- a guessed address (NAME.readthedocs.io): used if it links to the repository, else dropped,
  without a question
- docs that link neither way: asked; without a terminal not taken, and said how (--yes);
  with --yes taken, and kept as "you said yes"
- GitHub's hourly questions used up: said once; the docs' own links still checked
- an inventory without pages (mkdocstrings: FastAPI): its API objects, then the rest of the
  site page by page, each page once
- a search index only (Zensical, MkDocs), or no index at all: the site page by page
- the source code the entries link to (Sphinx's [source]): stored, each file once, not the
  docs' own sources nor other links; stopped half way, it goes on with nothing fetched twice;
  the page shows an entry's lines (a range; from one line, its block); a copy made before
  docsearch kept code gets it from `search add NAME`, without reading the pages again
- docs that state no version: the release their source links name (polars: py-2.0.0);
  development docs (links to main, or an address at /main/: jax, triton) are a nightly of
  their day, "after" PyPI's newest release, and `search update` pulls them anew; a version
  menu ("2 (stable)") made exact by PyPI's newest release; else the day, with that release; a
  version a build tool made up for an untagged checkout (fsspec's 0.0.post50+g0f76baaae) is
  no version; docs a major version behind PyPI's newest are said to be (pytz's 2014.10)
- a package that names no docs site: the README of its release (PyPI's record of it), in
  Markdown or reStructuredText, cut into entries by its headings; raw HTML and files from
  this computer never get in; NAME==VERSION: that release's README; never when a place the
  docs may be did not answer (a rate limit): said so, nothing indexed; a home page behind a
  login, or listed without https://, is not such a place; "UNKNOWN" (old tools' word for no
  README) is no README
- odd cases: a source repository or a PyPI page given as the docs' address (said so, nothing
  read); a download stopped by an earlier docsearch (kept as "sphinx") goes on; a whole page's
  entry (Go's package) does not take the source link of an entry on it
"""
from __future__ import annotations

import contextlib
import html
import io
import json
import os
import re
import sys
import tempfile
import zlib
from pathlib import Path

if "DOCSEARCH_DATA" not in os.environ:
    os.environ["DOCSEARCH_DATA"] = tempfile.mkdtemp(prefix="docsearch-source-")

import httpx  # noqa: E402

from docsearch import cli, web  # noqa: E402

SITES: dict[str, dict[str, tuple[int, bytes, dict]]] = {}   # host -> path -> (status, body, headers)
ASKED: list[str] = []


def answer(request: httpx.Request) -> httpx.Response:
    ASKED.append(str(request.url))
    status, body, headers = SITES.get(request.url.host, {}).get(request.url.raw_path.decode(), (404, b"no", {}))
    return httpx.Response(status, content=body, headers=headers)


def page(title: str, body: str = "", repo: str = "", root: str | None = None) -> tuple[int, bytes, dict]:
    link = f'<a href="https://{repo}">Source on GitHub</a>' if repo else ""
    hint = f' data-content_root="{root}"' if root is not None else ""      # (as Sphinx 7.2+ writes)
    return 200, (f"<html{hint}><head><title>{title}</title></head><body><nav>{link}</nav><main><h1>{title}</h1>"
                 f"<p>{f'What {title} is about, said plainly. ' * 6}</p>{body}</main></body></html>").encode(), {}


def inventory(project: str, lines: list[str], version: str = "1.0") -> tuple[int, bytes, dict]:
    return 200, (f"# Sphinx inventory version 2\n# Project: {project}\n# Version: {version}\n"
                 "# The remainder of this file is compressed using zlib.\n").encode() \
        + zlib.compress("".join(f"{x}\n" for x in lines).encode()), {}


def api_page(name: str, functions: list[str], repo: str = "") -> tuple[int, bytes, dict]:
    dl = "".join(f"<dl class='py function'><dt id='{name}.{f}'>{name}.{f}(x)</dt><dd><p>Does {f} to x.</p></dd></dl>"
                 for f in functions)
    return page(f"{name} reference", dl, repo)


def sphinx_site(host: str, root: str, repo: str = "", project: str = "Docs", version: str = "1.0") -> None:
    """A Sphinx site: its inventory lists its pages (std:doc) and one API object."""
    SITES.setdefault(host, {}).update({
        f"{root}objects.inv": inventory(project, ["index std:doc -1 index.html Home",
                                                  "guide std:doc -1 guide.html Guide",
                                                  f"{project.lower()}.run py:function 1 guide.html#{project.lower()}.run -"],
                                        version),
        root: page(f"{project} docs", '<a href="guide.html">Guide</a>', repo),
        f"{root}index.html": page(f"{project} docs", '<a href="guide.html">Guide</a>', repo),
        f"{root}guide.html": api_page(project.lower(), ["run"], repo),
    })


def pypi(name: str, urls: dict[str, str], summary: str = "A package.") -> None:
    SITES.setdefault("pypi.org", {})[f"/pypi/{name}/json"] = (200, json.dumps(
        {"info": {"name": name, "summary": summary, "version": "1.0", "project_urls": urls}}).encode(), {})


def github(repo: str, homepage: str) -> None:
    SITES.setdefault("api.github.com", {})[f"/repos/{repo}"] = (200, json.dumps(
        {"full_name": repo, "homepage": homepage}).encode(), {})


CODE = """def one(x):
    return x


@cache
def two(x,
        y):
    total = x + y
    return total


def three():
    pass
"""


def coded_site() -> None:
    """Docs whose entries link to their code (as numpy's do), at release v2.0.0."""
    pypi("coded", {"Documentation": "https://coded.example/", "Source": "https://github.com/c/coded"})
    blob = "https://github.com/c/coded/blob/v2.0.0"
    dl = "".join(f"<dl class='py function'><dt id='coded.{f}'>coded.{f}(x)<a class='reference external' "
                 f"href='{blob}/coded/{file}{lines}'></a></dt><dd><p>Does {f}.</p></dd></dl>"
                 for f, file, lines in (("one", "core.py", "#L1-L2"), ("two", "core.py", "#L5"),
                                        ("other", "other.py", "#L1-L2"), ("notes", "docs/notes.md", "")))
    SITES["coded.example"] = {
        "/objects.inv": inventory("Coded", ["index std:doc -1 index.html Home", "api std:doc -1 api.html API"]
                                  + [f"coded.{f} py:function 1 api.html#coded.{f} -"
                                     for f in ("one", "two", "other", "notes", "wide")]),
        "/": page("Coded", '<a href="api.html">API</a>', "github.com/c/coded"),
        "/index.html": page("Coded", '<a href="api.html">API</a>', "github.com/c/coded"),
        "/api.html": page("API", dl + f'<p>See <a href="{blob}/examples/demo.py">an example</a>.</p>'
                          # a multi-line signature (polars): its parameters in a <dl> inside the <dt>
                          "<dl class='py function'><dt id='coded.wide'>coded.wide(<dl><dd><em>a</em>,</dd>"
                          f"<dd><em>b</em></dd></dl>)<a class='reference external' href='{blob}/coded/wide.py#L1'></a>"
                          "</dt><dd><p>Takes two.</p></dd></dl>"),
    }
    SITES.setdefault("raw.githubusercontent.com", {}).update({
        "/c/coded/v2.0.0/coded/core.py": (200, CODE.encode(), {}),
        "/c/coded/v2.0.0/coded/other.py": (200, b"def other(x):\n    return -x\n", {}),
        "/c/coded/v2.0.0/coded/wide.py": (200, b"def wide(a, b):\n    return a, b\n", {}),
        "/c/coded/v2.0.0/examples/demo.py": (200, b"print('not an entry')\n", {}),
    })


def versions_sites() -> None:
    """Docs that state no version (their inventory's is empty)."""
    for name, ref in (("refd", "py-3.1.0"), ("jaxy", "main")):
        pypi(name, {"Documentation": f"https://{name}.example/", "Source": f"https://github.com/v/{name}"})
        SITES[f"{name}.example"] = {
            "/objects.inv": inventory(name, ["index std:doc -1 index.html Home", "api std:doc -1 api.html API",
                                             f"{name}.f py:function 1 api.html#{name}.f -"], ""),
            "/": page(name, '<a href="api.html">API</a>', f"github.com/v/{name}"),
            "/index.html": page(name, '<a href="api.html">API</a>', f"github.com/v/{name}"),
            "/api.html": page("API", f"<dl class='py function'><dt id='{name}.f'>{name}.f()<a class='reference external' "
                                     f"href='https://github.com/v/{name}/blob/{ref}/{name}.py#L1'></a></dt>"
                                     "<dd><p>F.</p></dd></dl>")}
        SITES.setdefault("raw.githubusercontent.com", {})[f"/v/{name}/{ref}/{name}.py"] = (200, b"def f():\n    pass\n", {})
    pypi("menu", {"Documentation": "https://menu.example/", "Source": "https://github.com/v/menu"})
    SITES["pypi.org"]["/pypi/menu/json"] = (200, json.dumps({"info": {"name": "menu", "summary": "", "version": "2.0.3",
        "project_urls": {"Documentation": "https://menu.example/", "Source": "https://github.com/v/menu"}}}).encode(), {})
    sphinx_site("menu.example", "/", "github.com/v/menu", "Menu", version="")
    SITES["menu.example"]["/"] = page("Menu", "<script>DOCUMENTATION_OPTIONS.theme_switcher_version_match = '2';</script>",
                                      "github.com/v/menu")


README_MD = """# Readmd

Encode and decode names.

## Usage

Call `encode` on a name.

## Options

The `strict` option refuses odd names.
"""
README_RST = """Readrst
=======

Reads things.

Install
-------

Run the installer.

.. raw:: html

   <script>alert(1)</script><b>RAWHTML</b>

.. include:: /etc/hosts

Configure
---------

Set the options.
"""


def readme_sites() -> None:
    """Packages that name no docs site: their README is their documentation."""
    for name, text, kind, versions in (("readmd", README_MD, "text/markdown", ("3.20", "3.10")),
                                       ("readrst", README_RST, "text/x-rst", ("1.0",))):
        pypi(name, {"Source": f"https://github.com/r/{name}"})
        github(f"r/{name}", "")
        info = {"name": name, "summary": "Reads.", "version": versions[0], "description": text,
                "description_content_type": kind, "project_urls": {"Source": f"https://github.com/r/{name}"}}
        SITES["pypi.org"][f"/pypi/{name}/json"] = (200, json.dumps({"info": info}).encode(), {})
        for v in versions:
            older = {**info, "version": v, "description": text.replace("Encode", f"Version {v}: encode")}
            SITES["pypi.org"][f"/pypi/{name}/{v}/json"] = (200, json.dumps({"info": older}).encode(), {})


def busy_site() -> None:
    """A package whose docs site answers "too many requests" (behind a bot check, as Read the Docs)."""
    pypi("busy", {"Documentation": "https://busy.readthedocs.io/", "Source": "https://github.com/b/busy"})
    SITES["pypi.org"]["/pypi/busy/json"] = (200, json.dumps({"info": {
        "name": "busy", "summary": "", "version": "1.0", "description": "# Busy\n\nA README.",
        "description_content_type": "text/markdown",
        "project_urls": {"Documentation": "https://busy.readthedocs.io/", "Source": "https://github.com/b/busy"}}}).encode(), {})
    github("b/busy", "https://busy.readthedocs.io/")
    SITES["busy.readthedocs.io"] = {p: (429, b"<title>Just a moment...</title>", {"server": "cloudflare", "cf-mitigated": "challenge"})
                                    for p in ("/", "/objects.inv", "/search/search_index.json", "/search.json")}
    # its first page answers, and says where its docs begin; its inventory there does not (a limit)
    pypi("busy2", {"Documentation": "https://busy2.example/en/stable/", "Source": "https://github.com/b/busy2"})
    github("b/busy2", "https://busy2.example/")
    SITES["busy2.example"] = {"/en/stable/": page("Busy2", "", "github.com/b/busy2", "./"),
                              "/en/stable/objects.inv": (429, b"slow down", {})}
    # an old docs page in PyPI (unchecked), and the site the repository names does not answer
    pypi("busy3", {"Documentation": "https://old.example/", "Source": "https://github.com/b/busy3"})
    github("b/busy3", "https://busy.readthedocs.io/")
    sphinx_site("old.example", "/", "", "Old")


def shared_sites() -> None:
    """A package of a repository many packages share, whose website lists them all; and two
    with no docs site, a home page behind a login, and one listed without https://."""
    pypi("cloudy-thing", {"Repository": "https://github.com/g/monorepo/tree/main/packages/cloudy-thing"})
    github("g/monorepo", "https://docs.cloud.example/python/reference")
    SITES["docs.cloud.example"] = {
        "/thing": (302, b"", {"location": "https://cloud.example/thing"}),     # the product, not the package
        "/python/reference": page("Reference", '<a href="/thing">Thing docs</a> '
                                               '<a href="/docs">Docs</a> <a href="/docs/get-started">Get started</a> '
                                               '<a href="/python/reference/other/latest/">other docs</a> '
                                               '<a href="/python/reference/thing/latest/">thing docs</a>'),
        "/python/reference/thing/latest/": page("Thing", '<a href="usage">Usage</a>'),
        "/python/reference/thing/latest/usage": page("Thing usage"),
        "/docs": page("All docs"), "/docs/get-started": page("Get started")}
    SITES["cloud.example"] = {"/thing": page("Thing, the product", '<a href="/">Home</a>', "github.com/g/monorepo")}
    for name, home in (("locked", "https://login.example/zone"), ("noscheme", "noscheme.example.io/home/")):
        SITES["pypi.org"][f"/pypi/{name}/json"] = (200, json.dumps({"info": {
            "name": name, "summary": "", "version": "1.0", "description": f"# {name}\n\nIts README.",
            "description_content_type": "text/markdown", "home_page": home}}).encode(), {})
        SITES["pypi.org"][f"/pypi/{name}/1.0/json"] = SITES["pypi.org"][f"/pypi/{name}/json"]
    SITES["login.example"] = {"/zone": (401, b"log in", {})}
    SITES["pypi.org"]["/pypi/unknownreadme/json"] = (200, json.dumps({"info": {
        "name": "unknownreadme", "summary": "UNKNOWN", "version": "0.1", "description": "UNKNOWN",
        "home_page": "https://gone.example/"}}).encode(), {})


def odd_version_sites() -> None:
    pypi("scmdev", {"Documentation": "https://scmdev.readthedocs.io/en/latest/", "Source": "https://github.com/s/scmdev"})
    sphinx_site("scmdev.readthedocs.io", "/en/latest/", "github.com/s/scmdev", "Scmdev", version="0.0.post50+g0f76baaae.d20260923")
    SITES["pypi.org"]["/pypi/olddocs/json"] = (200, json.dumps({"info": {
        "name": "olddocs", "summary": "", "version": "2025.2", "project_urls": {
            "Documentation": "https://olddocs.example/", "Source": "https://github.com/o/olddocs"}}}).encode(), {})
    sphinx_site("olddocs.example", "/", "github.com/o/olddocs", "Olddocs", version="2014.10")
    # PyPI points at docs pinned to an old version; the newest sit next to them
    SITES["pypi.org"]["/pypi/pinned/json"] = (200, json.dumps({"info": {
        "name": "pinned", "summary": "", "version": "2.1", "project_urls": {
            "Documentation": "https://pinned.example/en/1.0/", "Source": "https://github.com/p/pinned"}}}).encode(), {})
    sphinx_site("pinned.example", "/en/1.0/", "github.com/p/pinned", "Pinned", version="1.0")
    sphinx_site("pinned.example", "/en/2.1/", "github.com/p/pinned", "Pinned", version="2.1")
    # code on a host whose robots.txt asks programs not to fetch it
    pypi("labbed", {"Documentation": "https://labbed.example/", "Source": "https://gitlab.com/l/labbed"})
    SITES["labbed.example"] = {
        "/objects.inv": inventory("Labbed", ["index std:doc -1 index.html Home", "labbed.f py:function 1 index.html#labbed.f -"]),
        "/": page("Labbed", "<dl class='py function'><dt id='labbed.f'>labbed.f()<a class='reference external' "
                            "href='https://gitlab.com/l/labbed/-/blob/v1.0/labbed.py#L1'></a></dt><dd><p>F.</p></dd></dl>",
                  "gitlab.com/l/labbed"),
        "/index.html": page("Labbed", "<dl class='py function'><dt id='labbed.f'>labbed.f()<a class='reference external' "
                                      "href='https://gitlab.com/l/labbed/-/blob/v1.0/labbed.py#L1'></a></dt><dd><p>F.</p></dd></dl>",
                            "gitlab.com/l/labbed")}
    SITES["gitlab.com"] = {"/robots.txt": (200, b"User-agent: *\nDisallow: /l/labbed/-/raw/\n", {}),
                           "/l/labbed/-/raw/v1.0/labbed.py": (200, b"def f():\n    pass\n", {})}


def cppreference() -> None:
    """A tiny cppreference: every C++ standard on one site, C++23 its current one."""
    prose = "<p>" + "This page describes part of the C++ language and its standard library. " * 6 + "</p>"
    wiki = lambda title, body: (200, (f"<html><head><title>{title}</title></head><body><h1>{title}</h1>"   # noqa: E731
                                      f"<div id='mw-content-text'>{body}{prose}</div></body></html>").encode(), {})
    SITES["en.cppreference.com"] = {
        "/cpp": wiki("C++ reference", '<a href="/cpp/23">C++23</a> <a href="/cpp/26">C++26</a> '
                                      '<a href="/cpp/utility/format/format">std::format</a> '
                                      '<a href="/cpp/memory/auto_ptr">std::auto_ptr</a>'),
        "/cpp/23": wiki("C++23", "<p>The current revision of the C++ standard.</p>"),
        "/cpp/26": wiki("C++26", "<p>The next generation of the C++ standard.</p>"),
        "/cpp/utility/format/format": wiki("std::format", "<table><tr class='t-dcl t-since-cxx20'><td><pre>std::string "
                                                          "format(fmt);</pre></td><td>(since C++20)</td></tr></table>"
                                                          "<p>Formats things.</p>"),
        "/cpp/memory/auto_ptr": wiki("std::auto_ptr", "<table><tr class='t-dcl t-until-cxx17'><td><pre>class auto_ptr;"
                                                      "</pre></td><td>(removed in C++17)</td></tr></table><p>Old.</p>")}


def setup_sites() -> None:
    cppreference()
    odd_version_sites()
    shared_sites()
    busy_site()
    readme_sites()
    versions_sites()
    coded_site()
    # docs and repository point at each other; the first page says where the docs begin
    pypi("alpha", {"Documentation": "https://alpha.readthedocs.io/en/stable/guide.html",
                   "Source": "https://github.com/alpha-org/alpha"})
    sphinx_site("alpha.readthedocs.io", "/en/stable/", "github.com/alpha-org/alpha", "Alpha")
    SITES["alpha.readthedocs.io"]["/en/stable/guide.html"] = page("Guide", "", "github.com/alpha-org/alpha", "./")
    github("alpha-org/alpha", "https://alpha.readthedocs.io/")
    # a home page that links to its docs on the same site
    pypi("homey", {"Homepage": "https://homey.example/", "Source": "https://github.com/h/homey"})
    github("h/homey", "https://homey.example")
    SITES["homey.example"] = {"/": page("Homey", '<a href="https://docs.homey.example/en/latest/">Docs</a>')}
    sphinx_site("docs.homey.example", "/en/latest/", "", "Homey")
    # an umbrella site in PyPI; the repository names the real docs
    pypi("wsp", {"Documentation": "https://umbrella.example/", "Source": "https://github.com/hyper/wsp"})
    sphinx_site("umbrella.example", "/", "", "Umbrella")
    github("hyper/wsp", "https://wsp.readthedocs.io/")
    SITES["wsp.readthedocs.io"] = {"/": (302, b"", {"location": "http://umbrella.example/projects/wsp/"})}
    SITES["umbrella.example"]["/projects/wsp/"] = (302, b"", {"location": "http://umbrella.example/projects/wsp/en/stable/"})
    sphinx_site("umbrella.example", "/projects/wsp/en/stable/", "", "Wsp")
    # docs on a site under the one the repository names
    pypi("sci", {"Documentation": "https://docs.sci.example/doc/sci/", "Source": "https://github.com/sci/sci"})
    github("sci/sci", "https://sci.example")
    sphinx_site("docs.sci.example", "/doc/sci/", "", "Sci")
    # only the repository in PyPI; its website moved to /main/
    pypi("tri", {"Homepage": "https://github.com/tri-lang/tri"})
    github("tri-lang/tri", "https://tri.example/")
    SITES["tri.example"] = {"/": (200, b'<html><head><meta http-equiv="refresh" content="0; URL=https://tri.example/main/'
                                      b'index.html"></head></html>', {})}
    sphinx_site("tri.example", "/main/", "", "Tri", version="")
    # a guess that links the repository, and one that does not
    pypi("guessy", {"Source": "https://github.com/g/guessy"})
    github("g/guessy", "")
    sphinx_site("guessy.readthedocs.io", "/en/stable/", "github.com/g/guessy", "Guessy")
    SITES["guessy.readthedocs.io"]["/"] = (302, b"", {"location": "/en/stable/"})    # as Read the Docs does
    pypi("squat", {"Source": "https://github.com/s/squat"})
    github("s/squat", "")
    sphinx_site("squat.readthedocs.io", "/en/stable/", "github.com/other/thing", "Squat")
    SITES["squat.readthedocs.io"]["/"] = (302, b"", {"location": "/en/stable/"})
    # neither way
    pypi("plain", {"Documentation": "https://plain.example/", "Source": "https://github.com/p/plain"}, "Plain files.")
    github("p/plain", "")
    sphinx_site("plain.example", "/", "", "Plain")
    # GitHub's questions used up
    pypi("limited", {"Documentation": "https://limited.example/", "Source": "https://github.com/l/limited"})
    SITES.setdefault("api.github.com", {})["/repos/l/limited"] = (
        403, b'{"message": "API rate limit exceeded"}', {"x-ratelimit-remaining": "0"})
    sphinx_site("limited.example", "/", "", "Limited")
    # an inventory of the API only (mkdocstrings), and the rest of the site
    pypi("fast", {"Documentation": "https://fast.example/", "Source": "https://github.com/f/fast"})
    SITES["fast.example"] = {
        "/objects.inv": inventory("Fast", ["fast.App py:class 1 reference/app/#fast.App -",
                                           "fast.App.run py:method 1 reference/app/#fast.App.run -",
                                           "fast.route py:function 1 reference/route/#fast.route -"]),
        "/": page("Fast", '<a href="tutorial/one/">One</a> <a href="tutorial/two/">Two</a> '
                          '<a href="reference/app/">App</a> <a href="reference/route/">route</a>', "github.com/f/fast"),
        "/tutorial/one/": page("First steps", '<a href="../two/">next</a>'),
        "/tutorial/two/": page("Second steps", '<a href="../../reference/app/">App</a>'),
        "/reference/app/": page("App", "<dl class='py class'><dt id='fast.App'>class fast.App</dt><dd><p>An app.</p>"
                                       "<dl class='py method'><dt id='fast.App.run'>run()</dt><dd><p>Runs it.</p></dd></dl>"
                                       "</dd></dl>"),
        "/reference/route/": page("route", "<dl class='py function'><dt id='fast.route'>fast.route(path)</dt>"
                                           "<dd><p>A route.</p></dd></dl>"),
    }
    # a search index only (Zensical), and no index at all
    pypi("zen", {"Documentation": "https://zen.example/", "Source": "https://github.com/z/zen"})
    SITES["zen.example"] = {"/search.json": (200, b'{"config": {}, "items": []}', {}),
                            "/": page("Zen", '<a href="guide/">Guide</a>', "github.com/z/zen"),
                            "/guide/": page("Zen guide")}
    pypi("md", {"Documentation": "https://md.example/guide/", "Source": "https://github.com/m/md"})
    SITES["md.example"] = {"/guide/": page("Md guide", '<a href="more/">More</a>', "github.com/m/md"),
                           "/guide/more/": page("Md more")}


def check(ok: bool, what: str) -> None:
    print(("ok    " if ok else "FAIL  ") + what, flush=True)
    if not ok:
        sys.exit(1)


def run(*argv: str, terminal: bool = False) -> str:
    said = io.StringIO()
    stdin = sys.stdin
    sys.stdin = stdin if terminal else io.StringIO()      # no terminal to ask in
    try:
        with contextlib.redirect_stderr(said), contextlib.redirect_stdout(said):
            cli.main(list(argv))
    except SystemExit:
        pass
    finally:
        sys.stdin = stdin
    return said.getvalue()


def meta(sid: str) -> dict:
    try:
        return json.loads((cli.HOME / sid / "meta.json").read_text(encoding="utf-8"))
    except OSError:
        return {}


def titles(sid: str) -> list[str]:
    return sorted(e.title for e in cli.load(sid)[1])


def main() -> None:
    data = Path(os.environ["DOCSEARCH_DATA"])
    cli.CONFIG = data / "packages.toml"
    cli._CLIENT = httpx.Client(transport=httpx.MockTransport(answer), follow_redirects=False)
    cli.RETRY_WAITS = (0, 0, 0)                      # (answers that say "wait": no waiting here)
    setup_sites()

    ASKED.clear()
    cli.HOME.mkdir(parents=True, exist_ok=True)
    said = run("add", "alpha", "--no-embed")
    m = meta("alpha@1.0")
    found_with = ASKED[:ASKED.index("https://alpha.readthedocs.io/en/stable/objects.inv") + 1]
    check(m.get("repo") == "github.com/alpha-org/alpha" and "they link to" in m.get("verified", "")
          and "Index the docs" not in said and not any("api.github.com" in u for u in ASKED),
          "docs that link to their repository: taken, no question, the repository kept, GitHub not asked")
    check(len(found_with) == 3, f"a page that says where its docs begin: found with one question more ({found_with})")
    run("add", "byaddr=https://alpha.readthedocs.io/en/stable/", "--no-embed")
    m = meta("byaddr")
    check(m.get("repo") == "github.com/alpha-org/alpha" and m.get("kind") == "sphinx",
          f"docs added by address: read as they are; their repository from their links, named back ({m.get('repo')})")
    run("add", "cloudy-thing", "--no-embed")
    m = meta("cloudy-thing")
    check(m.get("root") == "https://docs.cloud.example/python/reference/thing/latest/" and "Thing usage" in titles("cloudy-thing"),
          f"a site many packages share: the docs its link names for the package, read page by page ({m.get('root')})")
    m = (run("add", "homey", "--no-embed"), meta("homey@1.0"))[1]
    check(m.get("root") == "https://docs.homey.example/en/latest/" and "names this site" in m.get("verified", ""),
          "a home page that links to its docs on the same site: those, checked")
    said = run("add", "wsp", "--no-embed")
    m = meta("wsp@1.0")
    check(m.get("root") == "https://umbrella.example/projects/wsp/en/stable/" and "names this site" in m.get("verified", ""),
          f"PyPI points at an umbrella site; the repository names the real docs: those ({m.get('root')})")
    m = (run("add", "sci", "--no-embed"), meta("sci@1.0"))[1]
    check(m.get("root") == "https://docs.sci.example/doc/sci/" and "names this site" in m.get("verified", ""),
          "docs on a site under the one the repository names: checked")
    m = (run("add", "tri", "--no-embed"), meta(f"tri@nightly-{__import__('time').strftime('%Y-%m-%d')}"))[1]
    check(m.get("root") == "https://tri.example/main/" and m.get("repo") == "github.com/tri-lang/tri",
          "only the repository in PyPI: its website, whose first page says 'go to /main/', found and checked")
    said = run("add", "guessy", "--no-embed")
    check("(a guess)" in said and meta("guessy@1.0").get("root") == "https://guessy.readthedocs.io/en/stable/",
          "a guessed address that links to the repository: used")
    said = run("add", "squat", "--no-embed")
    check(not meta("squat") and not meta("squat@1.0") and "Could not find docs" in said and "Index the docs" not in said,
          "a guessed address that does not: dropped, without a question")
    said = run("add", "plain", "--no-embed")
    check(not meta("plain@1.0") and "could not be checked" in said and "Plain files." in said and "--yes" in said,
          "docs that link neither way: asked; without a terminal not taken, and said how")
    run("add", "plain", "--no-embed", "--yes")
    check(meta("plain@1.0").get("verified") == "you said yes", "with --yes: taken, kept as 'you said yes'")
    said = run("add", "limited", "--no-embed")
    check(said.count("could not be asked") == 1 and "could not be checked" in said and not meta("limited@1.0"),
          "GitHub's questions used up: said once; the docs' own links checked; not taken unchecked")

    ASKED.clear()
    run("add", "fast", "--no-embed")
    m, names = meta("fast@1.0"), titles("fast@1.0")
    api_reads = [ASKED.count(f"https://fast.example/reference/{p}/") for p in ("app", "route")]
    check(m.get("kind") == "sphinx" and {"First steps", "Second steps"} <= set(names)
          and any("fast.App.run" in t for t in names) and any("fast.route" in t for t in names) and api_reads == [1, 1],
          f"an inventory of the API only: its objects, then the rest of the site; API pages read once "
          f"({api_reads}; {names})")
    run("add", "zen", "--no-embed")
    run("add", "md", "--no-embed")
    check(meta("zen").get("kind") == "website" and "Zen guide" in titles("zen")
          and meta("md").get("root") == "https://md.example/guide/" and "Md more" in titles("md"),
          "a search index only, or no index: the site page by page")
    source_code()
    versions()
    readmes()
    standards_download()
    said = run("add", "busy", "--no-embed")
    check(not cli.copies("busy") and "Could not reach" in said and "nothing indexed" in said and "README" not in said,
          "a place the docs may be did not answer (a rate limit): said so, nothing indexed, not the README instead")
    for name in ("locked", "noscheme"):
        said = run("add", name, "--no-embed")
        check(meta(f"{name}@1.0").get("kind") == "readme",
              f"a home page behind a login, or listed without https:// ({name}): nothing there, so the README")
    said = run("add", "busy2", "--no-embed")
    check(not cli.copies("busy2") and "Could not reach" in said and "pages" not in said,
          "docs whose inventory did not answer (a limit): said so; not read page by page instead")
    said = run("add", "busy3", "--no-embed", "--yes")
    check(not cli.copies("busy3") and "Could not reach" in said and "could not be checked" in said,
          "unchecked docs, while the site the repository names did not answer: not taken, not even with --yes")
    odd_cases()
    print("all good")


def odd_cases() -> None:
    said = run("add", "unknownreadme", "--no-embed")
    check(not cli.copies("unknownreadme") and "Could not find docs" in said,
          "a README of 'UNKNOWN' (old tools' word for none): no README, said so")
    for addr, what in (("https://github.com/alpha-org/alpha", "a source repository"),
                       ("https://pypi.org/project/alpha/", "a PyPI page"), ("https://bitbucket.org/", "a page of bitbucket.org")):
        ASKED.clear()
        said = run("add", f"wrongaddr={addr}", "--no-embed")
        check(not meta("wrongaddr") and f"{what}, not docs" in said and not ASKED,
              f"a repository, a PyPI page or a code host's page as the docs' address: said what it is, nothing read ({addr})")
    crawl = cli.HOME / "oldsx" / "crawl"                 # a download an earlier docsearch stopped
    crawl.mkdir(parents=True, exist_ok=True)
    (crawl / "plan.json").write_text(json.dumps({"plan": {"kind": "sphinx", "url": "https://alpha.readthedocs.io/en/stable/"},
                                                 "spec": "oldsx", "how": "sphinx"}), encoding="utf-8")
    said = run("add", "oldsx", "--no-embed")
    m = meta("oldsx") or meta("oldsx@1.0")
    check("going on where it stopped" in said and m.get("kind") == "sphinx" and m.get("count", 0) > 0,
          f"a download stopped by an earlier docsearch (kept as 'sphinx') goes on ({m.get('kind')}, {m.get('count')} entries)")
    from docsearch import pages
    package = "<h1>tar</h1><p>Package tar.</p>"
    member = ("<h3 id='Reader'>type <a class='Documentation-source' "
              "href='https://cs.opensource.google/go/go/+/go1.0:src/tar/reader.go;l=10'>Reader</a></h3><p>Reads.</p>")
    check(pages.source_link(package + member, True) is None and pages.source_link(member, True).endswith(";l=10"),
          "a whole page's entry (Go's package) does not take the source link of an entry on it; the entry does")


def readmes() -> None:
    said = run("add", "readmd", "--no-embed")
    m, names = meta("readmd@3.20"), titles("readmd@3.20")
    check(m.get("kind") == "readme" and m.get("version") == "3.20" and "README is its documentation" in said
          and any("Usage" in t for t in names) and any("Options" in t for t in names)
          and (cli.HOME / "readmd@3.20" / "pages" / "index.html.gz").exists(),
          f"no docs site: the README of the newest release, cut by its headings and kept for reading ({names})")
    run("add", "readmd==3.10", "--no-embed")
    check("Version 3.10" in " ".join(e.text for e in cli.load("readmd@3.10")[1]),
          "NAME==VERSION: that release's README")
    run("add", "readrst", "--no-embed")
    names = titles("readrst@1.0")
    page = __import__("gzip").decompress((cli.HOME / "readrst@1.0" / "pages" / "index.html.gz").read_bytes()).decode()
    texts = " ".join(e.text for e in cli.load("readrst@1.0")[1])
    check(any("Install" in t for t in names) and any("Configure" in t for t in names)
          and "RAWHTML" not in page + texts and "<script" not in page and "localhost" not in page + texts,
          f"reStructuredText: made into a page and entries; its raw HTML and a file include never get in ({names})")


def versions() -> None:
    day = __import__("time").strftime("%Y-%m-%d")
    run("add", "refd", "--no-embed")
    check(meta("refd@3.1.0").get("version") == "3.1.0", "the release the source links name: refd@3.1.0 (py-3.1.0)")
    run("add", "jaxy", "--no-embed")
    m = meta(f"jaxy@nightly-{day}")
    check(m.get("version") == "nightly" and m.get("after") == "1.0",
          f"links to main: development docs, a nightly of the day, after PyPI's newest release ({m})")
    m = meta(f"tri@nightly-{day}")                    # (added above)
    check(m.get("version") == "nightly", f"an address at /main/: development docs, a nightly of the day ({m.get('version')})")
    run("add", "menu", "--no-embed")
    check(meta("menu@2.0.3").get("version") == "2.0.3", "a version menu's '2', made exact by PyPI's newest release, 2.0.3")
    check(meta("zen").get("release") == "1.0" and "version" not in {k for k, v in meta("zen").items() if v},
          "nothing says: the day shows, and PyPI's newest release then is kept to say so")
    run("add", "scmdev", "--no-embed")
    m = meta(f"scmdev@nightly-{day}")
    check(m.get("version") == "nightly" and not cli.copies("scmdev") == [],
          f"a build tool's made-up version (0.0.post50+g...) is no version: development docs here, a nightly ({cli.copies('scmdev')})")
    said = run("add", "pinned", "--no-embed")
    check(cli.copies("pinned") == ["pinned@2.1"] and "its docs are at https://pinned.example/en/2.1/" in said,
          "PyPI points at docs of an old version: the newest release's docs next to them, said so")
    ASKED.clear()
    said = run("add", "labbed", "--no-embed")
    check(meta("labbed@1.0").get("source", {}).get("stored") == 0 and "robots.txt" in said
          and not any("/-/raw/" in u for u in ASKED),
          "code on a host that asks programs not to fetch it (robots.txt): its link only, nothing fetched")
    said = run("add", "olddocs", "--no-embed")
    check(cli.copies("olddocs") == ["olddocs@2014.10"] and "PyPI's newest release is 2025.2" in said,
          "docs a major version behind PyPI's newest: kept as what they are, and said so")
    said = run("update")
    check("jaxy: you have" in said and "jaxy: nightly docs change often" not in said,
          "search update pulls development-only docs anew (not only a note)")


def source_code() -> None:
    raw = "https://raw.githubusercontent.com/c/coded/v2.0.0/"
    ASKED.clear()
    run("add", "coded", "--no-embed")
    m = meta("coded@1.0")
    code_asks = [u for u in ASKED if u.startswith(raw)]
    check(m.get("source") == {"files": 3, "stored": 3, "repo": "github.com/c/coded", "ref": "v2.0.0"}
          and sorted(code_asks) == [raw + "coded/core.py", raw + "coded/other.py", raw + "coded/wide.py"],
          f"the code the entries link to: stored, each file once; not the docs' sources nor other links ({code_asks})")
    folder = cli.HOME / "coded@1.0" / "source"
    for f in folder.iterdir():
        f.unlink()
    stop = {"why": "ctrl+c"}                          # stopped before it starts: nothing (or one) stored
    first = cli.download_sources("coded@1.0", 1, stop)
    ASKED.clear()
    again = cli.download_sources("coded@1.0", 4)
    check(first is None and again and again["stored"] == 3 and len(ASKED) <= 3
          and len(set(ASKED)) == len(ASKED), f"stopped half way, it goes on, nothing fetched twice ({ASKED})")

    lib = web.Library()
    by_name = {e.title.split(" ")[0]: i for i, e in enumerate(lib.index.entries) if lib.sid_of[i] == "coded@1.0"}
    one, two = lib.source(by_name["coded.one"]), lib.source(by_name["coded.two"])
    entry = lib.entry(by_name["coded.one"])
    text = {k: html.unescape(re.sub(r"<[^>]+>", "", d["html"])) for k, d in (("one", one), ("two", two))}
    check(entry["code"]["stored"] and entry["repo"] == "github.com/c/coded"
          and (one["start"], one["end"]) == (1, 2) and "return x" in text["one"]
          and (two["start"], two["end"]) == (5, 9) and "return total" in text["two"] and "three" not in text["two"]
          and lib.source(by_name["coded.notes"]) is None and lib.entry(by_name["coded.notes"])["code"] is None
          and lib.source(by_name["coded.wide"])["path"] == "coded/wide.py",
          "the page shows an entry's code: a range as linked; from one line, its block; a multi-line signature's; "
          "none for docs sources")

    meta_f = cli.HOME / "coded@1.0" / "meta.json"
    old = json.loads(meta_f.read_text(encoding="utf-8"))
    del old["source"]                                 # a copy from before docsearch kept code
    meta_f.write_text(json.dumps(old), encoding="utf-8")
    for f in folder.iterdir():
        f.unlink()
    ASKED.clear()
    said = run("add", "coded", "--no-embed")
    check("you have this version already" in said and meta("coded@1.0").get("source", {}).get("stored") == 3
          and not any(u.endswith("api.html") for u in ASKED),
          "a copy from before: search add NAME stores its code, without reading its pages again")


def standards_download() -> None:
    from docsearch import standards
    ASKED.clear()
    said = run("add", "cpp", "--no-embed")
    read = [u for u in ASKED if "cppreference" in u and not u.endswith((".txt", ".xml"))]
    check(cli.copies("cpp") == ["cpp@23"] and standards.have_base("cpp") and not (cli.HOME / "cpp").exists()
          and "downloaded once" in said and len(read) >= 5,
          f"search add cpp: the site of every standard downloaded once, kept aside; C++23's copy made ({cli.copies('cpp')})")
    ASKED.clear()
    run("add", "cpp==17", "--no-embed")
    names = sorted(e.title for e in cli.iter_entries("cpp@17"))
    check(cli.copies("cpp") == ["cpp@23", "cpp@17"] and not any("cppreference" in u for u in ASKED)
          and not any("format" in t for t in names) and not any("auto_ptr" in t for t in names),
          f"search add cpp==17: made from it, nothing downloaded; C++17 has no std::format nor std::auto_ptr ({names})")


if __name__ == "__main__":
    main()
