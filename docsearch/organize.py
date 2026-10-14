"""Docs organized by what you read them for: learn, do, look up, understand.

Every entry gets a purpose, from the docs' own words, never guessed from its text:
- learn: tutorials, getting started, quickstarts (Python's tutorial, NumPy quickstart)
- do: how-tos, user guides, FAQs, installing (NumPy how-tos, pandas' user guide)
- look up: the reference, every API object (NumPy reference, the Python Standard Library)
- understand: fundamentals, concepts, internals (NumPy fundamentals)

A page's purpose is the nearest label of its own: its own title, else the title of the page
whose contents list it, and so on up the docs' table of contents (order.page_order). A page
no contents list is under its folder's index page (reference/ under reference/index.html),
and else named by its folder (tutorial/, howto/, reference/). API objects are look up.

Pages about the project, not about using it, are removed: release notes, what's new,
development and contributing, building from source, the license. A page is removed when it
or a page above it in the contents says so ("Contributing to NumPy" and all its pages).

Parts listed apart from the entry that already holds them are folded into it:
cppreference's "Parameters", "Return value", "See also"... sections (each is in its page's
entry, word for word); a Sphinx section that only repeats its page's title; a page that only
repeats its API object (numpy.sum's page, numpy.sum).
"""
from __future__ import annotations

import collections
import gzip
import json
import re
from typing import NamedTuple

from docsearch import cli
from docsearch import pages as offline

VERSION = 6                       # meta["organized"]: the rules a copy was organized with (2: examples;
                                  # 3: examples keep their purpose, only real ones, no placeholders,
                                  # whole sections; 4: a section reached by two labels, once;
                                  # 5: purposes by the site's structure, not by address;
                                  # 6: Markdown API references' pages, API entries)
PURPOSES = {"learn": "Learn", "do": "Do", "lookup": "Look up", "understand": "Understand"}

# The sites' own names for their parts, on a title made plain (lower case, without the
# project's name: "NumPy reference" -> "reference"), each matched as the whole title. A page
# that starts a part (its contents list other pages, or nothing lists it) is named by PARTS
# too: "F2PY reference manual", "Python HOWTOs"; any other page only by LABELS, whose words
# say what a page is wherever it is ("Logging HOWTO", "Argparse Tutorial"), not what it is
# about ("imp — Access the import internals", "doctest — Test interactive Python examples").
LABELS = [
    ("removed", r"(.* )?release notes?( .*)?|(.* )?(what'?s|what is) new( in( .*)?)?|whatsnew|(.* )?change ?log( .*)?|"
                r"release history|contributing( .*)?|(.* )?contributor'?s? guide|how to contribute( .*)?|"
                r"code of conduct|(.* )?licen[cs]e|copyright|history and licen[cs]e|"
                r"about( this| these)? (documents?|documentation|docs)|dealing with bugs|reporting bugs|"
                r"search( page)?|download( .*)? documentation|improve( a| this)? documentation( page)?"),
    ("learn", r"(.* )?tutorials?|getting started( .*)?|quick ?start( guide)?|absolute basics( .*)?|"
              r"(\d+ )?minutes to( .*)?|first steps( .*)?"),
    ("do", r"(.* )?how-?tos?|(.* )?howtos?|(.* )?cookbook|(.* )?faqs?|(.* )?frequently asked questions|"
           r"installing( .*)?|installation( .*)?|(.* )?migration guide|setup and usage"),
    ("lookup", r"glossary|(.* )?index"),
    ("understand", r"fundamentals|(key |core |basic )?concepts|internals|under[- ]the[- ]hood( .*)?|"
                   r"explanations?|background|overview|architecture|philosophy|what is .*"),
]
PARTS = [
    ("removed", r"changes|history|news|development|developers?|(.* )?developer'?s? guide|governance( .*)?|roadmap|"
                r"building( .*)? from source|build(ing)? from source( .*)?"),
    ("learn", r"(.* )?tutorials?( .*)?|(.* )?quick ?start( guide)?|(.* )?for (absolute )?beginners|"
              r"(.* )?tour( of .*)?|learn( .*)?"),
    ("do", r"(.* )?how-?tos?( .*)?|(.* )?howtos?( .*)?|how to .*|(.* )?user'?s? guide( .*)?|(.* )?recipes|"
           r"install( .*)?|migrating( .*)?|porting( .*)?|(.* )?examples|(.* )?gallery|(.* )?guides?"),
    ("lookup", r"(.* )?reference( manual| guide)?|(.* )?api( reference| documentation| docs)?|"
               r"(.* )?standard library|(.* )?module index"),
    ("understand", r"(.* )?fundamentals|(.* )?internals|(.* )?concepts|design( .*)?"),
]
LABEL_RE = {p: re.compile(rx) for p, rx in LABELS}
# Titles that name a place, not a kind of page: an "Overview" section holds how-tos and tutorials
# too (langchain's "Create an agent"), so such a title labels its own page only
PLACE_NAMES = {"overview", "introduction", "intro", "home", "welcome", "index", "start here", "about", "docs",
               "documentation"}
