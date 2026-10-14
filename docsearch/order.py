"""The order to list a source's entries in before you search: the order the docs are read.

Pages come in table-of-contents order and, within a page, its sections and API entries in
the order they appear on it. Nothing is downloaded: the order is read from the stored
offline pages.

- Pages are walked depth first from the docs' own contents: their sidebar (read once when
  the docs are added: `nav` in meta.json), Python's contents.html, the root page and the
  start pages in sources.py, following each page's links in order.
- Which links count as a page's children: on Sphinx pages, the table of contents
  (toctree) and API summary tables; elsewhere, links to pages below it (cppreference's
  cpp/container lists cpp/container/vector; std/vec/index.html lists std/vec/*), and
  only links in lists and tables, not in running text. Links across the docs ("see
  also", "as chapter 7 explains") are not followed, so the walk stays in order.
- Pages no walk reaches are then taken shallowest first, in natural order (ch2 before
  ch10), each walked the same way.

The result is cached next to the index (order.npy) and rebuilt when the entries change.
"""
from __future__ import annotations

import html
import re
import urllib.parse
from pathlib import Path
from typing import NamedTuple

import numpy as np

from docsearch import cli
from docsearch import pages as offline

ID = re.compile(r'\sid="([^"]+)"')
H1 = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.S | re.I)
TOC_CLASSES = ("toctree-wrapper", "autosummary")


def natural(s: str) -> list:
    """Sort key: ch2 before ch10."""
    return [(0, int(t), "") if t.isdigit() else (1, 0, t.lower()) for t in re.split(r"(\d+)", s) if t]


def rel_of(url: str, root: str) -> str | None:
    url = url.split("#")[0].split("?")[0]
    if not root or not url.startswith(root):
        return None
    return url[len(root):].strip("/") or "index.html"


def roots(meta: dict) -> list[tuple[str, str]]:
    """(address, folder of its pages) of each part of a copy with an address of its own: the
    docs' (pages/), then each official guide's (pages/guide/: meta["guides"]), the longest
    address first (a guide's may hold the docs': docs.pola.rs/ and docs.pola.rs/api/...)."""
    out = [(str(meta.get("root") or ""), "")] + [(g["root"], g["dir"] + "/") for g in meta.get("guides") or []]
    return sorted((r for r in out if r[0]), key=lambda r: -len(r[0]))


def rel_in(url: str, meta: dict) -> str | None:
    """A page's place among a copy's stored pages: reference/index.html; guide/user-guide/x."""
    for root, folder in roots(meta):
        rel = rel_of(url, root)
        if rel is not None:
            return folder + rel
    return None


def url_in(rel: str, meta: dict) -> str:
    """The address of a stored page (rel_in, the other way)."""
    for root, folder in roots(meta):
        if folder and rel.startswith(folder):
            return root + rel[len(folder):]
    return str(meta.get("root") or "") + rel


def stored_pages(pages_dir: Path) -> list[str]:
    if not pages_dir.exists():
        return []
    return [f.relative_to(pages_dir).as_posix()[:-3] for f in pages_dir.rglob("*.gz")     # (Windows:
            if "_images" not in f.relative_to(pages_dir).parts]                         # / too, not \\)


def below(parent: str, child: str) -> bool:
    """Is `child` inside the part of the docs `parent` introduces? An index page (or a
    page without .html) introduces its folder; another page only its own subfolder."""
    if parent.endswith("index.html"):
        folder = parent[: -len("index.html")]
    elif "." not in parent.rsplit("/", 1)[-1]:
        folder = parent + "/"
    else:
        folder = parent.rsplit(".", 1)[0] + "/"
    return child != parent and child.startswith(folder)


