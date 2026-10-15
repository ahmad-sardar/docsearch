"""Hugging Face's libraries' docs, from Hugging Face's own copy of them.

huggingface.co lets a visitor without an account load 100 of its web pages in five minutes
(https://huggingface.co/docs/hub/en/rate-limits); transformers' docs are about 760 pages. The
same docs, built, are published by Hugging Face as one file per version in the dataset
hf-doc-build/doc-build (its staff point there to download them): each page as Markdown, the
site's outline (_toctree.yml), and the versions it has (_versions.yml). So a library's docs
are two downloads, of files (whose limit is 3,000 in five minutes), and no page is asked for.
docs/notes/fetching-policy.md has the reasons.
"""
from __future__ import annotations

import io
import re
import zipfile

from docsearch import cli

ARCHIVE = "https://huggingface.co/datasets/hf-doc-build/doc-build/resolve/main/"
DOCS = re.compile(r"^https://(?:www\.)?huggingface\.co/docs/([\w.-]+?)(?:/|$)")
MAX_ARCHIVE = 400 * 2**20        # bytes: transformers' is 66 MB


def say(msg: str) -> None:
    cli.say(msg)


def library(root: str) -> str | None:
    """The library whose docs are at an address of huggingface.co/docs/ (transformers)."""
    m = DOCS.match(root)
    return m.group(1) if m and m.group(1) not in ("hub", "api-inference") else None


def versions(lib: str) -> list[str]:
    """The versions Hugging Face keeps of a library's docs ("main", "v5.9.0"...), newest first
    as it lists them; [] if it keeps none (not every library is there: Gradio is not)."""
    try:
        text = cli.http_get(f"{ARCHIVE}{lib}/_versions.yml", timeout=20)[0].decode("utf-8", "replace")
    except cli.Failed:
        return []
    return re.findall(r"(?m)^-\s*version:\s*['\"]?([\w.+-]+)", text)


def release(v: str) -> tuple[int, ...] | None:
    """A release's number (v5.9.0 -> (5, 9, 0)); None for main and pre-releases."""
    m = re.fullmatch(r"v?(\d+(?:\.\d+)*)", v)
    return tuple(int(x) for x in m.group(1).split(".")) if m else None


def choose(have: list[str], want: str, newest: str) -> str | None:
    """The version to read: the one asked for; else PyPI's newest release, if Hugging Face has
    its docs; else main, if that release is of a newer minor version than any it has
    (safetensors 0.5.2, kept up to v0.3.2); else the newest release it has. None: the one asked is not there."""
    by_number = {release(v): v for v in have if release(v)}
    if want:
        return by_number.get(release(want) or ()) or (want if want in have else None)
    if newest and release(newest) in by_number:
        return by_number[release(newest)]
    if "main" in have and (not by_number or (release(newest) or ())[:2] > max(by_number)[:2]):
        return "main"
    return by_number[max(by_number)] if by_number else None


def plan(name: str, lib: str, want: str, newest: str) -> dict | None:
    """How to read a library's docs from Hugging Face's copy (build_known: kind "hf-archive"),
    or None if it has none of them (they are then read from the site, as any site)."""
    have = versions(lib)
    if not have:
        return None
    ver = choose(have, want, newest)
    if ver is None:
        say(f"  Hugging Face keeps no docs of {lib} {want}: it has {', '.join(have[:8])}")
        return None
    root = f"https://huggingface.co/docs/{lib}/{ver}/en/"
    say(f"  {name}: Hugging Face's own copy of its docs ({lib} {ver}): one download, no page asked for")
    return {"found": "website", "kind": "hf-archive", "root": root, "url": root, "lib": lib, "archive": ver,
            "version": ver.lstrip("v") if release(ver) else ver}


def toctree(text: str) -> list[tuple[list[str], str]]:
    """The pages of a _toctree.yml, each with the sections it is under (outermost first):
    [(["Get started"], "quicktour"), ...]. Its YAML is always of one shape (lists of
    `local`/`title`, `sections` holding more), read here without a YAML library."""
    out: list[tuple[list[str], str]] = []
    stack: list[tuple[int, dict]] = []              # (indent, item) of the items above
    items: list[tuple[int, dict]] = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = re.match(r"^(\s*)(-\s+)?(\w+):\s*(.*?)\s*$", raw)
        if not m:
            continue
        indent = len(m.group(1)) + (len(m.group(2)) if m.group(2) else 0)
        if m.group(2):                                 # "- key: value": a new item at this depth
            items.append((indent, {}))
            target = items[-1][1]
        else:                                          # "key: value": of the last item this deep (a
            target = next((it for ind, it in reversed(items) if ind == indent), None)   # section's title
        if target is not None:                                                         # after its pages)
            target[m.group(3)] = m.group(4).strip("'\"")
    for indent, item in items:
        while stack and stack[-1][0] >= indent:
            stack.pop()
        crumbs = [s.get("title", "") for _, s in stack if s.get("title")]
        if item.get("local"):
            out.append((crumbs, item["local"]))
        stack.append((indent, item))
    return out


def build(name: str, sid: str, part: dict, store) -> tuple[list[cli.Entry], dict]:
    """Read a library's docs from Hugging Face's copy: its Markdown pages, cut into entries as
    any Markdown page (an API object's heading named by it: an API entry), and kept for reading
    offline; the site's outline for organizing them."""
    from docsearch import importers
    lib, ver, root = part["lib"], part["archive"], part["url"]
    url = f"{ARCHIVE}{lib}/{ver}.zip"
    say(f"  downloading {url}")
    data, _ = cli.http_get(url, timeout=600, limit=MAX_ARCHIVE)
    z = zipfile.ZipFile(io.BytesIO(data))
    prefix = f"{lib}/{ver}/en/"
    entries: list[cli.Entry] = []
    pages = sorted(n for n in z.namelist() if n.startswith(prefix) and n.endswith(".md"))
    for n in pages:
        page_url = root + n[len(prefix):-3]
        found, images, _ = importers.markdown_page(sid, name, store.root, store.dir, page_url, z.read(n),
                                                   {"api_ids": True})
        store.add_images(images)
        entries += found
    outline = {}
    if prefix + "_toctree.yml" in z.namelist():
        outline = {root + local: crumbs for crumbs, local in
                   toctree(z.read(prefix + "_toctree.yml").decode("utf-8", "replace")) if crumbs}
    part["outline"] = outline                        # (the site's own sections: organize.py)
    say(f"  {len(pages)} pages, {len(entries)} entries, from one download ({len(data) / 2**20:.0f} MB)")
    return entries, {"version": part.get("version", ""), "pages": True, "read_pages": len(pages),
                     "expected_pages": len(pages)}
