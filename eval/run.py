"""Run systems on the benchmark questions and write the report.

    .venv/bin/python eval/run.py --split dev  --systems baseline,bge,qwen-emb ...
    .venv/bin/python eval/run.py --split test --systems ...      (final numbers)
    .venv/bin/python eval/run.py --report                          (tables from saved runs)

Each system's per-question results are saved in eval/runs/<split>/<system>.json, so a long
run can stop and resume, and the report is rebuilt from saved results without re-running.
Models load from the Hugging Face cache given by HF_HOME (downloaded beforehand); this
script itself never goes online.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from docsearch import cli  # noqa: E402

import bench  # noqa: E402

RUNS = HERE / "runs"
CACHE = HERE / "cache"
FIRST = 50          # candidates kept from the first stage
RERANK_K = 20       # how many of them a reranker reads


def doc_text(e) -> str:
    return f"{cli.api_name(e.title)} ({e.kind}, {e.source})\n{cli.plain(e.text)[:1200]}"


TEST_MODELS = Path(os.environ.get("EVAL_MODELS", Path.home() / ".cache" / "huggingface" / "hub"))


def hf_path(repo: str) -> str:
    """A downloaded model: the test-model folder, else the user's own Hugging Face cache."""
    for cache in (TEST_MODELS, Path.home() / ".cache" / "huggingface" / "hub"):
        snaps = sorted((cache / f"models--{repo.replace('/', '--')}" / "snapshots").glob("*"))
        if snaps:
            return str(snaps[-1])           # the folder itself (a partial download is fine)
    raise SystemExit(f"model not downloaded: {repo}")


RERANKERS = {
    "rr-qwen3-0.6b-4bit": ("QwenReranker", "mlx-community/Qwen3-Reranker-0.6B-4bit"),
    "rr-qwen3-0.6b-8bit": ("QwenReranker", "mlx-community/Qwen3-Reranker-0.6B-mxfp8"),
    "rr-qwen3-4b-8bit": ("QwenReranker", "mlx-community/Qwen3-Reranker-4B-mxfp8"),
    "judge-qwen3-1.7b-4bit": ("ChatJudge", "mlx-community/Qwen3-1.7B-4bit"),
    "judge-llama3.2-1b-4bit": ("ChatJudge", "mlx-community/Llama-3.2-1B-Instruct-4bit"),
    "judge-gemma3-1b-4bit": ("ChatJudge", "mlx-community/gemma-3-1b-it-qat-4bit"),
    "judge-gemma4-e4b-4bit": ("ChatJudge", "mlx-community/gemma-4-e4b-it-qat-4bit"),
}


class Bench:
    def __init__(self, split: str):
        sids = sorted(cli.in_use(g)[0] or have[0] for g, have in cli.groups().items())   # one copy each
        self.index = cli.Index(sids, "hybrid")
        self.index.search("warm up")
        self.sid_of = [cli.source_id(e.source).split("@")[0] for e in self.index.entries]   # the package
        qs, dropped = bench.load_questions(self.index, self.sid_of)
        self.questions = [q for q in qs if q["split"] == split]
        self.split, self.dropped = split, dropped
        self.texts = None
        self.saved: dict[str, tuple[Path, dict]] = {}

    # ---- first stages ---------------------------------------------------------------
    def baseline(self, q):
        return [i for i, _, _ in self.index.search(q, limit=FIRST)]

    def vectors(self, name: str) -> np.ndarray:
        """Entry vectors, computed once in a separate process (its GPU memory is freed when
        it exits) and cached."""
        import subprocess
        CACHE.mkdir(exist_ok=True)
        f = CACHE / f"{name}-{len(self.index.entries)}.npy"
        if not f.exists():
            subprocess.run([sys.executable, str(HERE / "embed.py"), name, str(f)], check=True)
        V = np.load(f)
        assert len(V) == len(self.index.entries), "vectors and index differ: delete eval/cache"
        return V

    def dense(self, V, embed_query):
        def rank(q):
            s = V @ embed_query(q)
            top = np.argpartition(-s, FIRST)[:FIRST]
            return [int(i) for i in top[np.argsort(-s[top])]]
        return rank

    def hybrid(self, dense_rank):
        """The production pipeline (names, spelling, words) with another meaning ranker."""
        def rank(q):
            orig = self.index.rank_meaning
            self.index.rank_meaning = dense_rank
            try:
                return [i for i, _, _ in self.index.search(q, limit=FIRST)]
            finally:
                self.index.rank_meaning = orig
        return rank

    # ---- second stages: a model scores the first stage's top candidates ----------------
    def scored(self, key: str, first, score, k: int):
        """Order the first stage's top k by score(q, candidates). The scores are saved in
        eval/cache/scores-<key>.json, so other ways of combining them with the first stage
        (VARIANTS, `--derive`) are measured without running the model again."""
        f = CACHE / f"scores-{key}.json"
        saved = json.loads(f.read_text()) if f.exists() else {}
        self.saved[key] = (f, saved)

        def rank(q):
            if q not in saved:
                t = time.perf_counter()
                cand = first(q)
                s = score(q, cand[:k])
                saved[q] = {"cand": cand, "s": [float(x) for x in s], "ms": 1000 * (time.perf_counter() - t)}
                if len(saved) % 25 == 0:
                    f.write_text(json.dumps(saved))
            c = saved[q]
            return combine(c["cand"], c["s"], set(), "")
        return rank

    def rescore(self, key, first):
        """Qwen3-Embedding on the first stage's 50 candidates only (cheap: no index build)."""
        from models import QwenEmbedder
        m = QwenEmbedder(hf_path("mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ"), batch=50)

        def score(q, cand):
            V = m._embed([f"{cli.api_name(self.index.entries[i].title)}\n"
                          f"{cli.plain(self.index.entries[i].text)[:cli.EMBED_CHARS]}" for i in cand], 64)
            return V @ m.query(q)
        return self.scored(key, first, score, FIRST)

    def rerank(self, key, first, model, k=RERANK_K):
        return self.scored(key, first, lambda q, cand: model.score(q, [doc_text(self.index.entries[i]) for i in cand]), k)


