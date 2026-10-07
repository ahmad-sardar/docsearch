#!/usr/bin/env python3
"""
search: search Python package docs and man pages by name, spelling or meaning, and read
them in the browser (Safari on a Mac). Everything runs on this computer and is 100% offline: only `search add` and
`search sync` (and `search embed`, to download the meaning model once) use the internet.

Build an index once per source (downloads the docs pages and their images):
    search add numpy pandas          # PyPI packages with Sphinx or MkDocs docs
    search add torch=https://pytorch.org/docs/stable/   # give the docs URL yourself
    search add numpy==1.26           # docs of another version (replaces the indexed one)
    search list                      # shows which version of the docs each source has
    search sync                      # index everything listed in packages.toml
    search add git                   # every git man page (commands and guides)
    search add bash                  # the bash man page, split into sections
    search add man:tmux              # any other man page
    search list | remove NAME | embed NAME

Search (opens the browser: results on the left, the documentation as real HTML):
    search                           # the search page
    search numpy svd                 # svd, in numpy
    search pandas numpy mean         # several packages
    search sum of elements           # no package named: all packages
    search stop                      # stop the background server (it starts by itself)

In the page: type to search, Up/Down to choose, Enter for the full page (an offline
copy; links between pages work too), Esc to go back or clear, / to jump to the search box,
w to wrap or scroll long code, c to copy the name. Code blocks and signatures have Copy
buttons; text can be selected and copied as in any web page.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import functools
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import asdict, dataclass
from pathlib import Path

from docsearch import pages as offline

# --------------------------------------------------------------------------- settings

def project_root() -> Path:
    """The folder with pyproject.toml above this file (the tools project)."""
    for d in Path(__file__).resolve().parents:
        if (d / "pyproject.toml").exists():
            return d
    raise SystemExit("search: cannot find the project folder (pyproject.toml).")


# Everything this tool keeps lives in the project folder:
#   packages.toml          the docs to keep indexed (search sync)
#   data/index/<source>/   downloaded docs, keyword index, vectors
#   data/models/           the meaning model (a Hugging Face cache)
# DOCSEARCH_DATA moves data/ elsewhere.
ROOT = project_root()
DATA = Path(os.environ.get("DOCSEARCH_DATA", ROOT / "data"))
HOME = DATA / "index"
MODELS = DATA / "models"
# A model trained for question -> passage retrieval (asymmetric search), not only for
# sentence similarity. Exactly these files of one commit, each checked against its SHA-256
# (published by Hugging Face for that commit). The weights are safetensors: plain numbers.
# The repository also has pickle files (pytorch_model.bin), which can run code when
# loaded; they are never downloaded.
MODEL_NAME = "sentence-transformers/multi-qa-MiniLM-L6-cos-v1"
MODEL_REVISION = "b207367332321f8e44f96e224ef15bc607f4dbf0"
MODEL_FILES = {
    "config.json": "953f9c0d463486b10a6871cc2fd59f223b2c70184f49815e7efbcab5d8908b41",
    "sentence_bert_config.json": "ec8e29d6dcb61b611b7d3fdd2982c4524e6ad985959fa7194eacfb655a8d0d51",
    "tokenizer.json": "7fa9272f7ef1ebd1666bb3bfd9d4707660ff0076ca9d1671cd9a9c6e18e03331",
    "model.safetensors": "7bec4fd9eba43073d5c5dcf1b79b0a3397608fa063e6f626d6f8fd70a81f2d8c",
}
CONFIG = ROOT / "packages.toml"                 # your docs (not in git)
EXAMPLE = ROOT / "packages.example.toml"        # the starting list for a new copy (in git)
MAX_DOWNLOAD = 50 * 2**20       # bytes per download; docs pages are far smaller
MAX_INVENTORY = 100 * 2**20     # bytes of a Sphinx inventory after decompression
ALLOW_HTTP = os.environ.get("DOCSEARCH_ALLOW_HTTP") == "1"   # default: HTTPS only
USER_AGENT = "docsearch/1.0 (personal documentation index)"
RRF_K = 60            # constant k in reciprocal rank fusion (Cormack et al., SIGIR 2009)
CANDIDATES = 200      # how many results each ranker gives to the fusion step
SHOW = 100            # how many fused results the interface lists
KEEP_CHARS = 2000      # text kept in memory per entry by a running search (the rest on disk)
PREVIEW_CHARS = 100_000  # stored text per entry: in practice the whole docstring
EMBED_CHARS = 200     # text per entry the model reads: the name, signature and first words.
                      # Measured on numpy: 200 ranks the right answer higher than 1200 (mean
                      # rank 6.5 vs 15.8 on 10 questions) and embeds 3.5x faster.
CHUNK_CHARS = 2500    # long man page sections are cut into parts of about this size
SKIP_HOSTS = {"github.com", "gitlab.com", "bitbucket.org", "pypi.org", "www.github.com"}


@dataclass
class Entry:
    title: str      # what spelling search matches against
    kind: str       # function, class, page, section, man, ...
    location: str   # URL, or "man git-commit"
    text: str       # Markdown shown in the preview, also the input to the model
    source: str     # the source name the user typed, e.g. "numpy"


def die(msg: str) -> None:
    Progress.clear()
    print(f"search: {msg}", file=sys.stderr)
    sys.exit(1)


def say(msg: str) -> None:
    Progress.clear()                         # a message never lands inside a progress bar
    print(msg, file=sys.stderr, flush=True)
    Progress.redraw()


class Progress:
    """A progress bar on the terminal: what, a bar, how many of how many, speed, time left.

        with Progress("  pages", len(urls), "pages") as bar:
            for ...: bar.update()

    Redrawn at most 10 times a second, on one line. When the output is not a terminal (a
    log file), a plain line every 10% instead (every 250 when the total is not known).
    unit="B" counts bytes and shows MB."""
    active: Progress | None = None

    def __init__(self, what: str, total: int | None = None, unit: str = "", note=None,
                 quiet: bool = False) -> None:
        self.what, self.total, self.unit, self.note, self.quiet = what, total, unit, note, quiet
        self.done, self.t0, self.drawn, self.width, self.step = 0, time.time(), 0.0, 0, -1
        self.tty = sys.stderr.isatty()
        if not quiet:
            Progress.active = self

    def __enter__(self) -> Progress:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def update(self, n: int = 1, total: int | None = None) -> None:
        self.done += n
        if total is not None:
            self.total = total
        if self.quiet:
            return
        if self.tty:
            if time.time() - self.drawn >= 0.1:
                self.draw()
        else:
            step = int(10 * self.done / self.total) if self.total else self.done // 250
            if step > self.step:
                self.step = step
                print(self.text(), file=sys.stderr, flush=True)

    def amount(self, n: float) -> str:
        return f"{n / 2**20:,.0f}" if self.unit == "B" else f"{n:,.0f}"

    def text(self) -> str:
        took = max(time.time() - self.t0, 1e-9)
        rate = self.done / took
        unit = "MB" if self.unit == "B" else self.unit
        speed = f"{self.amount(rate)} {unit}/s".replace(" /s", "/s")
        parts = [self.what]
        if self.total:
            filled = min(20, int(20 * self.done / self.total))
            parts += ["\u2588" * filled + "\u2591" * (20 - filled),
                      f"{self.amount(self.done)}/{self.amount(self.total)} {unit}".rstrip(),
                      f"{100 * self.done / self.total:3.0f}%", speed]
            if 0 < self.done < self.total and took > 2:
                parts.append(f"{clock((self.total - self.done) / rate)} left")
        else:
            parts += [f"{self.amount(self.done)} {unit}".rstrip(), speed, clock(took)]
        if self.note:
            parts.append(self.note())
        return "  ".join(p for p in parts if p)

    def draw(self) -> None:
        self.drawn = time.time()
        line = self.text()[: shutil.get_terminal_size((80, 20)).columns - 1]   # never wraps
        sys.stderr.write("\r" + line + " " * max(0, self.width - len(line)))
        sys.stderr.flush()
        self.width = len(line)

    def close(self) -> None:
        if Progress.active is self:
            Progress.active = None
        if self.quiet:
            return
        if self.tty:
            self.draw()
            sys.stderr.write("\n")
            sys.stderr.flush()
        elif self.step < (10 if self.total else self.done // 250):
            print(self.text(), file=sys.stderr, flush=True)

    @staticmethod
    def clear() -> None:
        bar = Progress.active
        if bar is not None and bar.tty and bar.width:
            sys.stderr.write("\r" + " " * bar.width + "\r")
            bar.width = 0

    @staticmethod
    def redraw() -> None:
        if Progress.active is not None and Progress.active.tty:
            Progress.active.draw()


def clock(seconds: float) -> str:
    """75 -> 1:15, 4000 -> 1:06:40."""
    s = int(seconds)
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


# --------------------------------------------------------------------------- network

_SSL = None


def ssl_context() -> ssl.SSLContext:
    """Trusted root certificates, best source first:
    1. truststore: the operating system's store (macOS Keychain, incl. company roots)
    2. certifi: a maintained list of public roots (fixes python.org Python on macOS)
    3. Python's default (also honours the SSL_CERT_FILE environment variable)"""
    global _SSL
    if _SSL is None:
        try:
            import truststore
            _SSL = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        except ImportError:
            try:
                if os.environ.get("SSL_CERT_FILE"):
                    raise ImportError
                import certifi
                _SSL = ssl.create_default_context(cafile=certifi.where())
            except ImportError:
                _SSL = ssl.create_default_context()
    return _SSL


def safe_url(url: str) -> bool:
    """Only web addresses: https (http only with DOCSEARCH_ALLOW_HTTP=1). Never file:, ftp:,
    data: or other schemes, which urllib would otherwise open."""
    u = urllib.parse.urlparse(url)
    return bool(u.netloc) and (u.scheme == "https" or (ALLOW_HTTP and u.scheme == "http"))


_CLIENT = None
_CLIENT_LOCK = __import__("threading").Lock()


def http_client():
    """One shared connection pool: a docs site is fetched over a few kept-open connections
    instead of a new connection (and TLS handshake) per page, about 3.5x faster. Redirects
    are followed by hand in http_get, so each one can be checked."""
    global _CLIENT
    with _CLIENT_LOCK:
        if _CLIENT is None:
            import httpx
            _CLIENT = httpx.Client(verify=ssl_context(), follow_redirects=False,
                                   headers={"User-Agent": USER_AGENT},
                                   limits=httpx.Limits(max_connections=32, max_keepalive_connections=32))
    return _CLIENT


class Failed(urllib.error.URLError):
    """A download that failed, with what kind of failure it is (see WHY)."""

    def __init__(self, kind: str, url: str, detail: str = "", wait: float | None = None) -> None:
        super().__init__(f"{url}: {WHY[kind].format(detail=detail)}")
        self.kind, self.url, self.detail, self.wait = kind, url, detail, wait


# What each kind of failure means, and whether waiting can fix it.
WHY = {
    "dns": "the name does not exist (DNS lookup failed): check the address and your internet connection",
    "offline": "no route to the site: is this computer online?",
    "refused": "the server refused the connection",
    "certificate": "its HTTPS certificate is not valid ({detail}); docsearch only downloads from sites "
                   "whose identity can be checked",
    "timeout": "no answer in time, even after retrying",
    "dropped": "the connection dropped, even after retrying",
    "bot-check": "the site shows a bot check ({detail}) that only a person in a browser can pass; "
                 "docsearch does not try to get around it",
    "login": "the page needs a login (HTTP 401)",
    "forbidden": "the site refuses this download (HTTP 403)",
    "not-found": "no page at this address (HTTP 404): wrong, or moved",
    "gone": "the page is gone (HTTP {detail})",
    "rate-limited": "the site asked to slow down (HTTP 429), even after waiting",
    "server-error": "the site had a server error (HTTP {detail}), even after retrying",
    "too-large": "the file is larger than the limit ({detail})",
    "not-https": "not an https:// address ({detail}); docsearch only downloads over HTTPS",
    "redirect": "{detail}",
    "robots": "the site's robots.txt asks programs not to download these pages",
    "empty": "the page has no text of its own: it is built by JavaScript in the browser (a web app), "
             "which docsearch does not run",
    "other": "{detail}",
}
TRANSIENT = {"timeout", "dropped", "rate-limited", "server-error"}
RETRY_STATUS = {429, 500, 502, 503, 504}
RETRY_WAITS = (1, 3, 9)          # seconds before each new try (or what Retry-After asks, at most 30)
DEAD_HOSTS: dict[str, Failed] = {}   # hosts that failed for good this run: fail at once


def connect_failure(url: str, e: Exception) -> Failed:
    """Name the cause of a failed connection from the system's message."""
    import httpx
    msg = str(e)
    if isinstance(e, httpx.TimeoutException):
        return Failed("timeout", url)
    if "CERTIFICATE_VERIFY_FAILED" in msg or "SSL" in msg:
        detail = msg.split("certificate verify failed:")[-1].split("(_ssl")[0].strip() or "TLS error"
        return Failed("certificate", url, detail)
    if "nodename nor servname" in msg or "Name or service not known" in msg or "getaddrinfo" in msg:
        return Failed("dns", url)
    if "Connection refused" in msg:
        return Failed("refused", url)
    if "unreachable" in msg or "No route" in msg:
        return Failed("offline", url)
    return Failed("dropped", url, msg)


def bot_check(r, head: bytes) -> str | None:
    """Who is showing a bot check instead of the page (Cloudflare, Akamai...), if anyone."""
    server = r.headers.get("server", "").lower()
    if r.headers.get("cf-mitigated") == "challenge" or (
            "cloudflare" in server and (b"challenge-platform" in head or b"Just a moment" in head)):
        return "Cloudflare"
    if "akamai" in server or b"_abck" in head:
        return "Akamai"
    if b"captcha" in head.lower() and r.status_code in (403, 429, 503):
        return "a captcha"
    return None


def http_get(url: str, timeout: float = 20) -> tuple[bytes, str]:
    """Return (body, final URL after redirects). HTTPS only, certificate checked, at most
    MAX_DOWNLOAD bytes, at most 5 redirects and only to other HTTPS addresses. Failures are
    Failed, with their kind; the transient ones are tried again (RETRY_WAITS), and a host
    that failed for good (no such name, bad certificate, bot check) is not tried again."""
    host = urllib.parse.urlparse(url).netloc
    if host in DEAD_HOSTS:
        old = DEAD_HOSTS[host]
        raise Failed(old.kind, url, old.detail)
    for wait in (*RETRY_WAITS, None):
        try:
            return http_get_once(url, timeout)
        except Failed as e:
            if e.kind in ("dns", "certificate", "bot-check", "offline"):
                DEAD_HOSTS[host] = e
            if e.kind not in TRANSIENT or wait is None:
                raise
            time.sleep(min(30.0, e.wait if e.wait is not None else wait))
    raise AssertionError("unreachable")


def http_get_once(url: str, timeout: float = 20) -> tuple[bytes, str]:
    import httpx
    for _ in range(6):
        if not safe_url(url):
            raise Failed("not-https", url, url.split(":", 1)[0] + ":")
        try:
            with http_client().stream("GET", url, timeout=timeout) as r:
                if r.is_redirect:
                    nxt = urllib.parse.urljoin(url, r.headers.get("location", ""))
                    if url.startswith("https:") and not nxt.startswith("https:"):
                        raise Failed("redirect", url, f"it redirects from HTTPS to plain HTTP ({nxt}), "
                                                      "which is refused")
                    url = nxt
                    continue
                if r.status_code >= 400:
                    head = b""
                    for chunk in r.iter_bytes():
                        head += chunk
                        if len(head) > 65536:
                            break
                    who = bot_check(r, head)
                    if who:
                        raise Failed("bot-check", url, who)
                    code = r.status_code
                    if code in RETRY_STATUS:
                        after = r.headers.get("retry-after", "")
                        raise Failed("rate-limited" if code == 429 else "server-error", url, str(code),
                                     float(after) if after.isdigit() else None)
                    kind = {401: "login", 403: "forbidden", 404: "not-found", 410: "gone"}.get(code, "gone")
                    raise Failed(kind, url, str(code))
                body = bytearray()
                for chunk in r.iter_bytes():
                    body += chunk
                    if len(body) > MAX_DOWNLOAD:
                        raise Failed("too-large", url, f"{MAX_DOWNLOAD // 2**20} MB")
                return bytes(body), str(r.url)
        except httpx.TransportError as e:            # no connection, or it dropped
            raise connect_failure(url, e) from e
        except httpx.HTTPError as e:                 # other network trouble
            raise Failed("other", url, str(e) or type(e).__name__) from e
    raise Failed("redirect", url, "too many redirects")


