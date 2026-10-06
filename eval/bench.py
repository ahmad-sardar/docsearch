"""Measure search quality, with statistics: which setup finds the right documentation?

    .venv/bin/python eval/bench.py            (offline; see eval/README in results.md)

Question sets (reported separately):
  so      real Stack Overflow questions whose accepted answer links to the official docs
          (eval/so_questions.json, made by collect_so.py). The linked page/section is the
          correct answer, judged by the answerer, not by us.
  ideas   30 questions phrased as ideas, written by hand (eval/ideas.py)
  names   ~200 lookups by name ("Vec::push", "DataFrame.merge"), sampled from the index

Relevance is graded: 2 = the exact entry/section the answer linked to (or the entry with
that #anchor, even if the page moved), 1 = another part of the same page. MRR, recall and
nDCG@10 count grade >= 1; "strict MRR" counts grade 2 only.

Statistics: every number has a 95% confidence interval (bootstrap over questions, 10,000
resamples); every system is compared with the baseline on the same questions (paired
randomization test, 10,000 sign flips), and p-values are Holm-corrected for the number of
comparisons. Tuning (depth, prompts) uses the dev split only; results are on the test split.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import re
import statistics
import time
import urllib.parse
from collections import defaultdict
from pathlib import Path

import numpy as np

from docsearch import cli

HERE = Path(__file__).parent
RNG = np.random.default_rng(0)

# --------------------------------------------------------------------------- correct answers

VERSION_PATHS = [
    (r"numpy\.org/doc/[^/]+/", "numpy.org/doc/stable/"),
    (r"docs\.scipy\.org/doc/numpy[^/]*/", "numpy.org/doc/stable/"),
    (r"pandas\.pydata\.org/pandas-docs/(stable|version/[^/]+|dev)/", "pandas.pydata.org/docs/"),
    (r"pandas\.pydata\.org/docs/(version/[^/]+/)?", "pandas.pydata.org/docs/"),
    (r"(docs\.)?pytorch\.org/docs/[^/]+/", "docs.pytorch.org/docs/stable/"),
    (r"scikit-learn\.org/[^/]+/", "scikit-learn.org/stable/"),
    (r"docs\.python\.org/(\d[\d.]*|dev)/", "docs.python.org/3/"),
    (r"docs\.python\.org/(?!3/)", "docs.python.org/3/"),
    (r"doc\.rust-lang\.org/(stable/|beta/|nightly/|\d[\d.]*/)?", "doc.rust-lang.org/stable/"),
    (r"caml\.inria\.fr/pub/docs/manual-ocaml[^/]*/libref/", "ocaml.org/manual/5.5/api/"),
    (r"caml\.inria\.fr/pub/docs/manual-ocaml[^/]*/", "ocaml.org/manual/5.5/"),
    (r"(v2\.)?ocaml\.org/(releases/[^/]+/htmlman|manual/[^/]+)/libref/", "ocaml.org/manual/5.5/api/"),
    (r"(v2\.)?ocaml\.org/(releases/[^/]+/htmlman|manual/[^/]+)/", "ocaml.org/manual/5.5/"),
    (r"(v2\.)?ocaml\.org/api/", "ocaml.org/manual/5.5/api/"),
    (r"ocaml\.org/manual/(?!\d)", "ocaml.org/manual/5.5/"),
    (r"en\.cppreference\.com/w/", "en.cppreference.com/"),
    (r"(golang\.org|go\.dev)/pkg/", "pkg.go.dev/"),
    (r"golang\.org/ref/", "go.dev/ref/"),
    (r"golang\.org/doc/effective_go(\.html)?", "go.dev/doc/effective_go"),
    (r"developer\.mozilla\.org/[\w-]+/docs/", "developer.mozilla.org/en-US/docs/"),
]


def normalize(url: str) -> tuple[str, str]:
    """Today's address of an old docs link: (page, #fragment)."""
    url = urllib.parse.unquote(url.replace("http://", "https://"))
    for pat, rep in VERSION_PATHS:
        url = re.sub(r"(?<=https://)" + pat, rep, url, count=1)
    page, _, frag = url.partition("#")
    page = page.split("?")[0]
    page = re.sub(r"/index\.html$", "/", page)
    page = re.sub(r"(pandas\.pydata\.org/docs/)generated/", r"\1reference/api/", page)
    if "pkg.go.dev/" in page or "mozilla.org" in page or "cppreference" in page:
        page = page.rstrip("/")
    return page, frag


