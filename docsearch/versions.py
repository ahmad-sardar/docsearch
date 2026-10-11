"""What docs correspond to: the version (or versions) of the software they describe.

A copy is labeled by what it describes, never by the day it was downloaded:
- a release: numpy 2.5 (its 2.5 series), polars 2.0.0, Python 3.14, Rust 1.99.0
- development docs: the release to come, after the newest one (triton's main, after 3.8.0;
  Python's dev docs, 3.15 in development)
- every standard of a language at once: cppreference covers C++98 to C++26, and each entry
  says since which one (its declarations' "(since C++20)")
- the language as it is now: MDN (JavaScript) has no versions
- not stated: docs that say nothing (the day they were downloaded is only a note)

Each entry's own marks say which versions it belongs to: cppreference's "(since C++20)" and
"(removed in C++17)" on its declarations; Sphinx's "Added in version 3.13", "Deprecated since
version 3.12" (Python, numpy and most Python libraries). A project's version, or its language
standard (C++17 from its CMakeLists.txt), flags the entries newer than it.
"""
from __future__ import annotations

import re

STANDARD = re.compile(r"^(C\+\+|C)(\d\d)$")
# cppreference: a declaration's marks; (constexpr since C++20) is not about being there
CPP_MARK = re.compile(r"\((since|until|deprecated in|removed in) (C\+\+\d\d|C\d\d)\)")
# Sphinx (versionadded, deprecated, versionremoved): "Added in version 3.13." (since Sphinx 7.3;
# before, "New in version 3.8."). Bare, it is the object's own; with words after a colon ("Added
# in version 3.9: the *x* parameter") it is a part of it.
SPHINX_MARK = re.compile(r"\b(Added in|New in|Deprecated since|Removed in) version (\d+(?:\.\d+)*)(:[^\n]{0,80}|\.?)")
A_PART = re.compile(r"^:\s*(the\s+)?[*`]|parameter|argument|option|keyword|attribute", re.I)
PAGE_HEAD = 400            # a page's own mark comes first (a module's); later ones are its parts
RELEASE_REF = re.compile(r"[A-Za-z_.-]*?v?(\d+(?:\.\d+)+[\w.+-]*)")      # v2.5.0, py-2.0.0, go1.27.1


def release_of(ref: str) -> str:
    """The release a source ref names: v2.5.0 -> 2.5.0, py-2.0.0 -> 2.0.0; "" for a branch
    (main) or a commit."""
    m = RELEASE_REF.fullmatch(ref or "")
    return m.group(1) if m and not re.fullmatch(r"[0-9a-f]{7,40}", ref) else ""


def standard_year(name: str) -> int | None:
    """C++20 -> 2020, C++98 -> 1998, C11 -> 2011, C89 -> 1989."""
    m = STANDARD.match(name)
    if not m:
        return None
    yy = int(m.group(2))
    return 1900 + yy if yy >= 80 else 2000 + yy


def number(version: str) -> tuple[int, ...]:
    """2.5.1 -> (2, 5, 1); a version's leading numbers."""
    m = re.match(r"v?(\d+(?:\.\d+)*)", version or "")
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


def newer(mark: str, than: str) -> bool:
    """Is version (or standard) `mark` newer than `than`? C++20 newer than C++17; 3.13 newer
    than 3.12 (and than 3.12.4); 2.0 not newer than 2.0.1. False if they cannot be compared."""
    a, b = standard_year(mark), standard_year(than)
    if a is not None and b is not None:
        return STANDARD.match(mark).group(1) == STANDARD.match(than).group(1) and a > b
    x, y = number(mark), number(than)
    if not x or not y or a is not None or b is not None:
        return False
    return x[:len(y)] > y if len(x) >= len(y) else x > y[:len(x)]


# --------------------------------------------------------------------------- an entry's marks

