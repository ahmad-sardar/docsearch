# Organized docs: search before and after (eval/organized.py)

Measured 2026-10-12 on the dev split, with c@23, cpp@23, numpy@2.5, pandas@3.0.6, polars@2.0.0 and
python@3.15: `before` as they were downloaded, `organized` the same copies after the one-time
organizing (docsearch/organize.py). The test split is run once, after the last phase.

The name lookups' -0.020 is one question: "Series.head" (polars') is second behind
pandas.Series.head, an exact name too; they were in the other order before.


### All questions  (n = 144 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.342 [0.273, 0.412] | baseline | 0.240 | 0.26 | 0.46 | 0.54 | 0.75 | 0.258 | 0 / 0 | 0.0 |
| organized | 0.350 [0.283, 0.420] | +0.009 (p=0.3407) | 0.245 | 0.27 | 0.47 | 0.56 | 0.78 | 0.307 | 0 / 0 | 0.0 |

### Stack Overflow questions  (n = 113 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.224 [0.162, 0.288] | baseline | 0.095 | 0.14 | 0.35 | 0.44 | 0.69 | 0.114 | 0 / 0 | 0.0 |
| organized | 0.240 [0.176, 0.307] | +0.016 (p=0.1175) | 0.106 | 0.16 | 0.36 | 0.46 | 0.73 | 0.178 | 0 / 0 | 0.0 |

### Stack Overflow questions whose answer is learn  (n = 1 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.000 [0.000, 0.000] | baseline | 0.000 | 0.00 | 0.00 | 0.00 | 1.00 | 0.000 | 0 / 0 | 0.0 |
| organized | 0.000 [0.000, 0.000] | +0.000 (p=1.0000) | 0.000 | 0.00 | 0.00 | 0.00 | 1.00 | 0.000 | 0 / 0 | 0.0 |

### Stack Overflow questions whose answer is do  (n = 13 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.262 [0.092, 0.464] | baseline | 0.030 | 0.15 | 0.31 | 0.62 | 0.77 | 0.084 | 0 / 0 | 0.0 |
| organized | 0.312 [0.137, 0.516] | +0.049 (p=0.1252) | 0.040 | 0.15 | 0.46 | 0.69 | 0.77 | 0.130 | 0 / 0 | 0.0 |

### Stack Overflow questions whose answer is lookup  (n = 95 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.230 [0.163, 0.303] | baseline | 0.108 | 0.15 | 0.37 | 0.44 | 0.71 | 0.124 | 0 / 0 | 0.0 |
| organized | 0.243 [0.172, 0.319] | +0.013 (p=0.2983) | 0.120 | 0.17 | 0.37 | 0.45 | 0.75 | 0.194 | 0 / 0 | 0.0 |

### Stack Overflow questions whose answer is understand  (n = 1 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.000 [0.000, 0.000] | baseline | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | 0 / 0 | 0.0 |
| organized | 0.000 [0.000, 0.000] | +0.000 (p=1.0000) | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | 0 / 0 | 0.0 |

### Stack Overflow questions whose answer is removed  (n = 3 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.000 [0.000, 0.000] | baseline | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | 0 / 0 | 0.0 |
| organized | 0.000 [0.000, 0.000] | +0.000 (p=1.0000) | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | 0 / 0 | 0.0 |

### Idea questions  (n = 6 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.118 [0.021, 0.229] | baseline | 0.118 | 0.00 | 0.33 | 0.50 | 0.83 | 0.098 | 0 / 0 | 0.0 |
| organized | 0.099 [0.024, 0.182] | -0.019 (p=0.5055) | 0.099 | 0.00 | 0.33 | 0.50 | 0.83 | 0.139 | 0 / 0 | 0.0 |

