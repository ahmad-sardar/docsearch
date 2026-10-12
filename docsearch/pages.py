"""Offline copies of documentation pages, made safe to show in the browser.

Every page is downloaded once while indexing (`search add` / `search sync`, the only
time docsearch uses the internet), cut down to its main content, passed through an
allowlist (only harmless tags and attributes survive) and stored gzipped, with its images:

    data/index/<source>/pages/<path of the page on the docs site>.gz
    data/index/<source>/pages/_images/<sha1 of the image address>   (+ images.json: types)

The browser then shows only these copies: 100% offline. Links to other websites are kept as
plain text (their address can be copied), so nothing in a page can go online. A strict
Content-Security-Policy (see web.py) is the second line of defence: even if something
slipped through, the browser would not run it.
"""
from __future__ import annotations

import gzip
import hashlib
import os
import re
import urllib.parse
from pathlib import Path

from bs4 import BeautifulSoup, Comment

# Tags kept as they are. Anything else is unwrapped (its text stays), except DROP.
TAGS = {
    "a", "abbr", "b", "blockquote", "br", "caption", "cite", "code", "col", "colgroup",
    "dd", "del", "details", "div", "dl", "dt", "em", "figcaption", "figure", "h1", "h2",
    "h3", "h4", "h5", "h6", "hr", "i", "ins", "kbd", "li", "ol", "p", "pre", "q", "s",
    "samp", "section", "small", "span", "strong", "sub", "summary", "sup", "table", "img",
    "tbody", "td", "tfoot", "th", "thead", "tr", "tt", "u", "ul", "var", "article", "aside",
    "nav", "header", "footer", "main",
}
# MathML: Safari draws formulas natively from these.
MATHML = {
    "math", "semantics", "mrow", "mi", "mo", "mn", "ms", "mtext", "mspace", "msup", "msub",
    "msubsup", "mfrac", "msqrt", "mroot", "mover", "munder", "munderover", "mtable", "mtr",
    "mtd", "mstyle", "mpadded", "menclose", "mphantom", "merror", "mmultiscripts",
    "mprescripts", "none",
}
# Removed with everything inside them.
DROP = {
    "script", "style", "iframe", "frame", "frameset", "object", "embed", "applet", "form",
    "input", "button", "select", "option", "textarea", "noscript", "template", "svg",
    "canvas", "video", "audio", "source", "track", "link", "meta", "base", "annotation",
    "annotation-xml", "head", "title", "map", "area", "dialog", "portal",
}
ATTRS = {"class", "id", "title", "lang"}
TAG_ATTRS = {"a": {"href"}, "img": {"src", "alt", "width", "height", "loading"},
             "td": {"colspan", "rowspan"}, "th": {"colspan", "rowspan"},
             "ol": {"start"}, "col": {"span"}, "colgroup": {"span"}}
MATH_ATTRS = {"mathvariant", "display", "stretchy", "fence", "separator", "lspace", "rspace",
              "accent", "accentunder", "linethickness", "columnalign", "rowalign",
              "columnspacing", "rowspacing", "scriptlevel", "displaystyle", "movablelimits",
              "largeop", "symmetric", "minsize", "maxsize", "width", "height", "depth",
              "notation", "open", "close", "separators", "form"}
SAFE_CLASS = re.compile(r"[\w\- ]{0,200}")
SAFE_ID = re.compile(r"[\w.:/\-]{1,200}")         # (git-scm anchors contain /)


def safe_href(href: str, base: str) -> str | None:
    """Links: in-page (#x), or http(s) resolved against the page. Nothing else
    (no javascript:, data:, file:)."""
    href = href.strip()
    if href.startswith("#"):
        return href if SAFE_ID.fullmatch(href[1:] or "x") else None
    url = urllib.parse.urljoin(base, href)
    return url if urllib.parse.urlparse(url).scheme in ("http", "https") else None


def keep_mathml(soup) -> None:
    """KaTeX stores each formula three times. Keep the MathML copy; Safari draws it."""
    for el in soup.select("span.katex-display, span.katex"):
        if el.decomposed or el.parent is None:
            continue
        math = el.find("math")
        if math is None:
            continue
        if "katex-display" in (el.get("class") or []):
            math["display"] = "block"
        el.replace_with(math.extract())


LOCAL_IMAGE = re.compile(r"/asset/[\w.@\-]{1,100}/[0-9a-f]{40}")


def image_name(url: str) -> str:
    """The stored name of an image: the sha1 of its address."""
    return hashlib.sha1(url.encode()).hexdigest()


