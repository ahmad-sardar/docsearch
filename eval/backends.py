"""Do the models give the same search on the processor (numpy, cpu.py) as on the Apple GPU
(MLX)? The product's own search and AI reordering, on the benchmark questions, once per
backend; then the two compared question by question.

    .venv/bin/python eval/backends.py run --split dev                         (MLX)
    DOCSEARCH_BACKEND=numpy .venv/bin/python eval/backends.py run --split dev (numpy)
    .venv/bin/python eval/backends.py compare --split dev

Saved in eval/runs/<split>/backend-<mlx|numpy>.json (resumable). Reported: MRR@10 of the
normal search and of search ai, the difference with a 95% bootstrap interval and a paired
randomization test, how often the top 10 is identical, latency and peak memory.
"""
from __future__ import annotations

import argparse
import json
import resource
import statistics
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from docsearch import cli, rerank  # noqa: E402

import bench  # noqa: E402

RUNS = HERE / "runs"


def run(split: str) -> None:
    import run as runner
    name = "mlx" if cli.use_mlx() else "numpy"
    out = RUNS / split / f"backend-{name}.json"
    done = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    b = runner.Bench(split)
    model = rerank.get()
    model.scores("warm up", ["warm up"])
    ix = b.index
    for n, q in enumerate(b.questions):
        if q["q"] in done:
            continue
        t0 = time.perf_counter()
        ids = [i for i, _, _ in ix.search(q["q"], limit=cli.SHOW)]
        t1 = time.perf_counter()
        s = model.scores(q["q"], [runner.doc_text(ix.entries[i]) for i in ids[:rerank.TOP]])
        ai = rerank.reorder(ids, s, set(ix.rank_name(q["q"])[0]))
        t2 = time.perf_counter()
        done[q["q"]] = {"plain": ids[:50], "ai": ai[:50], "ms_plain": 1000 * (t1 - t0), "ms_ai": 1000 * (t2 - t0)}
        if n % 10 == 0 or n == len(b.questions) - 1:
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1e9 if sys.platform == "darwin" else 1e6)
            done["_peak_gb"] = peak
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(done), encoding="utf-8")
            print(f"{name}: {n + 1}/{len(b.questions)}  peak {peak:.1f} GB", flush=True)


def compare(split: str) -> None:
    import run as runner
    b = runner.Bench(split)
    r = {k: json.loads((RUNS / split / f"backend-{k}.json").read_text(encoding="utf-8")) for k in ("mlx", "numpy")}
    qs = [q for q in b.questions if all(q["q"] in r[k] for k in r)]
    print(f"{split}: {len(qs)} questions run with both backends\n")
    print("| search | MLX MRR@10 | numpy MRR@10 | numpy − MLX [95% CI] | p | same top 10 | "
          "median ms MLX | median ms numpy |\n|---|---|---|---|---|---|---|---|")
    for mode in ("plain", "ai"):
        m = {k: np.array([bench.per_query(r[k][q["q"]][mode], q["gold"])["mrr"] for q in qs]) for k in r}
        lo, hi = bench.bootstrap_ci(m["numpy"] - m["mlx"])
        same = np.mean([r["mlx"][q["q"]][mode][:10] == r["numpy"][q["q"]][mode][:10] for q in qs])
        ms = {k: statistics.median(r[k][q["q"]][f"ms_{mode}"] for q in qs) for k in r}
        print(f"| {mode} | {m['mlx'].mean():.3f} | {m['numpy'].mean():.3f} | "
              f"{m['numpy'].mean() - m['mlx'].mean():+.4f} [{lo:+.4f}, {hi:+.4f}] | "
              f"{bench.paired_p(m['mlx'], m['numpy']):.3f} | {100 * same:.0f}% | {ms['mlx']:.0f} | {ms['numpy']:.0f} |")
    print(f"\npeak memory (whole process): MLX {r['mlx'].get('_peak_gb', 0):.1f} GB, "
          f"numpy {r['numpy'].get('_peak_gb', 0):.1f} GB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "compare"])
    ap.add_argument("--split", default="dev")
    a = ap.parse_args()
    (run if a.cmd == "run" else compare)(a.split)
