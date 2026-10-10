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

import re
import urllib.parse
from pathlib import Path

import numpy as np

from docsearch import cli
from docsearch import pages as offline

ID = re.compile(r'\sid="([^"]+)"')
TOC_CLASSES = ("toctree-wrapper", "autosummary")


def natural(s: str) -> list:
    """Sort key: ch2 before ch10."""
    return [(0, int(t), "") if t.isdigit() else (1, 0, t.lower()) for t in re.split(r"(\d+)", s) if t]


def rel_of(url: str, root: str) -> str | None:
    url = url.split("#")[0].split("?")[0]
    if not root or not url.startswith(root):
        return None
    return url[len(root):].strip("/") or "index.html"


def stored_pages(pages_dir: Path) -> list[str]:
    if not pages_dir.exists():
        return []
    return [str(f.relative_to(pages_dir))[:-3] for f in pages_dir.rglob("*.gz")
            if "_images" not in f.relative_to(pages_dir).parts]


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
    return [u for u in out if u.startswith(root)]


def seeds(meta: dict) -> list[str]:
    """The docs' own starting points, in order: sidebar, contents pages, starts."""
    root = meta.get("root", "")
    out = ["contents.html"] + list(meta.get("nav") or []) + ["index.html"] + start_urls(meta)
    return [r for r in (s if not s.startswith("http") else rel_of(s, root) for s in out) if r]


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
                if u.startswith(root) and u not in out:
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


def page_order(sid: str, meta: dict) -> tuple[list[str], dict[str, dict[str, int]]]:
    """(stored pages in reading order, each page's anchors and their positions)."""
    pages_dir = cli.HOME / sid / "pages"
    root = meta.get("root", "")
    stored = set(stored_pages(pages_dir))
    found: dict[str, dict[str, int]] = {}

    def text(rel: str) -> str:
        """A page, read once: its anchors are kept, not its HTML (a big site's is gigabytes)."""
        page = offline.load_page(pages_dir, rel) or ""
        found[rel] = {m.group(1): m.start() for m in ID.finditer(page)}
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
            c = find(rel_of(urllib.parse.urljoin(root + rel, h), root))
            if c and c not in out and c != rel and (not only_below or below(rel, c)):
                out.append(c)
        return out

    def children(rel: str) -> list[str]:
        toc, nav = page_links(text(rel))   # a hidden table of contents has no links: use the page's
        return links(rel, toc, False) or links(rel, nav, True)

    order: list[str] = []
    seen: set[str] = set()

    def walk(start: str) -> None:
        stack = [start]
        while stack:
            rel = stack.pop()
            if rel in seen or rel not in stored:
                continue
            seen.add(rel)
            order.append(rel)
            stack += reversed([c for c in children(rel) if c not in seen])

    for s in seeds(meta):
        if find(s):
            walk(find(s))
    for rel in sorted(stored - seen, key=lambda r: (r.count("/"), natural(r))):
        walk(rel)
    anchors = {rel: found[rel] for rel in order}           # (each page in the order was read)
    return order, anchors


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
    order, anchors = page_order(sid, meta)
    rank = {rel: k for k, rel in enumerate(order)}
    root = meta.get("root", "")
    others = sorted({r for loc in locations if (r := rel_of(loc, root) or loc) not in rank}, key=natural)
    rank.update({r: len(order) + k for k, r in enumerate(others)})

    def key(i: int):
        loc = locations[i]
        rel = rel_of(loc, root) or loc
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