def sanitize(node, base: str, image=None, image_base: str | None = None) -> str:
    """Only allowlisted tags and attributes. `image(url)` gives the local address of a
    stored image (or None: then its description is shown instead). Image addresses are
    resolved against `image_base` (where the page really is), links against `base`."""
    soup = node if isinstance(node, BeautifulSoup) else BeautifulSoup(str(node), "lxml")
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for img in soup.find_all("img"):
        src = safe_href(img.get("src") or "", image_base or base)
        alt = (img.get("alt") or "").strip()
        local = image(src) if image and src and not src.startswith("#") else None
        if local:
            img.attrs = {"src": local, "alt": alt, "loading": "lazy",
                         **{k: img.get(k) for k in ("width", "height") if str(img.get(k, "")).isdigit()}}
        elif alt:
            span = soup.new_tag("span")
            span["class"] = "offline-image"
            span.string = f"image: {alt}"
            img.replace_with(span)
        else:
            img.decompose()
    for tag in list(soup.find_all(True)):
        if tag.decomposed:
            continue
        name = tag.name.lower()
        if name in DROP:
            tag.decompose()
            continue
        if name not in TAGS and name not in MATHML:
            tag.unwrap()
            continue
        allowed = ATTRS | TAG_ATTRS.get(name, set()) | (MATH_ATTRS if name in MATHML else set())
        for attr in list(tag.attrs):
            value = tag.attrs[attr]
            value = " ".join(value) if isinstance(value, list) else str(value)
            if attr.lower() not in allowed:
                del tag.attrs[attr]
            elif attr == "src":                      # only stored images, never the web
                if not LOCAL_IMAGE.fullmatch(value):
                    del tag.attrs[attr]
            elif attr == "href":
                url = safe_href(value, base)
                if url is None:
                    del tag.attrs[attr]
                else:
                    tag.attrs[attr] = url
            elif attr == "class" and not SAFE_CLASS.fullmatch(value):
                del tag.attrs[attr]
            elif attr == "id" and not SAFE_ID.fullmatch(value):
                del tag.attrs[attr]
            elif attr in ("colspan", "rowspan", "start", "span") and not value.isdigit():
                del tag.attrs[attr]
    body = soup.body if soup.body is not None else soup
    return "".join(str(c) for c in body.contents) if body.name == "body" else str(body)


# --------------------------------------------------------------------------- storage

PAGE_PATH = re.compile(r"[\w.~+\-]+(?:/[\w.~+\-]+)*")


# Names Windows keeps for devices (con.html is the console there), in any case, with or
# without an extension.
RESERVED = re.compile(r"(con|prn|aux|nul|com\d|lpt\d)(\..*)?", re.I)


def windows_name(part: str) -> str:
    """A path part Windows can store as it is: not a device name, not ending in a dot
    (Windows drops it). Only used on Windows; the same page always maps to the same file."""
    if RESERVED.fullmatch(part):
        part = "_" + part
    return part + "_" if part.endswith(".") else part


def page_file(pages_dir: Path, rel: str) -> Path | None:
    """Where a page is stored; None for a path that could leave the folder."""
    rel = rel.split("#")[0].split("?")[0].strip("/") or "index.html"
    if not PAGE_PATH.fullmatch(rel) or any(p in (".", "..") for p in rel.split("/")):
        return None
    if os.name == "nt":
        rel = "/".join(windows_name(p) for p in rel.split("/"))
    f = pages_dir / (rel + ".gz")
    try:
        f.resolve().relative_to(pages_dir.resolve())
    except ValueError:
        return None
    if os.name == "nt" and len(str(f.resolve())) >= 240:    # past Windows' 260-letter limit:
        return Path("\\\\?\\" + str(f.resolve()))            # the long-path form
    return f


def save_page(pages_dir: Path, rel: str, html_text: str) -> None:
    f = page_file(pages_dir, rel)
    if f is None:
        return
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(gzip.compress(html_text.encode("utf-8"), 6))


def load_page(pages_dir: Path, rel: str) -> str | None:
    f = page_file(pages_dir, rel)
    if f is None or not f.exists():
        return None
    return gzip.decompress(f.read_bytes()).decode("utf-8")


# --------------------------------------------------------------------------- links

