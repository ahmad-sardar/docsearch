"""The text of an article, without the site around it, by a general method: no rules for
particular sites. It follows Mozilla's Readability (Firefox's Reader View):

1. What is never article text goes first: elements whose class or id names them as
   comments, sidebars, footers, menus, sponsors... (Readability's list of "unlikely"
   names), unless the name also says article, content, main or body; and dialogs, menus
   and navigation by their ARIA role.
2. The article is the element whose paragraphs, lists and code carry the most text,
   discounted by how much of that text is links; an element whose one child holds nearly
   all of it gives way to that child.
3. Inside it, a block is dropped when it looks like page furniture rather than writing:
   mostly links with no sentence of its own (navigation, "next lesson", related posts,
   promotions, ad labels), too short to be a sentence with no image, or more form fields
   than paragraphs. A block with code, a formula, a data table (with header cells), or a
   long passage (10 commas or more) is always kept.
"""
from __future__ import annotations

import copy
import re

UNLIKELY = re.compile(r"-ad-|ai2html|banner|breadcrumbs|combx|comment|community|cover-wrap|disqus|extra|footer|"
                      r"gdpr|header|legends|menu|related|remark|replies|rss|shoutbox|sidebar|skyscraper|social|"
                      r"sponsor|supplemental|ad-break|agegate|pagination|pager|popup|yom-remote", re.I)
MAYBE = re.compile(r"and|article|body|column|content|main|shadow", re.I)
UNLIKELY_ROLES = {"menu", "menubar", "complementary", "navigation", "alert", "alertdialog", "dialog"}
POSITIVE = re.compile(r"article|body|content|entry|hentry|h-entry|main|page|pagination|post|text|blog|story", re.I)
NEGATIVE = re.compile(r"-ad-|hidden|^hid$| hid$| hid |^hid |banner|combx|comment|com-|contact|footer|gdpr|masthead|"
                      r"media|meta|outbrain|promo|related|scroll|share|shoutbox|sidebar|skyscraper|sponsor|"
                      r"shopping|tags|widget", re.I)
BLOCKS = ["form", "fieldset", "table", "ul", "ol", "div", "section", "aside", "figure"]
TEXT_TAGS = ["p", "pre", "li", "blockquote", "td", "dd"]


def names(el) -> str:
    return " ".join(list(el.get("class") or []) + [el.get("id") or ""])


def text_len(el) -> int:
    return len(el.get_text(" ", strip=True))


def link_density(el) -> float:
    """How much of an element's text is the text of links (0 to 1)."""
    total = text_len(el)
    return sum(text_len(a) for a in el.find_all("a")) / total if total else 0.0


def class_weight(el) -> int:
    """Readability's hint from names: +25 for article-like names, -25 for furniture."""
    n = names(el)
    return (25 if POSITIVE.search(n) else 0) - (25 if NEGATIVE.search(n) else 0)


def has_code(el) -> bool:
    return el.name == "pre" or el.find("pre") is not None


def drop_unlikely(soup) -> None:
    for el in soup.find_all(True):
        if getattr(el, "decomposed", False) or el.attrs is None or el.name in ("body", "html", "a"):
            continue
        n = names(el)
        if (n.strip() and UNLIKELY.search(n) and not MAYBE.search(n) and not has_code(el)) or (
                el.get("role") in UNLIKELY_ROLES):
            el.decompose()


def main_element(soup):
    """The element holding the article: most paragraph, list and code text, less links."""
    def score(el) -> float:
        return sum(text_len(x) for x in el.find_all(TEXT_TAGS)) * (1 - link_density(el))
    best = soup.find("article") or soup.find("main") or soup.body or soup
    candidates = soup.find_all(["article", "main", "div", "section"])
    if candidates:
        top = max(candidates, key=score)
        if score(top) > 1.3 * score(best) or score(best) == 0:
            best = top
    while True:                                   # step into a child that is nearly all of it
        total = score(best)
        inner = best.find_all(["article", "main", "div", "section"], recursive=False)
        heavy = next((c for c in inner if total and score(c) >= 0.85 * total), None)
        if heavy is None:
            return best
        best = heavy


def prose(el) -> bool:
    """Writing, not furniture: a sentence of its own outside its links (navigation, ad labels
    and promotions are link text and titles; a note that cites a lesson is a sentence)."""
    own = el.get_text(" ", strip=True)
    for a in el.find_all("a"):
        own = own.replace(a.get_text(" ", strip=True), " ", 1)
    return len(re.findall(r"\w+", own)) >= 8 and re.search(r"[.!?:](\s|$)", own) is not None


def furniture(el) -> bool:
    """Is this block page furniture rather than writing (Readability's conditional clean)?"""
    if has_code(el) or (el.name == "table" and el.find("th") is not None):   # code, data tables
        return False
    if el.find(["math", "code", "kbd", "svg"]) is not None and link_density(el) < 0.5:
        return False                              # a formula or a command, however short
    text = el.get_text(" ", strip=True)
    if text.count(",") >= 10:                     # a long passage of writing
        return False
    weight, density = class_weight(el), link_density(el)
    p, img = len(el.find_all("p")), len(el.find_all("img"))
    li, inputs = len(el.find_all("li")), len(el.find_all("input"))
    is_list = el.name in ("ul", "ol")
    return ((img > 1 and p / img < 0.5)
            or (not is_list and li > p + 100)
            or inputs > p / 3
            or (len(text) < 25 and (img == 0 or img > 2) and el.name not in ("figure", "table"))
            or (weight < 25 and density > 0.2 and not prose(el)
                and not (is_list and density < 0.5 and len(text) > 200))
            or (weight >= 25 and density > 0.5 and not prose(el)))


def clean(main) -> None:
    """Drop the furniture inside the article, innermost first."""
    for el in reversed(main.find_all(BLOCKS)):
        if getattr(el, "decomposed", False) or el.attrs is None:
            continue
        if furniture(el):
            el.decompose()
    for h in main.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):     # headings that are links lists
        if h.attrs is not None and class_weight(h) < 0 and link_density(h) > 0.33:
            h.decompose()


def extract(soup):
    """The article's element, cleaned, with its title on top. Changes `soup`."""
    h1 = soup.find("h1")
    title = copy.copy(h1) if h1 is not None else None     # often in a header, dropped below
    drop_unlikely(soup)
    main = main_element(soup)
    clean(main)
    if main.find("h1") is None and title is not None:
        main.insert(0, title)
    return main
