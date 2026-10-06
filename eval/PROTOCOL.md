# How the AI model is chosen

Written on 2026-10-06, before the dev results of the judge models and of the ways of
combining scores (`VARIANTS` in `run.py`) were known, and before any AI model was run on
the test split.

## Data

- 1,012 Stack Overflow questions whose accepted answer links to the official docs, 30
  hand-written idea questions, and lookups by name sampled from the index.
- Split once by a hash of the question: 30% dev, 70% test. Everything is tuned on dev
  (models, prompts, how many results the model reads, how its scores are combined). The
  test split is used once, for the final numbers.

## Systems on dev

- `baseline`: the normal search (names, spelling, words, meaning, fused).
- Rerankers that read the top 20 results: Qwen3-Reranker-0.6B (4-bit, 8-bit), and chat
  models asked "does this entry answer the question? yes/no": Qwen3-1.7B, Llama-3.2-1B and
  Gemma-3-1B (4-bit). Also Qwen3-Embedding-0.6B re-scoring the top 50.
- Each scored system with each variant: `pin` (results whose API name is exactly the
  query stay first), `fuseW` (rank fusion of the model's order with the normal order,
  weight W), and both together.
- Dropped for the memory budget or time: Qwen3-Reranker-4B and Gemma-4-E4B.

## Choice (fixed before looking at the test split)

1. Only systems whose whole search page fits in 4 GB (the model's peak GPU memory plus the
   index), and whose median latency is under 5 s on this Mac.
2. Among those, the highest MRR@10 on all dev questions. If two are within 0.005, the
   faster one.
3. Name lookups must not get worse: a system whose dev MRR@10 on name lookups is below
   the baseline's by more than 0.01 is not chosen.

## Test

Run once on the test split: `baseline`, the chosen system, the same model without the
chosen variant (to measure the variant), and the best dev system that uses a different
model. Reported: MRR@10 with 95% bootstrap intervals (10,000 resamples), paired
randomization tests against the baseline (10,000 sign flips), p-values Holm-corrected
for those three comparisons, per question set (Stack Overflow, ideas, names), latency
p50/p95 and peak GPU memory. The test numbers do not change the choice.