# Titles that name a collection of pages ("Advanced User Guide", "API reference", "Tutorials"):
# such a folder's page names what its folder holds, by address too; a page named for its own
# topic ("Getting Started", "Install spaCy") does not
COLLECTION = re.compile(r"(.* )?(user'?s? )?guides?( .*)?|(.* )?tutorials?( .*)?|(.* )?how-?tos?|(.* )?howtos?|"
                        r"(.* )?recipes|(.* )?examples|(.* )?gallery|(.* )?cookbook|(.* )?faqs?|"
                        r"(.* )?reference( manual| guide)?|(.* )?api( reference| documentation| docs)?|"
                        r"(.* )?standard library|(.* )?module index|(.* )?concepts|(.* )?internals|"
                        r"(.* )?fundamentals|explanations?")
PART_RE = {p: re.compile(rx) for p, rx in PARTS}
ORDER = ("removed", "learn", "do", "lookup", "understand")      # (the first that matches)

# A part's folder, where nothing above it says (the first folder of its address)
FOLDERS = {
    "learn": {"tutorial", "tutorials", "getting_started", "getting-started", "quickstart", "learn"},
    "do": {"howto", "howtos", "how-to", "how_to", "user_guide", "user-guide", "userguide", "user", "guide",
           "guides", "faq", "using", "installing", "install", "installation", "distributing", "extending",
           "examples", "cookbook", "usage"},
    "lookup": {"reference", "api", "library", "c-api", "capi", "builtins", "std", "ref", "generated", "cpp", "c"},
    "understand": {"concepts", "explanation", "explanations", "background", "internals"},
    "removed": {"whatsnew", "whats-new", "release", "releases", "changelog", "changes", "dev", "development",
                "contributing", "contribute", "building", "blog", "release_notes", "release-notes"},
}
FOLDER_OF = {f: p for p, fs in FOLDERS.items() for f in fs}

# Sections of an entry that only part it (cppreference's API pages, and others like them)
SUBPARTS = {"parameters", "return value", "return values", "returns", "exceptions", "complexity", "notes",
            "note", "defect reports", "see also", "references", "external links", "template parameters",
            "member types", "member functions", "non-member functions", "data members", "member constants",
            "member objects", "nested types", "nested classes", "helper classes", "helper types",
            "helper variable template", "helper variable templates", "helper templates", "helper concepts",
            "deduction guides", "specializations", "protected member functions", "public member functions",
            "member variables", "types", "constants", "functions", "classes", "macros", "macro constants",
            "objects", "keywords", "includes", "type requirements", "requirements", "error handling",
            "next steps", "what's next", "related", "related pages", "related content", "learn more",
            "further reading", "additional resources", "resources", "signature", "description", "properties",
            "extends", "constructors"}
LINK_LINE = re.compile(r"^\s*(?:[-*+]|\d+\.)?\s*\[[^\]]+\]\([^)]+\)\s*(?:[:—–-]?\s*.{0,200})?$")


RELEASES = re.compile(r"(.* )?release notes?( .*)?|(.* )?(what'?s|what is) new( in( .*)?)?|whatsnew|(.* )?change ?log( .*)?|"
                      r"release history")


def unread(titles: dict[str, str], api_pages: set[str], names: set[str]) -> set[str]:
    """Pages of a Sphinx site not worth downloading, known from its inventory alone (their
    titles): a page whose own title says it is about the project (release notes,
    contributing), and every page in a folder whose index page is release notes (pandas'
    whatsnew/: 120 pages). What else the contents put under such pages is left out after the
    download (page_purposes). Pages that document API objects are always read."""
    releases = {page.rsplit("/", 1)[0] + "/" for page, t in titles.items()
                if page.endswith("/index.html") and RELEASES.fullmatch(plain_title(t, names))}
    out = set()
    for page in set(titles) | {p for f in releases for p in titles if p.startswith(f)}:
        if page in api_pages:
            continue
        part = page.endswith("index.html")             # (a folder's first page starts a part)
        if label_of(titles.get(page, ""), names, part) == "removed" or any(page.startswith(f) for f in releases):
            out.add(page)
    return out


def plain_title(title: str, names: set[str]) -> str:
    """A title as LABELS reads it: "NumPy 2.5.0 Release Notes" -> "2.5.0 release notes"."""
    t = re.sub(r" \((page|section)\)$", "", title).lower().replace("’", "'")
    t = re.sub(r"[^\w\s'+./-]", " ", t)
    words = [w for w in t.split() if w not in names and w not in ("the", "a", "an")]
    return " ".join(words)


