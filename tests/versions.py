"""What docs correspond to (docsearch/versions.py): no internet, a few seconds.

    uv run python tests/versions.py

- versions and language standards compare as the software does: 3.13 after 3.12 (and after
  3.12.4), 1.10 after 1.9, C++20 after C++17; C11 and C++17 do not compare
- an entry's marks, as docs write them: cppreference's declarations, each with its own (an
  entry is there since its earliest one, and since C++98 if one has none; removed when every
  one is; "constexpr since" is not about being there); Sphinx's "Added in version 3.13.",
  "New in version", "Deprecated since version", "Removed in version" of the entry itself (not
  "Added in version 3.9: the *x* parameter"; on a module's page, its own, not its functions')
- a project's version or standard flags what it should know: newer, removed, deprecated
- a copy is labeled by what it describes, never by a day: a release (v26.6: 26.6), the release
  its source links name, development docs (after a release; a beta), every standard of a
  language (C++98 to the newest its entries name), the language as it is now (MDN), not stated
- a project's C and C++ standards from its build files (CMake, meson, Makefile,
  compile_commands.json and its aliases: c++2a is C++20, gnu17 is C17), Rust's rust-version,
  Python's requires-python; a standard never picks a copy, and it is not "a version you lack"
- the search page: each result and entry with its marks, flagged against the project's
  versions it is given
- a language's standards, one copy each (standards.py): docs of every standard from before
  are kept aside, and the current standard's copy (the one the site's page says is current) is
  made from them; search add cpp==17 makes C++17's with nothing downloaded: its entries (none
  added later, none removed before), their tables without other standards' rows, the pages
  shared (hard links), the vectors the download's; a draft (C++26) is cpp@26-draft; a project
  built with C++17 searches cpp@17; the page shows C++17's rows only; removing the last copy
  removes the download
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

if "DOCSEARCH_DATA" not in os.environ:
    os.environ["DOCSEARCH_DATA"] = tempfile.mkdtemp(prefix="docsearch-versions-")

from docsearch import cli, versions as V, web  # noqa: E402

# cppreference, as docsearch keeps its entries: a table of declarations, then the text
EXPECTED = """| | | |
| --- | --- | --- |
| Defined in header `<expected>` | | |
| ``` template< class T, class E > class expected; ``` | (1) | (since C++23) |
| ``` template< class T, class E > requires std::is_void_v<T> class expected<T, E>; ``` | (2) | (since C++23) |

The class template `std::expected` provides a way to represent either of two values (since C++11 types)."""
VECTOR = """| | | |
| --- | --- | --- |
| Defined in header `<vector>` | | |
| ``` template< class T, class Allocator = std::allocator<T> > class vector; ``` | (1) | |
| ``` namespace pmr { template< class T > using vector = std::vector<T>; } ``` | (2) | (since C++17) |

Member types: `value_type` (since C++11)."""
SORT = """| ``` template< class RandomIt > void sort( RandomIt first, RandomIt last ); ``` | (1) | (constexpr since C++20) |
| ``` template< class ExecutionPolicy, class RandomIt > void sort( ExecutionPolicy&& policy, RandomIt first ); ``` | (2) | (since C++17) |

Sorts the elements."""
AUTO_PTR = """| ``` template< class T > class auto_ptr; ``` | (1) | (deprecated in C++11) (removed in C++17) |
| ``` template<> class auto_ptr<void>; ``` | (2) | (deprecated in C++11) (removed in C++17) |

