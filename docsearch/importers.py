"""Importers for documentation that is not a Sphinx or MkDocs site on PyPI.

    website   any documentation site: found through its llms.txt (clean Markdown pages,
              e.g. Mojo, MAX), its sitemap (e.g. MDN), or by following its links inside
              given address prefixes (e.g. cppreference, the OCaml manual, the Rust Book)
    rustdoc   Rust API docs: the standard library (doc.rust-lang.org) or any crate on
              docs.rs. Every item, and every type's own methods, becomes an entry.

Pages are cut into entries the way a reader looks things up: one entry per API item,
one per page, and one per section (h2/h3) so that tutorials and guides can be found by
what a section explains, not only by their title.

Downloads run in threads (waiting on the network) while the pages are cut into entries
in worker processes (one per core). Every page is stored for offline reading through a
Store, with its images (see pages.py). robots.txt is respected.
"""
from __future__ import annotations

import concurrent.futures as cf
import gzip
import json
import os
import re
import shutil
import time
import urllib.parse
import urllib.robotparser
from pathlib import Path

from docsearch import article, cli
from docsearch import pages as offline
from docsearch.cli import Entry, say

# --------------------------------------------------------------------------- storing pages


class Store:
    """Offline pages and images of one source, all under one address prefix (`root`)."""

    def __init__(self, sid: str, root: str) -> None:
        self.sid, self.root = sid, root
        self.dir = cli.HOME / sid / "pages"
        self.images: dict[str, str] = {}

    def reset(self) -> None:
        if self.dir.exists():
            shutil.rmtree(self.dir)
        self.dir.mkdir(parents=True, mode=0o700)

    def add_images(self, images: dict[str, str]) -> None:
        self.images.update(images)

    def finish(self, workers: int) -> None:
        cli.download_images(self.images, self.dir / "_images", workers)


def image_namer(sid: str, root: str, images: dict[str, str]):
    """The `image` callback for pages.sanitize: only images of the docs site itself."""
    host = urllib.parse.urlparse(root).netloc

    def image(url: str) -> str | None:
        if not cli.safe_url(url) or urllib.parse.urlparse(url).netloc != host:
            return None                                  # never third parties
        images[url] = offline.image_name(url)
        return f"/asset/{sid}/{images[url]}"
    return image


def store_page(sid: str, root: str, pages_dir: Path, url: str, main, real_url: str | None,
               images: dict[str, str]) -> None:
    """Sanitize the page's main content and keep it for offline reading."""
    rel = url.split("#")[0]
    if not rel.startswith(root):
        return
    rel = rel[len(root):] or "index.html"
    offline.keep_mathml(main)
    html = offline.sanitize(main, url, image_namer(sid, root, images), real_url)
    offline.save_page(pages_dir, rel, cli.clean(html))


# --------------------------------------------------------------------------- finding pages

def robots(root: str):
    """The site's robots.txt rules (a missing file allows everything), and the pause it asks
    for between pages (Crawl-delay; AWS: 5 s), which every download from it then keeps."""
    rp = urllib.robotparser.RobotFileParser()
    u = urllib.parse.urlparse(root)
    try:
        body, _ = cli.http_get(f"{u.scheme}://{u.netloc}/robots.txt", timeout=10)
        rp.parse(body.decode("utf-8", "replace").splitlines())
    except Exception:  # noqa: BLE001 - no robots.txt: everything allowed
        rp.parse([])
    delay = rp.crawl_delay(cli.USER_AGENT)
    if delay:
        cli.set_crawl_delay(u.netloc, float(delay))
        say(f"  {u.netloc} asks programs to wait {float(delay):g} s between pages (robots.txt): "
            f"about {3600 / float(delay):,.0f} pages an hour")
    return rp


MD_LINK = re.compile(r"\]\((\S+?)\)")


def from_llms(url: str, prefixes: list[str], limit: int) -> list[str]:
    """Pages listed in an llms.txt index (and the section indexes it points to): web pages,
    or Markdown pages (.md)."""
    seen_idx, pages, todo = set(), [], [url]
    while todo and len(pages) < limit:
        idx = todo.pop(0)
        if idx in seen_idx:
            continue
        seen_idx.add(idx)
        try:
            text = cli.http_get(idx)[0].decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            continue
        for href in MD_LINK.findall(text):
            # absolute links only: relative ones are cross-references inside full-text files
            if not href.startswith(("http://", "https://", "/")):
                continue
            u = urllib.parse.urljoin(idx, href).split("#")[0]
            if not cli.safe_url(u) or (prefixes and not any(u.startswith(p) for p in prefixes)):
                continue
            if re.search(r"/llms[\w-]*\.txt$", u):
                todo.append(u)                           # a section index
            elif not u.endswith(".txt") and u not in pages:
                pages.append(u)
    return pages[:limit]


def sitemap_locs(body: bytes) -> tuple[list[str], list[str]]:
    """(the sitemaps it lists, the pages it lists) of one sitemap file (maybe gzipped)."""
    if body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)[:cli.MAX_DOWNLOAD]
    locs = [m.decode("utf-8", "replace").strip() for m in re.findall(rb"<loc>\s*([^<\s]+)\s*</loc>", body)]
    return [u for u in locs if u.endswith((".xml", ".xml.gz"))], [u for u in locs if not u.endswith((".xml", ".xml.gz"))]


def from_sitemap(url: str, prefixes: list[str], limit: int) -> list[str]:
    """Pages in a sitemap (or sitemap index), inside the prefixes."""
    out, todo, seen = [], [url], set()
    while todo and len(out) < limit:
        sm = todo.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        try:
            maps, pages = sitemap_locs(cli.http_get(sm)[0])
        except Exception:  # noqa: BLE001
            continue
        todo += maps
        out += [u for u in pages if cli.safe_url(u) and any(u.startswith(p) for p in prefixes) and u not in out]
    return out[:limit]