### Name lookups  (n = 25 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.928 [0.844, 1.000] | baseline | 0.928 | 0.88 | 1.00 | 1.00 | 1.00 | 0.946 | 0 / 0 | 0.0 |
| organized | 0.908 [0.816, 0.980] | -0.020 (p=1.0000) | 0.908 | 0.84 | 1.00 | 1.00 | 1.00 | 0.931 | 0 / 0 | 0.0 |

## Phase 2: official guides added (polars' user guide, numpy's tutorials)

`before`: organized, without guides; `organized`: the same, with the guides their docs link.
Questions are asked of all packages at once, as plain search does now: the guides' how-to pages
(polars' "JSON files") come before other packages' reference answers (json.dump). Phase 3 keeps
guides out of plain search (what) and in `search how`.


### All questions  (n = 141 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.357 [0.289, 0.429] | baseline | 0.250 | 0.28 | 0.48 | 0.57 | 0.79 | 0.314 | 0 / 0 | 0.0 |
| organized | 0.348 [0.280, 0.416] | -0.009 (p=0.2355) | 0.246 | 0.26 | 0.46 | 0.56 | 0.79 | 0.307 | 0 / 0 | 0.0 |

### Stack Overflow questions  (n = 110 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.246 [0.181, 0.316] | baseline | 0.108 | 0.16 | 0.37 | 0.47 | 0.75 | 0.183 | 0 / 0 | 0.0 |
| organized | 0.231 [0.168, 0.300] | -0.015 (p=0.0051) | 0.101 | 0.15 | 0.35 | 0.45 | 0.74 | 0.171 | 0 / 0 | 0.0 |

### Stack Overflow questions whose answer is learn  (n = 1 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.000 [0.000, 0.000] | baseline | 0.000 | 0.00 | 0.00 | 0.00 | 1.00 | 0.000 | 0 / 0 | 0.0 |
| organized | 0.000 [0.000, 0.000] | +0.000 (p=1.0000) | 0.000 | 0.00 | 0.00 | 0.00 | 1.00 | 0.000 | 0 / 0 | 0.0 |

### Stack Overflow questions whose answer is do  (n = 13 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.312 [0.138, 0.509] | baseline | 0.040 | 0.15 | 0.46 | 0.69 | 0.77 | 0.130 | 0 / 0 | 0.0 |
| organized | 0.302 [0.123, 0.508] | -0.010 (p=0.5020) | 0.032 | 0.15 | 0.46 | 0.62 | 0.77 | 0.106 | 0 / 0 | 0.0 |

### Stack Overflow questions whose answer is lookup  (n = 95 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.243 [0.172, 0.319] | baseline | 0.120 | 0.17 | 0.37 | 0.45 | 0.75 | 0.194 | 0 / 0 | 0.0 |
| organized | 0.226 [0.159, 0.299] | -0.016 (p=0.0164) | 0.112 | 0.15 | 0.34 | 0.44 | 0.74 | 0.184 | 0 / 0 | 0.0 |

### Stack Overflow questions whose answer is understand  (n = 1 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.000 [0.000, 0.000] | baseline | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | 0 / 0 | 0.0 |
| organized | 0.000 [0.000, 0.000] | +0.000 (p=1.0000) | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | 0 / 0 | 0.0 |

### Idea questions  (n = 6 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.099 [0.024, 0.182] | baseline | 0.099 | 0.00 | 0.33 | 0.50 | 0.83 | 0.139 | 0 / 0 | 0.0 |
| organized | 0.162 [0.037, 0.310] | +0.063 (p=0.5045) | 0.162 | 0.00 | 0.33 | 0.67 | 0.83 | 0.196 | 0 / 0 | 0.0 |

### Name lookups  (n = 25 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.908 [0.816, 0.980] | baseline | 0.908 | 0.84 | 1.00 | 1.00 | 1.00 | 0.931 | 0 / 0 | 0.0 |
| organized | 0.908 [0.816, 0.980] | +0.000 (p=1.0000) | 0.908 | 0.84 | 1.00 | 1.00 | 1.00 | 0.931 | 0 / 0 | 0.0 |
