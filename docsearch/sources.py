"""Known documentation that is not found through PyPI: languages and other toolkits.

`search add rust` uses this list, never a PyPI package that happens to be called "rust".
(To mean a PyPI package with such a name, write `search add pypi:NAME`.)

Each entry says how to import the docs (see importers.py) and where they are; "{version}"
in an address is replaced by the version you ask for (packages.toml: rust = "1.80"), or by
`version` (the default). Docs without "{version}" only exist as the current version.

`version_from`: where the current version number is published: an address and a pattern
whose first group is the number (matched in the page, or with "address" in the address it
redirects to). Docs whose default `version` is a number then follow new releases.

`channels`: the docs of a release that is not out yet, asked for by name (max==nightly, as a
version: see CHANNELS). The default is always the stable release. A channel is either the
value "{version}" takes for it (rust's "nightly"), or what changes for it (max's addresses),
which may be `version_now`: where to read which version is in that state now (python's
beta: the one in pre-release), then filled in as "{version}".
"""
from __future__ import annotations

import re

# Releases that are not out yet, by the names docs sites give them. Asked for as a version:
# max==nightly, rust==beta (a word in the list means its channel: numpy==dev is nightly).
CHANNELS: dict[str, tuple[str, ...]] = {
    "nightly": ("nightly", "dev", "development", "devdocs", "main", "master", "tip"),
    "beta": ("beta", "rc", "pre", "preview", "prerelease", "next"),
    "alpha": ("alpha",),
}


def channel(version: str) -> str | None:
    """'dev' -> 'nightly', 'rc' -> 'beta'; None for a version number (or the default)."""
    v = version.lower().strip()
    return next((ch for ch, words in CHANNELS.items() if v in words), None)