def count_pages(rp, root: str, wanted, seconds: float = 15, most: int = 100) -> int | None:
    """How many pages a download will read, before it starts: the pages its sitemap lists
    that `wanted(url)` keeps; the sitemap of the docs' own folder (AWS: one per guide), else
    those robots.txt names. None if there is none, or it lists over `most` sitemaps or takes
    more than `seconds` to read (learn.microsoft.com lists 5,412: not worth asking for; the
    count then grows as pages turn up)."""
    origin = "{0.scheme}://{0.netloc}/".format(urllib.parse.urlparse(root))
    deadline = time.monotonic() + seconds

    def get(u: str) -> bytes:
        try:
            return cli.http_get_once(u, timeout=max(1.0, min(10.0, deadline - time.monotonic())))[0]
        except Exception:  # noqa: BLE001 - no such sitemap
            return b""
    for first in ([root + "sitemap.xml"] if root.endswith("/") and root != origin else [],
                  rp.site_maps() or [origin + "sitemap.xml"]):
        found, todo, seen = set(), list(first), set()
        with cf.ThreadPoolExecutor(max_workers=8) as ex:
            while todo and time.monotonic() < deadline:
                batch = [u for u in dict.fromkeys(todo) if u not in seen][:8]
                hosts = {urllib.parse.urlparse(u).netloc for u in batch}
                if any(cli.PACE.get(h, {}).get("gap", 0) > 0 for h in hosts):
                    batch = batch[:1]                    # a paced site: one at a time, each in time
                if time.monotonic() + max((cli.turn_in(urllib.parse.urlparse(u).netloc) for u in batch),
                                          default=0) >= deadline:
                    break                                # its turn comes too late
                todo = [u for u in todo if u not in batch and u not in seen]
                seen.update(batch)
                for body in ex.map(get, batch):
                    maps, pages = sitemap_locs(body)
                    todo += maps
                    found.update(normal(u) for u in pages if wanted(normal(u)))
                if len(seen) + len(todo) > most:
                    return None                          # too many to read for a count
        if todo:
            return None                                  # not read in time: no guess
        if found:
            return len(found)
    return None


STRIP = re.compile(r"@go[\d.]+(?=$|/)")            # pkg.go.dev/fmt@go1.27.1: the same page
# A whole section again on one page, for printing: Hugo/Docsy's /_print/ folders (on
# Kubernetes, 166 such pages were 71% of all entries, each a copy, one of them 23 MB), and
# pages a link calls a print copy (mdBook's print.html: "Print this book"). Not every
# print.html: Kotlin's is the documentation of its print() function.
ALL_IN_ONE = re.compile(r"/_print/")
PRINT_LINK = re.compile(r"\bprint (this|entire|whole) (book|section|chapter|page|guide)\b|\bprintable (version|page)\b", re.I)


def normal(url: str) -> str:
    """One address per page: no #fragment, no ?query, no version tag."""
    return STRIP.sub("", urllib.parse.urldefrag(url)[0].split("?")[0])


def moved(url: str, real: str, base: str) -> str | None:
    """Where the docs under `base` went, if `url` (under it) redirected to `real` and kept its
    place: cloud.google.com/kubernetes-engine/docs/ -> docs.cloud.google.com/kubernetes-engine/docs/
    (a new host), .../oracle-database/23/sqlrf/ -> .../oracle-database/26/sqlrf/ (a new
    release). None if it did not move, or went to another organization's site."""
    if not url.startswith(base) or real.startswith(base):
        return None
    rest = url[len(base):]
    if not real.endswith(rest) or cli.organization(urllib.parse.urlparse(real).netloc) != \
            cli.organization(urllib.parse.urlparse(base).netloc):
        return None
    new = real[:len(real) - len(rest)]
    if base.endswith("/") and not new.endswith("/"):         # .../sqlrf/index.html -> .../sqlrf/
        head, _, last = new.rpartition("/")
        new = head + "/" if "." in last else new + "/"
    return new if cli.safe_url(new) else None


# --------------------------------------------------------------------------- cutting pages

DROP = (".theme-doc-toc-mobile, .theme-doc-toc-desktop, .theme-doc-version-badge, "
        ".theme-doc-breadcrumbs, .pagination-nav, .theme-edit-this-page, .theme-last-updated, "
        ".editsection, .mw-editsection, #toc, .toc, .t-navbar, .t-template-editlink, .noprint, "
        ".breadcrumbs, .headerlink, button, .copy-button, .baseline-indicator, .on-github, "
        "#sidebar, .sidebar, .nav-chapters, .mobile-nav-chapters, #menu-bar, "
        # what the page itself says is not its content: hidden (but not a tab you can switch
        # to), and Google's "nocontent" (breadcrumbs, bookmark and feedback buttons)
        "[hidden]:not([role=tabpanel]), .nocontent, #site-user-feedback-footer, .awsdocs-page-banner")
MEMBER_SECTIONS = {"methods", "fields", "functions", "properties", "aliases", "comptime members",
                   "static methods", "instance methods", "static properties", "instance properties",
                   "constructors", "operators", "member functions", "associated functions"}
HEADING_JUNK = re.compile(r"\s*(¶|#|Copy item path|Copy)\s*$")
OCAMLDOC_ID = re.compile(r"^(VAL|TYPE|EXCEPTION|MODULE|MODTYPE|CLASS|CLASSTYPE|METHOD)(.+)$")
OCAMLDOC_KIND = {"VAL": "val", "TYPE": "type", "EXCEPTION": "exception", "MODULE": "module",
                 "MODTYPE": "module type", "CLASS": "class", "CLASSTYPE": "class type", "METHOD": "method"}
IDENT = re.compile(r"[A-Za-z_$][\w$]*")
NAV_RELS = {"contents", "toc", "index", "start", "first", "prev", "previous", "next", "last", "up",
            "chapter", "section", "subsection", "appendix", "glossary"}


def heading_text(h) -> str:
    text = h.get_text(" ", strip=True).replace("\u200b", "").replace("\ufeff", "")
    return HEADING_JUNK.sub("", " ".join(text.split()))


def api_title(title: str, pattern: str | None) -> str | None:
    """'std::vector<T,Allocator>::push_back' -> 'std::vector::push_back' when the page is an
    API page (its title matches the source's api pattern)."""
    if not pattern or not re.fullmatch(pattern, title):
        return None
    name = title
    for _ in range(5):
        name = re.sub(r"<[^<>]*>", "", name)             # template parameters
    name = re.sub(r"\s*::\s*", "::", name)
    return re.sub(r"\(\)$", "", name.strip()) or None