# Ways to combine a model's scores with the first stage's order (chosen on the dev split):
#   pin     results whose API name is exactly the query (np.sum, Vec::push) stay first, in
#           the first stage's order; the model orders the rest
#   fuseW   reciprocal rank fusion of the model's order (weight 1) and the first stage's
#           order (weight W), as the first stage itself fuses its rankers
VARIANTS = ["pin", "fuse0.5", "fuse1", "fuse2", "pin+fuse0.5", "pin+fuse1"]


def combine(cand: list[int], s: list[float], exact: set[int], variant: str) -> list[int]:
    """The search page's own reorder (docsearch/rerank.py), with this variant's settings."""
    from docsearch import rerank
    parts = variant.split("+")
    fuse = next((float(x[4:]) for x in parts if x.startswith("fuse")), None)
    return rerank.reorder(cand, s, exact, pin="pin" in parts, fuse=fuse)


SCORED = set(RERANKERS) | {"rescore-qwen-emb"}       # systems whose scores are cached


def cache_key(name: str) -> str:
    first = os.environ.get("FIRST", "baseline")
    return name if first == "baseline" else f"{name}@{first}"


def scores_complete(name: str, qs: list[dict]) -> bool:
    f = CACHE / f"scores-{cache_key(name)}.json"
    if name not in SCORED:
        return True
    return f.exists() and all(q["q"] in json.loads(f.read_text()) for q in qs)


def systems(b: Bench, names: list[str]) -> dict:
    """Build only the systems asked for (models are large)."""
    out = {}
    lazy = {}

    def bge():
        if "bge" not in lazy:
            from sentence_transformers import SentenceTransformer
            V = b.vectors("bge-small")
            m = SentenceTransformer(hf_path("BAAI/bge-small-en-v1.5"), device="cpu", local_files_only=True)
            qf = lambda q: m.encode(["Represent this sentence for searching relevant passages: " + q],  # noqa: E731
                                    normalize_embeddings=True, show_progress_bar=False)[0]
            lazy["bge"] = b.dense(V, qf)
        return lazy["bge"]

    def qwen_emb():
        if "qe" not in lazy:
            from models import QwenEmbedder
            V = b.vectors("qwen3-emb")
            m = QwenEmbedder(hf_path("mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ"), batch=64)
            lazy["qe"] = b.dense(V, m.query)
        return lazy["qe"]

    def first_stage():                                   # chosen on dev (see results.md)
        return b.hybrid(bge()) if os.environ.get("FIRST", "baseline") == "hybrid-bge" else b.baseline

    makers = {
        "baseline": lambda: b.baseline,
        "bge": bge,
        "hybrid-bge": lambda: b.hybrid(bge()),
        "qwen-emb": qwen_emb,
        "rescore-qwen-emb": lambda: b.rescore(cache_key("rescore-qwen-emb"), first_stage()),
        "hybrid-qwen-emb": lambda: b.hybrid(qwen_emb()),
    }
    for n in names:
        if n in makers:
            out[n] = makers[n]
        elif n in RERANKERS:
            cls, repo = RERANKERS[n]

            def make(n=n, cls=cls, repo=repo):
                import models
                return b.rerank(cache_key(n), first_stage(), getattr(models, cls)(hf_path(repo)))
            out[n] = make
        else:
            raise SystemExit(f"unknown system {n}")
    return out


