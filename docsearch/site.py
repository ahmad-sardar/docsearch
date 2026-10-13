"""What a docs site says about itself, surveyed before it is read (a few requests).

Docs sites publish their pages for programs in several ways, and which ones a site has
depends on what built it (eval/sites.py surveyed 81 popular Python packages' docs):
- a Sphinx inventory (objects.inv): every page and API object, by name;
- a search index: MkDocs' search/search_index.json, Zensical's search.json (with each page's
  place in the site's navigation);
- sitemaps: every page of a site (tensorflow.org: 18,801), often of every version too;
- llms.txt: a list for programs, with the site's sections as its headings (docs.langchain.com,
  docs.streamlit.io), often of Markdown pages (page.md) when the HTML is drawn by JavaScript;
- the first page's links and its sidebar.

The survey gathers what a site publishes, and from it: the docs' folder (the deepest one
that holds the first page and most of the listed pages), how many pages the docs have (the
largest list inside that folder), whether a page's text is in its HTML or only in its
Markdown, and each page's place in the site's own outline (sections, nearest last), for
organizing (organize.py). A download is then checked against that number (cli.add_each).
"""
from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass, field

from docsearch import cli

ASSET = re.compile(r"\.(css|js|mjs|png|jpe?g|gif|svg|webp|ico|woff2?|ttf|json|xml|txt|pdf|zip|gz)(\?|$)", re.I)
# a section of another language than the package's (Python): left out of a PyPI package's docs
# unless you choose it (search add asks, in a terminal)
LANGUAGES = {"javascript", "typescript", "js", "ts", "node", "nodejs", "node.js", "java", "kotlin", "swift",
             "go", "golang", "rust", "ruby", "php", "csharp", "c#", ".net", "dotnet", "scala"}
TEXT = 300                    # characters of text a page has in its HTML, when its text is there
SAMPLE = 3                    # pages read to see whether the text is in the HTML
SITEMAP_FILES = 30            # sitemap files read at most (a host's index can list hundreds)