def entry_marks(text: str, standards: str = "", page: bool = False) -> dict[str, str]:
    """What an entry says of its versions: {"since": ..., "removed": ..., "deprecated": ...}.
    `standards`: docs of a language's standards (cppreference: "C++" or "C"), whose entries
    begin with a table of their declarations, each with its own marks. An entry is there since
    the earliest declaration's standard, and since the first standard if one has no "since";
    removed when every declaration is ("until", "removed in"). Else Sphinx's marks of the entry
    itself: the first bare "Added in version 3.13."; "Deprecated since version", "Removed in
    version" unless they are about a parameter or option. `page`: a page (a module's), whose
    own mark comes first, not its functions'."""
    if standards:
        return _declarations(text, standards)
    out: dict[str, str] = {}
    for kind, version, after in SPHINX_MARK.findall(text[:PAGE_HEAD] if page else text):
        key = {"Added in": "since", "New in": "since", "Deprecated since": "deprecated", "Removed in": "removed"}[kind]
        if (key == "since" and after.startswith(":")) or (key != "since" and A_PART.search(after)):
            continue                                # (a part of it: a parameter, an option)
        out.setdefault(key, version)
    return out


def _declarations(text: str, lang: str) -> dict[str, str]:
    rows: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith("|"):
            if "```" in line:
                rows.append(line)
        elif rows:                                  # the table of declarations ended
            break
    if not rows:                                    # (a page about the language, not a declaration)
        return {}
    sinces, ends, deprecated = [], [], []
    for row in rows:
        marks = [(k, s) for k, s in CPP_MARK.findall(row.rsplit("```", 1)[-1]) if s.startswith(lang) and
                 (s[len(lang):].isdigit())]
        since = [s for k, s in marks if k == "since"]
        sinces.append(min(since, key=standard_year) if since else "")
        end = [s for k, s in marks if k in ("until", "removed in")]
        ends.append(max(end, key=standard_year) if end else "")
        deprecated += [s for k, s in marks if k == "deprecated in"]
    out: dict[str, str] = {}
    if all(sinces):                                 # every declaration came with a standard
        out["since"] = min(sinces, key=standard_year)
    if all(ends):                                   # every declaration is gone
        out["removed"] = max(ends, key=standard_year)
    if deprecated and len(deprecated) == len(rows):
        out["deprecated"] = min(deprecated, key=standard_year)
    return out


def flags(marks: dict[str, str], project: str) -> list[str]:
    """What a project of version (or standard) `project` should know of an entry: "newer"
    (since a later one), "removed" (removed in it or before), "deprecated"."""
    if not project:
        return []
    out = []
    if marks.get("since") and newer(marks["since"], project):
        out.append("newer")
    if marks.get("removed") and not newer(marks["removed"], project) and (
            standard_year(marks["removed"]) or number(marks["removed"])):
        out.append("removed")
    elif marks.get("deprecated") and not newer(marks["deprecated"], project):
        out.append("deprecated")
    return out


# --------------------------------------------------------------------------- a copy