def page_key(loc: str) -> tuple[str, str]:
    page, _, frag = loc.partition("#")
    page = re.sub(r"/index\.html$", "/", page)
    if "pkg.go.dev/" in page or "mozilla.org" in page or "cppreference" in page:
        page = page.rstrip("/")
    return page, frag


class Gold:
    """Which entries answer a link, with grades."""

    def __init__(self, entries, sid_of):
        self.by_page = defaultdict(list)
        self.by_frag = defaultdict(list)
        self.by_file = defaultdict(set)                  # (source, file name) -> pages
        for i, e in enumerate(entries):
            page, frag = page_key(e.location)
            self.by_page[page].append((i, frag))
            self.by_file[(sid_of[i], page.rstrip("/").rsplit("/", 1)[-1])].add(page)
            if frag:
                self.by_frag[(sid_of[i], frag)].append((i, page))

    def grades(self, link: str, sid: str) -> dict[int, int]:
        page, frag = normalize(link)
        if page not in self.by_page:                     # the page moved (python: library/ ->
            moved = self.by_file.get((sid, page.rstrip("/").rsplit("/", 1)[-1]), set())  # builtins/)
            if len(moved) == 1:
                page = next(iter(moved))
        out: dict[int, int] = {}
        for i, f in self.by_page.get(page, []):
            if frag and f == frag:
                out[i] = 2
            elif not f:
                out[i] = max(out.get(i, 0), 1 if frag else 2)   # the page itself
            else:
                out[i] = max(out.get(i, 0), 1)                   # another part of the page
        if frag and 2 not in out.values():
            same = self.by_frag.get((sid, frag), [])
            if len({p for _, p in same}) == 1:                   # anchor moved with its page
                for i, _ in same:
                    out[i] = 2
        return out


# --------------------------------------------------------------------------- question sets

def split_of(text: str) -> str:
    return "dev" if int(hashlib.sha1(text.encode()).hexdigest(), 16) % 10 < 3 else "test"


def load_questions(index, sid_of) -> tuple[list[dict], dict]:
    gold = Gold(index.entries, sid_of)
    have = set(sid_of)
    qs, dropped = [], defaultdict(int)
    for row in json.loads((HERE / "so_questions.json").read_text()):
        if row["source"] not in have:
            continue
        g: dict[int, int] = {}
        for link in row["links"]:
            for i, grade in gold.grades(link, row["source"]).items():
                g[i] = max(g.get(i, 0), grade)
        if not g:
            dropped[row["source"]] += 1
            continue
        qs.append({"set": "so", "source": row["source"], "q": row["question"], "gold": g,
                   "split": split_of(row["question"])})
    # hand-written idea questions (names or title words)
    from ideas import QUESTIONS
    for q, answers in QUESTIONS:
        g = {}
        for i, e in enumerate(index.entries):
            name, title = cli.api_name(e.title), e.title.lower()
            if any(title.find(a[6:]) >= 0 if a.startswith("title:") else name == a for a in answers):
                g[i] = 2
        if g:
            qs.append({"set": "ideas", "source": "mixed", "q": q, "gold": g, "split": split_of(q)})
    # lookups by name: the last one or two parts of an API name
    rnd = random.Random(7)
    api = [i for i, e in enumerate(index.entries) if e.kind not in cli.PAGE_KINDS]
    by_source = defaultdict(list)
    for i in api:
        by_source[sid_of[i]].append(i)
    for sid, ids in sorted(by_source.items()):
        for i in rnd.sample(ids, min(16, len(ids))):
            name = cli.api_name(index.entries[i].title)
            parts = re.split(r"(\.|::)", name)
            q = "".join(parts[-3:]) if len(parts) >= 3 else name    # "DataFrame.merge", "Vec::push"
            qs.append({"set": "names", "source": sid, "q": q, "gold": {i: 2}, "split": split_of(q + sid)})
    return qs, dict(dropped)