def localize_links(html_text: str, sites: dict[str, tuple[str, Path]], own: str = "") -> str:
    """Links into an indexed docs site whose page is stored become in-app links
    (/?page=<source>/<path>&at=<anchor>), to the page's own copy first (cpp@17 stays in C++17,
    though cpp@23 has the same pages). Every other web link becomes plain text that shows its
    address: nothing in a page can open the internet."""
    mine = {k: v for k, v in sites.items() if k == own or k.startswith(own + "/")}     # (its guides too)
    sites = {**dict(sorted(mine.items(), key=lambda kv: -len(kv[1][0]))),
             **{k: v for k, v in sites.items() if k not in mine}}
    soup = BeautifulSoup(html_text, "lxml")
    for a in soup.find_all("a", href=True):
        url = a["href"]
        if url.startswith("#"):
            continue
        for sid, (root, pages_dir) in sites.items():
            if url.startswith(root):
                rel, _, anchor = url[len(root):].partition("#")
                rel = rel or "index.html"
                f = page_file(pages_dir, rel)
                if f is not None and f.exists():
                    a["href"] = "/?" + urllib.parse.urlencode(
                        {"page": f"{sid}/{rel}", **({"at": anchor} if anchor else {})})
                    break
        else:
            a.name = "span"
            del a["href"]
            a["class"] = (a.get("class") or []) + ["ext-link"]
            a["title"] = url
    body = soup.body if soup.body is not None else soup
    return "".join(str(c) for c in body.contents)


# --------------------------------------------------------------------------- images

IMAGE_TYPES = {b"\x89PNG\r\n\x1a\n": "image/png", b"\xff\xd8\xff": "image/jpeg",
               b"GIF87a": "image/gif", b"GIF89a": "image/gif"}
MAX_IMAGE = 5 * 2**20


def image_type(data: bytes) -> str | None:
    """The type of an image from its first bytes (never from what a server claims)."""
    for magic, ctype in IMAGE_TYPES.items():
        if data.startswith(magic):
            return ctype
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    head = data[:1000].lstrip().lower()
    if head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in head):
        return "image/svg+xml"
    return None


# --------------------------------------------------------------------------- source code

# A link to a file of code at a version: GitHub, GitLab, Codeberg, Go's source browser
CODE_LINK = re.compile(r"https://(?:(?:www\.)?github\.com/[^/]+/[^/]+/(?:blob|tree)/|gitlab\.com/.+?/-/blob/"
                       r"|codeberg\.org/[^/]+/[^/]+/src/(?:branch|tag|commit)/|cs\.opensource\.google/go/go/\+/)")
DOC_FILE = re.compile(r"\.(md|markdown|rst|txt|ipynb|html?)$", re.I)     # the docs' own sources: not code
# An entry's signature: its <dt> (with a multi-line one's parameters, a <dl> that the parser
# moves out of it, up to its description: polars), Go's source link, Python's "Source code:"
SIGNATURE = re.compile(r"<dt\b[^>]*>.*?</dt>(?:\s*<dl>(?:(?!<dt\b).)*?</dl>(?:(?!<dd\b).)*)?"
                       r"|<a\b[^>]*class=\"[^\"]*Documentation-source[^\"]*\"[^>]*>"
                       r"|<p\b[^>]*>\s*<strong>Source code:</strong>.*?</p>", re.S)
HREF = re.compile(r'href="([^"]+)"')


def code_link(href: str) -> bool:
    return bool(CODE_LINK.match(href)) and not DOC_FILE.search(re.split(r"[#;?]", href)[0])


def source_link(fragment_html: str, api: bool) -> str | None:
    """The code an entry documents, as its docs link to it: the link in its signature (Sphinx's
    [source] at the end of its <dt>; Go's "View Source"), or for a page, its "Source code:"
    line (Python's modules). None: the docs do not say."""
    soup = BeautifulSoup(fragment_html, "lxml")
    if api:                                       # (its own: in its signature or heading, never
        dt = soup.find("dt")                      # the first of a whole page's: Go's package pages)
        places = [dt, *signature_rest(dt)]
        heading = soup.find(re.compile(r"^h[1-6]$"))
        if heading is not None:
            places += [heading, heading.find_next_sibling()]
    else:
        places = [p for p in soup.find_all("p", limit=8) if p.get_text(" ", strip=True).startswith("Source code:")]
    for place in places:
        if place is None:
            continue
        for a in [place] if place.name == "a" else place.find_all("a", href=True):
            if code_link(a.get("href", "")):
                return a["href"]
    return None


def signature_rest(dt) -> list:
    """What follows a <dt> up to its description: a multi-line signature's parameters and its
    end, which the parser moves out of the <dt> (Sphinx's nested <dl>: polars)."""
    out = []
    for sib in dt.find_next_siblings() if dt is not None else []:
        if sib.name in ("dd", "dt"):
            break
        out.append(sib)
    return out


