"""Known documentation that is not found through PyPI: languages and other toolkits.

`search add rust` uses this list, never a PyPI package that happens to be called "rust".
(To mean a PyPI package with such a name, write `search add pypi:NAME`.)

Each entry says how to import the docs (see importers.py) and where they are; "{version}"
in an address is replaced by the version you ask for (packages.toml: rust = "1.80"), or by
`version` (the default). Docs without "{version}" only exist as the current version.

`version_from`: where the current version number is published: an address and a pattern
whose first group is the number (matched in the page, or with "address" in the address it
redirects to). Docs whose default `version` is a number then follow new releases.
"""
from __future__ import annotations

KNOWN: dict[str, dict] = {
    "python": {
        "about": "Python: the language reference, tutorial and standard library",
        "kind": "sphinx", "url": "https://docs.python.org/{version}/", "version": "3",
    },
    "rust": {
        "about": "Rust: the standard library, The Rust Book and The Rust Reference",
        "root": "https://doc.rust-lang.org/{version}/", "version": "stable",
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
        "prefix": "https://ocaml.org/manual/{version}/", "max_pages": 1500, "main": "div.content, div.api",
    },
    "cpp": {
        "about": "C++: the language and standard library (cppreference.com)",
        "kind": "website", "root": "https://en.cppreference.com/",
        "start": "https://en.cppreference.com/cpp", "prefix": "https://en.cppreference.com/cpp",
        "main": "#mw-content-text", "api": r"std::[\w:~<>, ]+(\(\))?", "max_pages": 8000,
        "exclude": r"action=|oldid=|printable=|/Special:",
    },
    "c": {
        "about": "C: the language and standard library (cppreference.com)",
        "kind": "website", "root": "https://en.cppreference.com/",
        "start": "https://en.cppreference.com/c", "prefix": "https://en.cppreference.com/c",
        "main": "#mw-content-text", "max_pages": 3000,
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
        "prefix": "https://mojolang.org/docs/", "api_path": r"/docs/std/", "max_pages": 6000,
    },
    "max": {
        "about": "MAX: Modular's AI serving and modeling platform (max.modular.com)",
        "kind": "website", "root": "https://max.modular.com/", "llms": "https://max.modular.com/llms.txt",
        "version_from": ["https://max.modular.com/llms.txt", r"(?m)^Version: *(\S+)"],
        "prefix": "https://max.modular.com/", "api_path": r"/api/", "max_pages": 6000,
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
             "max_pages": 400, "api_path": "^/", "member_tag": "h4",
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
        "api": r"[A-Za-z_$][\w$]*(\.[\w$]+)+(\(\))?", "max_pages": 2500,
    },
}


def resolve(name: str, version: str = "") -> dict | None:
    """The import plan for a known name, with {version} filled in."""
    entry = KNOWN.get(name)
    if entry is None:
        return None
    v = version or entry.get("version", "")

    def fill(x):
        if isinstance(x, str):
            return x.replace("{version}", v)
        if isinstance(x, list):
            return [fill(i) for i in x]
        if isinstance(x, dict):
            return {k: fill(i) for k, i in x.items()}
        return x
    plan = fill({k: v_ for k, v_ in entry.items() if k != "version"})
    plan["version"] = v
    return plan