def section_parts(main):
    """(id, heading, html, level, parent h2 heading) for every h2/h3 that can be linked to."""
    out, current_h2 = [], ""
    for h in main.find_all(["h2", "h3"]):
        if h.name == "h2":
            current_h2 = heading_text(h)
        hid = h.get("id")
        sec = h.parent if h.parent is not None and h.parent.name == "section" else None
        if not hid and sec is not None:
            hid = sec.get("id")
        if not hid:                               # MediaWiki: <h3><span id=...>; others: <a name>
            inner = h.find(attrs={"id": True}) or h.find("a", attrs={"name": True})
            hid = inner and (inner.get("id") or inner.get("name"))
        if not hid:
            continue
        if sec is not None and sec.find(["h2", "h3"]) is h:
            body = "".join(str(c) for c in sec.children if c is not h)
        else:
            stop = {"h1", "h2"} if h.name == "h2" else {"h1", "h2", "h3"}
            body = []
            for sib in h.next_siblings:
                if getattr(sib, "name", None) in stop:
                    break
                body.append(str(sib))
            body = "".join(body)
        out.append((hid, heading_text(h), body, h.name, current_h2))
    return out


def website_page(sid: str, name: str, root: str, pages_dir: Path, url: str, html: bytes,
                 real_url: str, spec: dict) -> tuple[list[Entry], dict[str, str], list[str]]:
    """Cut one HTML page into entries, store it, and return the links it has (worker)."""
    soup = cli.make_soup(html)
    hrefs = [a["href"] for a in soup.find_all(["a", "area"], href=True) if not PRINT_LINK.search(
        " ".join((a.get_text(" ", strip=True), a.get("title") or "", a.get("aria-label") or "")))]
    # books whose table of contents is not a link: <link rel="contents" href="toc.htm"> and
    # rel="next" (Oracle, DocBook), or the frames of a frameset (old Javadoc; not an <iframe>:
    # mdBook's is its sidebar again)
    hrefs += [ln["href"] for ln in soup.find_all("link", href=True) if NAV_RELS & {r.lower() for r in ln.get("rel") or []}]
    hrefs += [f["src"] for f in soup.find_all("frame", src=True)]
    links = [normal(urllib.parse.urljoin(real_url, h)) for h in hrefs]
    cli.clean_soup(soup)                       # (after the links: chapter lists live in <nav>)
    for el in soup.select(DROP + (", " + spec["drop"] if spec.get("drop") else "")):
        el.decompose()
    # a saved article: its text without the site around it (a general method, see article.py)
    main = article.extract(soup) if spec.get("article") else None
    if main is None and spec.get("main"):
        main = soup.select_one(spec["main"])
    # the usual names of a page's main part: what the page calls its main part, as it is (a
    # chapter page may hold only its heading); a vaguer name only on an element with a tenth of
    # the page's text, not a small box that happens to share it (AWS: a feedback box "content")
    body = soup.body or soup
    least = len(body.get_text(" ", strip=True)) / 10
    for sel, vague in [("#mw-content-text", False), ("article.bd-article", False), ('div[role="main"]', False),
                       ("#main-col-body", False), ("main", False), ("article", True), ("#content", True),
                       (".content", True), ("div.body", True)] if main is None else []:
        main = max(soup.select(sel), key=lambda el: len(el.get_text(" ", strip=True)), default=None)
        if main is not None and (not vague or len(main.get_text(" ", strip=True)) >= least):
            break
        main = None
    if main is None:
        main = body
    h1 = main.find("h1") or soup.find("h1")
    title = heading_text(h1) if h1 else (soup.title.get_text(strip=True) if soup.title else url)
    entries: list[Entry] = []
    api = api_title(title, spec.get("api"))
    if spec.get("api_path"):
        m = re.search(spec["api_path"] + r"(.+?)/?$", urllib.parse.urlparse(url).path)
        if m:
            api = ".".join(p for p in m.group(1).split("/") if p)
    if api and spec.get("api_rename"):                   # git-commit -> git commit
        api = re.sub(spec["api_rename"][0], spec["api_rename"][1], api)
    page_md = cli.html_to_md(str(main))
    entries.append(Entry(title=api or title, kind=spec.get("api_kind", "api") if api else "page",
                         location=url, text=page_md[:cli.PREVIEW_CHARS], source=name))
    # OCaml (ocamldoc): every value, type, module... of the page
    module = Path(urllib.parse.urlparse(url).path).stem
    for span in main.find_all("span", id=OCAMLDOC_ID):
        m = OCAMLDOC_ID.match(span["id"])
        if m.group(2).startswith("ELT") or (m.group(1) == "MODULE" and m.group(2) == module):
            continue                               # constructors; the page's own module
        pre = span.find_parent("pre")
        info = pre.find_next_sibling() if pre is not None else None
        doc = cli.html_to_md(str(info)) if info is not None and "info" in (info.get("class") or []) else ""
        sig = " ".join((pre or span).get_text(" ", strip=True).split())
        entries.append(Entry(title=f"{module}.{m.group(2)}", kind=OCAMLDOC_KIND[m.group(1)],
                             location=f"{url}#{span['id']}", text=f"```ocaml\n{sig}\n```\n\n{doc}"[:cli.PREVIEW_CHARS],
                             source=name))
    # members named by a pattern on their headings (Go: <h4 id="Reader.Read">func (b *Reader) Read)
    if spec.get("member_re"):
        pkg = Path(urllib.parse.urlparse(url).path).name
        for h in main.find_all(spec.get("member_tag", "h4"), id=True):
            m = re.match(spec["member_re"], heading_text(h))
            if not m:
                continue
            g = m.groupdict()
            member = ".".join(x for x in (pkg, g.get("rtype"), g.get("name") or g.get("tname")) if x)
            body = []
            for sib in h.next_siblings:
                if getattr(sib, "name", None) in ("h2", "h3", "h4"):
                    break
                body.append(str(sib))
            kind = h.get("data-kind") or ("type" if g.get("tname") else "method" if g.get("rtype") else "function")
            text = f"```\n{heading_text(h)}\n```\n\n{cli.html_to_md(''.join(body))}"
            entries.append(Entry(title=member, kind=kind, location=f"{url}#{h['id']}",
                                 text=text[:cli.PREVIEW_CHARS], source=name))
    # options in a definition list (git commit: <dt id=...>--amend</dt><dd>...</dd>)
    if spec.get("options") and api:
        for dt in main.find_all("dt"):
            hid = dt.get("id") or (dt.find(attrs={"id": True}) or {}).get("id")
            term = " ".join(dt.get_text(" ", strip=True).split())
            if not hid or not term.startswith("-"):
                continue
            dd = dt.find_next_sibling("dd")
            text = f"```\n{api} {term}\n```\n\n{cli.html_to_md(str(dd)) if dd is not None else ''}"
            entries.append(Entry(title=f"{api} {term}", kind="option", location=f"{url}#{hid}",
                                 text=text[:cli.PREVIEW_CHARS], source=name))
    # sections: API pages list their members as sections (Mojo: "List.append")
    for hid, head, body, level, under in section_parts(main):
        # a member (List.append): an h3 under "Methods", "Fields"... of an API page
        member = (api and level == "h3" and under.lower() in MEMBER_SECTIONS
                  and IDENT.fullmatch(head.removesuffix("()")))
        entries.append(Entry(title=f"{api}.{head.removesuffix('()')}" if member else f"{api or title} › {head}",
                             kind="method" if member else "section", location=f"{url}#{hid}",
                             text=f"## {head}\n\n{cli.html_to_md(body)}"[:cli.PREVIEW_CHARS], source=name))
    images: dict[str, str] = {}
    store_page(sid, root, pages_dir, url, main, real_url, images)
    return entries, images, links


