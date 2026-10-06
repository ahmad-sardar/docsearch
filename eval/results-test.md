# Search with AI: the final numbers

The test split (753 questions never used for tuning), run once on 2026-10-06 with the
systems fixed beforehand in `PROTOCOL.md`. Dev results: `results-dev.md`.

**Chosen: Qwen3-Reranker-0.6B, 4-bit, reading the top 20 results, with exact API-name
matches kept first** (`rr-qwen3-0.6b-4bit+pin`, as in `docsearch/rerank.py`).

| | Normal search | With AI | Difference |
|---|---|---|---|
| All questions (753), MRR@10 | 0.351 [0.321, 0.382] | **0.415** [0.383, 0.446] | +0.063, p = 0.0003 (Holm) |
| Stack Overflow questions (575) | 0.206 | **0.280** | +0.074, p = 0.0003 |
| Idea questions (22) | 0.289 | 0.473 | +0.184, p = 0.12 (too few to be sure) |
| Name lookups (156) | 0.896 | 0.902 | +0.005, p = 1.0 (no change) |
| Right answer first (R@1, all) | 28% | 33% | |
| Questions better / worse / same | | 156 / 47 / 550 | |

- **The name guard**: the same model without it is significantly worse on name lookups
  (0.817 vs 0.902, p = 0.0002, paired) and identical on questions; with it, names are as
  good as normal search.
- **Speed and memory** (the search page itself, measured afterwards on an idle Mac, 20
  questions): normal search 381 ms median; with AI 2.84 s median, 3.0 s at most. The
  whole page (index, meaning model, AI model) uses 1.9 GB (peak 2.7 GB while loading),
  within the 4 GB budget.
- **Not chosen**: Qwen3-Embedding re-scoring (best other model on dev) brings nothing on
  test (0.350 vs 0.351); its dev advantage on idea questions did not hold (0.263 vs 0.289).
  The chat models used as judges (Qwen3-1.7B, Llama-3.2-1B, Gemma-3-1B) were worse than
  normal search on dev, or only slightly better at 2.6x the chosen model's time (`results-dev.md`).

## Full tables

### All questions  (n = 753 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 0.351 [0.321, 0.382] | baseline | 0.245 | 0.28 | 0.44 | 0.51 | 0.67 | 0.270 | 377 / 702 | 0.2 |
| rescore-qwen-emb+pin+fuse1 | 0.350 [0.320, 0.380] | -0.002 (p=0.8382) | 0.245 | 0.27 | 0.44 | 0.52 | 0.67 | 0.270 | 1371 / 1689 | 1.2 |
| rr-qwen3-0.6b-4bit+pin | 0.415 [0.383, 0.446] | +0.063 (p=0.0003) | 0.294 | 0.33 | 0.52 | 0.57 | 0.67 | 0.300 | 2862 / 3312 | 1.3 |
| rr-qwen3-0.6b-4bit | 0.397 [0.367, 0.428] | +0.046 (p=0.0003) | 0.277 | 0.31 | 0.52 | 0.57 | 0.67 | 0.286 | 2862 / 3312 | 1.3 |

### Stack Overflow questions (real, answer = linked docs)  (n = 575 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 0.206 [0.177, 0.234] | baseline | 0.067 | 0.14 | 0.29 | 0.38 | 0.57 | 0.096 | 377 / 702 | 0.2 |
| rescore-qwen-emb+pin+fuse1 | 0.206 [0.178, 0.234] | +0.001 (p=0.9646) | 0.069 | 0.13 | 0.30 | 0.40 | 0.57 | 0.099 | 1371 / 1689 | 1.2 |
| rr-qwen3-0.6b-4bit+pin | 0.280 [0.249, 0.313] | +0.074 (p=0.0003) | 0.122 | 0.20 | 0.39 | 0.45 | 0.57 | 0.132 | 2862 / 3312 | 1.3 |
| rr-qwen3-0.6b-4bit | 0.280 [0.248, 0.312] | +0.074 (p=0.0003) | 0.122 | 0.20 | 0.39 | 0.45 | 0.57 | 0.132 | 2862 / 3312 | 1.3 |

### Idea questions (hand-written)  (n = 22 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 0.289 [0.139, 0.456] | baseline | 0.289 | 0.18 | 0.41 | 0.50 | 0.82 | 0.162 | 377 / 702 | 0.2 |
| rescore-qwen-emb+pin+fuse1 | 0.263 [0.116, 0.431] | -0.027 (p=0.7049) | 0.263 | 0.18 | 0.32 | 0.50 | 0.82 | 0.159 | 1371 / 1689 | 1.2 |
| rr-qwen3-0.6b-4bit+pin | 0.473 [0.295, 0.655] | +0.184 (p=0.1155) | 0.473 | 0.36 | 0.64 | 0.64 | 0.82 | 0.228 | 2862 / 3312 | 1.3 |
| rr-qwen3-0.6b-4bit | 0.473 [0.292, 0.652] | +0.184 (p=0.1155) | 0.473 | 0.36 | 0.64 | 0.64 | 0.82 | 0.228 | 2862 / 3312 | 1.3 |

### Name lookups  (n = 156 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 0.896 [0.863, 0.928] | baseline | 0.896 | 0.81 | 0.99 | 1.00 | 1.00 | 0.923 | 377 / 702 | 0.2 |
| rescore-qwen-emb+pin+fuse1 | 0.890 [0.853, 0.924] | -0.006 (p=0.9963) | 0.890 | 0.80 | 0.99 | 0.99 | 1.00 | 0.917 | 1371 / 1689 | 1.2 |
| rr-qwen3-0.6b-4bit+pin | 0.902 [0.868, 0.933] | +0.005 (p=1.0000) | 0.902 | 0.81 | 1.00 | 1.00 | 1.00 | 0.927 | 2862 / 3312 | 1.3 |
| rr-qwen3-0.6b-4bit | 0.817 [0.774, 0.859] | -0.079 (p=0.0012) | 0.817 | 0.69 | 0.99 | 1.00 | 1.00 | 0.863 | 2862 / 3312 | 1.3 |