def label_of(title: str, names: set[str], part: bool = True) -> str | None:
    """What a title says a page is: "removed", a purpose, or None. `part`: the page starts
    a part of the docs (PARTS name it too)."""
    t = plain_title(title, names)
    if not t:
        return None
    return next((p for p in ORDER if LABEL_RE[p].fullmatch(t) or (part and PART_RE[p].fullmatch(t))), None)


def names_of(meta: dict) -> set[str]:
    """The project's name as its titles write it: numpy; C++ (cpp); python."""
    from docsearch import sources
    name = str(meta.get("name") or "").lower()
    out = {name, name.replace("-", " ")}
    known = sources.KNOWN.get(name) or {}
    if known.get("standards"):
        out.add(known["standards"].lower())
    project = str(meta.get("project") or "").lower()
    if project:
        out.add(project)
    return {n for n in out if n}


def page_of(location: str, meta: dict, stored: set[str]) -> str | None:
    """The stored page an entry is on (as order.page_order names it; a guide's under guide/)."""
    from docsearch import order
    rel = order.rel_in(location, meta)
    if rel is None:
        return None
    for c in (rel, rel + "/index.html", rel + ".html"):
        if c in stored:
            return c
    return rel


class Pages(NamedTuple):
    order: list[str]                 # the pages in reading order (order.page_order)
    purpose: dict[str, str]          # each page's purpose, or "removed"
    anchor: dict[str, str | None]    # the page whose title gave it (None: its folder, or none)
    up: dict[str, str | None]        # the page above it (in the contents, else by its address)
    parent: dict[str, str | None]    # the page whose contents list it
    title: dict[str, str]
    first: dict[str, str]            # a section of the site's outline -> its first page