class Failures:
    """The pages of one download that failed, by cause (for the summary and meta.json)."""

    def __init__(self) -> None:
        self.by_kind: dict[str, list[str]] = {}

    def add(self, url: str, e: BaseException) -> None:
        if not isinstance(e, Failed):
            e = Failed("other", url, str(getattr(e, "reason", e)) or type(e).__name__)
        key = e.kind if e.kind not in ("redirect", "other") else f"{e.kind}:{e.detail}"
        self.by_kind.setdefault(key, []).append(url)

    def __len__(self) -> int:
        return sum(len(v) for v in self.by_kind.values())

    def report(self) -> None:
        for key, urls in sorted(self.by_kind.items(), key=lambda kv: -len(kv[1])):
            say(f"    {len(urls)} × {describe(key)}  (e.g. {urls[0]})")

    def as_meta(self) -> dict:
        return {k: {"count": len(v), "example": v[0]} for k, v in self.by_kind.items()}


def describe(key: str) -> str:
    """A failure kind (or "redirect:<what happened>") in words."""
    kind, _, detail = key.partition(":")
    return WHY.get(kind, "{detail}").format(detail=detail).replace(" ()", "") or kind


CONTROL = re.compile("[\x00-\x08\x0b-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]")


def clean(s: str) -> str:
    """Remove control characters (terminal escape codes) and bidirectional overrides from
    downloaded text, so a web page cannot send commands to your terminal or hide text."""
    return CONTROL.sub("", s)


# --------------------------------------------------------------------------- HTML -> Markdown

def make_soup(html: bytes):
    from bs4 import BeautifulSoup
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def clean_soup(soup) -> None:
    from bs4 import Comment
    for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()                                  # e.g. MDN's "lit-part" template markers
    for sel in ("script", "style", "a.headerlink", "span.viewcode-link", "nav", "footer",
                # page chrome of the PyData/PyTorch themes: ratings, breadcrumbs, prev/next
                "div.rating", ".header-article-items", ".bd-breadcrumbs", ".prev-next-area",
                ".bd-sidebar-secondary", ".bd-header-article", ".feedback"):
        for el in soup.select(sel):
            el.decompose()


TEX_SYMBOLS = {
    "times": "×", "cdot": "·", "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥", "neq": "≠", "ne": "≠",
    "approx": "≈", "infty": "∞", "sum": "Σ", "prod": "Π", "in": "∈", "notin": "∉", "ldots": "…",
    "dots": "…", "cdots": "…", "to": "→", "rightarrow": "→", "leftarrow": "←", "pm": "±",
    "partial": "∂", "nabla": "∇", "int": "∫", "log": "log", "exp": "exp", "max": "max", "min": "min",
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "varepsilon": "ε",
    "eta": "η", "theta": "θ", "lambda": "λ", "mu": "μ", "pi": "π", "rho": "ρ", "sigma": "σ",
    "tau": "τ", "phi": "φ", "omega": "ω", "Gamma": "Γ", "Delta": "Δ", "Sigma": "Σ", "Omega": "Ω",
    "lfloor": "⌊", "rfloor": "⌋", "lceil": "⌈", "rceil": "⌉", "mid": "|", "quad": " ", "qquad": "  ",
}


def tex_to_text(tex: str) -> str:
    """LaTeX maths as plain readable text: H_\\text{in} -> H_in, \\sqrt{k} -> √(k)."""
    t = tex.strip()
    t = re.sub(r"^\\\(|\\\)$|^\\\[|\\\]$|^\$+|\$+$", "", t).strip()
    t = re.sub(r"\\(?:left|right|big|Big|bigg|Bigg)\b", "", t)
    for _ in range(5):                                          # nested commands, inside out
        t = re.sub(r"\\(?:text|mathrm|mathbf|mathcal|mathit|mathbb|operatorname|textrm|textbf)\{([^{}]*)\}",
                   r"\1", t)
        t = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", t)
        t = re.sub(r"\\sqrt\{([^{}]*)\}", r"√(\1)", t)
        t = re.sub(r"([_^])\{([^{}]*)\}", lambda m: m.group(1) + (m.group(2) if len(m.group(2)) == 1
                                                                  else f"({m.group(2)})"), t)
    t = re.sub(r"\\([A-Za-z]+)", lambda m: TEX_SYMBOLS.get(m.group(1), m.group(1)), t)
    t = t.replace("\\_", "_").replace("\\,", " ").replace("\\;", " ").replace("\\!", "").replace("\\\\", " ")
    t = t.replace("{", "").replace("}", "").replace("~", " ")
    return " ".join(t.split())


def tidy_math(soup) -> None:
    """Formulas are stored three times (shown text, MathML, LaTeX); markdownify printed all
    of them run together. Keep one readable copy, as inline code."""
    for el in soup.select("span.katex, span.katex-display"):
        ann = el.find("annotation")
        if ann is None or not el.parent:
            continue
        code = soup.new_tag("code")
        code.string = tex_to_text(ann.get_text())
        el.replace_with(code)
    for el in soup.select("span.math, div.math"):                # MathJax: raw \(...\) text
        txt = el.get_text()
        if el.find("code") is None and "\\" in txt:
            code = soup.new_tag("code")
            code.string = tex_to_text(txt)
            el.replace_with(code)


def tidy_definitions(soup) -> None:
    """Rewrite Sphinx definition lists as HTML that becomes clean Markdown. Markdown has no
    definition lists, so markdownify would print "**a**array_like" with stray ':' lines.
    - API signatures (<dt class="sig">) become code blocks,
    - "Parameters:", "Returns:" (field lists) become small headings,
    - each parameter becomes "**name** : type" with its description quoted below it."""
    for sp in soup.select("span.classifier"):
        sp.insert_before(" : ")
    for dl in soup.find_all("dl"):
        field_list = "field-list" in (dl.get("class") or [])
        # The body of an API definition (a class, its methods) is not a quote: the signature
        # block above it already marks where it starts. Quoting it put bars on every line.
        api = any("sig" in (dt.get("class") or []) for dt in dl.find_all("dt", recursive=False))
        for dt in dl.find_all("dt", recursive=False):
            if "sig" in (dt.get("class") or []):
                text = " ".join(dt.get_text("").split())
                dt.clear()
                dt.name = "pre"
                dt.string = text
            elif field_list:
                text = dt.get_text(" ", strip=True).rstrip(":")
                dt.clear()
                dt.name = "h4"
                dt.string = text
            else:
                dt.name = "p"
        for dd in dl.find_all("dd", recursive=False):
            dd.name = "div" if field_list or api else "blockquote"
        dl.name = "div"


def html_to_md(html: str) -> str:
    from markdownify import markdownify
    soup = make_soup(html.encode() if isinstance(html, str) else html)
    tidy_math(soup)
    tidy_definitions(soup)
    html = str(soup.body or soup)
    md = markdownify(html, heading_style="ATX", strip=["a", "img"],
                     escape_underscores=False, escape_asterisks=False)
    md = re.sub(r"[ \t]+\n", "\n", md)
    return re.sub(r"\n{3,}", "\n\n", md).strip()


def plain(md: str) -> str:
    md = re.sub(r"```\w*", " ", md)          # drop code-fence markers like ```text
    return " ".join(md.replace("`", " ").replace("#", " ").split())


REFRESH = re.compile(rb'<meta[^>]+http-equiv=["\']?refresh["\']?[^>]+content=["\']?\s*\d+\s*;\s*url=([^"\'>\s]+)', re.I)


def get_page(url: str) -> bytes:
    return get_page_at(url)[0]


def get_page_at(url: str) -> tuple[bytes, str]:
    """Download a docs page; return it and the address it really came from. Some sites
    serve small redirect pages instead of the page (PyTorch: /stable/x.html only says
    "go to /2.14/x.html"). A browser follows them; here we follow up to 3, same site only."""
    for _ in range(4):
        html, final = http_get(url)
        m = REFRESH.search(html[:4096]) if len(html) < 20_000 else None
        if not m:
            return html, final
        nxt = urllib.parse.urljoin(final, m.group(1).decode("utf-8", "replace"))
        if not same_site(final, nxt):
            raise Failed("redirect", url, f"it redirects to another site ({nxt}), which is not followed")
        url = nxt
    raise Failed("redirect", url, "too many redirects")


def same_site(root: str, url: str) -> bool:
    """An inventory may list any address. Keep only pages on the docs site itself."""
    a, b = urllib.parse.urlparse(root), urllib.parse.urlparse(url)
    return safe_url(url) and (a.scheme, a.netloc) == (b.scheme, b.netloc)


# --------------------------------------------------------------------------- Sphinx

INV_LINE = re.compile(r"(?x)(.+?)\s+(\S+)\s+(-?\d+)\s+?(\S*)\s+(.*)")  # Sphinx's own pattern


def parse_objects_inv(data: bytes) -> tuple[str, str, list[dict]]:
    """Decode a Sphinx inventory (version 2): 4 text header lines, then zlib data."""
    head = data.split(b"\n", 4)
    if len(head) < 5 or not head[0].startswith(b"# Sphinx inventory version 2"):
        raise ValueError("not a Sphinx version 2 inventory")
    project = head[1].decode("utf-8", "replace").removeprefix("# Project:").strip()
    version = head[2].decode("utf-8", "replace").removeprefix("# Version:").strip()
    z = zlib.decompressobj()
    body = z.decompress(head[4], MAX_INVENTORY)
    if z.unconsumed_tail:
        raise ValueError("the Sphinx inventory is larger than the limit")
    body = body.decode("utf-8", "replace")
    out = []
    for line in body.splitlines():
        m = INV_LINE.match(line.rstrip())
        if not m:
            continue
        name, typ, prio, uri, disp = m.groups()
        domain, _, role = typ.partition(":")
        if uri.endswith("$"):
            uri = uri[:-1] + name
        out.append(dict(name=name, domain=domain, role=role, prio=int(prio), uri=uri,
                        disp=name if disp == "-" else disp, has_disp=disp != "-"))
    return project, version, out


def sphinx_title(o: dict) -> str:
    if o["role"] == "doc":
        return f"{o['disp']} (page)"
    if o["role"] == "label":
        return f"{o['disp']} (section)"
    return f"{o['disp']} ({o['role']})"


def main_content(soup):
    """The article of a docs page, without the site's navigation around it."""
    for sel in ("article.bd-article", 'article[role="main"]', 'div[role="main"]',
                "div.body", "main", "article"):
        el = soup.select_one(sel)
        if el is not None:
            return el
    return soup.body


def sphinx_fragment(soup, anchor: str):
    """Return the HTML nodes that document one inventory entry."""
    if not anchor:
        main = soup.select_one('div[role="main"], main, article, div.body') or soup.body
        return [main] if main else None
    el = soup.find(id=anchor)
    if el is None:
        return None
    if el.name == "dt":                       # API object: signature <dt> + body <dd>
        dd = el.find_next_sibling("dd")
        return [el, dd] if dd else [el]
    if el.name in ("span", "a") and not el.get_text(strip=True):  # older label anchors
        nxt = el.find_next(["section", "div", "dl", "p"])
        return [nxt] if nxt else None
    return [el]


def build_sphinx(name: str, root: str, inv: bytes, workers: int, max_pages: int | None,
                 store=None) -> tuple[list[Entry], dict]:
    """Every object in a Sphinx inventory, cut out of its page. `store` keeps the pages for
    offline reading (a source made of several Sphinx sites shares one, e.g. CUDA)."""
    project, version, objs = parse_objects_inv(inv)
    # One entry per target URL. Prefer API objects over pages, pages over labels.
    rank = {"doc": 1, "label": 2}
    best: dict[str, dict] = {}
    for o in objs:
        if o["role"] == "label" and not o["has_disp"]:
            continue  # anonymous labels have no title to search
        cur = best.get(o["uri"])
        if cur is None or rank.get(o["role"], 0) < rank.get(cur["role"], 0):
            best[o["uri"]] = o
    pages: dict[str, list[tuple[dict, str]]] = {}
    for o in best.values():
        page, _, anchor = o["uri"].partition("#")
        pages.setdefault(page, []).append((o, anchor))
    page_list = list(pages)[:max_pages] if max_pages else list(pages)
    say(f"  {project} {version}: {len(best)} documented objects on {len(page_list)} pages")
    if len(page_list) > 1500:
        say("  This is a large site. The first download can take several minutes.")

    page_list = [p for p in page_list if same_site(root, urllib.parse.urljoin(root, p))]

    def fetch(page: str):
        try:
            return page, get_page_at(urllib.parse.urljoin(root, page)), None
        except Exception as e:  # noqa: BLE001 - report and continue
            return page, None, e

    entries: list[Entry] = []
    fails = Failures()
    own = store is None
    if own:                                              # offline copies, for the browser
        from docsearch.importers import Store
        store = Store(source_id(name), root)
        store.reset()
    # Downloads (threads, waiting on the network) and cutting pages into entries (worker
    # processes, one per core) run at the same time: neither waits for the other.
    jobs = []
    with cf.ThreadPoolExecutor(max_workers=workers) as net, \
            cf.ProcessPoolExecutor(max_workers=os.cpu_count() or 4) as cpu:
        with Progress("  pages", len(page_list), note=lambda: f"{len(fails)} failed" if fails else "") as bar:
            for page, got, err in net.map(fetch, page_list):
                bar.update()
                if got is None:
                    fails.add(urllib.parse.urljoin(root, page), err)
                    continue
                jobs.append(cpu.submit(sphinx_page, name, root, page, got[0], got[1], pages[page],
                                       store.dir, store.root))
        for job in jobs:                                 # in page order: the same index each time
            found, used = job.result()
            entries += found
            store.add_images(used)
    if own:
        store.finish(workers)
    if fails:
        fails.report()
    return entries, {"project": project, "version": version, "failed_pages": len(fails),
                     "failures": fails.as_meta(), "pages": True}


def sphinx_page(name: str, root: str, page: str, html: bytes, real_url: str,
                items: list[tuple[dict, str]], pages_dir: Path, store_root: str) -> tuple[list[Entry], dict[str, str]]:
    """Cut one downloaded page into its entries and store its offline copy. Runs in a
    worker process. Returns the entries and the images the page shows."""
    sid = pages_dir.parent.name                          # numpy, or numpy@1.26
    root_host = urllib.parse.urlparse(root).netloc
    images: dict[str, str] = {}

    def image(url: str) -> str | None:
        # only the docs site's own images: never third parties (trackers, avatars, badges)
        if not safe_url(url) or urllib.parse.urlparse(url).netloc != root_host:
            return None
        images[url] = offline.image_name(url)
        return f"/asset/{sid}/{images[url]}"

    soup = make_soup(html)
    clean_soup(soup)
    entries = []
    for o, anchor in items:
        if not same_site(root, urllib.parse.urljoin(root, o["uri"])):
            continue
        nodes = sphinx_fragment(soup, anchor)
        if not nodes:
            continue
        if nodes[0].name == "dt":
            sig = " ".join(nodes[0].get_text("").split())
            short = sig.split("(")[0].split()[-1] if sig.split("(")[0].split() else ""
            if short and short != o["name"] and o["name"].endswith("." + short):
                sig = sig.replace(short, o["name"], 1)   # show the full dotted name
            body = html_to_md(nodes[1].decode_contents()) if len(nodes) > 1 else ""
            md = f"```python\n{sig}\n```\n\n{body}"
        else:
            md = html_to_md("".join(str(n) for n in nodes))
        entries.append(Entry(title=sphinx_title(o), kind=o["role"],
                             location=urllib.parse.urljoin(root, o["uri"]),
                             text=md[:PREVIEW_CHARS], source=name))
    # After the entries are cut out (that reads the same soup): keep the page itself.
    main = main_content(soup)
    if main is not None:
        offline.keep_mathml(main)
        # links resolve against the docs root (they must match the stored pages);
        # images against where the page really is (PyTorch: /2.14/, not /stable/)
        url = urllib.parse.urljoin(root, page)
        rel = url[len(store_root):] if url.startswith(store_root) else page
        offline.save_page(pages_dir, rel, clean(offline.sanitize(main, url, image, real_url)))
    return entries, images


