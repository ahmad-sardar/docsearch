"""Official guides of a package, read with its docs as parts of the same copy.

A package's reference often lives apart from its guide: polars' API reference
(docs.pola.rs/api/python/stable/) links "User guide" (docs.pola.rs/); numpy's docs link
"Learn" (numpy.org/numpy-tutorials/). Such a guide is found from the docs' own header, never
guessed, and taken only when it is official: on the docs' own site, or on a site that links
to the package's repository (cli.checked). Its pages are stored next to the docs' (pages/guide/,
with its own address: order.roots) and organized with them (learn, do, understand).

A guide has no version of its own (polars' is always the newest): it is said so, "as of" the
day it was read, and read only with the docs of the newest release, not with older ones.
`search add polars --guide URL` adds one the header does not link (kept in packages.toml).
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse

from docsearch import cli
from docsearch.cli import say

FOLDER = "guide"
CHROME = "header, nav, .bd-header, .navbar, .md-tabs, .md-header, [role=navigation]"
# What a link to a guide is named, the whole of it (or of its first words, in a menu that says
# more under it: "Tutorials" over "Learn how to use TensorFlow..."): not "Learn more" (pymongo's
# link to mongodb.com/solutions), not "Installing" (scipy's to scipy.org), not "Learn ML".
GUIDE_NAME = re.compile(r"(the |our )?((user|developer)('s)? )?(guides?|tutorials?|learn|learning|getting started|"
                        r"get started|quick ?start|how[- ]to( guides)?|how-tos|examples|cookbook|handbook|manual|"
                        r"docs|documentation|book|courses?)", re.I)
# What builds docs sites, as their pages say it (<meta name="generator">)
GENERATOR = re.compile(r"""<meta[^>]+name=["']generator["'][^>]+content=["'][^"']*\b(sphinx|mkdocs|zensical|"""
                       r"docusaurus|mintlify|vitepress|vuepress|docsify|gitbook|nextra|starlight|jupyter ?book|mdbook|"
                       r"antora|mystmd)", re.I)


def find_guides(root: str, page: str, names: set[str]) -> list[dict]:
    """The guides the docs' header and navigation link to, outside the docs: links named as
    something to learn or do from ("User guide", "Learn", "Tutorials", "Examples")."""
    from docsearch import organize
    soup = cli.make_soup(page.encode())
    out: dict[str, dict] = {}
    for el in soup.select(CHROME):
        for a in el.find_all("a", href=True):
            text = re.sub(r"^\W+|\W+$", "", " ".join(next(a.stripped_strings, "").split()))
            if not GUIDE_NAME.fullmatch(text):
                continue
            purpose = organize.label_of(text, names)
            if purpose not in ("learn", "do"):
                continue
            url = urllib.parse.urljoin(root, a["href"]).split("#")[0]
            host = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
            if not cli.safe_url(url) or url.startswith(root) or cli.repo_of(url) or host in cli.SKIP_HOSTS:
                continue
            out.setdefault(url, {"url": url, "title": text, "purpose": purpose})
    return list(out.values())


def official(url: str, root: str, repo: str | None) -> str:
    """Why a guide is the package's own, in words; "" if nothing says so."""
    if urllib.parse.urlparse(url).netloc.lower() == urllib.parse.urlparse(root).netloc.lower():
        return "on the docs' own site"
    return cli.checked(url, "", repo) if repo else ""


