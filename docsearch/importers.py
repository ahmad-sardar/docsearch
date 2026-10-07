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
    """The site's robots.txt rules (a missing file allows everything)."""
    rp = urllib.robotparser.RobotFileParser()
    u = urllib.parse.urlparse(root)
    try:
        body, _ = cli.http_get(f"{u.scheme}://{u.netloc}/robots.txt", timeout=10)
        rp.parse(body.decode("utf-8", "replace").splitlines())
    except Exception:  # noqa: BLE001 - no robots.txt: everything allowed
        rp.parse([])
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


def from_sitemap(url: str, prefixes: list[str], limit: int) -> list[str]:
    """Pages in a sitemap (or sitemap index), inside the prefixes."""
    out, todo, seen = [], [url], set()
    while todo and len(out) < limit:
        sm = todo.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        try:
            body = cli.http_get(sm)[0]
        except Exception:  # noqa: BLE001
            continue
        if body[:2] == b"\x1f\x8b":
            body = gzip.decompress(body)[:cli.MAX_DOWNLOAD]
        for loc in re.findall(rb"<loc>\s*([^<\s]+)\s*</loc>", body):
            u = loc.decode("utf-8", "replace").strip()
            if u.endswith((".xml", ".xml.gz")):
                todo.append(u)
            elif cli.safe_url(u) and any(u.startswith(p) for p in prefixes) and u not in out:
                out.append(u)
    return out[:limit]


STRIP = re.compile(r"@go[\d.]+(?=$|/)")            # pkg.go.dev/fmt@go1.27.1: the same page


def normal(url: str) -> str:
    """One address per page: no #fragment, no ?query, no version tag."""
    return STRIP.sub("", urllib.parse.urldefrag(url)[0].split("?")[0])


# --------------------------------------------------------------------------- cutting pages

DROP = (".theme-doc-toc-mobile, .theme-doc-toc-desktop, .theme-doc-version-badge, "
        ".theme-doc-breadcrumbs, .pagination-nav, .theme-edit-this-page, .theme-last-updated, "
        ".editsection, .mw-editsection, #toc, .toc, .t-navbar, .t-template-editlink, .noprint, "
        ".breadcrumbs, .headerlink, button, .copy-button, .baseline-indicator, .on-github, "
        "#sidebar, .sidebar, .nav-chapters, .mobile-nav-chapters, #menu-bar")
MEMBER_SECTIONS = {"methods", "fields", "functions", "properties", "aliases", "comptime members",
                   "static methods", "instance methods", "static properties", "instance properties",
                   "constructors", "operators", "member functions", "associated functions"}
HEADING_JUNK = re.compile(r"\s*(¶|#|Copy item path|Copy)\s*$")
OCAMLDOC_ID = re.compile(r"^(VAL|TYPE|EXCEPTION|MODULE|MODTYPE|CLASS|CLASSTYPE|METHOD)(.+)$")
OCAMLDOC_KIND = {"VAL": "val", "TYPE": "type", "EXCEPTION": "exception", "MODULE": "module",
                 "MODTYPE": "module type", "CLASS": "class", "CLASSTYPE": "class type", "METHOD": "method"}
IDENT = re.compile(r"[A-Za-z_$][\w$]*")


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
    links = [normal(urllib.parse.urljoin(real_url, a["href"])) for a in soup.find_all("a", href=True)]
    cli.clean_soup(soup)                       # (after the links: chapter lists live in <nav>)
    for el in soup.select(DROP + (", " + spec["drop"] if spec.get("drop") else "")):
        el.decompose()
    # a saved article: its text without the site around it (a general method, see article.py)
    main = article.extract(soup) if spec.get("article") else None
    selectors = ([spec["main"]] if spec.get("main") else []) + [
        "#mw-content-text", "article.bd-article", 'div[role="main"]', "main", "article", "#content", ".content", "div.body"]
    for sel in selectors if main is None else []:
        main = soup.select_one(sel)
        if main is not None:
            break
    if main is None:
        main = soup.body or soup
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

