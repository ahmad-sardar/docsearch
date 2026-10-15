"""Doxygen docs (C and C++ libraries: OpenCV, and many others): their API, from the tag file
Doxygen writes next to the pages (opencv.tag: every class, function, constant and macro, with
the page and the anchor it is documented at).

The pages themselves are read as any page (importers.website_page: the tutorials, the module
pages); the tag file adds an entry for each API object, named as the code names it
(cv::imread), with its signature and the text Doxygen wrote for it, at its place on its page.
A class's page is its class's entry. Doxygen titles every page "PROJECT: title": the project's
name is left out.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from docsearch import cli

KINDS = {"function": "function", "variable": "variable", "typedef": "type alias", "enumeration": "enum",
         "enumvalue": "constant", "define": "macro", "property": "property"}
SCOPES = ("namespace", "class", "struct", "union", "protocol")     # compounds whose members are named in them
TYPES = ("class", "struct", "union", "protocol")


def tag_file(folder: Path) -> Path | None:
    """The Doxygen tag file of a folder of docs (next to its index.html), if it has one."""
    for f in sorted(folder.rglob("*.tag"), key=lambda p: len(p.parts))[:3]:
        try:
            with open(f, "rb") as fh:
                head = fh.read(400)
        except OSError:
            continue
        if b"<tagfile" in head:
            return f
    return None


def api(tag: Path, root: str) -> tuple[dict[str, list[tuple[str, str, str, str]]], dict[str, tuple[str, str]]]:
    """From a tag file: the API objects on each page ({page: [(anchor, name, kind, signature)]}),
    each once (one documented in a module and its namespace both: named in its namespace), and
    the pages that are a class's ({page: (name, kind)})."""
    on: dict[tuple[str, str], tuple[str, str, str]] = {}
    types: dict[str, tuple[str, str]] = {}
    for comp in ET.parse(tag).getroot().iter("compound"):
        ckind, cname = comp.get("kind"), (comp.findtext("name") or "").strip()
        if ckind in TYPES and comp.findtext("filename"):
            page = comp.findtext("filename").strip()
            types[page if page.endswith(".html") else page + ".html"] = (cname, ckind)
        if ckind not in SCOPES + ("group", "file"):
            continue
        scope = cname + "::" if ckind in SCOPES else ""
        for m in comp.findall("member"):
            kind = KINDS.get(m.get("kind") or "")
            page, anchor = (m.findtext("anchorfile") or "").strip(), (m.findtext("anchor") or "").strip()
            if not kind or not page or not anchor:
                continue
            name = scope + (m.findtext("name") or "").strip()
            sig = f"{(m.findtext('type') or '').strip()} {name}{(m.findtext('arglist') or '').strip()}".strip()
            had = on.get((page, anchor))
            if had is None or ("::" in name and "::" not in had[0]):    # (its namespace's name over its module's)
                on[(page, anchor)] = (name, kind, sig)
    by_page: dict[str, list[tuple[str, str, str, str]]] = {}
    for (page, anchor), (name, kind, sig) in on.items():
        by_page.setdefault(page, []).append((anchor, name, kind, sig))
    return by_page, types