def part_of(guide: dict, root: str, k: int) -> dict | None:
    """How to read a guide, as a part of the docs (cli.build_known): its inventory's pages, or
    the pages its other lists name (site.py: sitemap, llms.txt); its own pages only (not the
    docs again, where its site holds them). None when nothing says which pages are the guide's."""
    found = cli.find_docs(guide["url"], lists=True)
    if found is None:
        return None
    kind, groot, _, page = found
    if groot == root or groot.startswith(root) or sibling(groot, root):   # (the docs themselves, a part
        return None                                                      # of them, another version of them)
    title = guide["title"]
    if guide.get("asked") or guide.get("pypi"):       # (named by you, or by PyPI: as its page names itself)
        h = re.search(r"<h1\b[^>]*>(.*?)</h1>|<title>(.*?)</title>", page or "", re.S | re.I)
        title = " ".join(re.sub(r"<[^>]+>", "", (h.group(1) or h.group(2)) if h else "").split()) or title
        named = [x for x in re.split(r"\s+[-|–—]\s+", title) if x.lower() not in ("home", "index", "welcome")]
        title = named[0] if named else title         # ("Home - Docs by LangChain": Docs by LangChain)
    info = {"root": groot, "dir": FOLDER if k == 0 else f"{FOLDER}{k + 1}", "title": title,
            "purpose": guide["purpose"]}
    if kind == "sphinx":
        return {"kind": "sphinx", "url": groot, "guide": info}
    from docsearch import site as sites
    part = {"kind": "website", "root": groot, "start": groot, "prefix": groot, "guide": info}
    surveyed = sites.survey(groot, root=groot)
    own = surveyed is not None and any(surveyed.lists.get(k) for k in ("search index", "llms.txt"))
    if not (own or GENERATOR.search(page or "") or cli.ROOT_HINT.search(page or "")):   # a docs site: its
        return None                                   # own list of pages, or a page that says what built it
                                                      # (or where its docs begin, as Sphinx's and MkDocs' do);
                                                      # not a site with only a sitemap (mongodb.com/solutions/)
    pages, _ = sites.choose(surveyed, "", "default") if surveyed is not None else ([], None)
    pages = [p for p in pages if not p.startswith(root)]          # (its site holds the docs: not them again)
    if pages:                                         # its pages, as its lists name them (site.py)
        part.update(sites.reading(surveyed, pages))
    elif root.startswith(groot):
        return None                                   # (no list: its links would lead to all of the site)
    if root.startswith(groot):                        # its site holds the docs (docs.pola.rs/api/...)
        part["exclude"] = "^" + re.escape(root) + ("|" + part["exclude"][1:] if part.get("exclude") else "")
    return part


def sibling(url: str, root: str) -> bool:
    """Is this the docs at the root again, of another version (docs.pytest.org/en/latest/ next
    to /en/stable/)?"""
    a, b = urllib.parse.urlparse(url), urllib.parse.urlparse(root)
    if a.netloc.lower() != b.netloc.lower():
        return False

    def bare(path: str) -> list[str]:
        return [seg for seg in path.split("/") if seg and not cli.VERSION_SEGMENT.match(seg)]
    return bare(a.path) == bare(b.path) and a.path.rstrip("/") != b.path.rstrip("/")


def wanted(name: str, args) -> list[dict]:
    """The guides you named: --guide URL, and packages.toml's [guides]."""
    urls = list(getattr(args, "guide", None) or []) + config_guides(name)
    return [{"url": u, "title": "Guide", "purpose": "do", "asked": True} for u in dict.fromkeys(urls)
            if cli.safe_url(u)]


def config_guides(name: str) -> list[str]:
    import tomllib
    if not cli.CONFIG.exists():
        return []
    try:
        got = (tomllib.loads(cli.CONFIG.read_text(encoding="utf-8")).get("guides") or {}).get(name)
    except tomllib.TOMLDecodeError:
        return []
    return [got] if isinstance(got, str) else [u for u in got or [] if isinstance(u, str)]


def pypi_docs(name: str, root: str) -> list[dict]:
    """The other docs sites a package's PyPI record names (langchain: its API reference is
    "Documentation", its guides docs.langchain.com "Homepage"): addresses that say they are
    docs (a docs. host, a /docs path), outside the docs found. Not a home page of another kind
    (numpy.org, pola.rs)."""
    try:
        p = cli.project_of(name)
    except (SystemExit, Exception):  # noqa: BLE001 - no record: none
        return []
    out = []
    for u in dict.fromkeys(p["docs"] + p["home"]):
        u = u if u.endswith("/") or "." in u.rsplit("/", 1)[-1] else u + "/"
        host, path = urllib.parse.urlparse(u).netloc.lower(), urllib.parse.urlparse(u).path
        if u.startswith(root) or not (host.startswith(("docs.", "doc.", "documentation.")) or
                                      re.search(r"/docs?(/|$)", path)):
            continue
        out.append({"url": u, "title": "Docs", "purpose": "do", "pypi": True})
    return out