# A path segment naming a language (fr, pt_BR, zh_HANS-CN...) or a version (2.43.0, v1.2)
LANGUAGE = re.compile(r"(ar|bg|bn|ca|cs|da|de|el|es|et|fa|fi|fr|he|hi|hr|hu|id|it|ja|ko|lt|lv|ms|nb|nl|no|pl|"
                      r"pt|ro|ru|sk|sl|sr|sv|th|tr|uk|vi|zh)([-_][a-z0-9]{2,4}){0,2}", re.I)
VERSION_SEGMENT = re.compile(r"v?\d+(\.\d+)+")


def other_variant(url: str, keep: set[str]) -> bool:
    """Is this page another language's or another version's copy of the docs (git-scm:
    /docs/git-commit/fr, /docs/git-commit/2.43.0)? Only English and the version you asked
    for are read, unless the starting address itself is in that language or version."""
    for seg in urllib.parse.urlparse(url).path.split("/"):
        low = seg.lower()
        if low and low not in keep and (LANGUAGE.fullmatch(low) or VERSION_SEGMENT.fullmatch(low)):
            return True
    return False


def save_pages(name: str, sid: str, urls: list[str], workers: int, series: bool) -> tuple[list[Entry], cli.Failures]:
    """Articles and tutorials kept for reading offline (search save): each page's main text,
    split into sections; with `series`, the following parts too (its "next" links, same site,
    up to 50 pages). Stored with the collection's other pages; nothing else is touched."""
    store = Store(sid, "https://")
    store.dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    entries: list[Entry] = []
    fails = cli.Failures()
    todo, seen = list(urls), set()
    folder = {}                                  # a series stays in the folder it started in
    for u in urls:
        path = urllib.parse.urlparse(u).path
        folder[u] = u[: len(u) - len(path)] + (path if path.endswith("/") else path.rsplit("/", 1)[0] + "/")
    while todo and len(seen) < 50 * max(1, len(urls)):
        url = todo.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            html, real = cli.get_page_at(url)
        except Exception as e:  # noqa: BLE001
            fails.add(url, e)
            continue
        found, imgs, _ = website_page(sid, name, "https://", store.dir, url, html, real, {"article": True})
        if not found or len(re.findall(r"\w+", found[0].text)) < 100:   # no article of its own: the
            fails.add(url, cli.Failed("empty", url))                    # text is drawn by JavaScript
            stored = offline.page_file(store.dir, url.split("#")[0][len("https://"):])
            if stored is not None:
                stored.unlink(missing_ok=True)                          # and its page is not kept
            continue
        for e in found:
            e.kind = "tutorial" if e.kind in ("page", "api") else e.kind
        entries += found
        store.add_images(imgs)
        if series:
            nxt = next_part(html, real)
            start = folder.get(url)
            if nxt and start and nxt.startswith(start) and nxt not in seen:
                folder[nxt] = start
                todo.insert(0, nxt)
    if store.images:                             # keep the images of the pages saved before
        known = store.dir / "_images" / "images.json"
        kept = json.loads(known.read_text(encoding="utf-8")) if known.exists() else {}
        store.finish(workers)
        new = json.loads(known.read_text(encoding="utf-8")) if known.exists() else {}
        cli.write_atomic(known, json.dumps({**kept, **new}).encode())
    return entries, fails


def next_part(html: bytes, base: str) -> str | None:
    """The next page of a series: <link rel="next">, <a rel="next">, or a link titled Next."""
    soup = cli.make_soup(html)
    el = soup.find(["link", "a"], rel=lambda r: r and "next" in (r if isinstance(r, list) else [r]))
    if el is None:
        el = next((a for a in soup.find_all("a", href=True)
                   if re.fullmatch(r"\s*(next|next page|next part|next chapter|next lesson)\s*[»›→>]*\s*",
                                   a.get_text(" ", strip=True), re.I)), None)
    return normal(urllib.parse.urljoin(base, el["href"])) if el is not None and el.get("href") else None


def markdown_page(sid: str, name: str, root: str, pages_dir: Path, url: str, md_bytes: bytes,
                  spec: dict) -> tuple[list[Entry], dict[str, str], list[str]]:
    """A Markdown page from an llms.txt site: entries, plus an HTML copy for reading (worker)."""
    from markdown_it import MarkdownIt
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import TextLexer, get_lexer_by_name

    md = md_bytes.decode("utf-8", "replace")
    md = re.sub(r"\A---\n.*?\n---\n", "", md, flags=re.S)        # front matter
    title_m = re.search(r"^#\s+(.+)$", md, re.M)
    title = title_m.group(1).strip() if title_m else Path(urllib.parse.urlparse(url).path).stem

    def slug(text: str) -> str:
        return re.sub(r"[^\w\- ]", "", text.lower()).strip().replace(" ", "-")

    def fence(code: str, lang: str, _attrs) -> str:
        try:
            lexer = get_lexer_by_name((lang or "text").split()[0])
        except Exception:  # noqa: BLE001
            lexer = TextLexer()
        return highlight(code, lexer, HtmlFormatter(cssclass="highlight"))
    mdi = MarkdownIt("commonmark", {"html": False, "highlight": fence}).enable("table")
    tokens = mdi.parse(md)
    for i, t in enumerate(tokens):                                   # ids on headings
        if t.type == "heading_open" and i + 1 < len(tokens):
            t.attrSet("id", slug(tokens[i + 1].content))
    html = mdi.renderer.render(tokens, mdi.options, {})
    page_url = url
    api = api_title(title, spec.get("api")) if spec.get("api") else None
    if spec.get("api_path") and re.search(spec["api_path"], url):
        api = title
    entries = [Entry(title=api or title, kind="api" if api else "page", location=page_url,
                     text=md[:cli.PREVIEW_CHARS], source=name)]
    parts = re.split(r"^(#{2,3})\s+(.+)$", md, flags=re.M)
    for k in range(1, len(parts) - 2, 3):
        head, body = parts[k + 1].strip(), parts[k + 2]
        clean_head = re.sub(r"`", "", head).removesuffix("()")
        member = api and parts[k] == "###" and IDENT.fullmatch(clean_head)
        entries.append(Entry(title=f"{api}.{clean_head}" if member else f"{api or title} › {head}",
                             kind="method" if member else "section",
                             location=f"{page_url}#{slug(head)}", text=f"## {head}\n{body}"[:cli.PREVIEW_CHARS],
                             source=name))
    images: dict[str, str] = {}
    from bs4 import BeautifulSoup
    main = BeautifulSoup(f"<article>{html}</article>", "lxml").article
    store_page(sid, root, pages_dir, page_url, main, url, images)
    return entries, images, []


