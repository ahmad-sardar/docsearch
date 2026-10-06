"""Saved articles: does the general extraction (docsearch/article.py) find the text of any
site? Measured against trafilatura, an independent and widely benchmarked extractor, as
the reference; it is only used here.

    uv run --with trafilatura python eval/articles.py

Recall: how much of the reference's text (4-word runs) the article kept; precision: how
much of the article's text the reference also counts as the article. Pages are cached in
eval/cache/articles/. Results: eval/results-articles.md.
"""
import hashlib
import re
import statistics
import sys
from pathlib import Path

import trafilatura

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from docsearch import article, cli, importers  # noqa: E402

CACHE = Path(__file__).parent / "cache" / "articles"
URLS = [
    "https://realpython.com/python-f-strings/",
    "https://www.learncpp.com/cpp-tutorial/bit-flags-and-bit-manipulation-via-stdbitset/",
    "https://jvns.ca/blog/2024/11/18/how-to-import-a-javascript-library/",
    "https://docs.python.org/3/howto/logging.html",
    "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Closures",
    "https://www.digitalocean.com/community/tutorials/how-to-use-git-a-reference-guide",
    "https://martinfowler.com/articles/microservices.html",
    "https://paulgraham.com/greatwork.html",
    "https://en.wikipedia.org/wiki/Bit_manipulation",
    "https://www.w3schools.com/python/python_lists.asp",
    "https://blog.rust-lang.org/2024/09/05/Rust-1.81.0/",
    "https://www.freecodecamp.org/news/git-cheat-sheet/",
    "https://go.dev/blog/errors-are-values",
    "https://danluu.com/look-stupid/",
]


def html_of(url: str) -> bytes:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".html")
    if not f.exists():
        f.write_bytes(cli.http_get(url)[0])
    return f.read_bytes()


def extract(html: bytes):
    soup = cli.make_soup(html)
    cli.clean_soup(soup)
    for el in soup.select(importers.DROP):
        el.decompose()
    return article.extract(soup)


def shingles(text: str, n: int = 4) -> set:
    w = re.findall(r"\w+", text.lower())
    return {tuple(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}


def main() -> None:
    rec, prec = [], []
    print(f"{'page':44} {'ref words':>9} {'recall':>7} {'precision':>9} {'code blocks':>11}")
    for url in URLS:
        html = html_of(url)
        ref = shingles(trafilatura.extract(html.decode("utf-8", "replace"), include_tables=True) or "")
        main_el = extract(html)
        ours = shingles(main_el.get_text(" ", strip=True))
        r = len(ref & ours) / len(ref) if ref else 0.0
        p = len(ref & ours) / len(ours) if ours else 0.0
        rec.append(r)
        prec.append(p)
        print(f"{re.sub(r'https?://(www[.])?', '', url)[:44]:44} {len(ref):9} {r:7.2f} {p:9.2f} {len(main_el.find_all('pre')):11}")
    print(f"median recall {statistics.median(rec):.2f}, median precision {statistics.median(prec):.2f}")


if __name__ == "__main__":
    main()