def page_links(html: str) -> tuple[list[str], list[str]]:
    """A page's links, in order: (those in its table of contents, the others that are
    not in running text)."""
    import lxml.html
    toc: list[str] = []
    nav: list[str] = []
    try:
        tree = lxml.html.fromstring(html)
    except Exception:  # noqa: BLE001 - an empty or broken page has no links
        return toc, nav
    for a in tree.iter("a"):
        href = a.get("href") or ""
        if not href or href.startswith("#"):
            continue
        around = list(a.iterancestors())
        if any(c in (x.get("class") or "") for x in around for c in TOC_CLASSES):
            toc.append(href)
            continue
        para = next((x for x in around if x.tag == "p"), None)     # in running text: the link is
        if para is None or 2 * len(a.text_content().strip()) >= len(para.text_content().strip()):
            nav.append(href)                                        # a small part of its paragraph
    return toc, nav


def start_urls(meta: dict) -> list[str]:
    """Where the docs begin: the root page, or the start of each part (sources.py)."""
    from docsearch import sources
    root = meta.get("root", "")
    name, _, want = str(meta.get("spec") or meta.get("name", "")).partition("==")
    known = sources.KNOWN.get(name) if meta.get("kind") == "known" else None
    if known and not want and known.get("version_from") and re.fullmatch(r"[\d.]+", known.get("version", "")):
        want = meta.get("version", "")                 # docs that follow releases (OCaml 5.5)
    plan = sources.resolve(name, want) if known else None
    out = [] if plan else [root]
    for part in ((plan.get("parts") or [plan]) if plan else []):
        starts = part.get("start") or part.get("url") or part.get("prefix") or part.get("root") or []
        out += [starts] if isinstance(starts, str) else list(starts)
    return [u for u in out if u.startswith(root)] + [g["root"] for g in meta.get("guides") or []]


def seeds(meta: dict) -> list[str]:
    """The docs' own starting points, in order: sidebar, contents pages, starts."""
    out = ["contents.html"] + list(meta.get("nav") or []) + ["index.html"] + start_urls(meta)
    return [r for r in (s if not s.startswith("http") else rel_in(s, meta) for s in out) if r]


NAV = ("nav, aside, [role=navigation], .sidebar, .bd-sidebar, #sidebar, .sphinxsidebar, .wy-menu, "
       ".md-nav, .menu, .theme-doc-sidebar-container")


def fetch_nav(meta: dict) -> list[str]:
    """The docs' sidebar order: the links in the navigation of their start pages (mdBook's
    toc.html too), as addresses under the docs root. An online step, done when the docs are
    added; the offline pages do not keep the sidebar."""
    root = meta.get("root", "")
    if not root.startswith("http"):
        return []
    out: list[str] = []

    def take(soup, base: str, selector: str | None) -> None:
        for part in (soup.select(selector) if selector else [soup]):
            for a in part.find_all("a", href=True):
                u = urllib.parse.urljoin(base, a["href"]).split("#")[0]
                if rel_in(u, meta) is not None and u not in out:
                    out.append(u)
    for start in start_urls(meta):
        try:
            html, final = cli.http_get(start, timeout=20)
        except Exception:  # noqa: BLE001 - no sidebar: the walk does without
            continue
        soup = cli.make_soup(html)
        for frame in soup.select("iframe[src]"):           # mdBook: the sidebar is toc.html
            if "toc" in frame["src"]:
                try:
                    take(cli.make_soup(cli.http_get(urllib.parse.urljoin(final, frame["src"]), timeout=20)[0]),
                         urllib.parse.urljoin(final, frame["src"]), None)
                except Exception:  # noqa: BLE001
                    pass
        take(soup, final, NAV)
    return out


class Contents(NamedTuple):
    order: list[str]                     # stored pages in reading order
    anchors: dict[str, dict[str, int]]   # each page's anchors and their positions
    parent: dict[str, str | None]        # the page whose contents list it (None: a start)
    title: dict[str, str]                # its first heading
    by_nav: frozenset = frozenset()      # pages whose parent lists them only in its sidebar, below its
                                         # folder (not a table of contents): a parent by address