def signature_links(page_html: str) -> list[str]:
    """Every entry's source link on a stored page (see source_link), each once."""
    out = []
    for block in SIGNATURE.findall(page_html):
        out += [h for h in HREF.findall(block) if code_link(h)]
    return list(dict.fromkeys(out))


def raw_source(link: str) -> tuple[str, str, str, str] | None:
    """Where a linked file's plain text is, and its repository, ref and path:
    github.com/numpy/numpy/blob/v2.5.0/numpy/x.py#L10 -> (raw.githubusercontent.com/...,
    "github.com/numpy/numpy", "v2.5.0", "numpy/x.py"). (A ref with "/" in it reads as its
    first part here; GitHub itself resolves the address the same way.)"""
    u = urllib.parse.urlparse(link)
    host, path = u.netloc.lower().removeprefix("www."), u.path
    if host == "github.com" and (m := re.match(r"/([^/]+)/([^/]+)/(?:blob|tree)/([^/]+)/(.+)", path)):
        return f"https://raw.githubusercontent.com/{m[1]}/{m[2]}/{m[3]}/{m[4]}", f"github.com/{m[1]}/{m[2]}", m[3], m[4]
    if host == "gitlab.com" and (m := re.match(r"/(.+?)/-/blob/([^/]+)/(.+)", path)):
        return f"https://gitlab.com/{m[1]}/-/raw/{m[2]}/{m[3]}", f"gitlab.com/{m[1]}", m[2], m[3]
    if host == "codeberg.org" and (m := re.match(r"/([^/]+)/([^/]+)/src/(branch|tag|commit)/([^/]+)/(.+)", path)):
        return (f"https://codeberg.org/{m[1]}/{m[2]}/raw/{m[3]}/{m[4]}/{m[5]}", f"codeberg.org/{m[1]}/{m[2]}",
                m[4], m[5])
    if host == "cs.opensource.google" and (m := re.match(r"/go/go/\+/([^:]+):([^;]+)", path)):
        return f"https://go.googlesource.com/go/+/{m[1]}/{m[2]}?format=TEXT", "go.googlesource.com/go", m[1], m[2]
    return None


def source_lines(link: str) -> tuple[int, int | None] | None:
    """The lines a source link points at: #L293-L325 -> (293, 325); #L28 or Go's ;l=77 -> one
    line, (28, None): its block is shown. None: the whole file."""
    m = re.search(r"#L(\d+)(?:-L?(\d+))?$", link) or re.search(r";l=(\d+)", link)
    if not m:
        return None
    return int(m[1]), (int(m[2]) if m.lastindex and m.lastindex > 1 and m[2] else None)


def source_file(folder: Path, raw: str) -> Path:
    return folder / (hashlib.sha1(raw.encode()).hexdigest() + ".gz")


# --------------------------------------------------------------------------- one standard (cppreference)

REV_CLASS = re.compile(r"\bt-(since|until)-(cxx|c)(\d\d)\b")    # cppreference: t-since-cxx20, t-until-c23


def for_standard(html_text: str, lang: str, year: int) -> str:
    """A cppreference page as one standard has it: rows and passages marked for other
    standards (their classes say t-since-cxx20, t-until-cxx11) left out. A table row with no
    mark of its own takes its member's (the "(C++11)" next to its name)."""
    soup = BeautifulSoup(html_text, "lxml")
    want = "cxx" if lang == "C++" else "c"

    def outside(classes) -> bool:
        since, until = [], []
        for kind, l, yy in REV_CLASS.findall(" ".join(classes or [])):
            if l == want:
                y = 1900 + int(yy) if int(yy) >= 80 else 2000 + int(yy)
                (since if kind == "since" else until).append(y)
        return bool(since and min(since) > year) or bool(until and max(until) <= year)
    for el in soup.find_all(class_=REV_CLASS):
        if el.decomposed or "t-mark" in " ".join(el.get("class") or []):
            continue                                  # (a mark's label: its row decides)
        if outside(el.get("class")):
            el.decompose()
    for row in soup.find_all("tr"):
        if row.decomposed or REV_CLASS.search(" ".join(row.get("class") or [])):
            continue
        mark = row.find(class_=REV_CLASS)
        if mark is not None and outside(mark.get("class")):
            row.decompose()
    body = soup.body if soup.body is not None else soup
    return "".join(str(c) for c in body.contents)