# --------------------------------------------------------------------------- metrics

def per_query(ranked: list[int], gold: dict[int, int], k: int = 10) -> dict[str, float]:
    top = ranked[:k]
    first = next((r for r, i in enumerate(top, 1) if gold.get(i, 0) >= 1), None)
    strict = next((r for r, i in enumerate(top, 1) if gold.get(i, 0) >= 2), None)
    dcg = sum((2 ** gold.get(i, 0) - 1) / math.log2(r + 1) for r, i in enumerate(top, 1))
    ideal = sorted(gold.values(), reverse=True)[:k]
    idcg = sum((2 ** g - 1) / math.log2(r + 1) for r, g in enumerate(ideal, 1)) or 1
    return {"mrr": 1 / first if first else 0.0, "strict_mrr": 1 / strict if strict else 0.0,
            "r1": float(first == 1), "r5": float(bool(first and first <= 5)),
            "r10": float(first is not None), "ndcg": dcg / idcg}


def bootstrap_ci(values: np.ndarray, n: int = 10_000) -> tuple[float, float]:
    idx = RNG.integers(0, len(values), size=(n, len(values)))
    means = values[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def paired_p(a: np.ndarray, b: np.ndarray, n: int = 10_000) -> float:
    """Randomization test: how often random sign flips of the per-question differences give
    a mean difference at least as large as the observed one (two-sided)."""
    d = b - a
    obs = abs(d.mean())
    signs = RNG.choice([-1.0, 1.0], size=(n, len(d)))
    return float(((np.abs((signs * d).mean(axis=1)) >= obs - 1e-12).sum() + 1) / (n + 1))


def holm(pvals: dict[str, float]) -> dict[str, float]:
    order = sorted(pvals, key=pvals.get)
    out, running = {}, 0.0
    for k, name in enumerate(order):
        running = max(running, min(1.0, pvals[name] * (len(order) - k)))
        out[name] = running
    return out


def evaluate(name: str, ranker, questions: list[dict], depth: int = 50) -> dict:
    """Run a system on all questions; per-question metrics and latency."""
    rows, times = [], []
    for q in questions:
        t = time.perf_counter()
        ranked = ranker(q["q"])[:depth]
        times.append(time.perf_counter() - t)
        rows.append(per_query(ranked, q["gold"]) | {"recall50": float(any(q["gold"].get(i, 0) >= 1 for i in ranked))})
    return {"name": name, "rows": rows, "ms_p50": 1000 * statistics.median(times),
            "ms_p95": 1000 * float(np.percentile(times, 95))}


def report(results: list[dict], questions: list[dict], baseline: str, title: str) -> str:
    """A Markdown table: every metric with its 95% CI, and the difference to the baseline."""
    base = next(r for r in results if r["name"] == baseline)
    lines = [f"### {title}  (n = {len(questions)} questions)", "",
             "| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    pvals = {}
    for r in results:
        if r["name"] != baseline:
            pvals[r["name"]] = paired_p(np.array([x["mrr"] for x in base["rows"]]),
                                        np.array([x["mrr"] for x in r["rows"]]))
    adj = holm(pvals) if pvals else {}
    for r in results:
        m = {k: np.array([x[k] for x in r["rows"]]) for k in r["rows"][0]}
        lo, hi = bootstrap_ci(m["mrr"])
        if r["name"] == baseline:
            delta = "baseline"
        else:
            d = m["mrr"].mean() - np.array([x["mrr"] for x in base["rows"]]).mean()
            delta = f"{d:+.3f} (p={adj[r['name']]:.4f})"
        lines.append(f"| {r['name']} | {m['mrr'].mean():.3f} [{lo:.3f}, {hi:.3f}] | {delta} | "
                     f"{m['strict_mrr'].mean():.3f} | {m['r1'].mean():.2f} | {m['r5'].mean():.2f} | "
                     f"{m['r10'].mean():.2f} | {m['recall50'].mean():.2f} | {m['ndcg'].mean():.3f} | "
                     f"{r['ms_p50']:.0f} / {r['ms_p95']:.0f} | {r.get('peak_gpu_gb', 0):.1f} |")
    return "\n".join(lines) + "\n"
