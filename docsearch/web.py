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
import gzip
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
from collections import Counter
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


def shown_name(e: cli.Entry) -> str:
    """An entry's name in the results: an API object's without its kind (numpy.sum)."""
    return cli.api_name(e.title) if e.kind not in cli.PAGE_KINDS else e.title


class Library:
    """Everything that is indexed, searchable, with its offline pages. Of each package the copy
    search uses is loaded (cli.in_use; with several and none chosen, the newest until you choose
    one), and another copy when a search first asks for it (the page's version menu)."""

    def __init__(self, extra: frozenset[str] = frozenset()) -> None:
        sids = [s for have in cli.groups().values() for s in have]      # (each package's newest first)
        if not sids:
            raise SystemExit("search: nothing is indexed yet. Run: search sync")
        self.meta = {s: json.loads((cli.HOME / s / "meta.json").read_text(encoding="utf-8")) for s in sids}
        self.default: set[str] = set()               # of each package, the copy search uses
        self.choose: set[str] = set()                # packages with several copies, none chosen
        for group, have in cli.groups().items():
            now, _ = cli.in_use(group)
            if now is None:
                self.choose.add(group)
            self.default.add(now or have[0])
        self.lock = threading.Lock()                 # one search at a time (the model), one load
        self.order: list[str] = []                   # the copies loaded, in the order they came
        self._browse_pos: tuple = (None, {})         # (index, entry -> place in index.browse)
        self._page_titles: tuple = (None, {})        # (index, a page's address -> its title)
        self._browse: tuple = (None, [])             # ((index, packages), the list before you type)
        self.summaries: dict[int, str] = {}
        self._covers: dict[str, dict] = {}          # copy -> what it describes
        self._marks: dict[int, dict] = {}           # entry -> its version marks
        self._complete: dict[int, dict | None] = {} # entry -> its example's completeness
        self.load(sorted(self.default | (set(extra) & set(sids))))
        self.sites: dict[str, tuple[str, Path]] = {}     # where each copy's pages are (a guide's: sid/guide)
        for s, m in self.meta.items():
            if str(m.get("root", "")).startswith("http"):
                self.sites[s] = (m["root"], cli.HOME / s / "pages")
                for g in m.get("guides") or []:
                    self.sites[f"{s}/{g['dir']}"] = (g["root"], cli.HOME / s / "pages" / g["dir"])
        self.image_types: dict[str, dict[str, str]] = {}
        self.pygments = pygments_css()
        self.index.search("warm up")                 # load caches before the first request

    def load(self, more: list[str]) -> None:
        """Index these copies too (the ones in use; later another one a search asks for). A
        copy stays loaded, and its entries keep their numbers: a new copy's come after them.
        So a result listed before, or a search still under way, still means the same entry."""
        order = self.order + [s for s in more if s not in self.order]
        vectors = any((cli.HOME / s / "emb.npy").exists() for s in order) and cli.model_cached()   # (a source
        # without vectors, embed = false or not made yet, is left out of search by meaning only)
        index = cli.Index(order, "hybrid" if vectors else "spell")
        ends = [first for first, _ in index.spans[1:]] + [len(index.entries)]
        self.sid_of = [sid for (first, sid), end in zip(index.spans, ends) for _ in range(end - first)]
        self.index, self.order = index, order       # (sid_of first: it covers the entries of both)

    def ensure(self, srcs: set[str]) -> None:
        """Copies a search asks for that are not loaded yet (another version, from the menu)."""
        new = sorted(s for s in srcs if s in self.meta and s not in self.order)
        if new:
            self.load(new)

    def use(self, sid: str) -> None:
        """The copy you chose for search, where several were and none was chosen (the page)."""
        group = sid.split("@")[0]
        cli.choose(sid)
        self.default = {s for s in self.default if s.split("@")[0] != group} | {sid}
        self.choose.discard(group)

    def info(self) -> dict:
        return {"app": "docsearch", "mode": self.index.mode,
                "sources": [{"id": s, "name": m.get("name", s), "version": self.label(s),
                             "note": self.note(s), "count": m.get("count", 0),
                             "offline": bool(m.get("pages")),
                             "about": m.get("about") or m.get("project") or "", "root": m.get("root", ""),
                             "group": s.split("@")[0], "default": s in self.default,
                             "choose": s.split("@")[0] in self.choose, "channel": cli.is_channel(s),
                             "kind": m.get("kind", ""), "added": m.get("created", ""), "repo": self.repo(s)}
                            for s, m in self.meta.items()]}

    def repo(self, sid: str) -> str:
        """Where a docs' source code is: as found when they were added; for docs we know, their
        profile; else the repository their entries' source links name."""
        return cli.copy_repo(self.meta[sid])

    def covers(self, sid: str) -> dict[str, str]:
        """What a copy describes (versions.covers): kept, it is asked once."""
        if sid not in self._covers:
            self._covers[sid] = cli.copy_covers(sid, self.meta[sid])
        return self._covers[sid]

    def label(self, sid: str) -> str:
        """The version shown next to the name: what the docs describe (2.5; C++98–C++26; in
        development, after 3.8.0); "" when they do not say."""
        return self.covers(sid)["label"]

    def note(self, sid: str) -> str:
        return self.covers(sid)["note"]

    def marks(self, i: int, sid: str) -> dict[str, str]:
        """What an entry says of its versions (versions.entry_marks): since C++20, added in 3.13."""
        from docsearch import sources, versions
        if i not in self._marks:
            m = self.meta[sid]
            lang = (sources.KNOWN.get(m.get("name", "")) or {}).get("standards", "") if m.get("kind") == "known" else ""
            e = self.index.entries[i]
            text = e.text if lang or i not in self.index.cut else self.full_text(i)
            self._marks[i] = versions.entry_marks(text, lang, page=e.kind in cli.PAGE_KINDS or e.kind == "module")
        return self._marks[i]

    def versioned(self, i: int, sid: str, project: dict[str, str] | None) -> dict:
        """An entry's marks, and what the project's version of its package (or language
        standard) should know: newer than it, removed in it, deprecated."""
        from docsearch import versions
        marks = self.marks(i, sid)
        mine = (project or {}).get(sid.split("@")[0], "")
        return {"marks": marks, "flags": versions.flags(marks, mine), "project": mine}

    def item(self, i: int, q: str, project: dict[str, str] | None = None) -> dict:
        e = self.index.entries[i]
        is_api = e.kind not in cli.PAGE_KINDS
        if is_api or not q:
            if i not in self.summaries:
                self.summaries[i] = cli.summary(e)
            text = self.summaries[i]
        else:                                        # a page's snippet is the query's: made each time
            text = cli.snippet(e, q)
        return {"id": i, "name": shown_name(e), "kind": e.kind,
                "source": self.sid_of[i], "api": is_api, "summary": text, "purpose": e.purpose,
                "complete": self.complete(i), **self.versioned(i, self.sid_of[i], project)}

    def complete(self, i: int) -> dict | None:
        """An example's (or a guide section's) code: complete, or what it needs (examples.py);
        None for entries without code it can read. Kept once found."""
        if i not in self._complete:
            from docsearch import examples
            e = self.index.entries[i]
            out = None
            if e.kind == "example" or (e.kind in cli.PAGE_KINDS and e.purpose in ("learn", "do") and "```" in e.text):
                m = self.meta[self.sid_of[i]]
                name = m.get("name", "")
                base = re.sub(r" › Examples?$", "", e.title)
                out = examples.needs(self.full_text(i), "cpp" if name in ("cpp", "c") else "", name,
                                     cli.api_name(base) if e.kind == "example" else "")
            self._complete[i] = out
        return self._complete[i]

    def search(self, q: str, srcs: set[str], offset: int, limit: int, ai: bool = False,
               project: dict[str, str] | None = None, mode: str = "what") -> dict:
        """`mode`: "what" (plain search: the reference, explanations) or "how" (tutorials,
        guides, how-tos, examples and the functions that do it first): cli.MODES. With no
        query, the docs organized (how: its learn and do parts)."""
        q = q.strip()
        mode = mode if mode in cli.MODES else "what"
        m = re.match(r"how\s+(?=\S)", q, re.I)          # "how merge two tables": how, as search how
        if m:
            q, mode = q[m.end():], "how"
        srcs = srcs or self.default                  # never two versions of one package at once
        with self.lock:
            self.ensure(srcs)
            index, sid_of = self.index, self.sid_of     # this search's, even if another loads more
        rest, phrases, patterns = cli.parse_strict(q)
        plain_q = " ".join([rest] + phrases).strip()     # what ranks the results (and the AI reads)
        if not q:                                    # no query: all the docs, each package by purpose
            ids = self.browse(index, sid_of, srcs)   # (learn, do, look up, understand), in reading order
            if mode == "how":
                ids = [i for i in ids if index.entries[i].purpose in cli.MODES["how"]]
        elif phrases or patterns:                    # strict: every match, the best first
            with self.lock:
                try:
                    found = index.strict(phrases, patterns, index.full_text)
                except ValueError as e:
                    return {"q": q, "total": 0, "ai": None, "items": [], "error": str(e)}
                hits = index.search(plain_q, limit=3000, mode=mode) if plain_q else []
            allowed = {i for i in found if (not srcs or sid_of[i] in srcs) and not index.duplicate(i)
                       and (mode == "how" or index.entries[i].purpose in cli.MODES[mode])}
            ranked = [i for i, _, _ in hits if i in allowed]
            if self._browse_pos[0] is not index:
                self._browse_pos = (index, {i: k for k, i in enumerate(index.browse)})
            pos = self._browse_pos[1]
            seen = set(ranked)
            ids = ranked + sorted((i for i in allowed if i not in seen), key=lambda i: pos.get(i, len(pos)))
        else:
            with self.lock:
                hits = index.search(q, limit=3000 if srcs else cli.SHOW, mode=mode)
            ids = [i for i, _, _ in hits if not srcs or sid_of[i] in srcs][:cli.SHOW]
        state = None
        if ai and plain_q:                           # the model reorders the top results
            from docsearch import rerank
            model = rerank.get()
            if model is None:
                state = "not installed"
            else:
                s = model.scores(plain_q, [self.rerank_text(i) for i in ids[:rerank.TOP]])
                with self.lock:
                    exact = set(index.rank_name(plain_q)[0])
                ids = rerank.reorder(ids, s, exact)
                state = "ranked"
        with self.lock:
            fixed = index.correction(plain_q) if plain_q else None
        items = [self.item(i, q, project) for i in ids[offset:offset + limit]]
        where = self.where(index, ids[:offset + limit])
        for it in items:                             # two of one name: where each is
            if it["id"] in where:
                it["where"] = where[it["id"]]
        return {"q": q, "total": len(ids), "ai": state, "corrected": fixed, "mode": mode, "items": items}

    def where(self, index, ids: list[int]) -> dict[int, str]:
        """Where each result is that has another of its name (in its package) in the list: its
        page's title (pandas' Sorting sections: Comparison with R, Essential basic
        functionality); else its folder (polars' GroupBy: reference/dataframe and
        reference/lazyframe); else its parameters (CUDA's cudaMallocAsync overloads). The first
        of these that tells them all apart."""
        if self._page_titles[0] is not index:
            self._page_titles = (index, {e.location: re.sub(r" \(page\)$", "", e.title)
                                         for e in index.entries if "#" not in e.location})
        named: dict[tuple[str, str], list[int]] = {}
        for i in ids:
            named.setdefault((shown_name(index.entries[i]), self.sid_of[i]), []).append(i)
        out = {}
        for (name, sid), same in named.items():
            if len(same) < 2:
                continue
            ways = [[self.place(index, i, name, way) for i in same] for way in ("page", "folder", "params")]
            best = next((w for w in ways if len(set(w)) == len(w)), max(ways, key=lambda w: len(set(w))))
            out.update(zip(same, best))
        return out

    def place(self, index, i: int, name: str, way: str) -> str:
        e = index.entries[i]
        page, _, part = e.location.partition("#")
        if way == "params":
            sig = re.search(r"```\w*\n(.*?)\n", e.text)
            m = re.search(re.escape(name.rsplit(".", 1)[-1]) + r"\s*(\(.*\))", sig.group(1)) if sig else None
            return m.group(1) if m else ""
        title = self._page_titles[1].get(page) if part else None
        if way == "page" and title and title != name:
            return title
        root = self.meta[self.sid_of[i]].get("root") or ""
        path = (page[len(root):] if root and page.startswith(root) else urllib.parse.urlparse(page).path).strip("/")
        return "/".join(path.split("/")[:-1]) or path

    def browse(self, index, sid_of: list[str], srcs: set[str]) -> list[int]:
        """The entries listed before you type: each package's learn, do, look up and understand
        entries, each in the order the docs are read (organize.py, order.py)."""
        from docsearch import organize
        key = (index, frozenset(srcs))
        if self._browse[0] != key:                   # (made once: scrolling asks again and again)
            rank = {p: k for k, p in enumerate(organize.PURPOSES)}
            where = {sid: k for k, (_, sid) in enumerate(index.spans)}
            ids = [i for i in index.browse if not srcs or sid_of[i] in srcs]
            self._browse = (key, sorted(ids, key=lambda i: (where[sid_of[i]],
                                                            rank.get(index.entries[i].purpose, len(rank)))))
        return self._browse[1]

    def contents(self, srcs: set[str]) -> list[dict]:
        """Each package's table of contents by purpose (organize.contents), with how many of
        its entries each purpose has."""
        from docsearch import organize
        srcs = srcs or self.default
        with self.lock:
            self.ensure(srcs)
        have: dict[tuple[str, str], int] = {}
        for i, e in enumerate(self.index.entries):
            have[self.sid_of[i], e.purpose] = have.get((self.sid_of[i], e.purpose), 0) + 1
        out = []
        for sid in [s for s in self.order if s in srcs]:
            groups = organize.contents(sid)
            for g in groups:
                g["count"] = have.get((sid, g["purpose"]), 0)
            out.append({"id": sid, "name": self.meta[sid].get("name", sid), "version": self.label(sid),
                        "groups": groups})
        return out

    def rerank_text(self, i: int) -> str:
        e = self.index.entries[i]
        return f"{cli.api_name(e.title)} ({e.kind}, {e.source})\n{cli.plain(e.text)[:1200]}"

    def entry(self, i: int, project: dict[str, str] | None = None) -> dict:
        e = self.index.entries[i]
        sid = self.sid_of[i]
        is_api = e.kind not in cli.PAGE_KINDS
        name = cli.api_name(e.title) if is_api else e.title
        html_text, page, code = None, None, None
        key, site = self.site_of(sid, e.location)
        if site:
            rel, _, anchor = e.location[len(site[0]):].partition("#")
            rel = rel or "index.html"
            stored = self.as_standard(sid, offline.load_page(site[1], rel))
            if stored is not None:
                own = e.kind != "example" or re.fullmatch(r"Examples?", anchor)   # (an example made from
                html_text = fragment(stored, anchor, e.kind) if own else None     # an entry: its own text)
                page = {"path": f"{key}/{rel}", "at": anchor}
                code = self.code_of(sid, html_text, is_api) if html_text is not None else None
        if html_text is None:                        # no offline page: draw the indexed text
            base = e.location if cli.safe_url(e.location) else "https://invalid.invalid/"
            html_text = offline.sanitize(MD.render(self.full_text(i)), base)
        return {"id": i, "name": name, "kind": e.kind, "source": sid, "api": is_api,
                "version": self.guide_label(sid, key) or self.label(sid), "code": code, "repo": self.repo(sid),
                **self.versioned(i, sid, project), "complete": self.complete(i),
                "html": offline.localize_links(html_text, self.sites, sid), "page": page,
                "web": e.location if cli.safe_url(e.location) else None,
                "import": import_line(name, e.kind) if is_api else None}

    def site_of(self, sid: str, location: str) -> tuple[str, tuple[str, Path] | None]:
        """Which of a copy's sites an address is in: its docs' (key sid), or one of its guides'
        (sid/guide), the longest address first; (sid, None) if none."""
        keys = [k for k in self.sites if k == sid or k.startswith(sid + "/")]
        for k in sorted(keys, key=lambda k: -len(self.sites[k][0])):
            if location.startswith(self.sites[k][0]):
                return k, self.sites[k]
        return sid, None

    def guide_label(self, sid: str, key: str) -> str:
        """A guide's entries are of no version: "guide, as of 2026-10-12" (guides.py)."""
        if key == sid:
            return ""
        g = next((g for g in self.meta[sid].get("guides") or [] if f"{sid}/{g['dir']}" == key), None)
        if g is None:
            return ""
        return f"{g['title']}, as of {g['asof']}" if g.get("asof") else g["title"]

    def as_standard(self, sid: str, html: str | None) -> str | None:
        """A stored page as a copy of one standard shows it (cpp@17: C++17's rows only)."""
        from docsearch import versions
        std = self.meta[sid].get("standard") or {}
        if not html or not std:
            return html
        return offline.for_standard(html, std["lang"], versions.standard_year(std["lang"] + std["edition"]))

    def code_of(self, sid: str, html_text: str, api: bool) -> dict | None:
        """An entry's source link (from its docs), and whether its code is stored with them."""
        link = offline.source_link(html_text, api)
        got = offline.raw_source(link) if link else None
        if got is None:
            return None
        span = offline.source_lines(link)
        return {"url": link, "repo": got[1], "ref": got[2], "path": got[3],
                "lines": (f"{span[0]}–{span[1]}" if span[1] else str(span[0])) if span else "",
                "stored": offline.source_file(cli.HOME / sid / "source", got[0]).exists()}

    def source(self, i: int) -> dict | None:
        """The code an entry documents, from the copy stored with its docs: its lines (a range;
        from one line, its block; else the whole file), highlighted."""
        entry = self.entry(i)
        code = entry.get("code")
        if not code or not code["stored"]:
            return None
        raw = offline.raw_source(code["url"])[0]
        text = gzip.decompress(offline.source_file(cli.HOME / entry["source"] / "source", raw).read_bytes())
        lines = text.decode("utf-8", "replace").splitlines()
        start, end = code_span(lines, offline.source_lines(code["url"]))
        from pygments import highlight
        from pygments.formatters import HtmlFormatter
        from pygments.lexers import TextLexer, get_lexer_for_filename
        from pygments.util import ClassNotFound
        try:
            lexer = get_lexer_for_filename(code["path"], stripnl=False)
        except ClassNotFound:
            lexer = TextLexer(stripnl=False)
        html = highlight("\n".join(lines[start - 1:end]), lexer,
                         HtmlFormatter(linenos="inline", linenostart=start, cssclass="highlight"))
        ref = code["ref"]                         # a branch (main; 3.14, CPython's): the code of that day
        branch = not re.search(r"\d", ref) or re.fullmatch(r"v?\d+\.\d+", ref) is not None
        day = str(self.meta[entry["source"]].get("created", ""))[:10]
        return {**code, "start": start, "end": end, "of": len(lines), "html": html, "asof": day if branch else ""}

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
        stored = self.as_standard(sid, offline.load_page(site[1], rel))
        if stored is None:
            return None
        title = BeautifulSoup(stored, "lxml").find("h1")
        key = f"{sid}/{rel.split('/')[0]}"                       # (a guide's page: sid/guide/...)
        web = self.sites[key][0] + rel.split("/", 1)[1] if key in self.sites and "/" in rel else site[0] + rel
        return {"path": path, "source": sid, "version": self.guide_label(sid, key) or self.label(sid),
                "title": title.get_text(" ", strip=True) if title else rel,
                "html": offline.localize_links(stored, self.sites, sid), "web": web}