def download_images(images: dict[str, str], folder: Path, workers: int, read=None) -> None:
    """Store the images the pages show, so the pages need no internet. The type is read
    from the image's own bytes; anything that is not PNG/JPEG/GIF/WebP/SVG is dropped.
    `read(url)`: where the bytes come from (default: download; a local import reads files)."""
    folder.mkdir(parents=True, exist_ok=True)

    def one(item: tuple[str, str]):
        url, name = item
        try:
            data = read(url) if read else get_page(url)    # follows PyTorch-style redirect stubs
        except Exception:  # noqa: BLE001 - a missing image shows its description instead
            return name, None
        ctype = offline.image_type(data) if len(data) <= offline.MAX_IMAGE else None
        if ctype:
            (folder / name).write_bytes(data)
        return name, ctype

    types: dict[str, str] = {}
    with cf.ThreadPoolExecutor(max_workers=workers) as ex, \
            Progress("  images", len(images), quiet=not images) as bar:
        for name, ctype in ex.map(one, images.items()):
            bar.update()
            if ctype:
                types[name] = ctype
    write_atomic(folder / "images.json", json.dumps(types).encode())
    say(f"  images: {len(types)} of {len(images)} stored")


# --------------------------------------------------------------------------- MkDocs

def build_mkdocs(name: str, root: str, data: bytes) -> tuple[list[Entry], dict]:
    docs = json.loads(data).get("docs", [])
    page_titles = {d.get("location", ""): d.get("title", "") for d in docs if "#" not in d.get("location", "")}
    entries = []
    for d in docs:
        loc = d.get("location", "")
        page = loc.split("#")[0]
        title = d.get("title") or page or "Home"
        parent = page_titles.get(page)
        if "#" in loc and parent and parent != title:
            title = f"{parent} › {title}"
        if not same_site(root, urllib.parse.urljoin(root, loc)):
            continue
        text = d.get("text", "") or ""
        md = html_to_md(text) if "<" in text else text
        entries.append(Entry(title=title, kind="section" if "#" in loc else "page",
                             location=urllib.parse.urljoin(root, loc),
                             text=md[:PREVIEW_CHARS], source=name))
    return entries, {"project": name, "version": ""}


# --------------------------------------------------------------------------- finding the docs of a PyPI package

PYPI_INFO: dict[str, dict] = {}      # package -> PyPI's own description (for the overlap check)
GUESSED: set[str] = set()            # docs addresses we made up rather than PyPI listing them


def pypi_candidates(pkg: str) -> list[str]:
    try:
        meta = json.loads(http_get(f"https://pypi.org/pypi/{pkg}/json")[0])
    except Failed as e:
        if e.kind == "not-found":
            die(f"'{pkg}' is not a package on PyPI.")
        raise
    info = meta.get("info", {})
    PYPI_INFO[pkg] = info
    urls = info.get("project_urls") or {}
    docs = [u for k, u in urls.items() if re.search(r"doc", k, re.I)]
    rtd = [u for u in urls.values() if "readthedocs" in u]
    home = [u for k, u in urls.items() if re.search(r"home|website", k, re.I)]
    norm = re.sub(r"[-_.]+", "-", pkg).lower()
    rtd_guess = [f"https://{norm}.readthedocs.io/en/stable/", f"https://{norm}.readthedocs.io/en/latest/"]
    listed = " ".join(list(urls.values()) + [info.get("docs_url") or "", info.get("home_page") or ""])
    if f"{norm}.readthedocs.io" not in listed:
        GUESSED.add(f"{norm}.readthedocs.io")       # only a guess: another project may live there
    legacy = [info[k] for k in ("docs_url", "home_page") if info.get(k)]
    seen, out = set(), []
    for u in docs + rtd + rtd_guess + home + legacy:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def probe_roots(candidate: str) -> list[str]:
    """Directories where objects.inv or search/search_index.json may live."""
    if candidate.startswith("http://") and not ALLOW_HTTP:
        candidate = "https://" + candidate[len("http://"):]     # PyPI often lists http links
    try:
        final = http_get(candidate, timeout=10)[1]
    except Exception:  # noqa: BLE001
        final = candidate
    u = urllib.parse.urlparse(final)
    if u.netloc.lower() in SKIP_HOSTS or not u.scheme.startswith("http"):
        return []
    base = f"{u.scheme}://{u.netloc}"
    path = u.path if u.path.endswith("/") else u.path.rsplit("/", 1)[0] + "/"
    parents, p = [], path
    while True:
        parents.append(base + p)
        if p == "/":
            break
        p = p.rstrip("/").rsplit("/", 1)[0] + "/"
    here = parents[0]
    suffixes = ["stable/", "en/stable/", "en/latest/", "latest/", "docs/", "docs/stable/", "doc/stable/"]
    roots = [here] + [here + s for s in suffixes] + parents[1:]
    return list(dict.fromkeys(roots))


def find_docs(candidates: list[str]) -> tuple[str, str, bytes] | None:
    tried: set[str] = set()
    for cand in candidates:
        say(f"  looking at {cand}")
        for root in probe_roots(cand):
            if root in tried:
                continue
            tried.add(root)
            for fname, kind in (("objects.inv", "sphinx"), ("search/search_index.json", "mkdocs")):
                try:
                    data, final = http_get(root + fname, timeout=10)
                except Exception:  # noqa: BLE001
                    continue
                real_root = final[: -len(fname)] if final.endswith(fname) else root
                if kind == "sphinx" and data.startswith(b"# Sphinx inventory version 2"):
                    return kind, real_root, data
                if kind == "mkdocs":
                    try:
                        if isinstance(json.loads(data).get("docs"), list):
                            return kind, real_root, data
                    except Exception:  # noqa: BLE001
                        pass
    return None


VERSION_SEGMENT = re.compile(r"^(stable|latest|dev|devdocs|main|master|current|v?\d+(\.\d+)*\w*)$")


def find_version(root: str, want: str) -> tuple[str, str, bytes] | None:
    """Docs of another version usually sit next to the current ones: numpy.org/doc/stable/
    -> numpy.org/doc/2.1/, foo.readthedocs.io/en/latest/ -> foo.readthedocs.io/en/v2.1/.
    Swap the version part of the URL and check that docs are there."""
    v = want.lstrip("v")
    short = ".".join(v.split(".")[:2])
    variants = list(dict.fromkeys([v, "v" + v, short, "v" + short, v + ".x", short + ".x"]))
    u = urllib.parse.urlparse(root)
    segs = u.path.strip("/").split("/")
    roots = []
    for k, seg in enumerate(segs):
        if VERSION_SEGMENT.match(seg):
            for var in variants:
                path = "/".join(segs[:k] + [var] + segs[k + 1:])
                roots.append(f"{u.scheme}://{u.netloc}/{path}/")
    for r in roots:
        for fname, kind in (("objects.inv", "sphinx"), ("search/search_index.json", "mkdocs")):
            try:
                data, final = http_get(r + fname, timeout=10)
            except Exception:  # noqa: BLE001
                continue
            if kind == "sphinx" and data.startswith(b"# Sphinx inventory version 2"):
                return kind, final[: -len(fname)], data
            if kind == "mkdocs" and data.lstrip().startswith(b"{"):
                return kind, final[: -len(fname)], data
    return None


def hosted_versions(root: str) -> list[str]:
    """The versions whose docs a Read the Docs project hosts (*.readthedocs.io only)."""
    host = urllib.parse.urlparse(root).netloc
    if not host.endswith(".readthedocs.io"):
        return []
    slug = host.removesuffix(".readthedocs.io")
    try:
        data = json.loads(http_get(f"https://readthedocs.org/api/v3/projects/{slug}/versions/"
                                   "?active=true&limit=100", timeout=10)[0])
    except Exception:  # noqa: BLE001
        return []
    return [v["slug"] for v in data.get("results", [])
            if VERSION_SEGMENT.match(v.get("slug", "")) and v["slug"] not in ("latest", "stable")]


# --------------------------------------------------------------------------- man pages

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
DASHES = str.maketrans({"\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2212": "-"})
SECTION_RE = re.compile(r"^[A-Z][A-Z0-9 _/&,.()'-]*[A-Z0-9)]$")
RUNNING_RE = re.compile(r"^\S.*\(\d[0-9a-zA-Z]*\)\s*$")   # page header and footer lines
ITEM_RE = re.compile(r"OPTION|COMMAND|BUILTIN|VARIABLE|PARAMETER|EXPANSION", re.I)


MAN_NAME = re.compile(r"[A-Za-z0-9_][\w.+:@-]{0,99}")   # never starts with '-': not an option


# A command's output as text (UTF-8 everywhere; Windows would otherwise guess its code page)
OUTPUT = {"capture_output": True, "text": True, "encoding": "utf-8", "errors": "replace"}