KNOWN: dict[str, dict] = {
    "python": {
        "about": "Python: the language reference, tutorial and standard library",
        "kind": "sphinx", "url": "https://docs.python.org/{version}/", "version": "3",
        "channels": {"nightly": "dev",           # docs.python.org/dev/: the main branch
                     "beta": {"version_now": ["https://peps.python.org/api/release-cycle.json",
                                              r'"(\d+\.\d+)":\s*\{[^{}]*"status":\s*"prerelease"']}},
    },
    "rust": {
        "about": "Rust: the standard library, The Rust Book and The Rust Reference",
        "root": "https://doc.rust-lang.org/{version}/", "version": "stable",
        "channels": {"beta": "beta", "nightly": "nightly"},
        "version_from": ["https://doc.rust-lang.org/stable/std/index.html", r'data-channel="(\d+\.\d+\.\d+)"'],
        "parts": [
            {"kind": "website", "start": "https://doc.rust-lang.org/{version}/book/",
             "prefix": "https://doc.rust-lang.org/{version}/book/", "exclude": r"print\.html|/404\.html"},
            {"kind": "website", "start": "https://doc.rust-lang.org/{version}/reference/",
             "prefix": "https://doc.rust-lang.org/{version}/reference/", "exclude": r"print\.html|/404\.html"},
            {"kind": "rustdoc", "url": "https://doc.rust-lang.org/{version}/std/"},
        ],
    },
    "ocaml": {
        "about": "OCaml: the manual and the standard library API",
        "kind": "website", "version": "5.5", "root": "https://ocaml.org/manual/{version}/",
        "version_from": ["https://ocaml.org/manual/latest/", r"/manual/(\d+\.\d+)/", "address"],
        "start": ["https://ocaml.org/manual/{version}/index.html", "https://ocaml.org/manual/{version}/api/index.html"],
        "prefix": "https://ocaml.org/manual/{version}/", "main": "div.content, div.api",
    },
    "cpp": {
        "about": "C++: the language and standard library (cppreference.com)",
        "kind": "website", "root": "https://en.cppreference.com/",
        "start": "https://en.cppreference.com/cpp", "prefix": "https://en.cppreference.com/cpp/",
        "main": "#mw-content-text", "api": r"std::[\w:~<>, ]+(::operator(\(\)|\[\]|\s\w+(\[\])?|[^\w\s,()\[\]]+))?(\(\))?",
        "exclude": r"action=|oldid=|printable=|/Special:",
    },
    "c": {
        "about": "C: the language and standard library (cppreference.com)",
        "kind": "website", "root": "https://en.cppreference.com/",
        "start": "https://en.cppreference.com/c", "prefix": "https://en.cppreference.com/c/",
        "main": "#mw-content-text",
        "exclude": r"action=|oldid=|printable=|/Special:",
    },
    "cuda": {
        "about": "CUDA: programming guide, best practices, runtime and driver APIs",
        "root": "https://docs.nvidia.com/cuda/",
        "version_from": ["https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/index.html",
                         r"CUDA Toolkit (\d+\.\d+(?: Update \d+)?)"],
        "parts": [
            {"kind": "sphinx", "url": "https://docs.nvidia.com/cuda/cuda-programming-guide/"},
            {"kind": "sphinx", "url": "https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/"},
            {"kind": "sphinx", "url": "https://docs.nvidia.com/cuda/cuda-runtime-api/"},
            {"kind": "sphinx", "url": "https://docs.nvidia.com/cuda/cuda-driver-api/"},
        ],
    },
    "mojo": {
        "about": "Mojo: the manual, language reference and standard library (mojolang.org)",
        "kind": "website", "root": "https://mojolang.org/", "llms": "https://mojolang.org/llms.txt",
        "version_from": ["https://mojolang.org/llms.txt", r"(?m)^Version: *(\S+)"],
        "prefix": "https://mojolang.org/docs/", "api_path": r"/docs/std/",
        "channels": {"nightly": {"llms": "https://mojolang.org/nightly/llms.txt",
                                 "version_from": ["https://mojolang.org/nightly/llms.txt", r"(?m)^Version: *(\S+)"],
                                 "prefix": "https://mojolang.org/nightly/docs/"}},
    },
    "max": {
        "about": "MAX: Modular's AI serving and modeling platform (max.modular.com)",
        "kind": "website", "root": "https://max.modular.com/", "llms": "https://max.modular.com/stable/llms.txt",
        "version_from": ["https://max.modular.com/stable/llms.txt", r"(?m)^Version: *(\S+)"],
        "prefix": "https://max.modular.com/stable/", "api_path": r"/api/",
        "channels": {"nightly": {"llms": "https://max.modular.com/llms.txt",   # the site's own root:
                                 "version_from": ["https://max.modular.com/llms.txt", r"(?m)^Version: *(\S+)"],
                                 "prefix": "https://max.modular.com/",        # all but /stable/
                                 "exclude": r"^https://max\.modular\.com/stable/"}},
    },
    "go": {
        "about": "Go: the language specification, Effective Go and the standard library",
        "root": "https://",                      # two sites: go.dev and pkg.go.dev
        "version_from": ["https://go.dev/VERSION?m=text", r"go(\d+\.\d+(?:\.\d+)?)"],
        "parts": [
            {"kind": "website", "start": ["https://go.dev/ref/spec", "https://go.dev/doc/effective_go"],
             "prefix": "https://go.dev/", "depth": 0},
            {"kind": "website", "start": "https://pkg.go.dev/std", "prefix": "https://pkg.go.dev/",
             "depth": 1, "exclude": r"pkg\.go\.dev/(search|about|license|badge|golang\.org/x|github\.com)|\?",
             "api_path": "^/", "member_tag": "h4",
             "member_re": r"^(func\s+(\((?:\w+\s+)?\*?(?P<rtype>\w+)(\[[^\]]*\])?\)\s+)?(?P<name>\w+)|type\s+(?P<tname>\w+))"},
        ],
    },
    "git": {
        "about": "Git: the reference (every command and option) and the Pro Git book (git-scm.com)",
        "root": "https://git-scm.com/",
        "version_from": ["https://git-scm.com/docs/git", r"last updated in (\d+\.\d+\.\d+)"],
        "parts": [
            {"kind": "website", "start": "https://git-scm.com/book/en/v2",
             "prefix": "https://git-scm.com/book/en/v2", "main": "#main", "exclude": r"/ch00/|\?"},
            {"kind": "website", "start": "https://git-scm.com/docs", "prefix": "https://git-scm.com/docs/",
             "main": "#main", "depth": 2, "api_path": r"/docs/", "api_rename": [r"^git-", "git "],
             "options": True, "exclude": r"/docs/[^/]+/.|\?|#"},
        ],
    },
    "javascript": {
        "about": "JavaScript: the language reference and guide (MDN)",
        "kind": "website", "root": "https://developer.mozilla.org/",
        "sitemap": "https://developer.mozilla.org/sitemaps/en-us/sitemap.xml.gz",
        "prefix": "https://developer.mozilla.org/en-US/docs/Web/JavaScript/",
        "api": r"[A-Za-z_$][\w$]*(\.[\w$]+)+(\(\))?",
    },
}


def offers(name: str, version: str) -> bool:
    """Are there docs of this version of a known name? The default always; a channel if the
    entry has it; a number if its addresses take one."""
    entry = KNOWN[name]
    if not version or version in ("latest", "stable"):
        return True
    ch = channel(version)
    if ch:
        return ch in entry.get("channels", {})
    return "{version}" in repr(entry) and bool(re.fullmatch(r"v?\d+(\.\d+)*", version))


def versions(name: str) -> str:
    """What a known name's docs come in, for a message: "stable (the default), nightly"."""
    entry = KNOWN[name]
    out = ["stable (the default)"] + list(entry.get("channels", {}))
    if "{version}" in repr(entry):
        out.insert(1, "a version number")
    return ", ".join(out)


def resolve(name: str, version: str = "") -> dict | None:
    """The import plan for a known name, with {version} filled in (and a channel's addresses)."""
    entry = KNOWN.get(name)
    if entry is None:
        return None
    ch = channel(version) if version else None
    how = entry.get("channels", {}).get(ch) if ch else None
    if isinstance(how, str):                     # rust's "nightly": the value {version} takes
        version = how
    elif how is not None:                        # max's nightly: its own addresses
        entry = {**entry, **how}
        version = ch
    v = version or entry.get("version", "")

    def fill(x):
        if isinstance(x, str):
            return x.replace("{version}", v)
        if isinstance(x, list):
            return [fill(i) for i in x]
        if isinstance(x, dict):
            return {k: fill(i) for k, i in x.items()}
        return x
    plan = fill({k: v_ for k, v_ in entry.items() if k not in ("version", "channels")})
    plan["version"] = v
    return plan