def classify(sid: str, meta: dict, entries: list[cli.Entry]) -> Pages:
    """Each page's purpose (see above), and where it comes from."""
    from docsearch import order
    root = meta.get("root", "")
    contents = order.page_order(sid, meta) if root.startswith("http") else order.Contents([], {}, {}, {})
    stored = set(contents.order)
    names = names_of(meta)
    title: dict[str, str] = dict(contents.title)
    named: set[str] = set()                      # API pages: their titles are names, not labels
    for e in entries:
        if "#" in e.location:
            continue
        rel = page_of(e.location, meta, stored)
        if rel and e.kind not in cli.PAGE_KINDS and e.kind not in ("tutorial", "module"):
            named.add(rel)
        elif rel and not title.get(rel):         # (a page whose heading is outside what is kept)
            title[rel] = re.sub(r" \(page\)$", "", e.title)
    pages = set(title) | {p for e in entries if (p := page_of(e.location, meta, stored))}
    guides = {g["dir"] + "/": g for g in meta.get("guides") or []}
    for g in guides.values():                    # a guide's first page: named as its link names it
        first = page_of(g["root"], meta, stored)   # (one its index does not list stands for it:
        if first:                                  # numpy's tutorials have no first page)
            pages.add(first)
            title[first] = g["title"]
    lists = {u for u in contents.parent.values() if u is not None}
    unread = {p for u in meta.get("unread") or [] if (p := page_of(u, meta, stored))}   # (not downloaded:
    unread -= pages                                                   # about the project, organize.unread)

    def above(rel: str) -> str | None:
        """The nearest page above a page by its address: its folder's index page (Sphinx:
        reference/index.html), or the page named as its folder (cppreference: c/keyword for
        c/keyword/alignas)."""
        parts = rel.split("/")
        for k in range(len(parts) - 1, 0, -1):
            folder = "/".join(parts[:k])
            for c in (folder + "/index.html", folder + ".html", folder):
                if c != rel and (c in pages or c in unread):
                    return c
        return None

    up: dict[str, str | None] = {r: contents.parent.get(r) or above(r) for r in pages}
    # What gives a page its purpose: its own title, then what is above it in the docs' contents
    # or the site's outline, never what is above it by its address (litellm's docs/ page,
    # "Getting Started", is not what docs/proxy/... are; spaCy's usage page, "Install spaCy",
    # is not what usage/... are): a page no contents nor outline places is named by its folder.
    walk: dict[str, str | None] = {r: contents.parent.get(r) for r in pages if r not in contents.by_nav}
    label = {r: None if r in named else label_of(title.get(r, ""), names, r in lists or contents.parent.get(r) is None)
             for r in pages}
    label.update({r: "removed" for r in unread})
    # A page no contents list has, in the site's own outline (site.py: its llms.txt headings, its
    # search index, its sidebar): above it are its sections ("§Get started"), as if they were
    # pages, named as the site names them; then its address.
    keys_of: dict[str, list[str]] = {}
    first: dict[str, str] = {}
    for rel, crumbs in outline_of(sid, meta, stored).items():
        if rel not in pages or (contents.parent.get(rel) is not None and rel not in contents.by_nav) or not crumbs:
            continue
        keys = ["§" + " / ".join(crumbs[:k]) for k in range(1, len(crumbs) + 1)]
        keys_of[rel] = keys
        for k, key in enumerate(keys):
            if key not in up:                    # (a top section: a part of its own, not under the
                up[key] = walk[key] = keys[k - 1] if k else None     # page its first page's address is in)
                title[key] = crumbs[k]
                label[key] = label_of(crumbs[k], names)
        up[rel] = walk[rel] = keys[-1]
        if rel not in named:                     # a page of the outline is a leaf: its sections name
            label[rel] = label_of(title.get(rel, ""), names, part=False)    # parts, not its title
    # A top section of the outline that holds much of the site ("AGENT DEVELOPMENT LIFECYCLE":
    # 4,000 of langchain's 6,800) parts the docs by its own sections (Build, Observe, Deploy)
    tops = collections.Counter(keys[0] for keys in keys_of.values())
    subs: dict[str, set[str]] = {}
    for keys in keys_of.values():
        if len(keys) > 1:
            subs.setdefault(keys[0], set()).add(keys[1])
    big = {t for t, n in tops.items() if n > len(keys_of) / 3 and len(subs.get(t, ())) >= 3}
    for t in big:
        for sub in subs[t]:
            up[sub] = None                       # (a part of its own, in the home view)

    def part_key(said: list[str]) -> str | None:
        """The outline section that is a page's part: its top one, or the one under it, if big."""
        keys = [r for r in reversed(said) if r.startswith("§")]
        return keys[1] if len(keys) > 1 and keys[0] in big else (keys[0] if keys else None)
    order_ = []
    for r in contents.order + sorted(pages - stored, key=order.natural):
        for key in keys_of.get(r, []):
            if key not in first:
                first[key] = r
                order_.append(key)
        order_.append(r)
    purpose: dict[str, str] = {}
    anchor: dict[str, str | None] = {}
    for rel in pages | set(first):
        cur, seen, said = rel, set(), []
        while cur is not None and cur not in seen:   # the page, then the pages above it
            seen.add(cur)
            said.append(cur)
            cur = walk.get(cur)
        guide = next((g for f, g in guides.items() if rel.startswith(f)), None)
        own = rel[len(guide["dir"]) + 1:] if guide else rel          # (its address in its part)
        if any(label.get(r) == "removed" for r in said) or (
                (guide or contents.parent.get(rel) is None) and FOLDERS["removed"] & set(own.lower().split("/")[:-1])):
            purpose[rel], anchor[rel] = "removed", None   # (a guide's page, or one no contents list: its
            continue                                      # folder says, as development/ in polars' guide)
        at = next((r for r in said if label.get(r) and (
            r == rel or plain_title(title.get(r, ""), names) not in PLACE_NAMES)), None)   # (a place: its own page)
        if at is None:                           # by its address: a folder's page that names a collection
            cur, seen_ = above(rel), set()
            while cur is not None and cur not in seen_ and at is None:
                seen_.add(cur)
                if label.get(cur) and COLLECTION.fullmatch(plain_title(title.get(cur, ""), names)):
                    at = cur
                cur = above(cur)
        top = own.split("/")[0] if "/" in own else ""
        if at is not None:
            purpose[rel], anchor[rel] = label[at], at
        elif guide is not None:                  # a guide's page: the guide's purpose, in its part:
            purpose[rel] = guide["purpose"]      # its top section in the guide's outline, else the guide
            anchor[rel] = part_key(said) or page_of(guide["root"], meta, stored)
        elif rel in keys_of or rel.startswith("§"):     # in the site's outline, and no section says
            purpose[rel] = "do"                           # reference, tutorial or explanation: a guide
            anchor[rel] = part_key(said)
        else:                                    # named by its folder (the nearest that says: docs/learn/):
            folders = own.split("/")[:-1]        # the part is that folder's first page
            k = next((k for k in range(len(folders) - 1, -1, -1) if folders[k].lower() in FOLDER_OF), None)
            purpose[rel] = FOLDER_OF[folders[k].lower()] if k is not None else "lookup"
            base = "/".join(folders[:k + 1]) + "/" if k is not None else None
            anchor[rel] = next((r for r in reversed(said) if base and r.startswith(base)), None)
    return Pages(order_, purpose, anchor, up, dict(contents.parent), title, first)