def build_website(name: str, sid: str, spec: dict, store: Store, workers: int,
                  max_pages: int | None) -> tuple[list[Entry], dict]:
    """Index a documentation website: its llms.txt, its sitemap, or its links."""
    limit = max_pages or spec.get("max_pages", 3000)
    prefixes = spec.get("prefix") or []
    prefixes = [prefixes] if isinstance(prefixes, str) else prefixes
    starts = spec.get("start") or []
    starts = [starts] if isinstance(starts, str) else starts
    rp = robots(store.root)
    allowed = lambda u: rp.can_fetch(cli.USER_AGENT, u)  # noqa: E731
    entries: list[Entry] = []
    fails, t0, done = cli.Failures(), time.time(), 0

    def fetch(u: str):
        try:
            return u, cli.get_page_at(u), None
        except Exception as e:  # noqa: BLE001
            return u, None, e

    frontier = list(starts)
    if spec.get("llms"):
        frontier += from_llms(spec["llms"], prefixes, limit)
        say(f"  {len(frontier)} pages listed in {spec['llms']}")
    if spec.get("sitemap"):
        frontier += from_sitemap(spec["sitemap"], prefixes, limit)
    follow = not spec.get("sitemap")                       # a sitemap lists every page already
    depth_left = spec.get("depth", 10**6)
    exclude = re.compile(spec.get("exclude", r"$^"))
    frontier = [u for u in dict.fromkeys(frontier) if not exclude.search(u)]
    seen = set(frontier)
    keep_segments = {seg.lower() for u in starts + prefixes for seg in urllib.parse.urlparse(u).path.split("/")}
    bar = cli.Progress("  pages", min(len(seen), limit), note=lambda: f"{len(fails)} failed" if fails else "")
    with cf.ThreadPoolExecutor(max_workers=workers) as net, \
            cf.ProcessPoolExecutor(max_workers=os.cpu_count() or 4) as cpu, bar:
        while frontier and done < limit:
            for u in frontier:
                if not allowed(u):
                    fails.add(u, cli.Failed("robots", u))
            batch = [u for u in frontier if allowed(u)][: limit - done]
            frontier = []
            jobs = []
            for u, got, err in net.map(fetch, batch):
                done += 1
                bar.update(total=min(len(seen), limit))      # more pages turn up as links are read
                if got is None:
                    fails.add(u, err)
                    continue
                if u.endswith(".md"):
                    jobs.append((u, cpu.submit(markdown_page, sid, name, store.root, store.dir, u, got[0], spec)))
                else:
                    jobs.append((u, cpu.submit(website_page, sid, name, store.root, store.dir, u, got[0], got[1],
                                               spec)))
            for u, j in jobs:
                found, imgs, links = j.result()
                if found and sum(len(e.text.strip()) for e in found) < 40:   # an empty app shell
                    fails.add(u, cli.Failed("empty", u))
                    continue
                entries += found
                store.add_images(imgs)
                if follow and depth_left > 0:
                    for link in links:
                        if (link not in seen and cli.safe_url(link) and not exclude.search(link)
                                and not link.endswith(".txt")        # llms.txt indexes, sources
                                and not other_variant(link, keep_segments)    # translations, old versions
                                and any(link.startswith(p) for p in prefixes)):
                            seen.add(link)
                            frontier.append(link)
            depth_left -= 1
    say(f"  {done} pages ({len(fails)} failed) in {time.time() - t0:.0f} s")
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
                    jobs.append(cpu.submit(markdown_page, sid, name, root, store.dir, url, data, {}))
                else:
                    jobs.append(cpu.submit(website_page, sid, name, root, store.dir, url, data, url, {}))
            with cli.Progress("  pages", len(jobs)) as bar:
                for j in jobs:
                    found, imgs, _ = j.result()
                    bar.update()
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
                jobs.append(cpu.submit(rustdoc_page, sid, name, store.root, store.dir, crate_root, u,
                                       got[0], got[1]))
        for j in jobs:
            found, imgs, _ = j.result()
            entries += found
            store.add_images(imgs)
    if fails:
        fails.report()
    return entries, {"version": version, "failed_pages": len(fails), "failures": fails.as_meta()}
