"""One copy per standard of a language whose docs describe every standard at once.

cppreference is one site for C++98 to C++29 (and C89 to C23): each page marks what came with
which standard. docsearch downloads it once and keeps that download aside (data/bases/cpp: not
a copy you search). From it, it makes a copy for each standard you ask for, in seconds and with
nothing downloaded: cpp@17 is C++17.
- Its entries are that standard's: none added later, none removed before. Their tables leave
  out the rows of other standards (a declaration added in C++20 is not in cpp@17).
- Its pages are the downloaded ones, shared through hard links, so they take no second space
  on disk. The page shows them as that standard has them (pages.for_standard).
- Its vectors are the download's own.

The current standard is the one the site's own page says it is ("C++23 is the current
revision"). Newer ones are drafts (cpp@26-draft): pulled only when asked for, never chosen for
you. A project built with C++17 (CMakeLists.txt...) searches cpp@17.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from pathlib import Path

from docsearch import cli, sources, versions
from docsearch import pages as offline
from docsearch.cli import say


def profile(group: str) -> dict | None:
    """The profile of a language kept one copy per standard (sources.py: editions)."""
    entry = sources.KNOWN.get(group)
    return entry if entry and entry.get("editions") else None


def base_dir(group: str) -> Path:
    return cli.DATA / "bases" / group


def have_base(group: str) -> bool:
    try:
        meta = json.loads((base_dir(group) / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return not meta.get("partial")


def current(group: str) -> str:
    """The standard the site says is the current one (its page about it: "C++23 is the
    current revision"); the profile's until the site is downloaded."""
    p = profile(group)
    for ed in reversed(p["editions"]):
        html = offline.load_page(base_dir(group) / "pages", p["edition_page"].format(ed))
        if html and re.search(r"\bcurrent revision\b", re.sub(r"<[^>]+>", " ", html[:20000]), re.I):
            return ed
    return p["current"]


def is_draft(group: str, ed: str) -> bool:
    eds = profile(group)["editions"]
    return eds.index(ed) > eds.index(current(group))


def year(group: str, ed: str) -> int:
    return versions.standard_year(profile(group)["standards"] + ed)


def copy_of(group: str, ed: str) -> str:
    """cpp@17; a draft: cpp@26-draft."""
    return f"{group}@{ed}" + ("-draft" if is_draft(group, ed) else "")


def edition_of(sid: str) -> str | None:
    """17 for cpp@17, 26 for cpp@26-draft."""
    group, _, label = sid.partition("@")
    ed = label.removesuffix("-draft")
    return ed if profile(group) and ed in profile(group)["editions"] else None


def link_tree(src: Path, dst: Path) -> None:
    """The same files under `dst`, as hard links (no second copy on disk); copies where links
    cannot be made (another drive, a file system without them)."""
    for f in src.rglob("*"):
        if f.is_dir():
            continue
        to = dst / f.relative_to(src)
        to.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(f, to)
        except OSError:
            shutil.copy2(f, to)


def make_copy(group: str, ed: str, spec: str = "") -> str:
    """The copy of one standard, made from the download of every standard: that standard's
    entries, their tables without other standards' rows, the shared pages, the download's
    vectors. Built in staging, then put in place (a copy made before is replaced)."""
    import numpy as np
    p, base = profile(group), base_dir(group)
    lang, y, sid = p["standards"], year(group, ed), copy_of(group, ed)
    meta = json.loads((base / "meta.json").read_text(encoding="utf-8"))
    later = re.compile(rf"^{re.escape(lang)}(\d\d)\b")      # a page about a later standard (C++26)
    keep, entries = [], []
    real, cli.HOME = cli.HOME, base.parent              # (the download, read as a copy)
    try:
        found = list(cli.iter_entries(base.name))
    finally:
        cli.HOME = real
    for k, e in enumerate(found):
        if not versions.in_standard(versions.entry_marks(e.text, lang), y):
            continue
        m = later.match(e.title)
        if m and (versions.standard_year(lang + m.group(1)) or 0) > y:
            continue
        e.text, e.source = versions.standard_text(e.text, lang, y), sid
        keep.append(k)
        entries.append(e)
    stage = cli.STAGING / sid
    shutil.rmtree(stage, ignore_errors=True)
    meta = {**meta, "spec": spec or group, "version": f"{lang}{ed}", "count": len(entries),
            "standard": {"lang": lang, "edition": ed, "draft": is_draft(group, ed), "of": meta.get("created", "")}}
    meta.pop("partial", None)
    meta.pop("standards", None)
    real, cli.HOME = cli.HOME, cli.STAGING
    try:
        cli.save(sid, entries, meta)
        for part in ("pages", "source"):
            if (base / part).is_dir():
                link_tree(base / part, stage / part)
        if (base / "emb.npy").exists() and keep:
            np.save(stage / "emb.npy", np.load(base / "emb.npy", mmap_mode="r", allow_pickle=False)[keep])
        cli.make_search_caches(sid)
    finally:
        cli.HOME = real
    cli.install_staged(stage, [])
    return sid


def keep_aside(d: Path, group: str) -> None:
    """A download of every standard, moved aside: not a copy any more, never searched (so
    without the caches a search makes)."""
    shutil.rmtree(base_dir(group), ignore_errors=True)
    base_dir(group).parent.mkdir(parents=True, exist_ok=True)
    cli.move_folder(d, base_dir(group))
    for f in ("bm25.npz", "tails.bin", "tails.npy", "order.npy"):
        (base_dir(group) / f).unlink(missing_ok=True)


def download(group: str, args) -> bool:
    """The site of every standard, downloaded once (as any docs: a stop goes on where it
    stopped) and kept aside. False if it did not finish."""
    say(f"  {profile(group)['about']}: one site for every standard. It is downloaded once; each "
        f"standard's copy is made from it")
    cli.cmd_add(argparse.Namespace(sources=[group], workers=args.workers, max_pages=getattr(args, "max_pages", None),
                                   no_embed=getattr(args, "no_embed", False), yes=getattr(args, "yes", False),
                                   record=False, force=False, standards_base=True))
    d = cli.HOME / group
    try:
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if meta.get("partial"):
        return False
    keep_aside(d, group)
    return True


def add(group: str, want: str, spec: str, args) -> None:
    """search add cpp==17 (cpp: the current standard): its copy, made from the download of
    every standard (downloaded first if there is none; --force: again)."""
    p = profile(group)
    ed = sources.edition(group, want) if want else None
    if want and ed is None:
        say(f"  {group}: there is no {p['standards']} standard {want}. {sources.versions(group).capitalize()}")
        return
    if getattr(args, "force", False) or not have_base(group):
        if not download(group, args):
            return
    ed = ed or current(group)
    sid = copy_of(group, ed)
    if (cli.HOME / sid / "meta.json").exists() and not getattr(args, "force", False):
        say(f"  {sid}: you have this standard already; nothing to download")
    else:
        made = make_copy(group, ed, spec)
        n = json.loads((cli.HOME / made / "meta.json").read_text(encoding="utf-8"))["count"]
        say(f"  {made}: {p['standards']}{ed}{' (a draft)' if is_draft(group, ed) else ''}, {n:,} entries, made from "
            f"the download of every standard")
    if getattr(args, "record", True):
        cli.remember(spec)
    cli.copy_hint(group, sid)


def upgrade(group: str, args) -> None:
    """search upgrade cpp: the site downloaded again, and each standard you have made anew."""
    have = [s for s in cli.copies(group) if edition_of(s)]
    if not download(group, args):
        say(f"  {group}: the new download did not finish; the copies you have stay as they are")
        return
    for sid in have:
        say(f"  {make_copy(group, edition_of(sid), sid.split('@')[0] + '==' + edition_of(sid))}: made anew")


def drop_base(group: str) -> None:
    """The download of every standard, when no copy is made from it any more."""
    if profile(group) and not cli.copies(group) and base_dir(group).exists():
        shutil.rmtree(base_dir(group), ignore_errors=True)
        say(f"removed the download of every {profile(group)['standards']} standard ({group}: no copy left)")


def migrate() -> None:
    """Docs of every standard downloaded before they were kept one copy per standard (cpp):
    kept aside as the download, and the current standard's copy made from it, once."""
    for group in [g for g in sources.KNOWN if profile(g)]:
        d = cli.HOME / group
        try:
            meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if meta.get("partial") or (d / "crawl").exists() or base_dir(group).exists():
            continue
        from docsearch import web
        web.stop()                                       # (a running search page holds its files)
        keep_aside(d, group)
        ed = current(group)
        eds = profile(group)["editions"]
        say(f"{group}: one copy per {profile(group)['standards']} standard now. Making {copy_of(group, ed)} "
            f"(the current one) from the docs you have; another: search add {group}=={eds[eds.index(ed) - 1]}")
        make_copy(group, ed, group)