def outline_of(sid: str, meta: dict, stored: set[str]) -> dict[str, list[str]]:
    """Each page's sections in the site's own outline (outline.json: site.py), by its place
    among the stored pages."""
    try:
        found = json.loads((cli.HOME / sid / "outline.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {rel: crumbs for url, crumbs in found.items() if (rel := page_of(url, meta, stored))}


def page_purposes(sid: str, meta: dict, entries: list[cli.Entry]) -> dict[str, str]:
    """Each page's purpose, or "removed" (see above)."""
    return classify(sid, meta, entries).purpose


def contents(sid: str) -> list[dict]:
    """The docs' table of contents, by purpose: for each, its parts (the pages that name it,
    "NumPy user guide", "The Python Tutorial") in reading order, each with the pages its
    contents list under it. Kept in contents.json, made again when the entries change."""
    d = cli.HOME / sid
    cache = d / "contents.json"
    newest = max((d / f).stat().st_mtime for f in ("entries.json", "meta.json"))
    if cache.exists() and cache.stat().st_mtime >= newest:
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except ValueError:
            pass
    meta = cli.load_meta(sid)
    entries = list(cli.iter_entries(sid, keep=1))
    pages = classify(sid, meta, entries)
    stored = set(pages.order)
    count: dict[tuple[str, str], int] = {}           # (a page, a purpose) -> its entries of that purpose
    prose: set[str] = set()                          # pages with more than API objects on them
    for e in entries:
        rel = page_of(e.location, meta, stored) or e.location
        count[(rel, e.purpose)] = count.get((rel, e.purpose), 0) + 1
        if e.kind in cli.PAGE_KINDS:
            prose.add(rel)

    def head_of(rel: str) -> str | None:
        """The topmost page above `rel` that gives its purpose (the part it is in)."""
        at, top, seen = pages.anchor.get(rel), None, set()
        while at is not None and at not in seen and pages.purpose.get(at) == pages.purpose.get(rel):
            seen.add(at)
            top = at
            at = pages.anchor.get(pages.up.get(at)) if pages.up.get(at) else None
        return top

    heads: dict[str, list[str]] = {p: [] for p in PURPOSES}
    under: dict[str, int] = {}
    for rel in pages.order:
        p = pages.purpose.get(rel)
        if p not in PURPOSES:
            continue
        h = head_of(rel)
        if h is None:
            continue
        if h == rel:
            heads[p].append(rel)
        under[h] = under.get(h, 0) + count.get((rel, p), 0)    # (its own purpose's: not the examples
                                                                  # of a Look up part)
    kids: dict[str, list[str]] = {}                  # a page's contents; by address, the pages that
    sections = {u for u in pages.up.values() if u}   # have pages under them, or prose (not numpy.sum's)
    for rel in pages.order:
        up = pages.up.get(rel)
        if up is not None and pages.purpose.get(rel) == pages.purpose.get(up) and head_of(rel) != rel \
                and (pages.parent.get(rel) == up or rel in sections or rel in prose):
            kids.setdefault(up, []).append(rel)
    pages_dir = d / "pages"

    def item(rel: str) -> dict:
        """A page to open; for a section of the site's outline, or one that stands for a guide
        with no first page, its first page."""
        at = pages.first.get(rel, rel)
        if offline.page_file(pages_dir, at) is not None and not offline.page_file(pages_dir, at).exists():
            at = next(iter(kids.get(rel, [])), at)
        return {"title": pages.title.get(rel) or rel, "path": f"{sid}/{at}"}
    out = []
    for p in PURPOSES:
        parts: dict[str, dict] = {}                  # (two pages of one title: one part)
        firsts = {page_of(g["root"], meta, stored): g for g in meta.get("guides") or []}
        for h in heads[p]:
            g = firsts.get(h)                        # (a guide: of no version, read on a day)
            part = parts.setdefault(item(h)["title"], item(h) | {"entries": 0, "pages": [], "more": 0}
                                    | ({"note": f"official guide, as of {g.get('asof', '')}"} if g else {}))
            part["entries"] += under.get(h, 0)
            part["pages"] += [item(k) for k in kids.get(h, [])]
        for title in [t for t, part in parts.items() if junk_part(t, part)]:
            del parts[title]                         # (no entries, or named "index" or by an address)
        for part in parts.values():
            pages_ = list({x["title"]: x for x in reversed(part["pages"])}.values())[::-1]   # (one of a title)
            part["more"], part["pages"] = max(0, len(pages_) - 80), pages_[:80]
        if parts:
            out.append({"purpose": p, "label": PURPOSES[p], "parts": list(parts.values())})
    try:
        cli.write_atomic(cache, json.dumps(out).encode())
    except OSError:
        pass
    return out


def junk_part(title: str, part: dict) -> bool:
    """A part the home view leaves out: one with no entries of its purpose, or named as no part
    is ("index"; an address: keras' "getting-started/faq")."""
    t = title.strip().lower()
    return not part["entries"] or t in ("index", "") or (" " not in t and ("/" in t or t.endswith((".html", ".md"))))


def subpart(e: cli.Entry) -> str | None:
    """The heading of a section that only parts its page: "Return value" of "std::format › Return value";
    one that only lists links to other pages ("Next steps", a grid of cards): its heading too."""
    if e.kind not in ("section", "label") or " › " not in e.title:
        return None
    head = e.title.rsplit(" › ", 1)[1].strip().lower()
    if head in SUBPARTS or head.startswith("inherited from"):
        return head
    return head if links_only(e.text) else None


def body(text: str) -> str:
    """A section's own text, without its heading: what its page's entry must hold."""
    return re.sub(r"^#+ [^\n]*(\n+|$)", "", text.strip(), count=1)[:300]


# An API reference page that says what it documents, first (reference.langchain.com, written as
# Markdown: "> **Function** in `langchain`")
REF_KIND = re.compile(r"^> \*\*(function|class|method|attribute|property|module|variable|constant|type alias|"
                      r"interface|enum)\*\* in `[^`]+`", re.I | re.M)


def named_api(entries: list[cli.Entry], meta: dict) -> set[int]:
    """A page titled as the last part of its address that says it documents an API object
    (create_agent at .../python/langchain/agents/factory/create_agent): an API entry, named from
    its address under its docs' folder (langchain.agents.factory.create_agent), of its kind.
    Returns the entries renamed (their vectors are made again)."""
    roots = [meta.get("root") or ""] + [g["root"] for g in meta.get("guides") or []]
    renamed = set()
    for i, e in enumerate(entries):
        if e.kind not in ("page", "doc") or "#" in e.location:
            continue
        m = REF_KIND.search(e.text[:2000])
        last = e.location.rstrip("/").removesuffix(".md").rsplit("/", 1)[-1]
        if not m or re.sub(r"\(\)$", "", e.title.strip()) != last:
            continue
        root = next((r for r in roots if r and e.location.startswith(r)), None)
        if root is None:
            continue
        top = root.rstrip("/").rsplit("/", 1)[-1]
        parts = ([top] if re.fullmatch(r"[A-Za-z_]\w*", top) else []) + \
            [x for x in e.location[len(root):].removesuffix(".md").strip("/").split("/") if x]
        if all(re.fullmatch(r"[A-Za-z_]\w*", x) for x in parts):
            e.title, e.kind = ".".join(parts), m.group(1).lower()
            renamed.add(i)
    return renamed


def heading_id(e: cli.Entry) -> bool:
    """Is a section's anchor the id its heading got from its words (#parquet), not a label the
    docs named it by (#io-parquet: what their cross-references and links elsewhere use)?"""
    title = re.sub(r" \((section|page)\)$", "", e.title.rsplit(" › ", 1)[-1])
    return e.location.partition("#")[2] == re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def links_only(text: str) -> bool:
    """Is a section's text only links to other pages (a list of them, cards)?"""
    lines = [ln for ln in re.sub(r"^#+ [^\n]*(\n+|$)", "", text.strip(), count=1).splitlines()
             if ln.strip() and not ln.lstrip().startswith("#")]
    links = linked = 0
    after = False                                    # (a card's description, on the line after its link)
    for ln in lines:
        if LINK_LINE.match(ln):
            links, linked, after = links + 1, linked + 1, True
        elif after and len(ln) < 200 and not re.match(r"\s*([-*+]|\d+\.)\s", ln):
            linked, after = linked + 1, False
        else:
            after = False
    return links >= 2 and linked >= 0.8 * len(lines)


def organize(sid: str, entries: list[cli.Entry], meta: dict) -> tuple[list[cli.Entry], list[int]]:
    """(the entries kept, each with its purpose, then the example entries made from them
    (examples.py); each one's number among `entries`, -1 for an example made now). The pages
    of removed entries are deleted from the copy's stored pages; meta says what was left out."""
    if meta.get("kind") in ("man", "saved"):         # man pages; articles you saved: all kept
        for e in entries:                            # (a man page is looked up; an article, learned)
            said = label_of(e.title, set(), part=False)
            e.purpose = said if said in PURPOSES else "lookup" if meta.get("kind") == "man" else "learn"
        meta["organized"] = VERSION
        return entries, list(range(len(entries)))
    renamed = named_api(entries, meta)               # (Markdown API references: their pages, API entries)
    purposes = page_purposes(sid, meta, entries)
    stored_pages = set(purposes)
    by_page: dict[str, list[int]] = {}
    for i, e in enumerate(entries):
        by_page.setdefault(page_of(e.location, meta, stored_pages) or e.location, []).append(i)
    drop: set[int] = set()
    removed_pages: set[str] = set()
    folded = 0
    for rel, ids in by_page.items():
        page_purpose = purposes.get(rel, "lookup")
        api = [i for i in ids if entries[i].kind not in cli.PAGE_KINDS]
        if page_purpose == "removed" and not api:
            drop.update(ids)
            removed_pages.add(rel)
            continue
        whole = [i for i in ids if "#" not in entries[i].location]
        page_title = {re.sub(r" \(page\)$", "", entries[i].title) for i in whole}
        api_names = {cli.api_name(entries[i].title).lower() for i in api}
        seen: set[tuple[str, str]] = set()          # (a section reached by two of its labels: the
        for i in sorted(ids, key=lambda i: heading_id(entries[i])):     # docs' own label kept)
            e = entries[i]
            e.purpose = "lookup" if e.kind not in cli.PAGE_KINDS else (
                "lookup" if page_purpose == "removed" else page_purpose)
            if e.kind == "example":                  # (an example is for doing, or learning, wherever it is)
                e.purpose = "learn" if page_purpose == "learn" else "do"
            if subpart(e) and (not body(e.text) or any(body(e.text) in entries[j].text for j in ids
                                                       if j != i and j not in drop and not subpart(entries[j]))):
                drop.add(i)                          # (its page's entry has it, word for word)
                folded += 1
            elif e.kind == "label" and re.sub(r" \(section\)$", "", e.title) in page_title:
                drop.add(i)                          # (the page under its own title again)
                folded += 1
            elif e.kind in cli.PAGE_KINDS and e.kind != "example" and (e.title, e.text) in seen:
                drop.add(i)                          # (one section twice: pandas' "Pure Python" is
                folded += 1                          # #pure-python and #enhancingperf-pure)
            elif e.kind == "doc" and "#" not in e.location and \
                    re.sub(r" \(page\)$", "", e.title).lower() in api_names:
                drop.add(i)                          # (numpy.sum's page: the object numpy.sum)
                folded += 1
            if i not in drop:
                seen.add((e.title, e.text))
    pages_dir = cli.HOME / sid / "pages"
    for rel in removed_pages:
        f = offline.page_file(pages_dir, rel)
        if f is not None:
            f.unlink(missing_ok=True)
    keep = [i for i in range(len(entries)) if i not in drop]
    from docsearch import examples
    for i in keep:                                   # an Example section: an example, for search how
        e = entries[i]
        if e.kind == "section" and re.search(r" › Examples?$", e.title):
            e.kind, e.purpose = "example", "learn" if e.purpose == "learn" else "do"
    keep = [i for i in keep if not (entries[i].kind == "example" and examples.placeholder(entries[i].text))]
    # An API entry's examples, an entry of their own: made again by today's rules. Those made
    # before that come out the same are kept (and their vectors with them); the others go.
    api_at = {entries[i].location for i in keep if entries[i].kind not in cli.PAGE_KINDS}
    made = {i for i in keep if entries[i].kind == "example" and entries[i].location in api_at}
    fresh = {x.title: x for x in examples.entries_of([entries[i] for i in keep if i not in made])}
    for i in sorted(made):
        same = fresh.get(entries[i].title)
        if same is not None and same.text == entries[i].text[:cli.PREVIEW_CHARS]:
            del fresh[entries[i].title]
        else:
            keep.remove(i)
    new = list(fresh.values())
    at = {entries[i].location: entries[i] for i in keep if entries[i].kind != "example"}
    changed = set(renamed)                           # an Example section, with what its page is
    for i in [i for i in keep if entries[i].kind == "example" and i not in made]:     # first
        host = at.get(entries[i].location.split("#")[0])
        text = examples.with_lead(host, entries[i].text) if host else entries[i].text
        if text != entries[i].text:
            entries[i].text = text
            changed.add(i)                           # (new text: a new vector)
    before = meta.get("left_out") or {} if meta.get("organized") else {}    # (organized again: a guide added)
    now = {"pages": len(removed_pages) + (0 if before else len(meta.get("unread") or [])),
           "entries": len(drop) - folded, "folded": folded}
    meta["organized"] = VERSION
    meta["left_out"] = {k: before.get(k, 0) + v for k, v in now.items()}
    return [entries[i] for i in keep] + new, [-1 if i in changed else i for i in keep] + [-1] * len(new)


def organize_copy(sid: str) -> dict:
    """A copy made before docs were organized: organized now, with nothing downloaded. Its
    entries are classified, removed and folded; its vectors keep the rows of the kept ones;
    its search caches are made again."""
    import numpy as np
    d = cli.HOME / sid
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    entries = list(cli.iter_entries(sid))
    had = dict(meta.get("left_out") or {})           # (organized before: say only what changed now)
    recut = whole_sections(sid, entries, meta) if (meta.get("organized") or 0) < 3 else set()
    kept, keep = organize(sid, entries, meta)
    keep = [-1 if i in recut else i for i in keep]   # (new text: a new vector)
    vectors = None
    if (d / "emb.npy").exists():
        vectors = np.load(d / "emb.npy", allow_pickle=False)
        if len(vectors) != len(entries):
            vectors = None                           # (not this copy's: made again by search embed)
    meta["count"] = len(kept)
    cli.save(sid, kept, meta)                        # (removes emb.npy: these rows replace it)
    for f in ("bm25.npz", "tails.bin", "tails.npy", "order.npy"):
        (d / f).unlink(missing_ok=True)
    cli.make_search_caches(sid)
    if vectors is not None:
        save_vectors(sid, vectors, kept, keep)
    return {k: v - had.get(k, 0) for k, v in (meta.get("left_out") or {}).items()}


def whole_sections(sid: str, entries: list[cli.Entry], meta: dict) -> set[int]:
    """Sections reached by a label, cut before version 3 as their first paragraph (Python's
    "Reading and writing files": 111 letters of 8,385): cut again, whole, from the stored
    pages. Nothing downloaded. Returns the entries whose text changed."""
    root, pages_dir = meta.get("root") or "", cli.HOME / sid / "pages"
    by_page: dict[str, list[int]] = {}
    for i, e in enumerate(entries):
        if e.kind == "label" and "#" in e.location and root and e.location.startswith(root):
            by_page.setdefault(e.location[len(root):].split("#")[0], []).append(i)
    changed = set()
    for rel, idx in by_page.items():
        f = offline.page_file(pages_dir, rel)
        if f is None or not f.exists():
            continue
        try:
            soup = cli.make_soup(gzip.decompress(f.read_bytes()))
        except (OSError, EOFError, ValueError):
            continue
        for i in idx:
            el = soup.find(id=entries[i].location.split("#", 1)[1])
            if el is None or el.name not in ("span", "a") or el.get_text(strip=True) or not cli.opens_section(el):
                continue
            text = cli.html_to_md(str(el.parent))[:cli.PREVIEW_CHARS]
            if len(text) > len(entries[i].text):
                entries[i].text = text
                changed.add(i)
    return changed


def save_vectors(sid: str, vectors, kept: list[cli.Entry], keep: list[int]) -> None:
    """A copy's vectors after it is organized: the rows it had for the entries kept (`keep`:
    their numbers among the old ones), and made for the new ones (-1, or past the old ones:
    examples, a guide's pages), with nothing else embedded again."""
    import numpy as np
    new = [k for k, i in enumerate(keep) if not 0 <= i < len(vectors)]
    made = {}
    if new:
        model = cli.get_model(download=True)
        texts = [f"{kept[k].title}\n{cli.plain(kept[k].text)[:cli.EMBED_CHARS]}" for k in new]
        with cli.Progress(f"  vectors for {len(new):,} new entries of {sid}", len(texts)) as bar:
            made = dict(zip(new, model.encode(texts, batch=64, progress=bar.update)))
    rows = [made[k] if k in made else vectors[i] for k, i in enumerate(keep)]
    np.save(cli.HOME / sid / "emb.npy", np.stack(rows).astype(np.float32) if rows else
            np.zeros((0, vectors.shape[1]), np.float32))


def migrate() -> None:
    """Copies, and downloads kept aside (standards.py), from before docs were organized:
    organized once. A language standard's copy is made again from its organized download."""
    from docsearch import standards
    places = [(standards.base_dir(g).parent, g) for g in standards_groups() if standards.have_base(g)]
    places += [(cli.HOME, s) for s in cli.indexed()]            # (the downloads first: copies come from them)
    stopped = False
    for home, sid in places:
        try:
            meta = json.loads((home / sid / "meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if meta.get("organized") == VERSION or meta.get("partial") or (home / sid / "crawl").exists():
            continue
        if not stopped:
            from docsearch import web
            web.stop()                               # (a running search page holds their files)
            stopped = True
        group, std = sid.split("@")[0], meta.get("standard") or {}
        if home == cli.HOME and std and standards.have_base(group):
            cli.say(f"{sid}: organizing its docs (learn, do, look up, understand), once: made again from "
                    f"the download of every {std.get('lang', group)} standard")
            standards.make_copy(group, std["edition"], meta.get("spec") or group)
            continue
        real, cli.HOME = cli.HOME, home
        try:
            cli.say(f"{sid}: organizing its docs (learn, do, look up, understand), once")
            out = organize_copy(sid)
            said = ([f"left out {out['pages']} pages about the project (release notes, development...)"]
                    if out.get("pages") else []) + \
                   ([f"folded {out['folded']} parts into the entries that hold them"] if out.get("folded") else [])
            if said:
                cli.say("  " + "; ".join(said))
        finally:
            cli.HOME = real


def standards_groups() -> list[str]:
    from docsearch import sources, standards
    return [g for g in sources.KNOWN if standards.profile(g)]


def counts(sid: str) -> dict[str, int]:
    """How many entries a copy has of each purpose."""
    out = {p: 0 for p in PURPOSES}
    for e in cli.iter_entries(sid, keep=1):
        if e.purpose in out:
            out[e.purpose] += 1
    return out