def page_order(sid: str, meta: dict) -> Contents:
    """The docs' contents, as their pages list each other (see above)."""
    pages_dir = cli.HOME / sid / "pages"
    stored = set(stored_pages(pages_dir))
    found: dict[str, dict[str, int]] = {}
    title: dict[str, str] = {}

    def text(rel: str) -> str:
        """A page, read once: its anchors and heading are kept, not its HTML (a big site's
        is gigabytes)."""
        page = offline.load_page(pages_dir, rel) or ""
        found[rel] = {m.group(1): m.start() for m in ID.finditer(page)}
        h1 = H1.search(page)
        title[rel] = " ".join(html.unescape(re.sub(r"<[^>]+>", "", h1.group(1))).split()) if h1 else ""
        return page

    def find(rel: str | None) -> str | None:
        """The stored page for an address: cuda-programming-guide/ -> .../index.html."""
        if rel is None:
            return None
        for c in (rel, rel + "/index.html", rel + ".html"):
            if c in stored:
                return c
        return None

    def links(rel: str, hrefs: list[str], only_below: bool) -> list[str]:
        out = []
        for h in hrefs:
            c = find(rel_in(urllib.parse.urljoin(url_in(rel, meta), h), meta))
            if c and c not in out and c != rel and (not only_below or below(rel, c)):
                out.append(c)
        return out

    by_nav: set[tuple[str, str]] = set()           # (a page, a page its sidebar lists below it)

    def children(rel: str) -> list[str]:
        toc, nav = page_links(text(rel))   # a hidden table of contents has no links: use the page's
        found = links(rel, toc, False)
        if found:
            return found
        found = links(rel, nav, True)
        by_nav.update((rel, c) for c in found)
        return found

    order: list[str] = []
    seen: set[str] = set()
    parent: dict[str, str | None] = {}

    def walk(start: str) -> None:
        stack: list[tuple[str, str | None]] = [(start, None)]
        while stack:
            rel, up = stack.pop()
            if rel in seen or rel not in stored:
                continue
            seen.add(rel)
            order.append(rel)
            parent[rel] = up
            stack += reversed([(c, rel) for c in children(rel) if c not in seen])

    for s in seeds(meta):
        if find(s):
            walk(find(s))
    for rel in sorted(stored - seen, key=lambda r: (r.count("/"), natural(r))):
        walk(rel)
    anchors = {rel: found[rel] for rel in order}           # (each page in the order was read)
    return Contents(order, anchors, parent, title, frozenset(r for r, up in parent.items() if (up, r) in by_nav))


def reading_order(sid: str, count: int | None = None) -> np.ndarray:
    """Entry numbers of one source in reading order (cached in order.npy; `count`, the
    number of entries, if known, saves reading them to check the cache)."""
    d = cli.HOME / sid
    cache, entries_f = d / "order.npy", d / "entries.json"
    if cache.exists() and cache.stat().st_mtime >= max(entries_f.stat().st_mtime, (d / "meta.json").stat().st_mtime):
        cached = np.load(cache, allow_pickle=False)
        if count is None or len(cached) == count:
            return cached
    meta = cli.load_meta(sid)
    locations = [e.location for e in cli.iter_entries(sid, keep=1)]     # (their addresses only)
    order, anchors = page_order(sid, meta)[:2]
    rank = {rel: k for k, rel in enumerate(order)}

    def page(loc: str) -> str:
        """The stored page of an address (user-guide/concepts/ -> .../index.html)."""
        rel = rel_in(loc, meta)
        if rel is None:
            return loc
        return next((c for c in (rel, rel + "/index.html", rel + ".html") if c in rank), rel)
    others = sorted({r for loc in locations if (r := page(loc)) not in rank}, key=natural)
    rank.update({r: len(order) + k for k, r in enumerate(others)})

    def key(i: int):
        loc = locations[i]
        rel = page(loc)
        anchor = urllib.parse.unquote(loc.partition("#")[2])
        where = anchors.get(rel, {})
        pos = -1 if not anchor else where.get(anchor, where.get(loc.partition("#")[2], 1 << 30))
        return rank[rel], pos, i
    out = np.array(sorted(range(len(locations)), key=key), dtype=np.int32)
    try:
        np.save(cache, out)
    except OSError:
        pass
    return out