def run(split: str, names: list[str], limit: int | None) -> None:
    try:
        import mlx.core as mx
        mx.set_cache_limit(1 << 30)                    # MLX keeps at most 1 GB of freed memory
    except ImportError:
        pass
    b = Bench(split)
    qs = b.questions[:limit] if limit else b.questions
    print(f"{len(qs)} {split} questions (dropped as unmappable: {b.dropped})", flush=True)
    (RUNS / split).mkdir(parents=True, exist_ok=True)
    for name, make in systems(b, names).items():
        f = RUNS / split / f"{name}.json"
        if f.exists() and json.loads(f.read_text())["n"] == len(qs) and scores_complete(name, qs):
            print(f"  {name}: done before", flush=True)
            continue
        t = time.time()
        try:
            import mlx.core as mx
            mx.reset_peak_memory()
        except ImportError:
            mx = None
        res = bench.evaluate(name, make(), qs)
        res["peak_gpu_gb"] = mx.get_peak_memory() / 2**30 if mx else 0.0
        if cache_key(name) in b.saved:                 # the model's time, also for questions scored before
            f_s, saved = b.saved[cache_key(name)]
            f_s.write_text(json.dumps(saved))
            ms = [saved[q["q"]]["ms"] for q in qs]
            res["ms_p50"], res["ms_p95"] = statistics.median(ms), float(np.percentile(ms, 95))
        import gc
        gc.collect()
        try:                                           # give the reranker's GPU memory back
            import mlx.core as mx
            mx.clear_cache()
        except ImportError:
            pass
        res["n"] = len(qs)
        res["questions"] = [{"set": q["set"], "source": q["source"]} for q in qs]
        f.write_text(json.dumps(res))
        m = np.mean([r["mrr"] for r in res["rows"]])
        print(f"  {name:26} MRR@10 {m:.3f}   ({time.time() - t:.0f} s, p50 {res['ms_p50']:.0f} ms, "
              f"peak GPU memory {res['peak_gpu_gb']:.2f} GB)", flush=True)


def derive(split: str, only: list[str] | None = None) -> None:
    """Each scored system combined with the first stage in each of VARIANTS, from the saved
    scores (no model runs). Latency and memory are the scored system's own. `only`: write
    just these (e.g. the systems chosen on dev, for the test split)."""
    b = Bench(split)
    for name in sorted(SCORED):
        base, f = RUNS / split / f"{name}.json", CACHE / f"scores-{cache_key(name)}.json"
        if not base.exists() or not scores_complete(name, b.questions):
            continue
        res0, saved = json.loads(base.read_text()), json.loads(f.read_text())
        exact = {q["q"]: set(b.index.rank_name(q["q"])[0]) for q in b.questions}
        for v in VARIANTS:
            if only and f"{name}+{v}" not in only:
                continue
            rows = []
            for q in b.questions:
                ranked = combine(saved[q["q"]]["cand"], saved[q["q"]]["s"], exact[q["q"]], v)[:50]
                rows.append(bench.per_query(ranked, q["gold"])
                            | {"recall50": float(any(q["gold"].get(i, 0) >= 1 for i in ranked))})
            res = {k: res0[k] for k in ("ms_p50", "ms_p95", "peak_gpu_gb", "n", "questions")}
            (RUNS / split / f"{name}+{v}.json").write_text(json.dumps(res | {"name": f"{name}+{v}", "rows": rows}))
            print(f"  {name}+{v:12} MRR@10 {np.mean([r['mrr'] for r in rows]):.3f}", flush=True)


def report(split: str, baseline: str = "baseline", show: list[str] | None = None) -> str:
    runs = [json.loads(f.read_text()) for f in sorted((RUNS / split).glob("*.json"))]
    if show:                                           # only the systems chosen beforehand
        runs = [r for r in runs if r["name"] in show]
    if not runs:
        return "no runs"
    n = min(r["n"] for r in runs)
    runs = [r | {"rows": r["rows"][:n]} for r in runs]
    meta = runs[0]["questions"][:n]
    out = [f"## Results on the {split} split\n"]
    for title, keep in [("All questions", lambda m: True),
                        ("Stack Overflow questions (real, answer = linked docs)", lambda m: m["set"] == "so"),
                        ("Idea questions (hand-written)", lambda m: m["set"] == "ideas"),
                        ("Name lookups", lambda m: m["set"] == "names")]:
        idx = [k for k, m in enumerate(meta) if keep(m)]
        if not idx:
            continue
        sub = [r | {"rows": [r["rows"][k] for k in idx]} for r in runs]
        out.append(bench.report(sub, [meta[k] for k in idx], baseline, title))
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev", choices=["dev", "test"])
    ap.add_argument("--systems", default="baseline")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--derive", action="store_true", help="the VARIANTS of scored systems, from saved scores")
    ap.add_argument("--show", help="report only these systems (comma-separated)")
    a = ap.parse_args()
    if a.derive:
        derive(a.split, [n for n in a.systems.split(",") if "+" in n] or None)
    elif not a.report:
        run(a.split, a.systems.split(","), a.limit)
    text = report(a.split, show=a.show.split(",") if a.show else None)
    (HERE / f"results-{a.split}.md").write_text(text)
    print(text)
