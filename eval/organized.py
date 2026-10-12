"""Search before and after the docs are organized (docsearch/organize.py), on the same questions.

    .venv/bin/python eval/organized.py --before data --after /tmp/organized-data --split dev

Two data folders, the same packages: `before` as the docs were, `after` organized (release
notes and development pages removed, sub-parts folded). The same questions are asked of both
(Stack Overflow, ideas, names: eval/bench.py), each answered by the entries of its own index:
- a Stack Overflow question whose linked page was removed has no answer after: it counts 0,
  the honest cost of removing it;
- a name lookup's answer is the same API entry in both (API entries are never removed).

Stack Overflow questions are also reported by the purpose of the page they link to (learn,
do, look up, understand; "removed"). Statistics as in bench.py: MRR@10 with 95% bootstrap
intervals, paired randomization tests, Holm-corrected.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from docsearch import cli  # noqa: E402

import bench  # noqa: E402

DEPTH = 50


def index_of(data: Path):
    """One copy of each package in a data folder, as the search page has them."""
    cli.DATA, cli.HOME = data, data / "index"
    sids = sorted(cli.in_use(g)[0] or have[0] for g, have in cli.groups().items())
    index = cli.Index(sids, "hybrid")
    index.search("warm up")
    return index, [cli.source_id(e.source).split("@")[0] for e in index.entries]


def questions(before, before_sid, after, after_sid, split: str) -> list[dict]:
    """Each question with its answers in both indexes."""
    qa, _ = bench.load_questions(before, before_sid)
    qb, _ = bench.load_questions(after, after_sid)
    later = {(q["set"], q["q"]): q for q in qb if q["set"] != "names"}
    where = {(after_sid[i], e.location, e.title): i for i, e in enumerate(after.entries)}
    out = []
    for q in qa:
        if q["split"] != split:
            continue
        if q["set"] == "names":
            (i, g), = q["gold"].items()
            e = before.entries[i]
            j = where.get((before_sid[i], e.location, e.title))
            gold_after = {j: g} if j is not None else {}
        else:
            gold_after = (later.get((q["set"], q["q"])) or {}).get("gold", {})
        out.append({**q, "gold_after": gold_after, "purpose": purpose(after, gold_after)})
    return out


def purpose(index, gold: dict[int, int]) -> str:
    """The purpose of the entries that answer a question after (the best graded first)."""
    if not gold:
        return "removed"
    best = max(gold.values())
    return Counter(index.entries[i].purpose or "?" for i, g in gold.items() if g == best).most_common(1)[0][0]


def complete_first(index, weight: float):
    """How mode, with complete examples (docsearch/examples.py) given one more vote of
    `weight` in the fusion: does preferring them find the answers sooner?"""
    from docsearch import examples
    done: dict[int, bool] = {}

    def ok(i: int) -> bool:
        if i not in done:
            e = index.entries[i]
            name = cli.source_id(e.source).split("@")[0]
            r = examples.needs(index.full_text(i), "cpp" if name in ("cpp", "c") else "", name) \
                if e.kind == "example" or "```" in e.text else None
            done[i] = bool(r and r.get("complete"))
        return done[i]

    def search(q: str, limit: int, mode: str | None = None):
        hits = [i for i, _, _ in index.search(q, limit=200, mode="how")]
        return cli.rrf([("how", hits, 1.0), ("complete", [i for i in hits if ok(i)], weight)])[:limit]
    return search


def rows(index, qs: list[dict], key: str, mode: str | None = None, search=None) -> list[dict]:
    out = []
    for q in qs:
        ranked = [i for i, _, _ in (search or index.search)(q["q"], limit=DEPTH, mode=mode)]
        out.append(bench.per_query(ranked, q[key]) | {"recall50": float(any(q[key].get(i, 0) >= 1 for i in ranked))})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", type=Path, default=cli.DATA)
    ap.add_argument("--after", type=Path, required=True)
    ap.add_argument("--split", default="dev", choices=["dev", "test"])
    ap.add_argument("--out", type=Path)
    ap.add_argument("--mode", choices=["what", "how"], help="the kind of search asked of --after (cli.MODES)")
    ap.add_argument("--modes", action="store_true",
                    help="on --after only: plain search as it was (all entries) against what and how (cli.MODES)")
    a = ap.parse_args()
    after, after_sid = index_of(a.after)
    if a.modes:
        qs = [{**q, "gold_after": q["gold"], "purpose": purpose(after, q["gold"])}
              for q in bench.load_questions(after, after_sid)[0] if q["split"] == a.split]
        runs = [{"name": name, "rows": rows(after, qs, "gold_after", mode), "ms_p50": 0, "ms_p95": 0}
                for name, mode in (("before", None), ("what", "what"), ("how", "how"))]
        runs += [{"name": f"how+complete{w:g}", "rows": rows(after, qs, "gold_after", "how", complete_first(after, w)),
                  "ms_p50": 0, "ms_p95": 0} for w in (0.5, 1.0)]
    else:
        before, before_sid = index_of(a.before)
        qs = questions(before, before_sid, after, after_sid, a.split)
        runs = [{"name": "before", "rows": rows(before, qs, "gold"), "ms_p50": 0, "ms_p95": 0},
                {"name": "organized", "rows": rows(after, qs, "gold_after", a.mode), "ms_p50": 0, "ms_p95": 0}]
    out = [f"## {'What and how' if a.modes else 'Organized docs'}, {a.split} split\n"]
    groups = [("All questions", lambda q: True),
              ("Stack Overflow questions", lambda q: q["set"] == "so")]
    groups += [(f"Stack Overflow questions whose answer is {p}", lambda q, p=p: q["set"] == "so" and q["purpose"] == p)
               for p in ("learn", "do", "lookup", "understand", "removed")]
    groups += [("Idea questions", lambda q: q["set"] == "ideas"), ("Name lookups", lambda q: q["set"] == "names")]
    for title, keep in groups:
        idx = [k for k, q in enumerate(qs) if keep(q)]
        if not idx:
            continue
        sub = [r | {"rows": [r["rows"][k] for k in idx]} for r in runs]
        out.append(bench.report(sub, [qs[k] for k in idx], "before", title))
    text = "\n".join(out)
    print(text)
    if a.out:
        a.out.write_text(text)
        (a.out.with_suffix(".json")).write_text(json.dumps(
            [{"q": q["q"], "set": q["set"], "source": q["source"], "purpose": q["purpose"],
              **{r["name"]: r["rows"][k]["mrr"] for r in runs}, "after": runs[1]["rows"][k]["mrr"]}
             for k, q in enumerate(qs)]))


if __name__ == "__main__":
    main()
