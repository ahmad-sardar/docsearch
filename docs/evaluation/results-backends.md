# The models on the processor (numpy) vs the Apple GPU (MLX)

Windows, Linux and Intel Macs have no MLX, so there both models run on the processor
(`docsearch/cpu.py`): the same model files and computations, in 32-bit floats (MLX runs
the reranker in bfloat16). The question here is not which is better, only whether the
processor version searches as well. Both ran the product's own search and `search ai` on
every dev question, on the same Mac (Apple M4, 10 cores), one after the other:
`eval/backends.py`.

## Outputs

- Meaning model: the same vectors (cosine 0.99999998 on test sentences).
- AI model: the same scores to bfloat16 rounding (e.g. 2.55 vs 2.63, -9.68 vs -9.50 for
  yes-minus-no).

## Search (dev split, 344 questions)

| search | MLX MRR@10 | numpy MRR@10 | numpy − MLX [95% CI] | p | same top 10 | median ms MLX | median ms numpy |
|---|---|---|---|---|---|---|---|
| plain | 0.346 | 0.346 | +0.0001 [+0.0000, +0.0004] | 0.49 | 84% | 52 | 52 |
| ai | 0.408 | 0.408 | +0.0007 [-0.0006, +0.0023] | 0.40 | 42% | 2,656 | 6,511 |

95% bootstrap intervals (10,000 resamples), paired randomization tests (10,000 sign
flips). No difference in quality: the intervals sit within ±0.003 of zero. The top 10
often differs in order (near-ties broken differently by the rounding), not in how often
the right entry is near the top.

Peak memory of the whole process: MLX 2.6 GB, numpy 2.8 GB (the reranker's 4-bit weights
are unpacked to floats once, about 2 GB).

Speed: plain search is the same. `search ai` takes 2.5x as long on this Mac's processor
(6.5 s median, 20 results read); on other processors it depends on their speed and cores.