@dataclass
class Site:
    address: str                                  # what was asked
    landing: str                                  # where it led
    root: str                                     # the docs' folder
    lists: dict[str, list[str]] = field(default_factory=dict)   # how the site lists its pages -> pages
    outline: dict[str, list[str]] = field(default_factory=dict)  # page -> its sections, outermost first
    md_of: dict[str, str] = field(default_factory=dict)          # page -> its Markdown address
    html_text: bool | None = None                 # a page's text is in its HTML (None: not seen)
    markdown: bool = False                        # its pages are there as Markdown too
    inventory: bytes | None = None

    @property
    def pages(self) -> list[str]:
        """Every page listed inside the docs' folder, each once, the fullest list first."""
        out: dict[str, None] = {}
        for _, got in sorted(self.lists.items(), key=lambda kv: -len(kv[1])):
            out.update(dict.fromkeys(got))
        return list(out)

    @property
    def expected(self) -> int:
        """How many pages the docs have, as the fullest list says."""
        return max((len(set(v)) for k, v in self.lists.items() if k != "links"), default=0)

    def sections(self, depth: int = 0) -> list[tuple[str, int]]:
        """The site's own top-level sections and their pages, at the shallowest depth where it
        has several (docs.langchain.com: "AGENT DEVELOPMENT LIFECYCLE / Build", 477 pages); else
        the first folders under the docs' address."""
        pages = self.pages
        if sum(1 for p in pages if self.outline.get(p)) >= len(pages) / 2:
            for level in range(depth or 1, 5):
                groups: dict[str, int] = {}
                for p in pages:
                    path = self.outline.get(p) or []
                    if len(path) >= level:
                        key = " / ".join(path[:level])
                        groups[key] = groups.get(key, 0) + 1
                big = {k: n for k, n in groups.items() if n >= max(2, len(pages) // 50)}
                if len(big) >= 3 or level == 4:
                    return sorted(big.items(), key=lambda kv: -kv[1])
        groups = {}
        for p in pages:
            rest = p[len(self.root):].strip("/")
            key = rest.split("/")[0] if "/" in rest else ""
            if key:
                groups[key + "/"] = groups.get(key + "/", 0) + 1
        return sorted(groups.items(), key=lambda kv: -kv[1])

    def other_language(self, page: str) -> bool:
        """Is a page in a section of another language (TypeScript, Java...)?"""
        names = [n.lower() for n in self.outline.get(page) or []]
        names += [s.lower() for s in page[len(self.root):].split("/")[:-1]]
        return any(n in LANGUAGES for n in names)


def folder_of(url: str) -> str:
    """https://x/a/b.html -> https://x/a/; https://x/a/b/ -> as is; https://x/a/b -> https://x/a/b/
    (an address without an extension names a folder)."""
    u = url.split("#")[0].split("?")[0]
    if u.endswith("/"):
        return u
    if not urllib.parse.urlparse(u).path:              # https://spacy.io
        return u + "/"
    last = u.rsplit("/", 1)[1]
    return u.rsplit("/", 1)[0] + "/" if "." in last else u + "/"


def parent(folder: str) -> str | None:
    u = urllib.parse.urlparse(folder)
    path = u.path.rstrip("/")
    if not path:
        return None
    return f"{u.scheme}://{u.netloc}{path.rsplit('/', 1)[0]}/"


def page_links(html: str, base: str) -> list[str]:
    """A page's links to pages (not to its styles, scripts and images), in order."""
    soup = cli.make_soup(html.encode())
    out: dict[str, None] = {}
    for a in soup.find_all(["a", "area"], href=True):
        u = urllib.parse.urljoin(base, a["href"]).split("#")[0].split("?")[0]
        if cli.safe_url(u) and not ASSET.search(u):
            out[u] = None
    return list(out)


def nav_outline(html: str, base: str) -> dict[str, list[str]]:
    """The sections of the pages a page's sidebar lists, as its nested lists show them: for each
    link, the names of the list items it is inside (outermost first)."""
    from docsearch import order
    soup = cli.make_soup(html.encode())
    out: dict[str, list[str]] = {}
    for nav in soup.select(order.NAV):
        for a in nav.find_all("a", href=True):
            u = urllib.parse.urljoin(base, a["href"]).split("#")[0]
            if not cli.safe_url(u) or u in out:
                continue
            names = []
            own = a.find_parent("li")
            for li in a.find_parents("li"):
                if li is own:
                    continue
                label = next((c for c in li.children if getattr(c, "name", None) not in (None, "ul", "ol", "nav")
                              and c.get_text(strip=True)), None)
                text = " ".join((label.get_text(" ", strip=True) if label is not None else "").split())
                if text:
                    names.append(text)
            out[u] = names[::-1]
    return out


def text_in(html: str) -> int:
    """How much text a page's main part has in its HTML, as docsearch reads it (importers.
    main_part): a page drawn by JavaScript has next to none, whatever its menus have."""
    from docsearch import importers
    soup = cli.make_soup(html.encode())
    cli.clean_soup(soup)
    for el in soup.select(importers.DROP):
        el.decompose()
    return len(importers.main_part(soup).get_text(" ", strip=True))


def get(url: str, timeout: float = 15) -> tuple[bytes, str] | None:
    try:
        return cli.http_get(url, timeout=timeout)
    except Exception:  # noqa: BLE001 - a list the site does not have
        return None


def search_index(root: str) -> tuple[list[str], dict[str, list[str]]]:
    """The pages of a MkDocs or Zensical search index, and (Zensical) each one's sections."""
    for path in ("search/search_index.json", "search.json"):
        got = get(root + path)
        if not got or got[0][:1] not in (b"{", b"["):
            continue
        try:
            data = json.loads(got[0])
        except ValueError:
            continue
        items = data.get("docs") or data.get("items") or [] if isinstance(data, dict) else data
        pages: dict[str, None] = {}
        crumbs: dict[str, list[str]] = {}
        for it in items:
            loc = str(it.get("location", ""))
            if "#" in loc:
                continue
            u = urllib.parse.urljoin(root, loc)
            pages[u] = None
            path = [str(x) for x in it.get("path") or []]
            if path:
                crumbs[u] = path[:-1] if path[-1] == it.get("title") else path
        return list(pages), crumbs
    return [], {}


def survey(address: str, name: str = "", root: str | None = None) -> Site | None:
    """What the docs at an address publish about themselves (see above). `root`: the docs'
    folder when it is known already (a Sphinx page says it). None: no page there."""
    from docsearch import importers
    roots, page, said = cli.probe_roots(address)
    if not page:
        return None
    landing = cli.PAGES_SEEN.get(address, (address,))[0] or address
    root = root or (roots[0] if said and roots else folder_of(landing))
    links = page_links(page, landing)
    for _ in range(2):                               # one folder too deep (huggingface.co's .../index):
        up = parent(root)                            # its own sidebar's links are around it, not in it
        if up is None or said or sum(1 for u in links if u.startswith(root)) >= 3 \
                or sum(1 for u in links if u.startswith(up)) < 3:
            break
        root = up
    site = Site(address, landing, root)
    site.lists["links"] = [u for u in links if u.startswith(root) and u != root]
    site.outline.update({u: c for u, c in nav_outline(page, landing).items() if c and u.startswith(root)})
    hit = cli.index_in([root], cli.SITE_INDEXES[:1])
    if hit is not None:                              # Sphinx: its inventory names every page
        site.inventory = hit[2]
        try:
            objs = cli.parse_objects_inv(hit[2])[2]
        except ValueError:
            objs = []
        docs = [o for o in objs if o["role"] == "doc"] or objs
        site.lists["inventory"] = list(dict.fromkeys(urllib.parse.urljoin(root, o["uri"].split("#")[0]) for o in docs))
        return site
    pages, crumbs = search_index(root)
    if pages:
        site.lists["search index"] = [u for u in pages if u.startswith(root)]
        site.outline.update({u: c for u, c in crumbs.items() if c})
    u = urllib.parse.urlparse(root)
    origin = f"{u.scheme}://{u.netloc}/"
    llms = next((x for x in dict.fromkeys([root + "llms.txt", origin + "llms.txt"])
                 if (got := get(x)) and b"](" in got[0][:200_000] and b"<html" not in got[0][:500].lower()), None)
    if llms:
        listed, crumbs, md_of = importers.read_llms(llms, [root], 50_000)
        site.lists["llms.txt"] = listed
        site.md_of.update(md_of)
        for p, c in crumbs.items():                  # (llms.txt's sections are the site's own)
            if c:
                site.outline[p] = c
    rp = importers.robots(root)
    maps = list(dict.fromkeys((rp.site_maps() or []) + [root + "sitemap.xml", origin + "sitemap.xml"]))
    listed = []
    for sm in maps:
        listed += [x for x in importers.from_sitemap(sm, [root], 50_000, SITEMAP_FILES) if x not in listed]
    if listed:
        site.lists["sitemap"] = listed
    from docsearch.importers import variants
    keep = {seg.lower() for seg in urllib.parse.urlparse(landing).path.split("/") if seg}
    for kind in ("sitemap", "llms.txt"):             # other versions' and languages' copies of pages
        if site.lists.get(kind):                     # (docs.streamlit.io/1.64.0/...): not these docs
            other = variants(site.lists[kind], keep)
            site.lists[kind] = [x for x in site.lists[kind] if x not in other]
    pages = [p for p in site.pages if p.rstrip("/") != landing.rstrip("/") and p.rstrip("/") != root.rstrip("/")]
    sample = [pages[k * len(pages) // (SAMPLE + 1)] for k in range(1, SAMPLE + 1)] if len(pages) > SAMPLE else pages
    seen = []
    for p in sample:                                 # text in the HTML, or drawn by JavaScript?
        got = get(p)
        if got and len(got[0]) > 200:                # (a page that did not come: not a vote)
            seen.append(text_in(got[0].decode("utf-8", "replace")))
    site.html_text = any(n >= TEXT for n in seen) if seen else None
    for p in sample[:1]:                             # its Markdown (page.md), where it says so or not
        md = site.md_of.get(p) or p.rstrip("/") + ".md"
        got = get(md)
        if got and b"<html" not in got[0][:500].lower() and len(got[0]) > 50:
            site.markdown = True
            site.md_of.setdefault(p, md)
    return site


# --------------------------------------------------------------------------- what to read of it

def in_section(site: Site, page: str, key: str) -> bool:
    """Is a page in a section: one of the site's own ("A / B", its outline), or a folder ("api/")."""
    if key.endswith("/"):
        return page[len(site.root):].startswith(key)
    path = site.outline.get(page) or []
    return " / ".join(path[:key.count(" / ") + 1]) == key


def skip_pattern(left: list[str], kept: list[str], root: str) -> str:
    """A pattern for the pages not to read, also when links lead to them: the folders that hold
    only such pages (docs.langchain.com/oss/javascript/), else the pages themselves."""
    out: dict[str, None] = {}
    for p in left:
        parts = p[len(root):].split("/")[:-1]
        folder = next((root + "/".join(parts[:k]) + "/" for k in range(1, len(parts) + 1)
                       if not any(q.startswith(root + "/".join(parts[:k]) + "/") for q in kept)), None)
        out[folder or p] = None
    folders = [f for f in out if not any(f != g and f.startswith(g) and g.endswith("/") for g in out)]
    return "^(?:" + "|".join(re.escape(f) + ("" if f.endswith("/") else "$") for f in folders) + ")"


def reading(site: Site, pages: list[str]) -> dict:
    """How to read these pages of a site (importers.build_website's plan): the pages its lists
    name; as Markdown where its HTML has no text, or where its own list gives nearly every page
    as Markdown (docs.langchain.com: 11 KB a page, not 1 MB); the rest kept out."""
    chosen = set(pages)
    md = sum(1 for p in pages if p in site.md_of) / max(1, len(pages))
    left = [p for p in site.pages if p not in chosen]
    return {"listed": pages, "expected": len(pages), "can_markdown": site.markdown,
            "markdown": site.markdown and (site.html_text is False or md >= 0.9),
            "md_of": {p: site.md_of[p] for p in pages if p in site.md_of},
            "outline": {p: site.outline[p] for p in pages if site.outline.get(p)},
            **({"exclude": skip_pattern(left, pages, site.root)} if left else {})}


def choose(site: Site, name: str, saved=None) -> tuple[list[str], object]:
    """The pages of a site to read, and the answer to keep (None: nothing asked). The sections
    you chose before (`saved`: packages.toml); else, in a terminal, asked when the site has
    pages of other languages than the package's (TypeScript next to Python) or many sections
    (tensorflow.org); else every page but the other languages'."""
    import sys
    pages = site.pages
    other = {p for p in pages if site.other_language(p)}
    default = [p for p in pages if p not in other]
    if saved == "all":
        return pages, None
    if saved and saved != "default":
        keys = [saved] if isinstance(saved, str) else list(saved)
        return [p for p in pages if any(in_section(site, p, k) for k in keys if k != "+")
                and (p not in other or "+" in keys)], None
    sections = site.sections()
    if saved == "default" or not (other or (len(sections) >= 3 and site.expected >= 500)):
        return default, None
    langs = sorted({n for p in other for n in (site.outline.get(p) or []) + p[len(site.root):].split("/")[:-1]
                    if n.lower() in LANGUAGES})
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        cli.say(f"  {site.root}: {len(pages):,} pages; reading {len(default):,}"
                + (f" (left out: {len(other):,} for {', '.join(langs)})" if other else "")
                + f". To choose its sections: search add {name}, in a terminal")
        return default, None
    print(f"  {site.root} has {len(pages):,} pages, in these sections:")
    for k, (key, n) in enumerate(sections[:30], 1):
        theirs = sum(1 for p in other if in_section(site, p, key))
        print(f"    {k:>2}) {key:<60} {n:>6,}" + (f"  ({theirs:,} of them for {', '.join(langs)})" if theirs else ""))
    if other:
        print(f"  {len(other):,} pages are for other languages ({', '.join(langs)}): left out unless you add +")
    while True:
        answer = input(f"  Read which? Enter: all those ({len(default):,} pages) · numbers (1 3 5) · "
                       f"+ for other languages too: ").strip()
        if not answer:
            return default, "default"
        if answer in ("+", "all+", "a+"):
            return pages, "all"
        picked = [int(x) for x in re.findall(r"\d+", answer) if 1 <= int(x) <= min(30, len(sections))]
        if picked:
            keys = [sections[k - 1][0] for k in picked] + (["+"] if "+" in answer else [])
            return [p for p in pages if any(in_section(site, p, k) for k in keys if k != "+")
                    and (p not in other or "+" in keys)], keys
        print("  (numbers from the list, Enter, or +)")