def read_man(page: str) -> str | None:
    if not shutil.which("man") or not MAN_NAME.fullmatch(page):
        return None
    env = dict(os.environ, MANPAGER="cat", PAGER="cat", MANWIDTH="100", GROFF_NO_SGR="1")
    env.pop("MAN_KEEP_FORMATTING", None)
    try:
        r = subprocess.run(["man", page], **OUTPUT, env=env, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0 or not r.stdout.strip():
        return None
    s = re.sub(r".\x08", "", r.stdout)       # remove overstrike bold/underline
    s = ANSI.sub("", s).translate(DASHES)
    return s if re.search(r"^NAME\s*$", s, re.M) else None   # every real man page has NAME


def indent_of(s: str) -> int:
    return len(s) - len(s.lstrip(" "))


def fence(lines: list[str]) -> str:
    body = textwrap.dedent("\n".join(lines)).strip("\n")
    return f"```text\n{body}\n```"


def split_items(buf: list[str]) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """Split a block into items. An item starts at a line on the base indent whose
    next non-blank line is indented deeper (the layout of groff .TP and .IP)."""
    nb = [i for i, line in enumerate(buf) if line.strip()]
    if not nb:
        return [], []
    base = min(indent_of(buf[i]) for i in nb)
    nxt = dict(zip(nb, nb[1:]))
    starts = [i for i in nb if indent_of(buf[i]) == base and i in nxt and indent_of(buf[nxt[i]]) > base]
    if not starts:
        return buf, []
    intro = buf[: starts[0]]
    items = []
    for s, e in zip(starts, starts[1:] + [len(buf)]):
        term = re.split(r"\s{2,}", buf[s].strip())[0][:70]
        items.append((term, buf[s:e]))
    return (intro if any(x.strip() for x in intro) else []), items


def chunk_paragraphs(buf: list[str], limit: int = CHUNK_CHARS) -> list[list[str]]:
    paras, cur = [], []
    for line in buf + [""]:
        if line.strip():
            cur.append(line)
        elif cur:
            paras.append(cur)
            cur = []
    chunks, cur, size = [], [], 0
    for p in paras:
        n = sum(len(x) for x in p)
        if cur and size + n > limit:
            chunks.append(cur)
            cur, size = [], 0
        cur += p + [""]
        size += n
    if cur:
        chunks.append(cur)
    return chunks


def split_man(page: str, raw: str, source: str) -> list[Entry]:
    lines = [ln for ln in raw.expandtabs().split("\n") if not RUNNING_RE.match(ln)]
    blocks: list[tuple[str, str | None, list[str]]] = []
    sec, sub, buf = "Header", None, []
    for ln in lines:
        if ln[:1] not in ("", " ") and SECTION_RE.match(ln.strip()):
            if any(x.strip() for x in buf):
                blocks.append((sec, sub, buf))
            sec, sub, buf = ln.strip(), None, []
        elif indent_of(ln) == 3 and ln.strip() and not ln.strip().startswith("-"):
            if any(x.strip() for x in buf):
                blocks.append((sec, sub, buf))
            sub, buf = ln.strip(), []
        else:
            buf.append(ln)
    if any(x.strip() for x in buf):
        blocks.append((sec, sub, buf))

    out: list[Entry] = []

    def emit(crumbs: list[str], body: list[str]) -> None:
        out.append(Entry(title=" › ".join(crumbs), kind="man", location=f"man {page}",
                         text=fence(body), source=source))

    for sec, sub, buf in blocks:
        crumbs = [page, sec.capitalize()] + ([sub] if sub else [])
        if ITEM_RE.search(sec) or (sub and ITEM_RE.search(sub)):
            intro, items = split_items(buf)
            if intro:
                emit(crumbs, intro)
            for term, body in items:
                emit(crumbs + [term], body)
            if items:
                continue
        parts = chunk_paragraphs(buf)
        for i, part in enumerate(parts, 1):
            emit(crumbs + ([f"part {i}"] if len(parts) > 1 else []), part)
    return out


def split_markdown(page: str, md: str, source: str, location: str) -> list[Entry]:
    """Fallback for HTML help files: one entry per '## ' section."""
    out, title, buf = [], "Overview", []
    for line in md.splitlines() + ["## "]:
        if line.startswith("## "):
            if "".join(buf).strip():
                out.append(Entry(title=f"{page} › {title.capitalize()}", kind="help",
                                 location=location, text="\n".join(buf).strip()[:PREVIEW_CHARS],
                                 source=source))
            title, buf = line[3:].strip() or "Overview", []
        else:
            buf.append(line)
    return out


def git_page_names() -> list[str]:
    env = dict(os.environ, GIT_PAGER="cat", PAGER="cat")
    names = ["git"]
    pat = re.compile(r"^\s{2,}([a-z][a-z0-9-]*)(?:\s{2,}\S.*)?$")
    for flag, prefix in (("-a", "git-"), ("-g", "git")):
        try:
            r = subprocess.run(["git", "help", flag], **OUTPUT, env=env, timeout=30)
        except OSError:
            die("git is not installed or not on PATH.")
        for line in r.stdout.splitlines():
            m = pat.match(line)
            if m:
                names.append(prefix + m.group(1))
    return list(dict.fromkeys(names))


def build_git(workers: int) -> list[Entry]:
    pages = git_page_names()
    say(f"  {len(pages)} git manual pages")
    try:
        html_dir = Path(subprocess.run(["git", "--html-path"], **OUTPUT).stdout.strip())
    except OSError:
        html_dir = Path()
    env = dict(os.environ, GIT_PAGER="cat", PAGER="cat")

    def one(page: str) -> list[Entry]:
        raw = read_man(page)
        if raw:
            return split_man(page, raw, "git")
        html_file = html_dir / f"{page}.html"            # Git for Windows ships HTML help
        if html_file.is_file():
            soup = make_soup(html_file.read_bytes())
            clean_soup(soup)
            return split_markdown(page, html_to_md(str(soup.body or soup)), "git", str(html_file))
        if page.startswith("git-"):                       # last resort: the short usage text
            r = subprocess.run(["git", page[4:], "-h"], **OUTPUT, env=env)
            usage = (r.stdout or r.stderr).strip()
            if usage:
                return [Entry(title=f"{page} › Usage", kind="usage", location=f"git {page[4:]} -h",
                              text=fence(usage.splitlines()), source="git")]
        return []

    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        return [e for group in ex.map(one, pages) for e in group]


def build_man(page: str, source: str) -> list[Entry]:
    raw = read_man(page)
    if raw:
        return split_man(page, raw, source)
    if page == "bash" and shutil.which("bash"):             # no man page: use bash's own help
        say("  no bash man page here; using 'help' text of the bash builtins instead")
        names = subprocess.run(["bash", "-c", "compgen -b"], **OUTPUT).stdout.split()
        out = []
        for b in dict.fromkeys(names):
            if not MAN_NAME.fullmatch(b):
                continue
            txt = subprocess.run(["bash", "-c", 'help -m -- "$1"', "bash", b],   # no shell string
                                 **OUTPUT).stdout
            if txt.strip():
                out.append(Entry(title=f"bash builtin › {b}", kind="help", location=f"bash: help {b}",
                                 text=fence(txt.splitlines()), source=source))
        return out
    die(f"no man page for '{page}' on this system.")
    return []


# --------------------------------------------------------------------------- storage

def source_id(spec: str) -> str:
    """The folder name of a source: numpy; numpy==1.26 -> numpy@1.26 (a second version, kept
    next to the latest one)."""
    name, _, version = spec.partition("==")
    name = name.split("=", 1)[0].removeprefix("pypi:")
    sid = re.sub(r"[^\w.-]+", "-", name).strip("-.").lower()
    if version and version not in ("latest", "stable"):
        sid += "@" + re.sub(r"[^\w.-]+", "-", version).strip("-.").lower()
    if not sid or sid.startswith("."):      # never "..": that would be a folder outside the cache
        die(f"'{spec}' is not a usable source name.")
    return sid


def source_dir(sid: str) -> Path:
    d = HOME / sid
    if d.resolve().parent != HOME.resolve():
        die(f"'{sid}' points outside {HOME}.")
    return d


def private_dir(d: Path) -> None:
    """Index folders are readable only by you (they decide what the tool shows and runs)."""
    for p in (HOME, d):
        p.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt" and p.stat().st_mode & 0o077:     # (Windows: the user folder's own rights)
            p.chmod(0o700)


def write_atomic(path: Path, data: bytes) -> None:
    """Write to a temporary file, then rename: a crash never leaves half a file."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


CHANGED = False                      # did this command change any index?


def save(sid: str, entries: list[Entry], meta: dict) -> None:
    global CHANGED
    CHANGED = True
    d = source_dir(sid)
    private_dir(d)
    for e in entries:
        e.title, e.kind, e.location, e.text = clean(e.title), clean(e.kind), clean(e.location), clean(e.text)
    write_atomic(d / "entries.json", json.dumps([asdict(e) for e in entries]).encode())
    write_atomic(d / "meta.json", json.dumps(meta, indent=2).encode())
    emb = d / "emb.npy"
    if emb.exists():
        emb.unlink()


def load(sid: str) -> tuple[dict, list[Entry]]:
    d = source_dir(sid)
    if d.exists():
        private_dir(d)
    if not (d / "entries.json").exists():
        die(f"'{sid}' is not indexed yet. Run: search add {sid}")
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    entries = [Entry(**{k: clean(e[k]) for k in ("title", "kind", "location", "text", "source")})
               for e in json.loads((d / "entries.json").read_text(encoding="utf-8"))]
    return meta, entries


# --------------------------------------------------------------------------- embeddings

_model = None


def pinned_dir(repo: str, revision: str) -> Path:
    return MODELS / "hub" / f"models--{repo.replace('/', '--')}" / "snapshots" / revision


# The same model files, attached to a release of this project on GitHub: `search setup`
# gets them there when Hugging Face cannot be reached (some networks block it). Each file
# is checked against the same SHA-256 either way. A changed model needs a new release tag.
MIRROR = "https://github.com/ahmad-sardar/docsearch/releases/download/models-v1/"
MAX_MODEL_FILE = 2**30
_HF_DOWN: str | None = None           # why Hugging Face failed (then the rest come from GitHub)


def sha256_of(f: Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    with open(f, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def mirror_url(repo: str, name: str) -> str:
    """Where a model file is on the GitHub release: Qwen3-Reranker-0.6B-4bit.config.json."""
    return MIRROR + f"{repo.split('/')[-1]}.{name}"


def download_checked(url: str, dest: Path, want: str) -> None:
    """Stream one file to `dest` (HTTPS only, each redirect checked), kept only if its
    SHA-256 is `want`."""
    import hashlib

    import httpx
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    for _ in range(6):
        if not safe_url(url):
            raise Failed("not-https", url, url.split(":", 1)[0] + ":")
        try:
            with http_client().stream("GET", url, timeout=60) as r:
                if r.is_redirect:
                    url = urllib.parse.urljoin(url, r.headers.get("location", ""))
                    continue
                if r.status_code >= 400:
                    kind = {401: "login", 403: "forbidden", 404: "not-found"}.get(r.status_code, "server-error")
                    raise Failed(kind, url, str(r.status_code))
                digest, size = hashlib.sha256(), 0
                length = int(r.headers.get("content-length", 0)) or None
                big = length is None or length >= 2**20            # small files are instant: no bar
                with open(tmp, "wb") as fh, Progress(f"  {dest.name}", length, "B", quiet=not big) as bar:
                    for chunk in r.iter_bytes(1 << 20):
                        size += len(chunk)
                        if size > MAX_MODEL_FILE:
                            raise Failed("too-large", url, f"{MAX_MODEL_FILE // 2**20} MB")
                        digest.update(chunk)
                        fh.write(chunk)
                        bar.update(len(chunk))
        except httpx.TransportError as e:
            tmp.unlink(missing_ok=True)
            raise connect_failure(url, e) from e
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        if digest.hexdigest() != want:
            tmp.unlink()
            raise Failed("other", url, "the file does not match its pinned SHA-256; deleted it")
        dest.unlink(missing_ok=True)
        os.replace(tmp, dest)
        return
    raise Failed("redirect", url, "too many redirects")


def fetch_pinned(repo: str, revision: str, files: dict[str, str]) -> Path:
    """Get exactly `files` of a model repository at one commit (only `search setup`, `add`
    and `embed` do this, once): from Hugging Face, else from this project's GitHub release.
    Each file's SHA-256 is checked; a file that does not match is deleted, never used.
    Files already here (copied by hand from another computer) are checked and kept."""
    global _HF_DOWN
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"           # never send your HF token
    folder = pinned_dir(repo, revision)
    hf_checked = False
    for name, want in files.items():
        if not name.endswith((".json", ".safetensors")):         # never pickle, never code
            die(f"{repo}: refusing to download {name}: only .json and .safetensors files")
        if (folder / name).exists() and sha256_of(folder / name) == want:
            continue
        if os.environ.get("DOCSEARCH_MODELS_FROM", "").lower() == "github":
            _HF_DOWN = _HF_DOWN or "skipped (DOCSEARCH_MODELS_FROM=github)"
        if _HF_DOWN is None and not hf_checked:                  # one quick look, not 5 slow retries
            hf_checked = True
            try:
                http_get_once(os.environ.get("HF_ENDPOINT", "https://huggingface.co"), timeout=10)
            except Failed as e:
                _HF_DOWN = WHY[e.kind].format(detail=e.detail)
                say(f"  Hugging Face: {_HF_DOWN}\n  getting the models from GitHub instead ({MIRROR})")
        if _HF_DOWN is None:
            try:
                from huggingface_hub import hf_hub_download
                f = Path(hf_hub_download(repo, name, revision=revision, cache_dir=str(MODELS / "hub")))
                if sha256_of(f) == want:
                    continue
                f.unlink()
                (folder / name).unlink(missing_ok=True)
                _HF_DOWN = f"{name} did not match its pinned SHA-256; deleted it"
            except Exception as e:  # noqa: BLE001 - blocked, offline, a proxy's page: try GitHub
                _HF_DOWN = str(e).splitlines()[0][:200] if str(e) else type(e).__name__
            say(f"  Hugging Face: {_HF_DOWN}\n  getting the models from GitHub instead ({MIRROR})")
        try:
            download_checked(mirror_url(repo, name), folder / name, want)
        except Failed as e:
            die(f"{repo}: could not get {name} from Hugging Face ({_HF_DOWN}) or GitHub "
                f"({WHY[e.kind].format(detail=e.detail)}). Another way: copy data/models from a "
                f"computer that has it into {MODELS}, then run search setup again.")
    return folder


def model_cached() -> bool:
    """Is the meaning model on disk?"""
    return all((pinned_dir(MODEL_NAME, MODEL_REVISION) / f).exists() for f in MODEL_FILES)


@functools.cache
def use_mlx() -> bool:
    """Run the models with MLX on the Apple GPU when it is installed (Apple-silicon Macs);
    otherwise on the processor with numpy (Windows, Linux, Intel Macs; see cpu.py).
    DOCSEARCH_BACKEND=numpy uses the processor anyway."""
    if os.environ.get("DOCSEARCH_BACKEND", "").lower() == "numpy":
        return False
    try:
        import mlx.core  # noqa: F401
        return True
    except ImportError:
        return False


def get_model(download: bool = False):
    """Load the meaning model, with no network access. Only `search setup`, `add` and
    `embed` may download it, once. Searching never contacts Hugging Face."""
    global _model
    if _model is None:
        if not model_cached():
            if not download:
                die("the meaning model is not on this computer yet. Run: search setup")
            say(f"Downloading the meaning model {MODEL_NAME} (once, about 90 MB)...")
            fetch_pinned(MODEL_NAME, MODEL_REVISION, MODEL_FILES)
        from docsearch.embedding import SentenceEncoder      # MLX or numpy, no PyTorch
        _model = SentenceEncoder(pinned_dir(MODEL_NAME, MODEL_REVISION))
    return _model


def embed_source(sid: str) -> None:
    global CHANGED
    CHANGED = True
    import numpy as np
    meta, entries = load(sid)
    texts = [f"{e.title}\n{plain(e.text)[:EMBED_CHARS]}" for e in entries]
    model = get_model(download=True)
    with Progress(f"  vectors for {sid}", len(texts)) as bar:
        vecs = model.encode(texts, batch=64, progress=bar.update)
    tmp = HOME / sid / "emb.tmp.npy"
    np.save(tmp, vecs.astype(np.float32))
    os.replace(tmp, HOME / sid / "emb.npy")
    meta["model"] = MODEL_NAME
    (HOME / sid / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- ranking

def subsequence_score(q: str, title: str) -> float:
    """fzf-style score: q must appear in order inside title. Bonus for matches at word
    starts and for consecutive matches; small penalty per skipped character."""
    t = title.lower()
    qi, end = 0, -1
    for ti, ch in enumerate(t):                 # forward pass: earliest end of a match
        if ch == q[qi]:
            qi += 1
            if qi == len(q):
                end = ti
                break
    if end < 0:
        return -1.0
    qi, start = len(q) - 1, 0
    for ti in range(end, -1, -1):              # backward pass: shortest window ending at `end`
        if t[ti] == q[qi]:
            qi -= 1
            if qi < 0:
                start = ti
                break
    score, qi, prev = 0.0, 0, -2
    for ti in range(start, end + 1):
        if qi < len(q) and t[ti] == q[qi]:
            s = 16.0
            boundary = ti == 0 or not t[ti - 1].isalnum() or (title[ti].isupper() and title[ti - 1].islower())
            if boundary:
                s += 8
            if prev == ti - 1:
                s += 4
            score += s
            prev, qi = ti, qi + 1
        else:
            score -= 1
    return score - 0.01 * len(t)              # tie-break: shorter titles first


def rrf(lists: list[tuple[str, list[int], float]], k: int = RRF_K) -> list[tuple[int, float, dict]]:
    """Reciprocal rank fusion: score(d) = sum_i w_i / (k + rank_i(d)). Uses ranks only,
    so the rankers' raw scores never need a common scale."""
    score: dict[int, float] = {}
    ranks: dict[int, dict[str, int]] = {}
    for name, lst, w in lists:
        for r, i in enumerate(lst, 1):
            score[i] = score.get(i, 0.0) + w / (k + r)
            ranks.setdefault(i, {})[name] = r
    order = sorted(score, key=lambda i: -score[i])
    return [(i, score[i], ranks[i]) for i in order]


# --------------------------------------------------------------------------- keyword index (BM25)

TOKEN = re.compile(r"[a-z0-9]+")
BM25_K1, BM25_B = 1.2, 0.75   # standard values (Robertson and Zaragoza, 2009)
TITLE_WEIGHT = 3              # a word in the title counts 3 times: it is strong evidence


def tokens(s: str) -> list[str]:
    return TOKEN.findall(s.lower())


TRIGRAM_KEEP = 5000           # titles the spelling ranker scores (see Index.rank_edit)
TYPO_EDITS = 2                # letters a misspelled API name may have wrong (Index.rank_typo)
TYPO_WEIGHT = 2.0             # its vote in the fusion (exact name: 3; chosen on the benchmark)


def trigrams(s: str) -> set[str]:
    """'svd' -> {'  s', ' sv', 'svd', 'vd '}: padded, so word starts and ends count."""
    s = f"  {s} "
    return {s[k:k + 3] for k in range(len(s) - 2)}


class FileSlices:
    """Bytes of a file by position, opening it for each read. Windows cannot delete a file
    another program holds open (a memory map does), so there the running search page holds
    none, and remove and upgrade can replace index folders under it."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def __getitem__(self, part: slice) -> bytes:
        with open(self.path, "rb") as f:
            f.seek(part.start)
            return f.read(part.stop - part.start)


def tails(sid: str, entries: list[Entry]):
    """What a running search does not keep in memory of each text (from KEEP_CHARS on), in
    one file read by position (tails.bin, offsets in tails.npy): reading one entry's whole
    text then costs microseconds. Built once per index, from the full texts in `entries`."""
    import numpy as np
    d = HOME / sid
    data_f, offs_f, src = d / "tails.bin", d / "tails.npy", d / "entries.json"
    if not (offs_f.exists() and data_f.exists() and offs_f.stat().st_mtime >= src.stat().st_mtime
            and len(np.load(offs_f, mmap_mode="r")) == len(entries) + 1):
        parts = [e.text[KEEP_CHARS:].encode("utf-8") for e in entries]
        write_atomic(data_f, b"".join(parts))
        tmp = d / "tails.tmp.npy"
        np.save(tmp, np.cumsum([0] + [len(x) for x in parts]).astype(np.int64))
        os.replace(tmp, offs_f)
    offs = np.load(offs_f)
    if not data_f.stat().st_size:
        return offs, np.zeros(0, np.uint8)
    return offs, (FileSlices(data_f) if os.name == "nt" else np.memmap(data_f, dtype=np.uint8, mode="r"))


# --------------------------------------------------------------------------- strict search

# "exact words" anywhere in the query; /regex/ as a word of its own (so cpp/vector/push stays
# an ordinary search)
STRICT = re.compile(r'"([^"]+)"|(?:(?<=\s)|^)/((?:\\.|[^/\\])+)/(?=\s|$)')


def parse_strict(q: str) -> tuple[str, list[str], list[str]]:
    """'pandas "keep=" first' -> ('pandas first', ['keep='], []): the fuzzy rest, the quoted
    phrases, the /patterns/."""
    phrases: list[str] = []
    patterns: list[str] = []

    def take(m) -> str:
        (phrases if m.group(1) is not None else patterns).append(m.group(1) if m.group(1) is not None else m.group(2))
        return " "
    rest = STRICT.sub(take, q)
    return " ".join(rest.split()), [p for p in phrases if p.strip()], patterns


def phrase_regex(p: str) -> re.Pattern:
    """A quoted phrase as a pattern: exactly these words in this order (any spacing), whole
    words at its ends (sum: not cumsum or sum_x), any case unless it has a capital letter."""
    body = r"\s+".join(re.escape(w) for w in p.split())
    if re.match(r"\w", p.strip()):
        body = r"(?<!\w)" + body
    if re.search(r"\w$", p.strip()):
        body += r"(?!\w)"
    return re.compile(body, 0 if any(c.isupper() for c in p) else re.I)


def keyword_postings(sid: str, entries: list[Entry]):
    """Inverted index of one source: word -> (entry ids, counts). Built once, then cached."""
    from collections import Counter

    import numpy as np
    f, src = HOME / sid / "bm25.npz", HOME / sid / "entries.json"
    (HOME / sid / "bm25.pkl").unlink(missing_ok=True)      # old format: pickle can run code
    if f.exists() and f.stat().st_mtime >= src.stat().st_mtime:
        with np.load(f, allow_pickle=False) as z:          # plain arrays only, no code
            words, starts = z["words"].tolist(), z["starts"]
            ids, tfs, lengths = z["ids"], z["tfs"], z["lengths"]
        return ({w: (ids[starts[k]:starts[k + 1]], tfs[starts[k]:starts[k + 1]])
                 for k, w in enumerate(words)}, lengths)
    say(f"Building the keyword index for '{sid}' (only once)...")
    post: dict[str, tuple[list[int], list[int]]] = {}
    lengths = []
    for i, e in enumerate(entries):
        toks = tokens(e.title) * TITLE_WEIGHT + tokens(plain(e.text))
        lengths.append(len(toks))
        for t, c in Counter(toks).items():
            p = post.setdefault(t, ([], []))
            p[0].append(i)
            p[1].append(c)
    data = ({t: (np.array(a, np.int32), np.array(c, np.float32)) for t, (a, c) in post.items()},
            np.array(lengths, np.float32))
    words = list(data[0])
    starts = np.cumsum([0] + [len(data[0][w][0]) for w in words])
    tmp = f.with_name("bm25.tmp.npz")
    np.savez(tmp, words=np.array(words, dtype=str), starts=starts,
             ids=np.concatenate([data[0][w][0] for w in words]) if words else np.zeros(0, np.int32),
             tfs=np.concatenate([data[0][w][1] for w in words]) if words else np.zeros(0, np.float32),
             lengths=data[1])
    os.replace(tmp, f)
    return data


PAGE_KINDS = {"doc", "label", "page", "section", "man", "help", "usage", "term"}   # prose, not API
ALIASES = {"np": "numpy", "pd": "pandas", "plt": "matplotlib.pyplot", "sp": "scipy", "tf": "tensorflow",
           "nn": "torch.nn", "F": "torch.nn.functional", "sk": "sklearn"}


def api_name(title: str) -> str:
    """'numpy.sum (function)' -> 'numpy.sum'."""
    return re.sub(r"\s+\([^)]*\)$", "", title)


def summary(e: Entry) -> str:
    """First line of prose after the signature: what a result list shows under the name."""
    text = re.sub(r"```.*?```", " ", e.text, flags=re.S)
    for line in text.splitlines():
        line = plain(line)
        if len(line) > 3 and not line.endswith(":"):
            return line[:200]
    return ""


SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def snippet(e: Entry, q: str, width: int = 170) -> str:
    """The sentence with the most query words (a query-biased snippet, as web search shows)."""
    sents = [s.strip() for s in SENTENCE_END.split(plain(e.text))[:300] if s.strip()]
    if not sents:
        return ""
    terms = set(tokens(q))
    best = max(sents, key=lambda s: len(terms & set(tokens(s))))   # ties: the earliest sentence
    if len(best) <= width:
        return best
    low = best.lower()
    hits = [low.find(t) for t in terms if t in low]
    start = max(0, min(hits) - width // 3) if hits else 0
    return ("…" if start else "") + best[start:start + width].strip() + "…"


# --------------------------------------------------------------------------- the search index

class Index:
    def __init__(self, specs: list[str], mode: str):
        import numpy as np
        self.mode = mode
        self.entries: list[Entry] = []
        self.cut: set[int] = set()           # entries whose text is shortened in memory
        self.tails: list = []                # per source: (first entry, offsets, the rest on disk)
        self.pool = cf.ThreadPoolExecutor(max_workers=1)    # the spelling ranker, see search()
        vecs, posts, lens = [], [], []
        self.labels: list[str] = []          # "numpy 2.5": the name and the docs version
        for spec in specs:
            sid = source_id(spec)
            meta, ents = load(sid)
            self.labels.append(f"{spec} {meta.get('version') or ''}".strip())
            post, ln = keyword_postings(sid, ents)       # (built from the full text, cached)
            posts.append((post, len(self.entries)))
            lens.append(ln)
            self.tails.append((len(self.entries), *tails(sid, ents)))
            for e in ents:          # memory: keep the start of each text (summaries, snippets);
                if len(e.text) > KEEP_CHARS:              # the rest is read from disk if needed
                    self.cut.add(len(self.entries))
                    e.text = e.text[:KEEP_CHARS]
                self.entries.append(e)
            if mode != "spell":
                f = HOME / sid / "emb.npy"
                if not f.exists():
                    die(f"'{sid}' has no vectors. Run: search embed {sid}")
                if meta.get("model") != MODEL_NAME:
                    die(f"'{sid}' was embedded with {meta.get('model')}, not {MODEL_NAME}. "
                        f"Run: search embed {sid}")
                vecs.append(np.load(f, allow_pickle=False))
        if not self.entries:
            die("the chosen sources have no entries.")
        # One keyword index for all chosen sources: shift each source's ids by its offset.
        merged: dict[str, list] = {}
        for post, off in posts:
            for t, (ids, tf) in post.items():
                merged.setdefault(t, []).append((ids + off, tf))
        self.post = {t: (np.concatenate([a for a, _ in v]), np.concatenate([b for _, b in v]))
                     for t, v in merged.items()}
        self.dl = np.concatenate(lens)
        self.avgdl = float(self.dl.mean()) or 1.0
        from rapidfuzz.utils import default_process
        self.titles_proc = [default_process(e.title) for e in self.entries]
        # three-letter pieces of each title -> the titles that have them (see rank_edit)
        posts_by_gram: dict[str, list[int]] = {}
        for i, t in enumerate(self.titles_proc):
            for g in trigrams(t):
                posts_by_gram.setdefault(g, []).append(i)
        self.gram_ids = {g: k for k, g in enumerate(posts_by_gram)}
        self.gram_posts = [np.array(v, np.int32) for v in posts_by_gram.values()]
        # Exact API names: "sum", "linalg.sum" and "numpy.linalg.sum" all find numpy.linalg.sum.
        self.names: dict[str, list[int]] = {}
        self.full_names: set[str] = set()
        for i, e in enumerate(self.entries):
            if e.kind in PAGE_KINDS:
                continue
            parts = re.split(r"\.|::", api_name(e.title).lower())     # numpy.sum, Vec::push
            self.full_names.add(".".join(parts))
            for k in range(len(parts)):
                self.names.setdefault(".".join(parts[k:]), []).append(i)
        self.keys_by_len: dict[int, list[str]] = {}      # API name keys by length (rank_typo)
        for k in self.names:
            self.keys_by_len.setdefault(len(k), []).append(k)
        # The list shown before you type: every entry, in the order the docs are read
        # (table of contents, then each page top to bottom; see order.py).
        from docsearch import order
        ends = [off for _, off in posts[1:]] + [len(self.entries)]
        browse = np.concatenate([order.reading_order(source_id(spec), end - off) + off
                                 for spec, (_, off), end in zip(specs, posts, ends)]).tolist()
        self.browse, prev = [], None             # Sphinx keeps a page and its first heading under
        for i in browse:                         # one title: list it once
            key = (re.sub(r" \((page|section)\)$", "", self.entries[i].title), self.entries[i].location.split("#")[0])
            if key != prev:
                self.browse.append(i)
            prev = key
        from docsearch.spelling import Speller             # misspelled words (see search)
        self.speller: Speller | None = Speller({t: len(v[0]) for t, v in self.post.items()})
        if mode != "spell":
            if use_mlx():
                import mlx.core as mx
                # on the GPU at half precision: half the memory, and the similarity is computed there
                self.emb = mx.array(np.concatenate(vecs)).astype(mx.float16)
            else:
                self.emb = np.concatenate(vecs).astype(np.float32)
            self.model = get_model()
            self.model.encode(["warm up"])               # the first search is then fast

    # Spelling: two rankers over titles ------------------------------------------
    def rank_edit(self, q: str) -> list[int]:
        """Titles close to the query in spelling (WRatio), for typos: dataframe.mrege.

        Only the TRIGRAM_KEEP titles sharing the most three-letter pieces with the query are
        scored (as Postgres's pg_trgm does), not all of them: 5 ms instead of 120. On the
        benchmark this changed nothing measurable (dev questions, and name lookups with a
        typo: MRR 0.509 exact vs 0.512, p = 0.30), and without this ranker typo'd names drop
        to 0.456. Scored on all cores (rapidfuzz spreads cdist's rows over threads, outside
        the GIL); ties: earlier first."""
        import numpy as np
        from rapidfuzz import fuzz, process
        from rapidfuzz.utils import default_process
        q = default_process(q)
        ids = [self.gram_ids[g] for g in trigrams(q) if g in self.gram_ids]
        if not ids:
            return []
        shared = np.bincount(np.concatenate([self.gram_posts[k] for k in ids]), minlength=len(self.titles_proc))
        cand = np.argpartition(-shared, min(TRIGRAM_KEEP, len(shared) - 1))[:TRIGRAM_KEEP]
        cand = np.sort(cand[shared[cand] > 0])
        s = process.cdist([self.titles_proc[i] for i in cand], [q], scorer=fuzz.WRatio, processor=None,
                          score_cutoff=45, dtype=np.float64, workers=-1)[:, 0]
        hit = np.flatnonzero(s >= 45)
        return cand[hit[np.lexsort((cand[hit], -s[hit]))]][:CANDIDATES].tolist()

    def rank_abbrev(self, q: str) -> list[int]:
        qs = re.sub(r"\s+", "", q.lower())
        if len(qs) < 3:
            return []
        # q0 [^q1]* q1 [^q2]* q2 ... : each gap stops at the next wanted letter (no backtracking blow-up)
        pat = re.compile(re.escape(qs[0]) + "".join(f"[^{re.escape(c)}]*{re.escape(c)}" for c in qs[1:]))
        hits = [i for i, e in enumerate(self.entries) if pat.search(e.title.lower())]
        if len(hits) > 5000:  # short queries match almost everything: score the shortest titles
            hits = sorted(hits, key=lambda i: len(self.entries[i].title))[:5000]
        scored = sorted(((subsequence_score(qs, self.entries[i].title), i) for i in hits), reverse=True)
        return [i for s, i in scored[:CANDIDATES] if s > 0]

    # Words: BM25 over title + full text ---------------------------------------------
    def rank_words(self, q: str) -> list[int]:
        import math

        import numpy as np
        n = len(self.entries)
        scores = np.zeros(n, np.float32)
        for t in set(tokens(q)):
            if t not in self.post:
                continue
            ids, tf = self.post[t]
            idf = math.log((n - len(ids) + 0.5) / (len(ids) + 0.5) + 1.0)   # rare words weigh more
            norm = BM25_K1 * (1 - BM25_B + BM25_B * self.dl[ids] / self.avgdl)  # long entries weigh less
            scores[ids] += idf * tf * (BM25_K1 + 1) / (tf + norm)            # repeats saturate
        hit = np.flatnonzero(scores)
        return hit[np.argsort(-scores[hit])][:CANDIDATES].tolist()

    # Meaning: embedding similarity ---------------------------------------------------
    def rank_meaning(self, q: str) -> list[int]:
        import numpy as np
        if not use_mlx():
            sims = self.emb @ self.model.encode([q])[0]     # cosine similarity (unit vectors)
            k = min(CANDIDATES, len(sims))
            top = np.argpartition(-sims, k - 1)[:k]
            return [int(i) for i in top[np.lexsort((top, -sims[top]))]]
        import mlx.core as mx
        qv = mx.array(self.model.encode([q])[0]).astype(mx.float16)
        sims = self.emb @ qv                       # cosine similarity (vectors are unit length)
        k = min(CANDIDATES, sims.shape[0])
        top = np.array(mx.argpartition(-sims, k - 1)[:k])
        s = np.array(sims[mx.array(top)].astype(mx.float32))
        return [int(i) for i in top[np.argsort(-s)]]

    @staticmethod
    def name_key(q: str) -> str | None:
        """The query as an API name key: 'np.linalg svd' -> 'numpy.linalg_svd', 'Vec::push'
        -> 'vec.push' (None if it cannot be a name)."""
        key = re.sub(r"\s+", "_", q.strip().lower()).replace("::", ".")   # read csv -> read_csv
        for short, full in ALIASES.items():
            if key.startswith(short + "."):
                key = full + key[len(short):]
                break
        return key if re.fullmatch(r"[\w.]+", key) else None

    def name_order(self, i: int):
        name = api_name(self.entries[i].title)
        return name.count("."), len(name)

    def rank_typo(self, q: str) -> list[int]:
        """API names the query misspells (dataframe.mrege, torch.nn.Lienar, Vec::psuh): at
        most TYPO_EDITS letters missing, extra, wrong or swapped, fewer for short names.
        Only when no name is spelled exactly like the query. Closest first."""
        import numpy as np
        from rapidfuzz import process
        from rapidfuzz.distance import OSA
        key = self.name_key(q)
        if key is None or key in self.names:
            return []
        most = min(TYPO_EDITS, 0 if len(key) < 4 else 1 if len(key) < 6 else 2)
        if most == 0:
            return []
        cand = [k for n in range(len(key) - most, len(key) + most + 1) for k in self.keys_by_len.get(n, [])]
        if not cand:
            return []
        d = process.cdist(cand, [key], scorer=OSA.distance, score_cutoff=most, dtype=np.int32, workers=-1)[:, 0]
        out: list[int] = []
        for _, k in sorted((int(d[j]), cand[j]) for j in np.flatnonzero(d <= most)):
            out += sorted(set(self.names[k]) - set(out), key=self.name_order)
            if len(out) >= CANDIDATES:
                break
        return out[:CANDIDATES]

    def rank_name(self, q: str) -> tuple[list[int], list[int]]:
        """(API names equal to the query, names starting with it). Short paths first,
        so 'sum' gives numpy.sum before numpy.ma.sum."""
        key = self.name_key(q)
        if key is None:
            return [], []
        exact = self.names.get(key, [])
        prefix = [i for k, ids in self.names.items() if k != key and k.startswith(key) for i in ids] \
            if len(key) >= 3 else []

        def order(i: int):
            name = api_name(self.entries[i].title)
            return name.count("."), len(name)
        return (sorted(set(exact), key=order)[:CANDIDATES],
                sorted(set(prefix) - set(exact), key=order)[:CANDIDATES])

    def search(self, q: str, limit: int = SHOW) -> list[tuple[int, float, dict]]:
        """The ranked results. If the query has words the docs never use (misspelled), the
        corrected query is searched too and the two result lists are fused: a right
        correction brings its results up, a wrong one cannot push the typed query's out
        (benchmark: eval/results-spelling.md)."""
        hits = self.search_as_typed(q, limit)
        fixed = self.correction(q)
        if fixed is None:
            return hits
        other = self.search_as_typed(fixed, limit)
        return rrf([("typed", [i for i, _, _ in hits], 1.0), ("corrected", [i for i, _, _ in other], 1.0)])[:limit]

    def correction(self, q: str) -> str | None:
        """The query with its misspelled words corrected, or None if it has none."""
        if self.speller is None or not q.strip():
            return None
        fixed = self.speller.correct(q)
        return fixed if fixed != q else None

    def search_as_typed(self, q: str, limit: int = SHOW) -> list[tuple[int, float, dict]]:
        q = q.strip()
        if not q:
            return []
        # The spelling ranker runs on the other cores (in C++, outside the GIL) while the
        # others run here; together they take about as long as it does alone.
        edit = self.pool.submit(self.rank_edit, q) if self.mode in ("spell", "hybrid") else None
        exact, prefix = self.rank_name(q)
        # An exact API name is the strongest evidence (nn.Linear -> torch.nn.Linear); a name
        # that only starts with the query (torch.nn.Linear.forward) counts much less.
        lists = [("name", exact, 3.0), ("prefix", prefix, 1.0), ("typo", self.rank_typo(q), TYPO_WEIGHT)]
        if edit is not None:
            # The two title rankers share one vote; the full-text word ranker has one vote.
            abbrev, words = self.rank_abbrev(q), self.rank_words(q)
            lists += [("edit", edit.result(), 0.5), ("abbrev", abbrev, 0.5), ("words", words, 1.0)]
        if self.mode in ("meaning", "hybrid"):
            lists.append(("meaning", self.rank_meaning(q), 1.0))
        # A page about one API object (numpy.sum's page) repeats that object: keep the object.
        return [h for h in rrf(lists) if not self.duplicate(h[0])][:limit]

    def full_text(self, i: int) -> str:
        """An entry's whole text: the start kept in memory, the rest read from its tails file."""
        e = self.entries[i]
        if i not in self.cut:
            return e.text
        import bisect
        start, offs, data = self.tails[bisect.bisect_right([t[0] for t in self.tails], i) - 1]
        k = i - start
        return e.text + bytes(data[offs[k]:offs[k + 1]]).decode("utf-8", "replace")

    def strict(self, phrases: list[str], patterns: list[str], full_text) -> list[int]:
        """Every entry that contains each quoted phrase (in its name or text) and whose name
        matches each /pattern/. The keyword index narrows the candidates first; texts kept
        only partly in memory are read in full (full_text) when their start does not match."""
        try:
            regs = [re.compile(p) for p in patterns if len(p) <= 200]
        except re.error as e:
            raise ValueError(f"not a valid /pattern/: {e}") from None
        if len(regs) != len(patterns):
            raise ValueError("a /pattern/ may be at most 200 characters")
        phr = [phrase_regex(p) for p in phrases]
        cand = None
        for p in phrases:
            for t in set(tokens(p)):
                ids = set(self.post[t][0].tolist()) if t in self.post else set()
                cand = ids if cand is None else cand & ids
        out = []
        for i in sorted(cand) if cand is not None else range(len(self.entries)):
            e = self.entries[i]
            name = api_name(e.title) if e.kind not in PAGE_KINDS else e.title
            if not all(r.search(name) for r in regs):
                continue
            if all(r.search(e.title) or r.search(e.text) for r in phr) or (
                    i in self.cut and all(r.search(e.title) or r.search(full_text(i)) for r in phr)):
                out.append(i)
        return out

    def duplicate(self, i: int) -> bool:
        e = self.entries[i]
        return e.kind in PAGE_KINDS and api_name(e.title).lower() in self.full_names


def same_project(asked: str, found: str) -> bool:
    """Is a docs site titled `found` about `asked`? numpy / "NumPy": yes; torch / "PyTorch":
    yes; click / "Welcome to Click — Click Documentation (8.1.x)": yes; mojo / "Mojo Django
    toolkit": no; max / "Maxima": no."""
    from rapidfuzz import fuzz

    def norm(s: str) -> str:
        s = re.sub(r"\b(documentation|docs|welcome to|the|user guide|manual|reference|api|stable|"
                   r"latest|v?\d+(\.\d+)*\w*)\b", " ", s.lower())
        return re.sub(r"[^a-z0-9]", "", s)
    a = norm(asked)
    for piece in [found, *re.split(r"[—–|:·()]| - ", found)]:
        f = norm(piece)
        if f and (a == f or f in (f"py{a}", f"python{a}", f"{a}py") or a in (f"py{f}", f"{f}py")
                  or fuzz.ratio(a, f) >= 88):
            return True
    return False


def confirm(question: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        say("  (not asked: no terminal to ask in. Add --yes to accept.)")
        return False
    return input(f"  {question} [y/N] ").strip().lower() in ("y", "yes")


def build_known(name: str, sid: str, plan: dict, workers: int, max_pages: int | None) -> tuple[list[Entry], dict]:
    """Docs from the known list (sources.py): one or more parts, one offline store."""
    from docsearch import importers
    parts = plan.get("parts") or [plan]
    root = plan.get("root") or parts[0].get("url")
    store = importers.Store(sid, root)
    store.reset()
    entries: list[Entry] = []
    meta = {"kind": "known", "root": root, "about": plan.get("about", ""), "version": plan.get("version", ""),
            "pages": True}
    for part in parts:
        kind = part["kind"]
        if kind == "sphinx":
            inv, _ = http_get(part["url"] + "objects.inv")
            found, extra = build_sphinx(name, part["url"], inv, workers, max_pages, store=store)
        elif kind == "website":
            found, extra = importers.build_website(name, sid, part, store, workers, max_pages)
        elif kind == "rustdoc":
            found, extra = importers.build_rustdoc(name, sid, part, store, workers, max_pages)
        else:
            die(f"unknown kind of docs: {kind}")
        entries += found
        say(f"  {kind}: {len(found)} entries")
        meta["failed_pages"] = meta.get("failed_pages", 0) + extra.get("failed_pages", 0)
        for k, v in (extra.get("failures") or {}).items():           # the causes, over all parts
            have = meta.setdefault("failures", {}).setdefault(k, {"count": 0, "example": v["example"]})
            have["count"] += v["count"]
        got, have = extra.get("version") or "", meta["version"] or ""
        if got and (not re.fullmatch(r"\d+(\.\d+)*", have) or got.startswith(have + ".")):
            meta["version"] = got                             # the real number for "stable", "3"
    if not meta["version"]:
        meta["version"] = published_version(plan)
    store.finish(workers)
    return entries, meta


def cmd_add(args) -> None:
    from docsearch import sources
    for spec in args.sources:
        t0 = time.time()
        say(f"Indexing {spec}")
        forced_pypi = spec.startswith("pypi:")
        spec_ = spec[len("pypi:"):] if forced_pypi else spec
        name, want = spec_.split("==", 1) if "==" in spec_ else (spec_, "")
        name, _, override = name.partition("=")
        sid = source_id(f"{name}=={want}" if want else name)
        if not getattr(args, "staged", False) and (HOME / sid / "meta.json").exists():
            refresh(spec, sid, args)                     # never risks the copy you have
            continue
        meta = {"name": name, "spec": spec, "created": time.strftime("%Y-%m-%d %H:%M"), "model": None}
        if override and not LOCAL_PATH.match(override) and not urllib.parse.urlparse(override).path:
            override += "/"                              # https://git-scm.com -> https://git-scm.com/
        known_as = known_site(override) if override and not LOCAL_PATH.match(override) else None
        if known_as:                                     # an address of docs we know: their profile
            say(f"  {override} is the {known_as} docs: reading them as such (search known)")
            override = ""
        plan = None if (forced_pypi or override) else sources.resolve(known_as or name, want)
        if plan and not want and re.fullmatch(r"[\d.]+", sources.KNOWN[name].get("version", "")):
            plan = sources.resolve(name, published_version(plan) or "")    # the newest release
        try:
            if override and LOCAL_PATH.match(override):  # docs you downloaded yourself
                from docsearch import importers
                entries, extra = importers.build_local(name, sid, Path(override), args.workers)
                meta.update(extra)
            elif plan is not None:                       # a language or toolkit we know
                say(f"  {plan.get('about', name)}")
                entries, extra = build_known(name, sid, plan, args.workers, args.max_pages)
                meta.update(extra)
            elif spec == "git-man":                      # the git manual pages on this Mac
                entries = build_git(args.workers)
                meta.update(kind="man", root="man pages")
            elif spec == "bash":
                entries = build_man("bash", "bash")
                meta.update(kind="man", root="man bash")
            elif spec.startswith("man:"):
                if not MAN_NAME.fullmatch(spec[4:]):
                    say(f"  '{spec[4:]}' is not a man page name.")
                    continue
                entries = build_man(spec[4:], spec)
                meta.update(kind="man", root=f"man {spec[4:]}")
            else:
                if not override and not forced_pypi and name in sys.stdlib_module_names:
                    say(f"  '{name}' is part of Python's standard library; its docs are in the "
                        f"Python docs: search add python")
                    say(f"  (For a PyPI package of that name: search add pypi:{name})")
                    continue
                found = find_docs([override] if override else pypi_candidates(name))
                if found and want:
                    current_root = found[1]
                    found = find_version(current_root, want)
                    if not found:
                        say(f"  Could not find docs for {name} {want} next to the current ones.")
                        hosted = hosted_versions(current_root)
                        if hosted:
                            say(f"  Versions with docs there: {', '.join(hosted)}")
                        say(f"  Find the docs URL of that version and run: search add {name}=https://.../")
                        continue
                if not found and override:               # any other docs site: read it as a website
                    if not confirm(f"No Sphinx or MkDocs index at {override}. Read it as a website "
                                   f"(pages under that address)?", args.yes):
                        continue
                    plan = {"kind": "website", "root": override, "start": override, "prefix": override}
                    entries, extra = build_known(name, sid, plan, args.workers, args.max_pages)
                    meta.update(extra)
                    found = None
                elif not found:
                    say(f"  Could not find Sphinx or MkDocs docs for '{name}'.")
                    for host, why in DEAD_HOSTS.items():
                        say(f"  {host}: {WHY[why.kind].format(detail=why.detail)}")
                        say(f"  {NEXT.get(why.kind, '')}".rstrip())
                    say(f"  If you know the docs URL, run: search add {name}=https://.../")
                    known = ", ".join(sorted(sources.KNOWN))
                    say(f"  Languages and toolkits that need no PyPI package: {known}")
                    continue
                if found:
                    kind, root, data = found
                    project = parse_objects_inv(data)[0] if kind == "sphinx" else page_title(root)
                    say(f"  found the {kind} docs of “{project}” at {root}")
                    # the guards against name overlap: docs of another project with a similar
                    # name, or a docs address we only guessed (NAME.readthedocs.io)
                    guessed = urllib.parse.urlparse(root).netloc in GUESSED
                    if not override and (guessed or not same_project(name, project)):
                        summary = (PYPI_INFO.get(name) or {}).get("summary") or "(no description)"
                        say(f"  PyPI describes '{name}' as: {summary}")
                        if guessed:
                            say(f"  PyPI does not list these docs; {root} was only a guess, and "
                                f"another project may live there.")
                        else:
                            say(f"  These docs are titled “{project}”, which does not look like '{name}'.")
                        if not confirm(f"Index “{project}” at {root} as '{name}'?", args.yes):
                            say(f"  Skipped. For other docs: search add {name}=https://...  "
                                f"(or see: search known)")
                            continue
                    if want and kind == "sphinx":
                        got = parse_objects_inv(data)[1]
                        if not got.startswith(want.lstrip("v")):
                            say(f"  Note: you asked for {want}, these docs say version {got}.")
                    if kind == "sphinx":
                        from docsearch.importers import Store
                        store = Store(sid, root)
                        store.reset()
                        entries, extra = build_sphinx(name, root, data, args.workers, args.max_pages, store=store)
                        store.finish(args.workers)
                    else:
                        entries, extra = build_mkdocs(name, root, data)
                    meta.update(kind=kind, root=root, **extra)
        except urllib.error.URLError as e:
            kind = e.kind if isinstance(e, Failed) else "other"
            say(f"  Could not download: {getattr(e, 'reason', e)}")
            if kind == "certificate" and "local issuer" in str(e):    # this Mac's Python, not the site
                say("  Python on this computer cannot check certificates. Fix: cd ~/tools && uv add truststore")
            else:
                say(f"  {NEXT.get(kind, NEXT['other'])}")
            say(f"  {LOCAL_TIP.format(name=name)}")
            continue
        if not entries and meta.get("failures") and str(meta.get("root", "")).startswith("http"):
            entries, extra = try_alternatives(name, sid, meta, args)
            meta.update(extra)
        if not entries:
            say(f"  No entries for '{spec}'. Nothing saved.")
            causes = sorted((meta.get("failures") or {}).items(), key=lambda kv: -kv[1]["count"])
            if causes:
                kind, c = causes[0]
                say(f"  Why: {describe(kind)} ({c['count']} pages, e.g. {c['example']})")
                say(f"  {NEXT.get(kind.partition(':')[0], NEXT['other'])}")
            say(f"  {LOCAL_TIP.format(name=name)}")
            continue
        if sid != source_id(name):                  # a second version: its entries say which
            for e in entries:
                e.source = sid
        meta["count"] = len(entries)
        if str(meta.get("root", "")).startswith("http") and meta.get("kind") != "local":
            from docsearch import order
            meta["nav"] = order.fetch_nav(meta)        # the docs' sidebar: their reading order
        save(sid, entries, meta)
        say(f"  saved {len(entries)} entries in {time.time() - t0:.0f} s")
        if not args.no_embed:
            embed_source(sid)
        failed = int(meta.get("failed_pages") or 0)
        if failed and failed > 0.05 * (failed + stored_pages(sid)) and not getattr(args, "staged", False):
            say(f"  Note: {failed} pages could not be downloaded (the site may be busy or blocking); "
                f"saved the rest. To try again later: search upgrade {name} --force")
        if getattr(args, "record", True):
            remember(spec)


# NAME=/path, ~/path, ./path, and on Windows C:\path, .\path, \\server\share: a local copy
LOCAL_PATH = re.compile(r"^(/|~|\.{1,2}[/\\]|[A-Za-z]:[/\\]|\\\\)")
NEXT = {
    "dns": "Check the address; if it is right, check this computer's internet connection.",
    "offline": "Connect to the internet and run the same command again.",
    "refused": "The site is not answering. Try again later.",
    "timeout": "The site is slow or overloaded. Try again later, or more gently: --workers 2",
    "dropped": "The site is slow or overloaded. Try again later, or more gently: --workers 2",
    "rate-limited": "The site limits how fast it may be read. Try again later, more gently: --workers 2",
    "server-error": "The site has a problem of its own. Try again later.",
    "certificate": "The site's certificate is broken; docsearch will not download from it.",
    "bot-check": "The site does not allow programs to read it.",
    "forbidden": "The site does not allow programs to read these pages.",
    "login": "These docs need a login.",
    "robots": "The site asks programs not to read these pages, and docsearch respects that.",
    "not-found": "The address is wrong or the docs moved: find their current address and run "
                 "search add NAME=https://.../",
    "gone": "The docs are no longer there: find their current address.",
    "too-large": "A page is larger than the 50 MB limit.",
    "empty": "Such sites often publish their docs for programs too (llms.txt; tried above) or as a download.",
    "other": "",
}
LOCAL_TIP = ("Another way, which always works: download the docs yourself (many projects offer an HTML "
             ".zip: look for 'Download' or 'Offline'; or save the pages from your browser), then: "
             "search add {name}=/path/to/folder-or.zip")


def try_alternatives(name: str, sid: str, meta: dict, args) -> tuple[list[Entry], dict]:
    """When the pages could not be read one way, the other official ways a site offers:
    its llms.txt (a list of its pages for programs) and its sitemap."""
    from docsearch import importers
    root = meta["root"]
    causes = meta.get("failures") or {}
    if causes and all(k.partition(":")[0] in ("dns", "offline", "certificate", "bot-check", "login") for k in causes):
        return [], {}                                  # the same site: no other way in
    origin = "{0.scheme}://{0.netloc}/".format(urllib.parse.urlparse(root))
    tries = dict.fromkeys([(("llms.txt", "llms", urllib.parse.urljoin(root, "llms.txt"))),
                           ("llms.txt", "llms", origin + "llms.txt"), ("sitemap", "sitemap", origin + "sitemap.xml")])
    for label, key, url in tries:
        try:
            data, _ = http_get(url, timeout=15)
        except urllib.error.URLError as e:
            say(f"  Alternative: {url}: {getattr(e, 'reason', e)}")
            continue
        if key == "sitemap" and b"<urlset" not in data[:4096] and b"<sitemapindex" not in data[:4096]:
            continue
        say(f"  Alternative: the site's {label} at {url}")
        plan = {"kind": "website", "root": root, "prefix": root, key: url}
        if key == "llms":                        # its pages may live on a sister site of the same
            org = organization(urllib.parse.urlparse(url).netloc)        # organization only
            hosts = sorted({h for h in (urllib.parse.urlparse(u).netloc for u in
                                        importers.MD_LINK.findall(data.decode("utf-8", "replace")))
                            if h and organization(h) == org})
            plan["prefix"] = [f"https://{h}/" for h in hosts] or [origin]
            plan["root"] = plan["prefix"][0] if len(plan["prefix"]) == 1 else "https://"
        store = importers.Store(sid, root)
        store.reset()
        entries, extra = importers.build_website(name, sid, plan, store, args.workers, args.max_pages)
        store.finish(args.workers)
        if entries:
            return entries, {**extra, "kind": "website", "root": plan["root"], "pages": True, "via": url}
    return [], {}


def known_site(url: str) -> str | None:
    """The known docs (sources.py) an address belongs to: the one whose start or prefix
    is the longest beginning of it, or the only one on its host."""
    from docsearch import sources
    best, length, on_host = None, 0, []
    host = urllib.parse.urlparse(url).netloc
    for key, entry in sources.KNOWN.items():
        plan = sources.resolve(key, "")
        addrs = []
        for part in plan.get("parts") or [plan]:
            for k in ("prefix", "start", "url", "root"):
                v = part.get(k)
                addrs += [v] if isinstance(v, str) else list(v or [])
        addrs = [a for a in addrs + [plan.get("root") or ""] if a and urllib.parse.urlparse(a).netloc]
        if any(urllib.parse.urlparse(a).netloc == host for a in addrs):
            on_host.append(key)
        for a in addrs:
            if a and url.startswith(a.rstrip("/")) and len(a) > length:
                best, length = key, len(a)
    return best or (on_host[0] if len(on_host) == 1 else None)


def organization(host: str) -> str:
    """platform.openai.com -> openai.com: who runs a site (the last two parts of its name)."""
    return ".".join(host.lower().split(":")[0].split(".")[-2:])


def page_title(url: str) -> str:
    """The <title> of a page (how a docs site names itself)."""
    try:
        soup = make_soup(get_page(url))
        return (soup.title.get_text(" ", strip=True) if soup.title else "") or url
    except Exception:  # noqa: BLE001
        return url


def forget(sid: str) -> bool:
    """Remove a source: its index, and its line in packages.toml (so sync does not bring it
    back)."""
    global CHANGED
    CHANGED = True
    d = source_dir(sid)
    gone = d.exists()
    if gone:
        shutil.rmtree(d)
    if CONFIG.exists():
        base, _, version = sid.partition("@")
        lines = CONFIG.read_text(encoding="utf-8").splitlines(keepends=True)
        out = []
        for ln in lines:
            m = re.match(rf'(\s*"?{re.escape(base)}"?\s*=\s*)(.*?)(\s*(#.*)?)$', ln, re.I | re.S)
            if not m:
                out.append(ln)
                continue
            if not version:                              # the latest docs: the whole line goes
                gone = True
                continue
            values = re.findall(r'"([^"]*)"', m.group(2))
            keep = [v for v in values if v.lower() != version]
            if len(keep) != len(values):
                gone = True
                if keep:
                    out.append(m.group(1) + ("[" + ", ".join(f'"{v}"' for v in keep) + "]" if len(keep) > 1
                                             else f'"{keep[0]}"') + "\n")
                continue
            out.append(ln)
        if out != lines:
            write_atomic(CONFIG, "".join(out).encode())
    return gone


def cmd_known(_args) -> None:
    from docsearch import sources
    indexed = {d.name for d in HOME.iterdir()} if HOME.exists() else set()
    for name, e in sources.KNOWN.items():
        mark = "indexed" if name in indexed else ""
        print(f"{name:12} {e.get('about', ''):70} {mark}")
    print("\nAdd one with: search add NAME   (or NAME==VERSION, e.g. python==3.12)")


CONFIG_TEMPLATE = """\
# Documentation that `search sync` keeps indexed. Edit this file, then run: search sync
# (This file lives in the project folder, next to pyproject.toml.)
#
#   name = "latest"                          the current docs (PyPI finds the site)
#   name = "1.26"                            the docs of one version
#   name = { url = "https://.../" }          the docs at this address (HTTPS)
#   name = { version = "2.1", embed = false }   no meaning search (no model, faster)
#   name = ["latest", "1.26"]                   several versions, side by side

[packages]

[man]
pages = []               # man pages (mac and linux): "git" (all git manual pages), "bash", "tmux"...
"""

PKG_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")
VERSION = re.compile(r"v?[0-9A-Za-z][0-9A-Za-z.+_-]{0,49}")


def read_config() -> list[tuple[str, bool]]:
    """packages.toml -> [(spec, embed)], with every value checked."""
    import tomllib
    try:
        cfg = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        die(f"{CONFIG}: {e}")
    out = []
    items = []
    for name, val in (cfg.get("packages") or {}).items():     # numpy = ["latest", "1.26"]
        items += [(name, v) for v in val] if isinstance(val, list) else [(name, val)]
    for name, val in items:
        if not PKG_NAME.fullmatch(name):
            die(f"{CONFIG}: '{name}' is not a package name.")
        opts = val if isinstance(val, dict) else {"version": val}
        unknown = set(opts) - {"version", "url", "path", "embed"}
        if unknown:
            die(f"{CONFIG}: [{name}] has unknown keys: {', '.join(sorted(unknown))}")
        version, url = str(opts.get("version", "latest")), opts.get("url")
        if opts.get("path"):                                 # docs you downloaded yourself
            out.append((f"{name}={opts['path']}", bool(opts.get("embed", True))))
            continue
        if url:
            if not isinstance(url, str) or not safe_url(url):
                die(f"{CONFIG}: [{name}] url must be an https:// address.")
            spec = f"{name}={url if url.endswith('/') else url + '/'}"
        elif version in ("latest", "stable", ""):
            spec = name
        elif VERSION.fullmatch(version):
            spec = f"{name}=={version}"
        else:
            die(f"{CONFIG}: [{name}] '{version}' is not a version.")
        out.append((spec, bool(opts.get("embed", True))))
    for page in (cfg.get("man") or {}).get("pages", []):
        if not isinstance(page, str) or not MAN_NAME.fullmatch(page):
            die(f"{CONFIG}: '{page}' is not a man page name.")
        out.append(("git-man" if page == "git" else page if page == "bash" else f"man:{page}", True))
    return out


def cmd_sync(args) -> None:
    if not CONFIG.exists():
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        if EXAMPLE.exists():
            shutil.copy(EXAMPLE, CONFIG)
        else:
            CONFIG.write_text(CONFIG_TEMPLATE, encoding="utf-8")
        print(f"Created {CONFIG}\nList your packages there, then run: search sync")
        return
    wanted = read_config()
    keep = set()
    for spec, embed in wanted:
        sid = source_id(spec)
        keep.add(sid)
        meta_f = HOME / sid / "meta.json"
        meta = json.loads(meta_f.read_text(encoding="utf-8")) if meta_f.exists() else {}
        meta.setdefault("spec", meta.get("name"))           # indexes made before sync existed
        ready = meta.get("spec") == spec and (not embed or (HOME / sid / "emb.npy").exists())
        if ready and not args.force:
            say(f"{spec}: up to date ({meta.get('version') or 'no version'})")
            if "nav" not in meta and str(meta.get("root", "")).startswith("http") and meta.get("kind") != "local":
                from docsearch import order                # docs added before the order was kept
                meta["nav"] = order.fetch_nav(meta)
                write_atomic(meta_f, json.dumps(meta, indent=2).encode())
                (HOME / sid / "order.npy").unlink(missing_ok=True)
            continue
        if meta.get("spec") == spec and embed and not args.force:   # only the vectors are missing
            embed_source(sid)
            continue
        cmd_add(argparse.Namespace(sources=[spec], workers=args.workers, max_pages=None, no_embed=not embed,
                                   yes=False, accept_partial=args.accept_partial))
    import tomllib                                       # saved pages ([saved] in packages.toml)
    for name, urls in (tomllib.loads(CONFIG.read_text(encoding="utf-8")).get("saved") or {}).items():
        sid = source_id(name)
        keep.add(sid)
        have = set(json.loads((HOME / sid / "meta.json").read_text(encoding="utf-8")).get("urls", [])) \
            if (HOME / sid / "meta.json").exists() else set()
        missing = [u for u in urls if isinstance(u, str) and safe_url(u) and u not in have]
        if missing:
            cmd_save(argparse.Namespace(urls=missing, to=name, series=False, workers=args.workers))
        else:
            say(f"{name}: up to date ({len(have)} saved pages)")
    extra = sorted(d.name for d in HOME.iterdir() if (d / "meta.json").exists() and d.name not in keep) \
        if HOME.exists() else []
    if extra and args.prune:
        cmd_remove(argparse.Namespace(sources=extra))
    elif extra:
        say(f"Indexed but not in {CONFIG.name}: {', '.join(extra)}  (search sync --prune removes them)")


def cmd_list(_args) -> None:
    if not HOME.exists() or not any(HOME.iterdir()):
        print("Nothing indexed yet. Start with: search add git")
        return
    for d in sorted(HOME.iterdir()):
        f = d / "meta.json"
        if f.exists():
            m = json.loads(f.read_text(encoding="utf-8"))
            vec = "vectors ready" if (d / "emb.npy").exists() else "no vectors"
            if m.get("failed_pages"):
                vec += f", {m['failed_pages']} pages missing"
            ver = m.get("version") or "-"
            print(f"{d.name:<14} {ver:<10} {m.get('count', 0):>7} entries   {m.get('kind', ''):<7} "
                  f"{vec:<14} {m.get('root', '')}   (indexed {m.get('created', '?')})")


def cmd_remove(args) -> None:
    for spec in args.sources:
        sid = source_id(spec)
        print(f"removed {sid} (index and packages.toml)" if forget(sid) else f"'{spec}' is not indexed")


def cmd_embed(args) -> None:
    for spec in args.sources:
        embed_source(source_id(spec))


# --------------------------------------------------------------------------- versions

STAGING = DATA / "staging"


def published_version(plan: dict) -> str:
    """The version number a docs site publishes now (sources.py: version_from), or ""."""
    where = plan.get("version_from")
    if not where:
        return ""
    try:
        data, final = http_get(where[0], timeout=15)
    except Exception:  # noqa: BLE001
        return ""
    m = re.search(where[1], final if where[2:] == ["address"] else data.decode("utf-8", "replace"))
    return m.group(1) if m else ""


def current_version(meta: dict) -> str:
    """The version of these docs online now, read without downloading them ("" if the
    site does not say: then only downloading them again can tell)."""
    from docsearch import sources
    plan = sources.resolve(meta.get("name", "")) if meta.get("kind") == "known" else None
    if plan and plan.get("version_from"):
        return published_version(plan)
    inv = meta.get("root") if meta.get("kind") == "sphinx" else \
        plan.get("url") if plan and plan.get("kind") == "sphinx" else None
    if not inv:
        return ""
    try:
        return parse_objects_inv(http_get(inv + "objects.inv", timeout=15)[0])[1]
    except Exception:  # noqa: BLE001
        return ""


def indexed() -> list[str]:
    return sorted(d.name for d in HOME.iterdir() if (d / "meta.json").exists()) if HOME.exists() else []


def stored_pages(sid: str) -> int:
    d = HOME / sid / "pages"
    return sum(1 for f in d.rglob("*.gz") if "_images" not in f.parts) if d.exists() else 0


def incomplete(new: Path, old: dict | None) -> str | None:
    """Why a fresh download should not replace the copy you have, if it should not: more
    than 5% of its pages failed, or (same docs, `old`) it has under 70% of their entries."""
    meta = json.loads((new / "meta.json").read_text(encoding="utf-8"))
    failed = int(meta.get("failed_pages") or 0)
    pages = sum(1 for f in (new / "pages").rglob("*.gz") if "_images" not in f.parts) if (new / "pages").exists() else 0
    if failed > 0.05 * (failed + pages):
        return f"{failed} of {failed + pages} pages failed"
    if old and meta.get("count", 0) < 0.7 * old.get("count", 0):
        return f"{meta.get('count', 0)} entries; the copy you have has {old['count']}"
    return None


def refresh(spec: str, sid: str, args) -> bool:
    """Download docs you already have again (sync, add) without risking them: built in
    data/staging, swapped in only when complete enough; otherwise your copy stays."""
    old = json.loads((HOME / sid / "meta.json").read_text(encoding="utf-8"))
    say(f"  {sid}: downloading again; the copy you have stays in use until the new one is complete")
    d = build_staged(spec, args)
    if d is None:
        say(f"  {sid}: the download failed; your copy is kept.")
        return False
    why = incomplete(d, old)
    if why and not getattr(args, "accept_partial", False):
        shutil.rmtree(STAGING, ignore_errors=True)
        say(f"  {sid}: the new download looks incomplete ({why}); your copy is kept. "
            f"Try again later, or take it anyway with --accept-partial.")
        return False
    install_staged(d, [])
    if getattr(args, "record", True):
        remember(spec)
    return True


def build_staged(spec: str, args) -> Path | None:
    """Download and index `spec` into data/staging, leaving the index in use untouched.
    Returns the finished folder, or None if that failed."""
    global HOME
    if STAGING.exists():
        shutil.rmtree(STAGING)
    real, HOME = HOME, STAGING
    try:
        cmd_add(argparse.Namespace(sources=[spec], workers=args.workers, max_pages=None,
                                   no_embed=False, yes=getattr(args, "yes", False), record=False, staged=True))
    finally:
        HOME = real
    d = STAGING / source_id(spec)
    return d if (d / "meta.json").exists() and (d / "emb.npy").exists() else None


def install_staged(d: Path, replace: list[str]) -> None:
    """Put finished docs into the index, in place of `replace` (the versions they replace)."""
    global CHANGED
    CHANGED = True
    for sid in replace:
        if source_dir(sid).exists():
            shutil.rmtree(source_dir(sid))
    target = source_dir(d.name)
    if target.exists():
        shutil.rmtree(target)
    os.replace(d, target)
    shutil.rmtree(STAGING, ignore_errors=True)


def cmd_save(args) -> None:
    """search save URL... [--to NAME] [--series]: tutorials and articles you like, kept to read
    and search offline, in a collection (NAME, "tutorials" by default). Earlier saves stay;
    saving a page again replaces its copy."""
    from docsearch import importers
    name, now = args.to, time.strftime("%Y-%m-%d %H:%M")
    sid = source_id(name)
    for u in args.urls:
        if not safe_url(u):
            die(f"'{u}' is not an https:// address.")
    if (HOME / sid / "meta.json").exists():
        meta, old = load(sid)
        if meta.get("kind") != "saved":
            die(f"'{name}' holds docs, not saved pages; choose another collection: --to NAME")
    else:
        meta, old = {"name": name, "spec": name, "kind": "saved", "root": "https://", "pages": True,
                     "urls": [], "created": now, "model": None, "about": "pages you saved"}, []
    say(f"Saving {len(args.urls)} page{'s' if len(args.urls) > 1 else ''} to '{name}'"
        + (" (and the parts that follow)" if args.series else ""))
    new, fails = importers.save_pages(name, sid, args.urls, args.workers, args.series)
    if fails:
        fails.report()
        if not new:
            kind = next(iter(fails.by_kind)).partition(":")[0]
            say(f"  {NEXT.get(kind, NEXT['other'])}".rstrip())
    if not new:
        say("  Nothing saved.")
        return
    pages = [e.location for e in new if "#" not in e.location]
    for e in new:
        e.source = name
    kept = [e for e in old if e.location.split("#")[0] not in set(pages)]
    meta.update(urls=list(dict.fromkeys(meta.get("urls", []) + pages)), updated=now, count=len(kept) + len(new))
    meta["nav"] = meta["urls"]                       # read in the order you saved them
    save(sid, kept + new, meta)
    for e in new:
        if "#" not in e.location:
            say(f"  saved: {e.title}  ({e.location})")
    embed_source(sid)
    config_set(name, meta["urls"], table="saved")


def windows_command() -> None:
    """Windows: the search command for every new terminal. A copy of .venv's search.exe
    goes in bin\\ (a folder of its own: putting .venv\\Scripts on the PATH would bring its
    python.exe along), and bin\\ goes first on your user PATH. Says so if another program
    called search would still come first (programs installed for all users come first)."""
    import ctypes
    import winreg
    src, bin_dir = Path(sys.executable).with_name("search.exe"), ROOT / "bin"
    if not src.exists():
        return
    bin_dir.mkdir(exist_ok=True)
    dest = bin_dir / "search.exe"
    if not dest.exists() or sha256_of(dest) != sha256_of(src):
        try:
            shutil.copy2(src, dest)
        except PermissionError:                  # it is the one running this setup
            pass
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
        try:
            user, kind = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            user, kind = "", winreg.REG_EXPAND_SZ
        parts = [p for p in user.split(";") if p]
        if not any(os.path.normcase(os.path.expandvars(p).rstrip("\\")) == os.path.normcase(str(bin_dir))
                   for p in parts):
            user = ";".join([str(bin_dir)] + parts)
            winreg.SetValueEx(key, "Path", 0, kind, user)
            ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x1A, 0, "Environment", 2, 5000, None)  # tell Windows
            say(f"Added {bin_dir} to your PATH: the search command works in new terminals.")
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                        r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment") as key:
        machine = winreg.QueryValueEx(key, "Path")[0]
    first = shutil.which("search", path=os.path.expandvars(f"{machine};{user}"))
    if first and os.path.normcase(str(Path(first).parent)) != os.path.normcase(str(bin_dir)):
        say(f"Note: another program called search comes first on your PATH: {first}\n"
            f"  Run docsearch as {dest}, or remove that folder from your PATH.")


def cmd_setup(args) -> None:
    """A new copy of the project: the search command (Windows), the two models (fixed
    commits, checked), then the docs your packages.toml lists: none in a new copy, you add
    what you want. Online, once; searching never downloads."""
    from docsearch import rerank
    if os.name == "nt":
        windows_command()
    if not CONFIG.exists():
        shutil.copy(EXAMPLE, CONFIG)
        say(f"Created {CONFIG.name} from {EXAMPLE.name}: edit it any time to choose your docs.")
    if model_cached():
        say(f"meaning model: already here ({MODEL_NAME})")
    else:
        get_model(download=True)
    if rerank.model_dir():
        say(f"AI model: already here ({rerank.MODEL})")
    else:
        say(f"Downloading the AI model {rerank.MODEL} (once, about 330 MB)...")
        rerank.download()
    import tomllib
    if not read_config() and not tomllib.loads(CONFIG.read_text(encoding="utf-8")).get("saved"):
        say("Ready. Now add the docs you want, e.g.: search add numpy pandas rust\n"
            "  (search known: languages and toolkits by name; any PyPI package or docs site works)")
        return
    cmd_sync(argparse.Namespace(force=False, prune=False, workers=args.workers, accept_partial=False))


def cmd_upgrade(args) -> None:
    """search upgrade [NAME[==VERSION]...] and search downgrade NAME==VERSION: replace a
    package's docs with the newest (or the given) version. The new docs are downloaded
    first; the old ones are deleted only when the new ones are complete."""
    from docsearch import sources
    named = bool(args.sources)
    specs = args.sources or [s for s in indexed() if "@" not in s]     # pinned ones stay
    for spec in specs:
        forced = spec.startswith("pypi:")
        name, _, want = spec.removeprefix("pypi:").partition("==")
        base = source_id(name)
        have = [s for s in indexed() if s.split("@")[0] == base]
        if args.cmd == "downgrade" and not want:
            say(f"{name}: say which version, e.g. search downgrade {name}==1.2")
            continue
        known = sources.KNOWN.get(name) if not forced else None
        if want and known is not None and "{version}" not in json.dumps(known):
            say(f"{name}: these docs only exist as the current version (no {want}).")
            continue
        if not have:
            say(f"{name}: not indexed. Add it with: search add {spec}")
            continue
        meta = json.loads((HOME / (base if base in have else have[0]) / "meta.json").read_text(encoding="utf-8"))
        old = ", ".join(f"{s} ({json.loads((HOME / s / 'meta.json').read_text(encoding='utf-8')).get('version') or 'no version'})"
                        for s in have)
        if not want:
            now = current_version(meta) if base in have else ""     # a pinned version's site is not the newest
            if have == [base] and now and now == meta.get("version") and not args.force:
                say(f"{name}: up to date ({now})")
                continue
            if not now and not named:
                say(f"{name}: the site does not publish a version number (downloaded "
                    f"{meta.get('created', '?')[:10]}). To download it again: search upgrade {name}")
                continue
            build = meta.get("spec") if base in have and meta.get("spec") else name
            say(f"{name}: {old} -> {now or 'the newest docs'}")
        else:
            build = f"{'pypi:' if forced or str(meta.get('spec', '')).startswith('pypi:') else ''}{name}=={want}"
            say(f"{name}: {old} -> {want}")
        d = build_staged(build, args)
        if d is None:
            say(f"  {name}: the new docs could not be downloaded; the old ones are kept.")
            continue
        same = d.name in have
        why = incomplete(d, json.loads((HOME / d.name / "meta.json").read_text(encoding="utf-8")) if same else None)
        if why and not args.accept_partial:
            shutil.rmtree(STAGING, ignore_errors=True)
            say(f"  {name}: the new download looks incomplete ({why}); the old docs are kept. "
                f"Try again later, or take it anyway with --accept-partial.")
            continue
        install_staged(d, [s for s in have if s != d.name])
        config_set(name, want or "latest")
        new = json.loads((HOME / d.name / "meta.json").read_text(encoding="utf-8")).get("version") or "no version number"
        say(f"  {name}: now {d.name} ({new})")


# --------------------------------------------------------------------------- packages.toml

def config_values(name: str):
    import tomllib
    if not CONFIG.exists():
        return None
    try:
        return (tomllib.loads(CONFIG.read_text(encoding="utf-8")).get("packages") or {}).get(name)
    except tomllib.TOMLDecodeError:
        return None


def toml_value(v) -> str:
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{k} = {toml_value(x)}" for k, x in v.items()) + " }"
    if isinstance(v, list):
        return toml_value(v[0]) if len(v) == 1 else "[" + ", ".join(toml_value(x) for x in v) + "]"
    if isinstance(v, bool):
        return "true" if v else "false"
    return json.dumps(str(v))


def config_set(name: str, value, table: str = "packages") -> None:
    """Set name's line in a table of packages.toml ([packages], or [saved] for collections),
    keeping its comment; or add it at the end of that table (made if missing)."""
    if not CONFIG.exists():
        CONFIG.write_text(CONFIG_TEMPLATE.split("[packages]")[0] + "[packages]\n", encoding="utf-8")
    old = config_values(name) if table == "packages" else None
    if isinstance(old, dict) and isinstance(value, str):         # { embed = false }: keep it
        value = {k: v for k, v in old.items() if k != "version"} | ({} if value == "latest" else {"version": value})
        value = value or "latest"
    lines = CONFIG.read_text(encoding="utf-8").splitlines(keepends=True)
    key = re.compile(rf'(\s*"?{re.escape(name)}"?\s*=\s*)(.*?)(\s*#.*)?$', re.I | re.S)
    shown = json.dumps(value) if isinstance(value, list) and table != "packages" else toml_value(value)
    current, end, done, has_table = None, None, False, False
    for k, ln in enumerate(lines):
        head = re.match(r"\s*\[([^\]]+)\]", ln)
        if head:
            current = head.group(1).strip()
            has_table = has_table or current == table
            if current == table:
                end = k
            continue
        if current == table:
            if ln.strip():
                end = k
            m = key.match(ln)
            if m and not done:
                lines[k] = f"{m.group(1)}{shown}{(m.group(3) or '').rstrip()}\n"
                done = True
    key_text = name if re.fullmatch(r"[A-Za-z0-9_-]+", name) else json.dumps(name)   # c++_x -> "c++_x"
    if not done and has_table:
        lines.insert(end + 1, f"{key_text} = {shown}\n")
    elif not done:
        lines += [("\n" if lines and lines[-1].strip() else ""), f"[{table}]\n", f"{key_text} = {shown}\n"]
    text = "".join(lines)
    if text != CONFIG.read_text(encoding="utf-8"):
        write_atomic(CONFIG, text.encode())


def remember(spec: str) -> None:
    """After `search add`: list the new docs in packages.toml, so `search sync` keeps them
    (and a copy of the project on another computer gets them too)."""
    import tomllib
    if spec.startswith("pypi:"):
        say(f"  (not added to {CONFIG.name}: list it there by hand if you want sync to keep it)")
        return
    if spec in ("git-man", "bash") or spec.startswith("man:"):
        page = "git" if spec == "git-man" else spec.removeprefix("man:")
        cfg = tomllib.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}
        pages = (cfg.get("man") or {}).get("pages", [])
        if page not in pages and CONFIG.exists():
            text = CONFIG.read_text(encoding="utf-8")
            listed = "[" + ", ".join(json.dumps(x) for x in pages + [page]) + "]"
            new = re.sub(r"(?m)^(\s*pages\s*=\s*)\[[^\]]*\]", lambda m: m.group(1) + listed, text, count=1)
            if new != text:
                write_atomic(CONFIG, new.encode())
        return
    name, _, want = spec.partition("==")
    name, _, url = name.partition("=")
    old = config_values(name)
    if url:
        if old is None:
            config_set(name, {"path": url} if LOCAL_PATH.match(url) else {"url": url})
        return
    want = want or "latest"
    if old is None:
        config_set(name, want)
    elif isinstance(old, (str, list)):
        vals = [old] if isinstance(old, str) else list(old)
        if want not in vals:
            config_set(name, vals + [want])