def plan_with(plan: dict, name: str, args, newest: bool, pypi: bool = False) -> dict:
    """The docs' plan with their official guides as more parts: those their header links, and
    (`pypi`: a package found through PyPI) the other docs sites its record names; only with
    the docs of the newest release (a guide has no versions); and those you named."""
    root = plan.get("root") or plan.get("url") or ""
    if not root.startswith("http") or plan.get("found") == "readme":
        return plan
    names = {name.lower(), name.replace("-", " ").lower()}
    found: list[dict] = []
    if newest:
        try:
            _, page = cli.landing(root)
        except Exception:  # noqa: BLE001 - no page: no header to read
            page = ""
        found = find_guides(root, page, names) if page else []
        if pypi:
            found += [g for g in pypi_docs(name, root) if g["url"] not in {f["url"] for f in found}]
    asked = wanted(name, args)
    parts = list(plan.get("parts") or [{k: v for k, v in plan.items() if k not in ("found", "repo", "verified",
                                                                                 "about", "older")}])
    candidates = {g["url"]: g for g in found}
    for g in asked:                                  # (one you named that the header links too: said)
        candidates[g["url"]] = {**candidates[g["url"]], "asked": True} if g["url"] in candidates else g
    for guide in candidates.values():
        if sibling(guide["url"], root):              # (these docs again, of another version)
            continue
        why = official(guide["url"], root, plan.get("repo"))
        if not why:
            if guide.get("asked"):
                say(f"  {guide['url']}: not taken as a guide of {name}: it is not on the docs' site, and it "
                    f"does not link to {plan.get('repo') or 'their repository'}")
            continue
        part = part_of(guide, root, sum(1 for p in parts if p.get("guide")))
        if part is None:
            if guide.get("asked"):
                say(f"  {guide['url']}: not a docs site (no objects.inv, search index or llms.txt, and its page "
                    f"does not say what built it); not read")
            continue
        if any(p.get("guide") and p["guide"]["root"] == part["guide"]["root"] for p in parts):
            continue                                 # (two links to one guide: once)
        say(f"  {name}: " + ("its PyPI record names more official docs" if guide.get("pypi") else
                             "its docs link an official guide")
            + f", \"{part['guide']['title']}\" ({part['guide']['root']}, {why}): read with them")
        parts.append(part)
    if not any(p.get("guide") for p in parts):
        return plan
    taken = [p["guide"]["root"] for p in parts if p.get("guide")]
    if any(g["url"] in taken or g["url"].rstrip("/") + "/" in taken for g in asked):   # (sync reads it again)
        cli.config_set(name, [g["url"] for g in asked], table="guides")
    return {**plan, "root": root, "parts": parts}


def record(meta: dict, part: dict, pages: int) -> None:
    """What a copy says of a guide it has: its address, its folder, its name, the day."""
    g = {**part["guide"], "asof": time.strftime("%Y-%m-%d"), "pages": pages}
    meta["guides"] = [x for x in meta.get("guides") or [] if x["root"] != g["root"]] + [g]


def add_to_copy(sid: str, args) -> None:
    """A copy you have, without the guides found or named now: they are read and added to it
    (its own docs are not downloaded again). Its vectors keep their rows; the guide's are made."""
    from docsearch import importers, organize
    meta = cli.load_meta(sid)
    if meta.get("partial") or not str(meta.get("root", "")).startswith("http") or meta.get("kind") in (
            "man", "saved", "local", "readme"):
        return
    name = meta.get("name") or sid.split("@")[0]
    have = {g["root"] for g in meta.get("guides") or []}
    newest = "==" not in str(meta.get("spec") or "") and not meta.get("standard")
    if meta.get("guides_checked") and not wanted(name, args):
        return
    plan = plan_with({"root": meta["root"], "kind": "website", "repo": cli.copy_repo(meta)}, name, args, newest)
    parts = [p for p in plan.get("parts") or [] if p.get("guide") and p["guide"]["root"] not in have]
    meta["guides_checked"] = time.strftime("%Y-%m-%d")
    if not parts:
        cli.write_atomic(cli.HOME / sid / "meta.json", json.dumps(meta, indent=2).encode())
        return
    old = list(cli.iter_entries(sid))
    new: list[cli.Entry] = []
    for k, part in enumerate(parts):
        part["guide"]["dir"] = f"{FOLDER}{len(have) + k + 1}" if have or k else FOLDER
        store = importers.Store(sid, part["guide"]["root"], part["guide"]["dir"])
        store.reset()
        if part["kind"] == "sphinx":
            found, _ = cli.build_sphinx(name, part["url"], None, args.workers, None, store=store)
        else:
            found, _ = importers.build_website(name, sid, part, store, args.workers, None)
        store.finish(args.workers)
        for e in found:
            e.source = sid if "@" in sid else e.source
        new += found
        record(meta, part, len({e.location.split("#")[0] for e in found}))
        say(f"  {part['guide']['title']}: {len(found)} entries")
    from docsearch import order
    meta["nav"] = order.fetch_nav(meta)
    kept, keep = organize.organize(sid, old + new, meta)
    meta["count"] = len(kept)
    import numpy as np
    d = cli.HOME / sid
    vectors = np.load(d / "emb.npy", allow_pickle=False) if (d / "emb.npy").exists() else None
    cli.save(sid, kept, meta)
    cli.make_search_caches(sid)
    if vectors is not None and len(vectors) == len(old):
        organize.save_vectors(sid, vectors, kept, keep)    # (the guide's rows made; the docs' kept)
    elif vectors is not None:
        cli.make_vectors(sid, name)
