"""Usability: does the search give the answer a person wants, where they would look?

    .venv/bin/python eval/usability.py [--data DIR] [--ai] [--out eval/results-usability.md]

Each question in eval/usability.json is asked as a person would ask it (the package they
search, plain search or `search how`), and the rank of the first result whose name holds the
answer they want is kept (top 50). Reported: answered first, in the top 3, in the top 5, not
in the top 50, by mode and by package; and each question's rank, so a change shows which
questions it helped or hurt. No statistics here: these are a few dozen questions to read, not a
benchmark (that is eval/organized.py and bench.py).
"""
from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, help="a data folder (default: yours)")
    ap.add_argument("--ai", action="store_true", help="rank with the AI model too")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--json", type=Path, help="each question's rank, to compare runs")
    a = ap.parse_args()
    if a.data:
        os.environ["DOCSEARCH_DATA"] = str(a.data)
    from docsearch import web
    lib = web.Library()
    groups = {sid.split("@")[0]: sid for sid in lib.default}
    qs = json.loads((HERE / "usability.json").read_text())["questions"]
    rows, t0 = [], time.time()
    for q in qs:
        if q["package"] and q["package"] not in groups:
            continue
        srcs = {groups[q["package"]]} if q["package"] else set()
        project = ({g: sid.split("@")[1] for g, sid in groups.items()          # (a project in that
                    if "@" in sid and web.language_of(g) == q["language"]} if q.get("language") else None)  # language)
        got = lib.search(q["q"], srcs, 0, 50, ai=a.ai, mode=q["mode"], project=project)
        want = [w.lower() for w in q["want"]]
        rank = next((k for k, it in enumerate(got["items"], 1) if any(w in it["name"].lower() for w in want)), None)
        rows.append({**q, "rank": rank, "first": got["items"][0]["name"] if got["items"] else None,
                     "mode_used": got["mode"]})
    lines = [f"## Usability ({time.strftime('%Y-%m-%d')}, {a.data or 'your data'}{', with AI' if a.ai else ''})", "",
             f"{len(rows)} questions in {time.time() - t0:.0f} s. A question counts as answered at #1, in the top 3, "
             "in the top 5, or missing (not in the top 50).", ""]

    def table(title: str, by) -> None:
        groups_: dict[str, list] = defaultdict(list)
        for r in rows:
            groups_[by(r)].append(r)
        lines.extend([f"### {title}", "", "| | questions | #1 | top 3 | top 5 | missing |", "|---|---|---|---|---|---|"])
        for key in sorted(groups_):
            rs = groups_[key]
            n = len(rs)
            count = lambda k: sum(1 for r in rs if r["rank"] and r["rank"] <= k)     # noqa: E731
            lines.append(f"| {key} | {n} | {count(1)} | {count(3)} | {count(5)} | {sum(1 for r in rs if not r['rank'])} |")
        lines.append("")
    table("By mode", lambda r: r["mode"])
    table("By package", lambda r: r["package"] or "all packages")
    lines.extend(["### Each question", "", "| package | mode | question | rank | first result |", "|---|---|---|---|---|"])
    for r in rows:
        lines.append(f"| {r['package'] or 'all'} | {r['mode']} | {r['q']}{' (new)' if r.get('new') else ''} | "
                     f"{r['rank'] or '—'} | {(r['first'] or '')[:60]} |")
    text = "\n".join(lines) + "\n"
    print(text)
    if a.out:
        a.out.write_text(text)
    if a.json:
        a.json.write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