COMMANDS = {"add", "sync", "list", "remove", "embed", "serve", "stop", "known", "ai", "upgrade", "downgrade",
            "setup", "save"}
ONLINE = {"add", "sync", "embed", "upgrade", "downgrade", "setup", "save"}   # the only commands that may go online
                                       # (embed: only to download the model, once)


def split_sources(words: list[str]) -> tuple[list[str], str]:
    """'numpy pandas mean of rows' -> (['numpy', 'pandas'], 'mean of rows')."""
    indexed = {d.name for d in HOME.iterdir() if (d / "meta.json").exists()} if HOME.exists() else set()
    words, sources = list(words), []
    while words and source_id(words[0]) in indexed:
        sources.append(source_id(words.pop(0)))
    return sources, " ".join(words)


def offline_only() -> None:
    """Cut this process off from the internet. From here on it can only connect to this
    computer (127.0.0.1, ::1, local sockets); any other address raises an error instead of
    connecting. docsearch uses the internet only in `search add` and `search sync`."""
    import ipaddress
    import socket
    os.environ["HF_HUB_OFFLINE"] = os.environ["TRANSFORMERS_OFFLINE"] = "1"

    def local(host) -> bool:
        if host is None:
            return True                                   # a listening socket
        host = host.decode(errors="replace") if isinstance(host, bytes) else str(host)
        if host == "localhost":
            return True
        try:
            return ipaddress.ip_address(host.split("%")[0]).is_loopback
        except ValueError:
            return False

    def refuse(host) -> None:
        raise OSError(f"docsearch is offline: refused to connect to {host!r} "
                      "(only `search add` and `search sync` use the internet)")

    real_getaddrinfo = socket.getaddrinfo
    real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex

    def getaddrinfo(host, *args, **kwargs):          # no name lookups for other hosts
        if not local(host):
            refuse(host)
        return real_getaddrinfo(host, *args, **kwargs)

    def check(sock, address) -> None:
        if sock.family in (socket.AF_INET, socket.AF_INET6) and not local(address[0]):
            refuse(address[0])

    def connect(self, address):
        check(self, address)
        return real_connect(self, address)

    def connect_ex(self, address):
        check(self, address)
        return real_connect_ex(self, address)

    socket.getaddrinfo = getaddrinfo
    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex


def quick_search(words: list[str], ai: bool = False) -> None:
    """search numpy svd  ->  the browser opens with the results for 'svd' in numpy.
    Leading package names choose the packages; without one, all packages are searched.
    search ai IDEA  ->  the same, and the AI model reorders the top results."""
    from docsearch import rerank, web
    if ai and rerank.model_dir() is None:
        say("The AI model is not downloaded yet; showing the normal results. Get it with: search setup")
        ai = False
    sources, q = split_sources(words)
    web.open_browser({"q": q, "src": ",".join(sources), "ai": "1" if ai else "0"})


def cmd_serve(args) -> None:
    from docsearch import web
    web.serve(args.port)


def cmd_stop(_args) -> None:
    from docsearch import web
    print("stopped" if web.stop() else "the search page was not running")


def index_changed() -> None:
    """A running search page still has the old index in memory: stop it. The next search
    starts it again with the new one."""
    from docsearch import web
    if CHANGED and web.stop():
        say("Stopped the running search page; your next search starts it with the new index.")


def main(argv: list[str] | None = None) -> None:
    if os.name == "nt":                     # output piped to a file would be in the code page
        for stream in (sys.stdout, sys.stderr):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="search", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="download and index sources")
    a.add_argument("sources", nargs="+", help="numpy, pkg=URL, git, bash, man:PAGE")
    a.add_argument("--workers", type=int, default=16, help="parallel downloads (default 16)")
    a.add_argument("--max-pages", type=int, help="stop after this many doc pages")
    a.add_argument("--no-embed", action="store_true", help="skip vectors (spell search only)")
    a.add_argument("--yes", action="store_true", help="accept docs whose title does not match the name")
    a.add_argument("--accept-partial", action="store_true",
                   help="replace docs you have even if the new download looks incomplete")
    a.set_defaults(func=cmd_add)
    y = sub.add_parser("sync", help=f"index what {CONFIG} lists (creates the file the first time)")
    y.add_argument("--force", action="store_true", help="download again even if up to date")
    y.add_argument("--prune", action="store_true", help="remove indexed sources the file does not list")
    y.add_argument("--workers", type=int, default=16, help="parallel downloads (default 16)")
    y.add_argument("--accept-partial", action="store_true",
                   help="replace docs you have even if the new download looks incomplete")
    y.set_defaults(func=cmd_sync)
    sub.add_parser("list", help="show indexed sources").set_defaults(func=cmd_list)
    sub.add_parser("known", help="languages and toolkits that can be added by name").set_defaults(func=cmd_known)
    r = sub.add_parser("remove", help="delete indexed sources")
    r.add_argument("sources", nargs="+")
    r.set_defaults(func=cmd_remove)
    e = sub.add_parser("embed", help="compute vectors again (after --no-embed or a model change)")
    e.add_argument("sources", nargs="+")
    e.set_defaults(func=cmd_embed)
    sv = sub.add_parser("serve", help="run the search page server in the foreground")
    sv.add_argument("--port", type=int, default=int(os.environ.get("DOCSEARCH_PORT", "8765")))
    sv.set_defaults(func=cmd_serve)
    sub.add_parser("stop", help="stop the background search page server").set_defaults(func=cmd_stop)
    sv2 = sub.add_parser("save", help="keep tutorials or articles to read and search offline")
    sv2.add_argument("urls", nargs="+", metavar="URL")
    sv2.add_argument("--to", default="tutorials", metavar="NAME", help="the collection (default: tutorials)")
    sv2.add_argument("--series", action="store_true", help="also the parts that follow (its Next links)")
    sv2.add_argument("--workers", type=int, default=8, help="parallel image downloads (default 8)")
    sv2.set_defaults(func=cmd_save)
    st = sub.add_parser("setup", help="a new copy: the search command and the models (once), "
                                      "then the docs packages.toml lists")
    st.add_argument("--workers", type=int, default=16, help="parallel downloads (default 16)")
    st.set_defaults(func=cmd_setup)
    for cmd, text in (("upgrade", "replace docs with the newest version (or NAME==VERSION); no NAME: all"),
                      ("downgrade", "replace docs with an older version: NAME==VERSION")):
        u = sub.add_parser(cmd, help=text)
        u.add_argument("sources", nargs="*" if cmd == "upgrade" else "+", metavar="NAME[==VERSION]")
        u.add_argument("--force", action="store_true", help="download again even if up to date")
        u.add_argument("--yes", action="store_true", help="accept docs whose title does not match the name")
        u.add_argument("--workers", type=int, default=16, help="parallel downloads (default 16)")
        u.add_argument("--accept-partial", action="store_true",
                       help="replace docs you have even if the new download looks incomplete")
        u.set_defaults(func=cmd_upgrade)
    sub.add_parser("ai", help="search with AI: search ai IDEA (a model on this computer reorders the top results)")
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in ONLINE:          # everything but indexing stays offline
        offline_only()
    if not argv:                                   # just "search": open the search page
        quick_search([])
        return
    if argv[0] == "ai":                            # search ai IDEA (any words, even "-O3")
        quick_search(list(argv[1:]), ai=True)
        return
    if argv[0] in ("-e", "--exact"):               # search -e drop_duplicates: "drop_duplicates"
        sources, q = split_sources(list(argv[1:]))  # (the shell removes quotes typed around words)
        quick_search(sources + [f'"{q}"'] if q else sources)
        return
    if argv[0] not in COMMANDS and not argv[0].startswith("-"):
        quick_search(list(argv))
        return
    args = p.parse_args(argv)
    args.func(args)
    if args.cmd in ("add", "sync", "remove", "embed", "upgrade", "downgrade", "setup", "save"):
        index_changed()


if __name__ == "__main__":
    main()