def project_of(text: str) -> dict[str, str]:
    """A project's versions as the page passes them: "cpp:C++17;python:3.12"."""
    out = {}
    for part in text.split(";")[:200]:
        name, _, version = part.partition(":")
        if re.fullmatch(r"[\w.+-]{1,100}", name) and re.fullmatch(r"[\w.+-]{1,40}", version):
            out[name] = version
    return out


HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")
MAX_CODE_LINES = 600


def code_span(lines: list[str], span: tuple[int, int | None] | None) -> tuple[int, int]:
    """The lines to show (1-based, inclusive): a range as linked; from one line, its block
    (what follows it more indented, and the line that closes it); else the whole file."""
    if not span or not lines:
        return 1, min(len(lines), MAX_CODE_LINES * 5)
    start = max(1, min(span[0], len(lines)))
    if span[1]:
        return start, max(start, min(span[1], len(lines), start + MAX_CODE_LINES))

    def indent(line: str) -> int:
        return len(line) - len(line.lstrip())
    first, end = lines[start - 1], start
    while first.lstrip().startswith("@") and end < len(lines):    # decorators: on to their def
        end += 1
        first = lines[end - 1]
    for k in range(end, min(len(lines), start + MAX_CODE_LINES)):
        line = lines[k]
        if line.strip() and indent(line) <= indent(first):
            if line.strip()[0] not in ")]}":
                break
            end = k + 1                                              # the line that closes it, and
            if not line.rstrip().endswith((":", "{")):               # on if it opens the body
                break                                                # (def f(\n a,\n) -> int:)
            continue
        end = k + 1
    while end > start and not lines[end - 1].strip():             # no blank lines at the end
        end -= 1
    return start, end


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
                return self.json(lib.search(qs.get("q", "")[:300], srcs, offset, limit, qs.get("ai") == "1",
                                            project_of(qs.get("proj", "")), qs.get("mode", "what")))
            m = re.fullmatch(r"/api/source/(\d+)", url.path)
            if m:
                i = int(m.group(1))
                data = lib.source(i) if 0 <= i < len(lib.index.entries) else None
                return self.json(data) if data else self.json({"error": "no stored source"}, 404)
            m = re.fullmatch(r"/api/entry/(\d+)", url.path)
            if m:
                i = int(m.group(1))
                if not 0 <= i < len(lib.index.entries):
                    return self.json({"error": "no such entry"}, 404)
                return self.json(lib.entry(i, project_of(qs.get("proj", ""))))
            if url.path == "/api/contents":
                return self.json({"sources": lib.contents({s for s in qs.get("src", "").split(",") if s})})
            if url.path == "/api/page":
                data = lib.page(qs.get("path", ""))
                return self.json(data) if data else self.json({"error": "page not stored"}, 404)
            return self.send(404, b"not found", "text/plain")
        except Exception as ex:  # noqa: BLE001 - keep serving; the log has the details
            print(f"{time.strftime('%H:%M:%S')} error on {self.path}: {ex!r}", file=sys.stderr, flush=True)
            return self.json({"error": "internal error"}, 500)

    def do_POST(self) -> None:
        """What the page can change: remove a source (wrong docs were matched), and choose the
        copy of a package search uses (several, none chosen).
        Only from the docsearch page itself: the Origin must be this server, and the
        request must carry a custom header, which other sites cannot send without asking
        this server first (CORS preflight), and it never says yes."""
        host = self.headers.get("Host", "")
        if (host not in self.hosts or self.headers.get("Origin") != f"http://{host}"
                or self.headers.get("X-Docsearch") != "1"):
            return self.send(403, b"forbidden", "text/plain")
        if self.path not in ("/api/remove", "/api/use"):
            return self.send(404, b"not found", "text/plain")
        try:
            size = int(self.headers.get("Content-Length", "0"))
            sid = json.loads(self.rfile.read(min(size, 1000)) or b"{}").get("source", "")
        except (ValueError, AttributeError):
            return self.json({"error": "bad request"}, 400)
        lib = self.library
        if sid not in lib.meta:
            return self.json({"error": "no such source"}, 404)
        if self.path == "/api/use":                  # the copy search uses, chosen in the page
            lib.use(sid)
            return self.json({"ok": True, "use": sid})
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


class Server(ThreadingHTTPServer):
    request_queue_size = 128       # a page asks for its images at once: 5 waiting (the default) drop some


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
            httpd = Server(("127.0.0.1", p), Handler)
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
                         stdin=subprocess.DEVNULL, cwd=str(cli.ROOT), **detach,
                         env={**os.environ, "DOCSEARCH_CONFIG": str(cli.CONFIG)})   # (choices it keeps go there)
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
