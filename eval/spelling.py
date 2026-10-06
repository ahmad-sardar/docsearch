"""Misspelled queries: fit the speller's weights and measure it on real human misspellings.

    .venv/bin/python eval/spelling.py            fit on dev words, print the weights and the
                                                 word accuracy on the other words
    .venv/bin/python eval/spelling.py --search   also search with misspelled benchmark
                                                 questions (dev), --test for the test split

Data (downloaded, not kept in the repository): the Birkbeck spelling error corpus (Roger
Mitton; real misspellings from people's writing) and Wikipedia's list of common
misspellings (CC BY-SA). Only pairs whose correct word the docs use, and whose misspelling
they never use, count. Words are split by a hash: weights are fit on dev words only; the
other words, and the benchmark questions of each split, are used only for measuring.
"""
from __future__ import annotations

import hashlib
import random
import re
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from docsearch import cli, spelling  # noqa: E402

import bench  # noqa: E402

CACHE = HERE / "cache"
SOURCES = {"birkbeck.dat": "https://www.dcs.bbk.ac.uk/~ROGER/missp.dat",
           "wikipedia.txt": "https://en.wikipedia.org/w/index.php?title=Wikipedia:Lists_of_common_misspellings/"
                            "For_machines&action=raw"}


def word_is_dev(word: str) -> bool:
    return int(hashlib.sha1(word.encode()).hexdigest(), 16) % 10 < 3


def misspellings(known: dict[str, int]) -> dict[str, set[str]]:
    """{misspelling: the words it was meant to be}, for words in the docs."""
    CACHE.mkdir(exist_ok=True)
    for name, url in SOURCES.items():
        if not (CACHE / name).exists():
            (CACHE / name).write_bytes(cli.http_get(url, timeout=60)[0])
    pairs = set()
    cur = None
    for ln in (CACHE / "birkbeck.dat").read_text(errors="replace").splitlines():
        if ln.startswith("$"):
            cur = ln[1:].strip().lower()
        elif cur and ln.strip():
            pairs.add((ln.strip().lower(), cur))
    for ln in (CACHE / "wikipedia.txt").read_text(errors="replace").splitlines():
        m = re.fullmatch(r"([a-z]+)->([a-z, ]+)", ln.strip())
        if m:
            pairs |= {(m.group(1), c.strip()) for c in m.group(2).split(",")}
    gold: dict[str, set[str]] = defaultdict(set)
    for w, c in pairs:
        if (re.fullmatch(r"[a-z]+", w) and re.fullmatch(r"[a-z]{4,}", c) and w != c
                and known.get(c, 0) >= spelling.MIN_FREQUENCY and known.get(w, 0) == 0):
            gold[w].add(c)
    return gold


def fit(sp: spelling.Speller, data, gold) -> tuple[list, list, list]:
    """Softmax regression over each misspelling's candidates (Adam, 400 steps)."""
    data = [(w, cs, F) for w, cs, F in data if any(c in gold[w] for c in cs)]
    allF = np.concatenate([F for _, _, F in data])
    mu, sd = allF.mean(0), allF.std(0) + 1e-9
    C = max(len(cs) for _, cs, _ in data)
    X = np.zeros((len(data), C, len(spelling.FEATURES)), np.float32)
    M = np.full((len(data), C), -1e9, np.float32)
    Y = np.zeros((len(data), C), np.float32)
    for q, (w, cs, F) in enumerate(data):
        X[q, :len(cs)] = (F - mu) / sd
        M[q, :len(cs)] = 0
        g = [j for j, c in enumerate(cs) if c in gold[w]]
        Y[q, g] = 1 / len(g)
    wv, m1, m2 = (np.zeros(len(spelling.FEATURES), np.float32) for _ in range(3))
    for it in range(1, 401):
        z = X @ wv + M
        z -= z.max(1, keepdims=True)
        p = np.exp(z)
        p /= p.sum(1, keepdims=True)
        grad = np.einsum("qc,qcf->f", p - Y, X) / len(data)
        m1 = 0.9 * m1 + 0.1 * grad
        m2 = 0.999 * m2 + 0.001 * grad ** 2
        wv -= 0.05 * (m1 / (1 - 0.9 ** it)) / (np.sqrt(m2 / (1 - 0.999 ** it)) + 1e-8)
    return [round(float(x), 5) for x in mu], [round(float(x), 5) for x in sd], [round(float(x), 5) for x in wv]


def main() -> None:
    import run
    test = "--test" in sys.argv
    b = run.Bench("test" if test else "dev")
    ix = b.index
    known = {t: len(v[0]) for t, v in ix.post.items()}
    sp = spelling.Speller(known)
    gold = misspellings(known)
    t = time.time()
    rows = [(w, *sp.candidates(w)) for w in sorted(gold)]
    print(f"{len(rows)} real misspellings of {len({c for g in gold.values() for c in g})} docs words "
          f"(candidates in {time.time() - t:.0f} s)")
    dev = [r for r in rows if word_is_dev(min(gold[r[0]]))]
    other = [r for r in rows if not word_is_dev(min(gold[r[0]]))]
    spelling.MEAN, spelling.SCALE, spelling.WEIGHTS = fit(sp, dev, gold)
    print(f"MEAN = {spelling.MEAN}\nSCALE = {spelling.SCALE}\nWEIGHTS = {spelling.WEIGHTS}")
    first = [sp.suggest(w, 1)[0][0] in gold[w] for w, _, _ in other]
    top3 = [any(c in gold[w] for c, _ in sp.suggest(w, 3)) for w, _, _ in other]
    print(f"on {len(other)} misspellings of other words: right word first {100 * np.mean(first):.1f}%, "
          f"in the top 3 {100 * np.mean(top3):.1f}%")
    if "--search" not in sys.argv and not test:
        return
    # benchmark questions with real misspellings of this split's words
    meant_as = defaultdict(list)
    for w, cs in gold.items():
        for c in cs:
            meant_as[c].append(w)
    rnd = random.Random(11 if test else 7)

    def misspell(q: str) -> tuple[str, int]:
        out, n = [], 0
        for tok in re.split(r"(\W+)", q):
            if meant_as.get(tok.lower()) and word_is_dev(tok.lower()) != test:
                out.append(rnd.choice(meant_as[tok.lower()]))
                n += 1
            else:
                out.append(tok)
        return "".join(out), n
    wrong, right = [], []
    for q in b.questions:
        mq, n = misspell(q["q"])
        if n:
            wrong.append(dict(q, q=mq))
            right.append(q)
    sets = {"misspelled questions": wrong, "the same, spelled right": right, "all questions as written": b.questions}
    res: dict = {}
    for on in (False, True):
        ix.speller = sp if on else None
        ts: list[float] = []
        for s, qs in sets.items():
            out = []
            for q in qs:
                t0 = time.perf_counter()
                r = [i for i, _, _ in ix.search(q["q"], limit=50)]
                ts.append(1000 * (time.perf_counter() - t0))
                out.append(bench.per_query(r, q["gold"])["mrr"])
            res[on, s] = np.array(out)
        print(f"correction {'on ' if on else 'off'}: median search {statistics.median(ts):.0f} ms")
    for s, qs in sets.items():
        a, c = res[False, s], res[True, s]
        lo, hi = bench.bootstrap_ci(c - a)
        print(f"{s:28} n={len(qs):4}  off {a.mean():.3f}  on {c.mean():.3f}  "
              f"{c.mean() - a.mean():+.3f} [{lo:+.3f}, {hi:+.3f}]  p={bench.paired_p(a, c):.4f}")


if __name__ == "__main__":
    main()