def structure(tag: Path) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Its pages' titles ({file: title}: Doxygen's own, not the first heading on the page) and
    each page's place in the docs' own outline ({file: [the titles above it, topmost first]}):
    a tutorial under the pages that list it (its subpages: "OpenCV-Python Tutorials", "Image
    Processing in OpenCV"); a module, and a class, under the modules above it, in the API
    reference ("API reference", "Image Processing"). Organizing reads the outline
    (organize.outline_of)."""
    title: dict[str, str] = {}
    files: dict[str, str] = {}
    kind: dict[str, str] = {}
    subs: dict[str, list[str]] = {}
    members: dict[str, list[str]] = {}              # a module -> the classes in it
    class_file: dict[str, str] = {}
    for comp in ET.parse(tag).getroot().iter("compound"):
        ck, name = comp.get("kind"), (comp.findtext("name") or "").strip()
        f = (comp.findtext("filename") or "").strip()
        f = f if not f or f.endswith(".html") else f + ".html"
        if ck in TYPES:
            class_file[name] = f
        if ck not in ("page", "group"):
            continue
        kind[name], files[name], title[name] = ck, f, (comp.findtext("title") or name).strip()
        subs[name] = [(x.text or "").strip() for x in comp.findall("subpage" if ck == "page" else "subgroup")]
        members[name] = [(x.text or "").strip() for x in comp.findall("class")] if ck == "group" else []
    by_file = {f: n for n, f in files.items()}
    up: dict[str, str] = {}
    for name, children in subs.items():              # (a subpage is named by its file, or by its name)
        for c in children:
            up.setdefault(by_file.get(c if c.endswith(".html") else c + ".html", c), name)

    def above(name: str) -> list[str]:
        crumbs, cur, seen = [], up.get(name), set()
        while cur and cur not in seen and cur != "index":
            seen.add(cur)
            crumbs.insert(0, title.get(cur, cur))
            cur = up.get(cur)
        return crumbs
    places: dict[str, list[str]] = {}
    for name, f in files.items():
        crumbs = above(name)
        if kind[name] == "group":
            crumbs = ["API reference"] + crumbs
            for cls in members[name]:
                if class_file.get(cls):
                    places.setdefault(class_file[cls], crumbs + [title[name]])
        if crumbs:
            places[f] = crumbs
    return {files[n]: t for n, t in title.items() if files.get(n)}, places


def entries_of(page_html: bytes, url: str, objs: list[tuple[str, str, str, str]], source: str) -> list[cli.Entry]:
    """The API objects documented on one page, cut out of it: each one's text is its "memdoc"
    (what Doxygen wrote for it), after its signature. One walk through the page: each anchor
    takes the documentation block that follows it (a page of 2,000 objects, read once)."""
    soup = cli.make_soup(page_html)
    wanted = {a for a, _, _, _ in objs}
    doc_of: dict[str, object] = {}
    pending: list[str] = []
    for el in soup.find_all(["a", "div"]):
        if el.name == "a":
            a = el.get("id") or el.get("name")
            if a in wanted and a not in doc_of:
                pending.append(a)
        elif pending and "memitem" in (el.get("class") or []):
            doc = el.find("div", class_="memdoc")
            for a in pending:
                doc_of[a] = doc
            pending = []
    out = []
    for anchor, name, kind, sig in objs:
        doc = doc_of.get(anchor)
        text = cli.html_to_md(str(doc)) if doc is not None else ""
        out.append(cli.Entry(name, kind, f"{url}#{anchor}", f"```cpp\n{sig}\n```\n\n{text}"[:cli.PREVIEW_CHARS], source))
    return out


def tidy(entries: list[cli.Entry], root: str, types: dict[str, tuple[str, str]], titles: dict[str, str]) -> None:
    """Pages read as pages: a class's page is that class's entry (cv::Mat); a page and its
    sections are titled as Doxygen titles the page (the Clojure tutorial's first heading is
    "What we'll do in this tutorial"); the "PROJECT: " Doxygen puts before every title is left
    out (when most pages have it)."""
    pages = [e for e in entries if e.kind == "page"]
    heads = [m.group(1) for e in pages if (m := re.match(r"^([^:]{1,40}): ", e.title))]
    common = max(set(heads), key=heads.count) if heads else None
    strip = common is not None and heads.count(common) >= 0.8 * len(pages)
    for e in entries:
        page, _, part = e.location.partition("#")
        named = titles.get(page[len(root):]) if e.kind in ("page", "section") and page.startswith(root) else None
        if named and not part and e.kind == "page":
            e.title = named
        elif named and part and " › " in e.title:
            e.title = f"{named} › {e.title.split(' › ', 1)[1]}"
    for e in entries:
        if strip and e.title.startswith(common + ": "):
            e.title = e.title[len(common) + 2:]
        if e.kind == "page" and e.location.startswith(root):
            hit = types.get(e.location[len(root):])
            if hit:
                e.title, e.kind = hit