def covers(meta: dict, sid: str, profile: dict | None = None) -> dict[str, str]:
    """What a copy of docs corresponds to: {"style", "label", "note"}. `profile`: its entry in
    sources.KNOWN, which says when docs span a language's standards or are not versioned."""
    profile = profile or {}
    if meta.get("kind") in ("saved", "man"):          # an article, a man page: no docs version
        return {"style": "none", "label": "", "note": ""}
    std = meta.get("standard") or {}
    if std:                                         # one standard of a language (standards.py)
        name = f"{std['lang']}{std['edition']}"
        return {"style": "development" if std.get("draft") else "release",
                "label": name + (" (draft)" if std.get("draft") else ""),
                "note": (f"The {name} standard{', a draft,' if std.get('draft') else ''} as the site describes it: "
                         f"what later standards added, and what earlier ones removed, left out")}
    version = re.sub(r"^v(?=\d)", "", str(meta.get("version") or "").strip())      # v26.6: 26.6
    day = str(meta.get("created", ""))[:10]
    label = sid.partition("@")[2]
    if profile.get("standards"):
        span = meta.get("standards") or {}
        first, last = span.get("from") or profile.get("since", ""), span.get("to", "")
        text = f"{first}–{last}" if first and last else f"{first} and later" if first else "every standard"
        return {"style": "standards", "label": text,
                "note": f"Every {profile['standards']} standard ({text}); each entry says since which one"}
    if profile.get("living"):
        return {"style": "living", "label": "current", "note": profile["living"]}
    ref = str((meta.get("source") or {}).get("ref") or "")
    dev = re.match(r"(nightly|beta|alpha)(?:-\d{4}-\d\d-\d\d)?$", label) or re.match(r".+-(beta|alpha)$", label) \
        or version.lower() in ("nightly", "dev", "main", "master", "latest") \
        or (not number(version) and ref and not re.search(r"\d", ref))     # its source links name main
    after = str(meta.get("after") or "")
    if dev:
        stage = "beta" if "beta" in label else "alpha" if "alpha" in label else "in development"
        num = ".".join(map(str, number(version)))      # (26.7.0.dev2026100605: 26.7.0)
        text = f"{num} ({stage})" if num else stage + (f", after {after}" if after else "")
        return {"style": "development", "label": text,
                "note": (f"The release to come{f' after {after}' if after else ''}: docs of its development"
                         + (f", as of {day}" if day else ""))}
    if number(version):
        return {"style": "release", "label": version, "note": ""}
    if number(label):                               # (a copy named for its version before this kept it)
        return {"style": "release", "label": label, "note": ""}
    if release_of(ref):                             # the release its source links name
        return {"style": "release", "label": release_of(ref), "note": "The release their source links name"}
    release = str(meta.get("release") or "")
    return {"style": "unknown", "label": "",
            "note": "These docs do not say which version they describe" + (f"; downloaded {day}" if day else "")
                    + (f", when the newest release was {release}" if release else "")}


# --------------------------------------------------------------------------- one standard of a language

ROW_MARK = re.compile(r"\((since |until |removed in )?(C\+\+\d\d|C\d\d)\)")   # (since C++20), (C++11): a member's


def row_in(row: str, lang: str, year: int) -> bool:
    """Is a row of a declarations or members table in the standard of `year`? Its marks say
    since which standard (a member list's bare "(C++11)" too) and until which one."""
    since, until = [], []
    for kind, std in ROW_MARK.findall(row):
        y = standard_year(std) if std.startswith(lang) and std[len(lang):].isdigit() else None
        if y is None:
            continue
        (until if kind in ("until ", "removed in ") else since).append(y)
    return (not since or min(since) <= year) and (not until or max(until) > year)


def standard_text(text: str, lang: str, year: int) -> str:
    """An entry's text in one standard: the rows of its tables that other standards have
    (declarations added later, members removed before) left out. A row of several standards'
    versions of one thing (cppreference's revisions, made one line: "... (until C++11) | ...
    (since C++11)(until C++17) | ... (since C++17)") keeps only this standard's; a cell that is
    only a mark goes with the cell before it."""
    out = []
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            out.append(line)
        elif "```" in line:                          # a declaration: the whole row
            if row_in(line, lang, year):
                out.append(line)
        else:
            cells, kept = line.split("|"), []
            for cell in cells:
                if not ROW_MARK.sub("", cell).strip() and ROW_MARK.search(cell):   # only a mark
                    if not row_in(cell, lang, year):
                        while kept and not kept[-1].strip():
                            kept.pop()
                        if kept and len(kept) > 1:
                            kept.pop()               # the text it marks
                    else:
                        kept.append(cell)
                elif row_in(cell, lang, year):
                    kept.append(cell)
            if any(c.strip() for c in kept):
                out.append("|".join(kept))
    return "\n".join(out)


def in_standard(marks: dict[str, str], year: int) -> bool:
    """Is an entry (its marks, entry_marks) part of the standard of `year`?"""
    since, removed = standard_year(marks.get("since", "")), standard_year(marks.get("removed", ""))
    return (since is None or since <= year) and (removed is None or removed > year)