A smart pointer."""
EMPLACE = """| ``` template< class... Args > void emplace_back( Args&&... args ); ``` | | (since C++11) (until C++17) |
| ``` template< class... Args > reference emplace_back( Args&&... args ); ``` | | (since C++17) (constexpr since C++20) |"""


def run(*argv: str) -> str:
    said = io.StringIO()
    try:
        with contextlib.redirect_stderr(said), contextlib.redirect_stdout(said):
            cli.main(list(argv))
    except SystemExit:
        pass
    return said.getvalue()


def check(ok: bool, what: str) -> None:
    print(("ok    " if ok else "FAIL  ") + what, flush=True)
    if not ok:
        sys.exit(1)


def main() -> None:
    data = Path(os.environ["DOCSEARCH_DATA"])
    cli.CONFIG = data / "packages.toml"
    pairs = [("3.13", "3.12", True), ("3.13", "3.12.4", True), ("3.12", "3.12.4", False), ("1.10", "1.9", True),
             ("2.0.1", "2.0", False), ("C++20", "C++17", True), ("C++98", "C++17", False), ("C11", "C++17", False),
             ("C23", "C11", True)]
    check(all(V.newer(a, b) == want for a, b, want in pairs),
          f"versions and standards compare as the software does ({[(a, b) for a, b, w in pairs if V.newer(a, b) != w]})")

    marks = {n: V.entry_marks(t, "C++") for n, t in
             (("expected", EXPECTED), ("vector", VECTOR), ("sort", SORT), ("auto_ptr", AUTO_PTR), ("emplace", EMPLACE))}
    check(marks == {"expected": {"since": "C++23"}, "vector": {}, "sort": {},
                    "auto_ptr": {"removed": "C++17", "deprecated": "C++11"}, "emplace": {"since": "C++11"}},
          f"cppreference's declarations: since the earliest; one without a mark: since C++98; removed when all are ({marks})")
    sphinx = [V.entry_marks("Groups items.\n\nAdded in version 3.12."), V.entry_marks("New in version 1.4.0"),
              V.entry_marks("Deprecated since version 3.12: use x.\n\nRemoved in version 3.14."), V.entry_marks("No marks."),
              V.entry_marks("Parses.\n\nAdded in version 3.9: the *exit_on_error* parameter."),
              V.entry_marks("Deprecated since version 3.13: the *strict* parameter."),
              V.entry_marks("itertools: iterators.\n\n" + "Functions. " * 50 + "accumulate. Added in version 3.2.", page=True),
              V.entry_marks("tomllib: parse TOML.\n\nAdded in version 3.11.\n\n" + "x " * 300, page=True)]
    check(sphinx == [{"since": "3.12"}, {"since": "1.4.0"}, {"deprecated": "3.12", "removed": "3.14"}, {}, {}, {},
                     {}, {"since": "3.11"}],
          f"Sphinx's marks of the entry itself: added, new, deprecated, removed; not a parameter's; a page's (a "
          f"module's) own, not its functions' ({sphinx})")
    got = [V.flags({"since": "C++23"}, "C++17"), V.flags({"since": "C++11"}, "C++17"), V.flags(marks["auto_ptr"], "C++17"),
           V.flags(marks["auto_ptr"], "C++14"), V.flags({"since": "3.12"}, "3.11"), V.flags({"since": "3.12"}, ""),
           V.flags({"deprecated": "3.12"}, "3.13")]
    check(got == [["newer"], [], ["removed"], ["deprecated"], ["newer"], [], ["deprecated"]],
          f"a project's version or standard flags what is newer, removed, deprecated ({got})")

    from docsearch import sources
    labels = {
        "release": V.covers({"version": "v26.6"}, "max@26.6")["label"],
        "links": V.covers({"kind": "sphinx", "source": {"ref": "py-2.0.0"}}, "polars")["label"],
        "dev": V.covers({"version": "nightly", "after": "3.8.0", "created": "2026-10-11"}, "triton@nightly-2026-10-11")["label"],
        "main": V.covers({"source": {"ref": "main"}}, "jax")["label"],
        "beta": V.covers({"version": "3.1.0rc0"}, "pandas@3.1-beta")["label"],
        "standards": V.covers({"kind": "known", "standards": {"from": "C++98", "to": "C++29"}}, "cpp", sources.KNOWN["cpp"])["label"],
        "living": V.covers({"kind": "known"}, "javascript", sources.KNOWN["javascript"])["label"],
        "unknown": V.covers({"created": "2026-10-06 10:00", "release": "4.2"}, "thing"),
        "saved": V.covers({"kind": "saved"}, "fstrings")["label"]}
    check(labels["release"] == "26.6" and labels["links"] == "2.0.0" and labels["dev"] == "in development, after 3.8.0"
          and labels["main"] == "in development" and labels["beta"] == "3.1.0 (beta)" and labels["standards"] == "C++98–C++29"
          and labels["living"] == "current" and labels["unknown"]["label"] == "" and "4.2" in labels["unknown"]["note"]
          and labels["saved"] == "" and not any("2026" in str(v) for k, v in labels.items() if k not in ("unknown",)),
          f"a copy is labeled by what it describes, never by a day ({labels})")

    proj = data / "proj"
    (proj / "build").mkdir(parents=True)
    (proj / ".git").mkdir()
    (proj / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.20)\nset(CMAKE_CXX_STANDARD 17)\n"
                                         "set(CMAKE_C_STANDARD 11)\n")
    (proj / "Cargo.toml").write_text('[package]\nname = "x"\nrust-version = "1.80"\n')
    (proj / "pyproject.toml").write_text('[project]\nname = "x"\nrequires-python = ">=3.10"\n')
    found = cli.project_versions(proj)
    other = data / "other"
    other.mkdir()
    (other / ".git").mkdir()
    (other / "meson.build").write_text("project('x', 'cpp', default_options : ['cpp_std=c++2a', 'c_std=gnu17'])\n")
    found2 = cli.project_versions(other)
    third = data / "third"
    (third / "build").mkdir(parents=True)
    (third / ".git").mkdir()
    (third / "build" / "compile_commands.json").write_text(json.dumps([{"command": "c++ -std=gnu++2b -c a.cpp"}]))
    found3 = cli.project_versions(third)
    check(found == {"cpp": "C++17", "c": "C11", "rust": "1.80", "python": "3.10"} and found2 == {"cpp": "C++20", "c": "C17"}
          and found3 == {"cpp": "C++23"},
          f"a project's standards and versions from its files ({found}, {found2}, {found3})")

    docs = data / "docs"
    docs.mkdir()
    (docs / "index.html").write_text("<html><head><title>Mini</title></head><body><main><h1>Mini</h1>"
                                     "<h2 id='batched'>batched</h2><p>Groups items into tuples.</p>"
                                     "<p>Added in version 3.12.</p>"
                                     "<h2 id='old'>old</h2><p>The old way.</p><p>Added in version 2.1.</p>"
                                     "</main></body></html>")
    cli.main(["add", f"mini={docs}", "--no-embed"])
    check(cli.in_use("mini", {"mini": "C++17"}) == ("mini", ""),
          "a language standard, for docs not kept one copy per standard, picks no copy, nor says one is missing")
    lib = web.Library()
    items = {it["name"]: it for it in lib.search("batched old", {"mini"}, 0, 20, project={"mini": "3.11"})["items"]}
    batched = next(v for k, v in items.items() if "batched" in k)
    old = next(v for k, v in items.items() if k.endswith("old"))
    entry = lib.entry(batched["id"], {"mini": "3.11"})
    check(batched["marks"] == {"since": "3.12"} and batched["flags"] == ["newer"] and old["flags"] == []
          and entry["flags"] == ["newer"] and entry["project"] == "3.11"
          and web.project_of("cpp:C++17;python:3.12;bad name:x") == {"cpp": "C++17", "python": "3.12"},
          f"the search page: each result with its marks, flagged against the project's version ({batched}, {old})")
    standards_copies(data)
    print("all good")


def cpp_docs(data: Path) -> None:
    """docs of every C++ standard, as docsearch had them before: data/index/cpp."""
    import numpy as np
    from docsearch import pages
    root = "https://en.cppreference.com/"
    entries = [cli.Entry(title=t, kind=k, location=root + loc, text=text, source="cpp") for t, k, loc, text in (
        ("std::vector (class)", "class", "cpp/container/vector", VECTOR), ("std::expected (class)", "class", "cpp/utility/expected", EXPECTED),
        ("std::auto_ptr (class)", "class", "cpp/memory/auto_ptr", AUTO_PTR), ("std::sort (function)", "function", "cpp/algorithm/sort", SORT),
        ("C++26", "page", "cpp/26", "The next generation of the C++ standard."),
        ("C++23", "page", "cpp/23", "The current revision of the C++ standard."))]
    cli.save("cpp", entries, {"name": "cpp", "spec": "cpp", "kind": "known", "root": root, "pages": True,
                              "created": "2026-10-06 10:00", "model": None, "count": len(entries)})
    folder = cli.HOME / "cpp" / "pages"
    pages.save_page(folder, "cpp/23", "<p>C++23 is the current revision of the C++ standard.</p>")
    pages.save_page(folder, "cpp/26", "<p>The next generation of the C++ standard.</p>")
    pages.save_page(folder, "cpp/container/vector",
                    "<table><tr class='t-dcl'><td>template&lt;class T&gt; class vector;</td><td>(1)</td></tr>"
                    "<tr class='t-dcl t-since-cxx17'><td>namespace pmr { using vector = ...; }</td><td>(2)</td></tr>"
                    "<tr class='t-dsc'><td>append_range <span class='t-mark-rev t-since-cxx23'>(C++23)</span></td>"
                    "<td>adds a range</td></tr></table><p>A sequence container.</p>")
    np.save(cli.HOME / "cpp" / "emb.npy", np.arange(len(entries) * 4, dtype=np.float32).reshape(len(entries), 4))


def standards_copies(data: Path) -> None:
    import numpy as np
    from docsearch import standards
    cpp_docs(data)
    said = run("list")
    check(cli.copies("cpp") == ["cpp@23"] and standards.base_dir("cpp").is_dir() and "one copy per C++ standard" in said
          and cli.copy_covers("cpp@23")["label"] == "C++23",
          f"docs of every standard from before: kept aside; the current one's copy made from them ({cli.copies('cpp')})")
    said = run("add", "cpp==17", "--no-embed")
    names = lambda sid: sorted(e.title.split(" (")[0] for e in cli.iter_entries(sid))        # noqa: E731
    vec17 = next(e for e in cli.iter_entries("cpp@17") if e.title.startswith("std::vector"))
    emb = np.load(cli.HOME / "cpp@17" / "emb.npy")
    page = next(f for f in (cli.HOME / "cpp@17" / "pages").rglob("*.gz"))
    check(names("cpp@17") == ["std::sort", "std::vector"] and "(since C++17)" in vec17.text
          and names("cpp@23") == ["C++23", "std::expected", "std::sort", "std::vector"]
          and emb.shape == (2, 4) and emb[0, 0] == 0 and emb[1, 0] == 12 and page.stat().st_nlink >= 2
          and "made from the download" in said,
          f"search add cpp==17: C++17's entries (not the page about C++23), with nothing downloaded; their own "
          f"rows of the download's vectors; the pages shared ({names('cpp@17')}, {emb[:, 0]})")
    run("add", "cpp==11", "--no-embed")
    vec11 = next(e for e in cli.iter_entries("cpp@11") if e.title.startswith("std::vector"))
    check("auto_ptr" in " ".join(names("cpp@11")) and "pmr" not in vec11.text and "(since C++17)" not in vec11.text,
          "C++11's: what it had (auto_ptr), its tables without later standards' rows")
    run("add", "cpp==26", "--no-embed")
    check("cpp@26-draft" in cli.copies("cpp") and cli.copies("cpp")[-1] == "cpp@26-draft"
          and cli.copy_covers("cpp@26-draft")["label"] == "C++26 (draft)" and cli.match_version(cli.copies("cpp"), "26") is None,
          f"a standard newer than the current one: a draft, never chosen for you ({cli.copies('cpp')})")
    said = run("add", "cpp==16", "--no-embed")
    check("there is no C++ standard 16" in said, "a standard that is not one: said so")
    check(cli.in_use("cpp", {"cpp": "C++17"})[0] == "cpp@17" and "search add cpp==20" in cli.in_use("cpp", {"cpp": "C++20"})[1],
          "a project built with C++17 searches cpp@17; one with C++20 is told how to get it")
    lib = web.Library(frozenset({"cpp@17"}))
    i = next(i for i, e in enumerate(lib.index.entries) if lib.sid_of[i] == "cpp@17" and e.title.startswith("std::vector"))
    html = lib.entry(i)["html"]
    check("pmr" in html and "append_range" not in html and lib.entry(i)["version"] == "C++17",
          "the page shows C++17's rows only")
    run("remove", "cpp", "--all")
    check(not cli.copies("cpp") and not standards.base_dir("cpp").exists(),
          "removing the last copy removes the download of every standard")


if __name__ == "__main__":
    main()