# --------------------------------------------------------------------------- the website importer

ROUND = 200                 # pages read, cut into entries and saved before the next ones
AGAIN = cli.TRANSIENT | {"offline", "dns"}       # failures a later try may not have
TRIES = 3                   # a page failing so goes back in the queue, up to this many tries in all
GONE = 10                   # a round whose pages all failed so (at least this many): the site is gone


def crawl_dir(sid: str) -> Path:
    """Where a website download keeps what it has read (entries.jsonl) and what is left
    (state.json), round by round, until it is finished."""
    return cli.HOME / sid / "crawl"


def unfinished(sid: str) -> dict | None:
    """A website download of `sid` that stopped before the end (ctrl+c, a lost connection):
    its state, to continue it. None if there is none."""
    try:
        return json.loads((crawl_dir(sid) / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def continues(sid: str, spec: dict) -> bool:
    """Is there a stopped download of these very docs (the same plan) to continue?"""
    state = unfinished(sid)
    return state is not None and state.get("plan") == json.loads(json.dumps(spec))


def ignore_ctrl_c() -> None:
    """Worker processes leave ctrl+c to the main one, which stops the download."""
    import signal
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def pages(n: int) -> str:
    return f"{n:,} page" + ("" if n == 1 else "s")


def duration(seconds: float) -> str:
    return (f"{seconds / 60:.0f} min" if seconds < 5400 else f"{seconds / 3600:.0f} hours" if seconds < 172800
            else f"{seconds / 86400:.1f} days")


def build_website(name: str, sid: str, spec: dict, store: Store, workers: int,
                  max_pages: int | None, resume: bool = False) -> tuple[list[Entry], dict]:
    """Index a documentation website: its llms.txt, its sitemap, or its links: every page
    under its address (a known site may set its own `max_pages`). Read ROUND pages at a time.

    With `resume`, each round is saved in crawl/ as it ends, so the download can stop and
    continue later: ctrl+c (after the pages under way; twice: at once), a lost connection,
    or `max_pages` (the pages to read this time) stop it with what it has read, marked
    "partial"; called again with the same spec, it continues where it stopped."""
    import signal
    cap = spec.get("max_pages") or 10**9
    starts = spec.get("start") or []
    starts = [starts] if isinstance(starts, str) else starts
    exclude = re.compile(spec.get("exclude", r"$^"))
    depth = spec.get("depth", 10**6)
    follow = not spec.get("sitemap")                       # a sitemap lists every page already
    folder = crawl_dir(sid)
    state = unfinished(sid) if resume and continues(sid, spec) else None
    fails, t0 = cli.Failures(), time.time()
    if state is None:                                      # a new download
        shutil.rmtree(folder, ignore_errors=True)
        prefixes = spec.get("prefix") or []
        prefixes = [prefixes] if isinstance(prefixes, str) else list(prefixes)
        rp = robots(store.root)
        keep = {seg.lower() for u in starts + prefixes for seg in urllib.parse.urlparse(u).path.split("/")}
        listed = []
        if spec.get("llms"):
            listed += from_llms(spec["llms"], prefixes, cap)
            say(f"  {len(listed)} pages listed in {spec['llms']}")
        if spec.get("sitemap"):
            listed += from_sitemap(spec["sitemap"], prefixes, cap)
        todo = [[u, 0] for u in dict.fromkeys(starts + listed) if not exclude.search(u)
                and (u in starts or not ALL_IN_ONE.search(u))]
        state = {"plan": spec, "todo": todo, "seen": [u for u, _ in todo], "read": [], "failures": {},
                 "retry": [], "images": {}, "prefixes": prefixes, "root": store.root, "keep": sorted(keep),
                 "bytes": 0, "listed": bool(listed), "about": len(todo) if listed else None}
        if not listed and resume:                          # how many pages, before the first one
            state["about"] = count_pages(rp, store.root, lambda u: any(u.startswith(p) for p in prefixes)
                                         and not exclude.search(u) and not ALL_IN_ONE.search(u)
                                         and not other_variant(u, keep))
        if state["about"] and not listed:
            delay = cli.PACE.get(urllib.parse.urlparse(store.root).netloc, {}).get("floor")
            say(f"  about {state['about']:,} pages under {store.root} (its sitemap)"
                + (f": about {duration(state['about'] * delay)} at {delay:g} s a page" if delay else ""))
        elif resume and not listed:
            say("  the number of pages shows as they turn up (no sitemap to count them first)")
        if resume and (state["about"] or 10**9) > 1000:
            say(f"  ctrl+c stops and keeps what is read; search add {name} continues")
    else:                                                  # one that stopped: go on
        store.root, prefixes, keep = state["root"], state["prefixes"], set(state["keep"])
        store.images = state["images"]
        fails.by_kind = state["failures"]
        rp = robots(store.root)
        say(f"  continuing: {pages(len(state['read']))} read before"
            + (f", about {state['about']:,} in all" if state["about"] else ""))
    allowed = lambda u: rp.can_fetch(cli.USER_AGENT, u)  # noqa: E731
    todo, seen, read = state["retry"] + state["todo"], set(state["seen"]), set(state["read"])
    retry: list = []                            # pages that failed for a reason that may pass
    tries: dict = state.setdefault("tries", {})      # how often each such page failed
    entries_file = folder / "entries.jsonl"
    folder.mkdir(parents=True, exist_ok=True)
    if entries_file.exists():                              # cut what a stop left half written
        with open(entries_file, "rb+") as f:
            f.truncate(state.get("entries_bytes", 0))
    got_bytes = [state["bytes"]]

    def fetch(u: str):
        try:
            page = cli.get_page_at(u)
            got_bytes[0] += len(page[0])
            return u, page, None
        except Exception as e:  # noqa: BLE001
            return u, None, e

    def done() -> int:          # pages read, failed, or the same page again (a page read but not
        return (len(read) + sum(len(v) for v in fails.by_kind.values())      # usable is read and
                + state.get("dups", 0) - state.get("broken", 0))              # failed: counted once)

    def total() -> int:
        return max(state["about"] or 0, done() + len(todo) + len(retry))

    stop: dict = {"why": None}

    def ctrl_c(_sig, _frame) -> None:
        if stop["why"] == "ctrl+c":
            raise KeyboardInterrupt                        # the second time: at once
        stop["why"], cli.STOPPING = "ctrl+c", True
        say("  stopping after the pages under way (ctrl+c again: at once)")
    def arrived(futures):
        """Each result in order, waited for in short slices: ctrl+c is seen at once (on Windows
        a long wait cannot be interrupted before Python 3.14); none once the download stops.
        Each is let go once handed over (as Executor.map does): its page is not kept till the end."""
        futures = futures[::-1]
        while futures:
            fut = futures.pop()
            while not stop["why"]:
                try:
                    yield fut.result(timeout=0.2)
                    break
                except cf.TimeoutError:
                    pass
            if stop["why"]:
                return

    old_handler = None
    if resume and __import__("threading").current_thread() is __import__("threading").main_thread():
        old_handler = signal.signal(signal.SIGINT, ctrl_c)
    host = urllib.parse.urlparse(store.root).netloc
    bar = cli.Progress("  pages", total(), start=done(),
                       note=lambda: f"{got_bytes[0] / 2**20:,.{0 if got_bytes[0] >= 10 * 2**20 else 1}f} MB"
                       + (f"  {len(fails)} failed" if fails else ""))
    bar.guess, bar.so_far = bool(state["about"]) and not state["listed"], not state["about"]
    net = cf.ThreadPoolExecutor(max_workers=workers)
    cpu = cf.ProcessPoolExecutor(max_workers=os.cpu_count() or 4, initializer=ignore_ctrl_c)
    this_time = 0
    try:
        while (todo or retry) and done() < cap and not stop["why"]:
            if not todo:                                 # the end: the pages to try again, once more
                todo, retry = retry, []
            if max_pages and this_time >= max_pages:
                stop["why"] = "max-pages"
                break
            chunk, k = [], 0                               # the next round
            size = min(ROUND, cap - done(), max_pages - this_time if max_pages else ROUND)
            while k < len(todo) and len(chunk) < size:
                u, d = todo[k]
                k += 1
                if allowed(u):
                    chunk.append((u, d))
                else:
                    fails.add(u, cli.Failed("robots", u))
            depth_of = dict(chunk)
            jobs, again, new_read, failed, dups, taken, broken = [], [], set(), [], 0, set(), 0
            for u, got, err in arrived([net.submit(fetch, u) for u, _ in chunk]):
                if stop["why"]:
                    break                                    # the rest of the round: next time
                taken.add(u)
                bar.update()
                if got is None:
                    failed.append((u, err))
                    continue
                real = normal(got[1])
                same = re.sub(r"/index\.html?$", "/", real)      # docs/ and docs/index.html: one page
                if u in starts and real != normal(u) and not any(real.startswith(p) for p in prefixes):
                    new = [m for m in (moved(u, real, p) for p in prefixes) if m]
                    if new:                                  # the docs moved: read them there
                        say(f"  {u} has moved to {real}: reading the docs there")
                        prefixes += new
                        keep |= {seg.lower() for m in new for seg in urllib.parse.urlparse(m).path.split("/")}
                        store.root = moved(u, real, store.root) or store.root
                        if urllib.parse.urlparse(store.root).netloc != host:
                            host = urllib.parse.urlparse(store.root).netloc
                            rp = robots(store.root)          # the new site's rules (and crawl delay)
                    else:
                        say(f"  {u} redirects to {real}, outside {', '.join(prefixes)}: only that page "
                            f"is read. If the docs moved there: search add {name}={real}")
                if same in read or same in new_read:
                    dups += 1
                    continue                                 # a page already read, by another address
                new_read.add(same)
                if real != u and real.startswith(store.root) and any(real.startswith(p) for p in prefixes):
                    depth_of[real] = depth_of[u]
                    u = real                                 # its own address: one entry per page
                if u.endswith(".md"):
                    jobs.append((u, cpu.submit(markdown_page, sid, name, store.root, store.dir, u, got[0], spec)))
                else:
                    jobs.append((u, cpu.submit(website_page, sid, name, store.root, store.dir, u, got[0], got[1],
                                               spec)))
            found_entries, images, links = [], {}, []
            for u, j in jobs:                                # (the pages read are cut, even when stopping)
                while not j.done():
                    cf.wait([j], timeout=0.2)                # (short waits, as in arrived)
                got = cli.page_result(j, u, fails)
                if got is None:
                    broken += 1
                    continue
                found, imgs, page_links = got
                if found and sum(len(e.text.strip()) for e in found) < 40:   # an empty app shell
                    fails.add(u, cli.Failed("empty", u))
                    broken += 1
                    continue
                found_entries += found
                images.update(imgs)
                if follow and depth_of.get(u, 0) < depth:
                    links += [(link, depth_of.get(u, 0) + 1) for link in page_links]
            kinds = [err.kind if isinstance(err, cli.Failed) else "other" for _, err in failed]
            for (u, err), kind in zip(failed, kinds):        # what failed, and why
                if kind in AGAIN and tries.get(u, 0) < TRIES - 1:
                    tries[u] = tries.get(u, 0) + 1
                    again.append([u, depth_of[u]])           # it may pass: later (TRIES in all)
                else:
                    fails.add(u, err)
            if resume and any(k_ in ("offline", "dns") for k_ in kinds):
                stop["why"] = "offline"                      # the connection is gone: stop, keep it
            elif resume and len(failed) >= GONE and len(failed) == len(taken) and all(k_ in AGAIN for k_ in kinds):
                stop["why"] = "unreachable"                  # a whole round, and none answered
            fresh = []
            for link, d in links:
                if (link not in seen and cli.safe_url(link) and not exclude.search(link)
                        and not link.endswith(".txt")        # llms.txt indexes, sources
                        and not ALL_IN_ONE.search(link)      # print copies of whole sections
                        and not other_variant(link, keep)    # translations, old versions
                        and any(link.startswith(p) for p in prefixes)):
                    seen.add(link)
                    fresh.append([link, d])
            with open(entries_file, "a", encoding="utf-8") as f:     # the round, saved
                f.writelines(json.dumps(cli.asdict(e)) + "\n" for e in found_entries)
            read |= new_read
            state["dups"] = state.get("dups", 0) + dups
            state["broken"] = state.get("broken", 0) + broken
            store.add_images(images)
            retry += again
            todo = [[u, d] for u, d in chunk if u not in taken] + todo[k:] + fresh
            this_time += len(taken)
            if resume:
                state.update(todo=todo, seen=sorted(seen), read=sorted(read), retry=retry, images=store.images,
                             failures=fails.by_kind, tries=tries,
                             prefixes=prefixes,
                             root=store.root, keep=sorted(keep), bytes=got_bytes[0],
                             entries_bytes=entries_file.stat().st_size)
                cli.write_atomic(folder / "state.json", json.dumps(state).encode())
            bar.update(done() - bar.done, total=total())
        if not todo and not retry:
            bar.total, bar.guess, bar.so_far = bar.done, False, False      # all read: 100%
    except KeyboardInterrupt:
        stop["why"] = stop["why"] or "ctrl+c"
        raise
    finally:
        stopped = bool(stop["why"])
        net.shutdown(wait=not stopped, cancel_futures=stopped)
        cpu.shutdown(wait=not stopped, cancel_futures=stopped)
        bar.close()
        if old_handler is not None:
            signal.signal(signal.SIGINT, old_handler)
        cli.STOPPING = False
    entries = [Entry(**json.loads(ln)) for ln in
               entries_file.read_text(encoding="utf-8").splitlines() if ln.strip()] if entries_file.exists() else []
    if stop["why"] and resume:
        why = (f"the site stopped answering ({cli.describe(kinds[-1])}); stopped" if stop["why"] == "unreachable"
               else "the connection is gone; stopped" if stop["why"] == "offline" else "stopped")
        about = total() if state["about"] else None           # a guess from the sitemap, or none
        say(f"  {why}: {pages(len(read))} read" + (f" of about {about:,}" if about else
                                                    f"; {len(todo) + len(retry):,} more found so far")
            + f". They are kept and searchable; to continue: search add {name}")
        return entries, {"failed_pages": len(fails), "failures": fails.as_meta(),
                         "partial": {"pages": len(read), "about": about, "again": len(retry)}}
    shutil.rmtree(folder, ignore_errors=True)                # finished: nothing to continue
    say(f"  {done()} pages ({len(fails)} failed) in {time.time() - t0:.0f} s")
    if fails:
        fails.report()
    return entries, {"failed_pages": len(fails), "failures": fails.as_meta()}


# --------------------------------------------------------------------------- local copies

LOCAL_HOST = "local-docs.invalid"     # .invalid never exists (RFC 2606): nothing can be fetched
LOCAL_LIMITS = {"files": 50_000, "bytes": 2 * 2**30}


def unpack_zip(zip_path: Path, into: Path) -> Path:
    """Unpack a downloaded docs .zip safely: no path may leave the folder, and the unpacked
    size and number of files are limited (a "zip bomb" is refused)."""
    import zipfile
    with zipfile.ZipFile(zip_path) as z:
        infos = [i for i in z.infolist() if not i.is_dir()]
        if len(infos) > LOCAL_LIMITS["files"] or sum(i.file_size for i in infos) > LOCAL_LIMITS["bytes"]:
            cli.die(f"{zip_path}: more than {LOCAL_LIMITS['files']} files or 2 GB unpacked; refused.")
        base = into.resolve()
        for i in infos:
            target = (into / i.filename).resolve()
            if base not in target.parents:
                cli.die(f"{zip_path}: '{i.filename}' would be written outside the folder; refused.")
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(i) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
    tops = [p for p in into.iterdir() if not p.name.startswith((".", "__MACOSX"))]
    return tops[0] if len(tops) == 1 and tops[0].is_dir() else into     # docs-1.2/... -> its folder


def build_local(name: str, sid: str, src: Path, workers: int) -> tuple[list[Entry], dict]:
    """Docs you downloaded yourself (a folder, or a .zip of HTML or Markdown pages): read
    from disk, nothing fetched. The pages get the address https://SID.local-docs.invalid/
    so links between them work in the search page."""
    import tempfile
    src = src.expanduser().resolve()
    if not src.exists():
        cli.die(f"{src}: no such file or folder.")
    root = f"https://{sid}.{LOCAL_HOST}/"
    if src.is_file() and src.suffix.lower() != ".zip":
        cli.die(f"{src}: give a folder, or a .zip of the docs.")
    tmp = Path(tempfile.mkdtemp(prefix="docsearch-")) if src.is_file() else None
    try:
        folder = unpack_zip(src, tmp) if tmp else src
        files = sorted(f for f in folder.rglob("*") if f.is_file() and f.suffix.lower() in
                       (".html", ".htm", ".md", ".markdown")
                       and not any(p.startswith(".") for p in f.relative_to(folder).parts))
        if len(files) > LOCAL_LIMITS["files"]:
            cli.die(f"{folder}: more than {LOCAL_LIMITS['files']} pages.")
        say(f"  {len(files)} pages in {src}")
        store = Store(sid, root)
        store.reset()
        entries: list[Entry] = []
        fails = cli.Failures()
        with cf.ProcessPoolExecutor(max_workers=os.cpu_count() or 4) as cpu:
            jobs = []
            for f in files:
                rel = f.relative_to(folder).as_posix()
                url = root + rel
                data = f.read_bytes()
                if len(data) > cli.MAX_DOWNLOAD:
                    fails.add(url, cli.Failed("too-large", url, f"{cli.MAX_DOWNLOAD // 2**20} MB"))
                    continue
                if f.suffix.lower() in (".md", ".markdown"):
                    jobs.append((url, cpu.submit(markdown_page, sid, name, root, store.dir, url, data, {})))
                else:
                    jobs.append((url, cpu.submit(website_page, sid, name, root, store.dir, url, data, url, {})))
            with cli.Progress("  pages", len(jobs)) as bar:
                for url, j in jobs:
                    got = cli.page_result(j, url, fails)
                    bar.update()
                    if got is None:
                        continue
                    found, imgs, _ = got
                    entries += found
                    store.add_images(imgs)

        def read_image(url: str) -> bytes:              # images come from the folder, not the web
            path = (folder / urllib.parse.unquote(url[len(root):].split("?")[0])).resolve()
            if folder.resolve() not in path.parents:
                raise ValueError("outside the folder")
            return path.read_bytes()
        cli.download_images(store.images, store.dir / "_images", workers, read=read_image)
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
    if fails:
        fails.report()
    return entries, {"kind": "local", "root": root, "local": str(src), "pages": True,
                     "failed_pages": len(fails), "failures": fails.as_meta()}


# --------------------------------------------------------------------------- Rust (rustdoc)

RUST_ITEM = re.compile(r"(?:^|/)(struct|enum|trait|fn|macro|primitive|constant|type|union|keyword|"
                       r"derive|attr|static|traitalias)\.([^/]+)\.html$")
RUST_KIND = {"fn": "function", "constant": "constant", "type": "type alias", "traitalias": "trait alias",
             "attr": "attribute macro", "derive": "derive macro"}
RUST_MEMBER = re.compile(r"^(method|tymethod|associatedconstant|associatedtype)\.(.+)$")


def rust_name(crate_root: str, url: str) -> tuple[str, str]:
    """('std::vec::Vec', 'struct') from .../std/vec/struct.Vec.html."""
    rel = url[len(crate_root):]
    crate = crate_root.rstrip("/").rsplit("/", 1)[-1]
    m = RUST_ITEM.search(rel)
    if m:
        path = [p for p in rel[:m.start()].split("/") if p]
        return "::".join([crate, *path, m.group(2)]), RUST_KIND.get(m.group(1), m.group(1))
    path = [p for p in rel.removesuffix("index.html").split("/") if p]
    return "::".join([crate, *path]), "module"


def rustdoc_page(sid: str, name: str, root: str, pages_dir: Path, crate_root: str, url: str,
                 html: bytes, real_url: str) -> tuple[list[Entry], dict[str, str], list[str]]:
    """One rustdoc page: the item, and the item's own methods (worker)."""
    soup = cli.make_soup(html)
    cli.clean_soup(soup)
    main = soup.select_one("#main-content") or soup.select_one("main") or soup.body
    item, kind = rust_name(crate_root, url)
    decl = main.select_one("pre.item-decl, .item-decl")
    top = main.select_one("details.top-doc .docblock") or main.select_one(".docblock")
    sig = f"```rust\n{decl.get_text(strip=False).strip()}\n```\n\n" if decl else ""
    entries = [Entry(title=item, kind=kind, location=url,
                     text=(sig + (cli.html_to_md(str(top)) if top else ""))[:cli.PREVIEW_CHARS], source=name)]
    # the type's own methods, and a trait's required/provided methods (not trait impls:
    # those repeat the trait's documentation on every type)
    for box in [main.find(id=i) for i in ("implementations-list", "required-methods", "provided-methods",
                                         "required-associated-types", "required-associated-consts")]:
        if box is None:
            continue
        for sec in box.find_all(id=RUST_MEMBER):
            m = RUST_MEMBER.match(sec["id"])
            head = sec.select_one(".code-header")
            det = sec.find_parent("details")
            doc = det.select_one(".docblock") if det is not None else None
            text = (f"```rust\n{head.get_text(' ', strip=True) if head else m.group(2)}\n```\n\n"
                    + (cli.html_to_md(str(doc)) if doc else ""))
            entries.append(Entry(title=f"{item}::{m.group(2)}", kind="method" if "method" in m.group(1) else
                                 m.group(1).replace("associated", "associated "),
                                 location=f"{url}#{sec['id']}", text=text[:cli.PREVIEW_CHARS], source=name))
    for junk in main.select("#synthetic-implementations-list, #blanket-implementations-list, "
                            "#synthetic-implementations, #blanket-implementations, rustdoc-toolbar, "
                            ".src, button"):
        junk.decompose()                                  # boilerplate, and buttons that need JS
    images: dict[str, str] = {}
    store_page(sid, root, pages_dir, url, main, real_url, images)
    return entries, images, []


def build_rustdoc(name: str, sid: str, spec: dict, store: Store, workers: int,
                  max_pages: int | None) -> tuple[list[Entry], dict]:
    """Every item of a Rust crate (its all.html), with the methods on each item's page."""
    crate_root = spec["url"] if spec["url"].endswith("/") else spec["url"] + "/"
    html, real = cli.get_page_at(crate_root + "all.html")
    soup = cli.make_soup(html)
    meta = soup.find("meta", attrs={"name": "rustdoc-vars"})
    version = (meta.get("data-channel") if meta else "") or ""
    items = [normal(urllib.parse.urljoin(real, a["href"])) for a in soup.select("#main-content a[href]")]
    items = [u for u in dict.fromkeys(items) if u.startswith(crate_root)]
    modules = sorted({u[: u.rfind("/") + 1] + "index.html" for u in items})
    urls = list(dict.fromkeys([crate_root + "index.html", *modules, *items]))[: max_pages or 10**6]
    say(f"  {name}: {len(items)} items in {len(modules)} modules (rustdoc {version})")
    entries: list[Entry] = []
    fails = cli.Failures()

    def fetch(u: str):
        try:
            return u, cli.get_page_at(u), None
        except Exception as e:  # noqa: BLE001
            return u, None, e

    jobs = []
    with cf.ThreadPoolExecutor(max_workers=workers) as net, \
            cf.ProcessPoolExecutor(max_workers=os.cpu_count() or 4) as cpu:
        with cli.Progress("  pages", len(urls), note=lambda: f"{len(fails)} failed" if fails else "") as bar:
            for u, got, err in net.map(fetch, urls):
                bar.update()
                if got is None:
                    fails.add(u, err)
                    continue
                jobs.append((u, cpu.submit(rustdoc_page, sid, name, store.root, store.dir, crate_root, u,
                                           got[0], got[1])))
        for u, j in jobs:
            got = cli.page_result(j, u, fails)
            if got is None:
                continue
            found, imgs, _ = got
            entries += found
            store.add_images(imgs)
    if fails:
        fails.report()
    return entries, {"version": version, "failed_pages": len(fails), "failures": fails.as_meta()}
