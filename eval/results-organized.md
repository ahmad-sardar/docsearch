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

## Phase 3: plain search (what) and search how, on the organized docs with guides

`before`: plain search over every entry (as phases 1 and 2 had it); `what`: look up and understand
entries only; `how`: learn and do only. `how` has no reference entries yet (phase 4 adds the
examples of API entries), so reference-answer questions and names are not its questions. Asked in
its matching mode (reference answers: what; how-to answers: how), the Stack Overflow questions
would score about 0.256 against 0.231: an estimate that assumes the right mode is chosen.


### All questions  (n = 141 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.348 [0.280, 0.416] | baseline | 0.246 | 0.26 | 0.46 | 0.56 | 0.79 | 0.307 | 0 / 0 | 0.0 |
| what | 0.348 [0.279, 0.418] | -0.001 (p=0.9588) | 0.246 | 0.26 | 0.46 | 0.52 | 0.74 | 0.308 | 0 / 0 | 0.0 |
| how | 0.067 [0.033, 0.107] | -0.281 (p=0.0002) | 0.024 | 0.05 | 0.09 | 0.11 | 0.14 | 0.034 | 0 / 0 | 0.0 |

### Stack Overflow questions  (n = 110 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.231 [0.170, 0.298] | baseline | 0.101 | 0.15 | 0.35 | 0.45 | 0.74 | 0.171 | 0 / 0 | 0.0 |
| what | 0.229 [0.165, 0.297] | -0.002 (p=0.9015) | 0.099 | 0.15 | 0.35 | 0.41 | 0.68 | 0.173 | 0 / 0 | 0.0 |
| how | 0.074 [0.033, 0.123] | -0.157 (p=0.0004) | 0.019 | 0.05 | 0.10 | 0.12 | 0.15 | 0.035 | 0 / 0 | 0.0 |

### Stack Overflow questions whose answer is learn  (n = 1 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.000 [0.000, 0.000] | baseline | 0.000 | 0.00 | 0.00 | 0.00 | 1.00 | 0.000 | 0 / 0 | 0.0 |
| what | 0.000 [0.000, 0.000] | +0.000 (p=1.0000) | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | 0 / 0 | 0.0 |
| how | 1.000 [1.000, 1.000] | +1.000 (p=1.0000) | 0.000 | 1.00 | 1.00 | 1.00 | 1.00 | 0.423 | 0 / 0 | 0.0 |

### Stack Overflow questions whose answer is do  (n = 13 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.302 [0.121, 0.504] | baseline | 0.032 | 0.15 | 0.46 | 0.62 | 0.77 | 0.106 | 0 / 0 | 0.0 |
| what | 0.192 [0.038, 0.385] | -0.110 (p=0.2522) | 0.000 | 0.08 | 0.31 | 0.31 | 0.31 | 0.036 | 0 / 0 | 0.0 |
| how | 0.346 [0.147, 0.569] | +0.044 (p=0.7059) | 0.157 | 0.23 | 0.54 | 0.62 | 0.85 | 0.213 | 0 / 0 | 0.0 |

### Stack Overflow questions whose answer is lookup  (n = 95 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.226 [0.159, 0.298] | baseline | 0.112 | 0.15 | 0.34 | 0.44 | 0.74 | 0.184 | 0 / 0 | 0.0 |
| what | 0.239 [0.169, 0.313] | +0.013 (p=0.4311) | 0.115 | 0.16 | 0.36 | 0.43 | 0.75 | 0.195 | 0 / 0 | 0.0 |
| how | 0.028 [0.002, 0.061] | -0.198 (p=0.0002) | 0.000 | 0.02 | 0.03 | 0.04 | 0.05 | 0.007 | 0 / 0 | 0.0 |

### Stack Overflow questions whose answer is understand  (n = 1 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.000 [0.000, 0.000] | baseline | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | 0 / 0 | 0.0 |
| what | 0.000 [0.000, 0.000] | +0.000 (p=1.0000) | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | 0 / 0 | 0.0 |
| how | 0.000 [0.000, 0.000] | +0.000 (p=1.0000) | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | 0 / 0 | 0.0 |

### Idea questions  (n = 6 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.162 [0.037, 0.310] | baseline | 0.162 | 0.00 | 0.33 | 0.67 | 0.83 | 0.196 | 0 / 0 | 0.0 |
| what | 0.183 [0.044, 0.333] | +0.021 (p=1.0000) | 0.183 | 0.00 | 0.33 | 0.67 | 0.83 | 0.179 | 0 / 0 | 0.0 |
| how | 0.217 [0.017, 0.533] | +0.055 (p=1.0000) | 0.217 | 0.17 | 0.33 | 0.50 | 0.50 | 0.163 | 0 / 0 | 0.0 |

### Name lookups  (n = 25 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.908 [0.816, 0.980] | baseline | 0.908 | 0.84 | 1.00 | 1.00 | 1.00 | 0.931 | 0 / 0 | 0.0 |
| what | 0.908 [0.816, 0.980] | +0.000 (p=1.0000) | 0.908 | 0.84 | 1.00 | 1.00 | 1.00 | 0.931 | 0 / 0 | 0.0 |
| how | 0.000 [0.000, 0.000] | -0.908 (p=0.0002) | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | 0 / 0 | 0.0 |

## Phase 4: examples, dev split

With an example entry for each API entry's Examples part (numpy +1,477, pandas +2,133, polars
+1,265, Python +1,477; cppreference's Example sections made examples). `how+completeW`: how
mode with complete examples (examples.py) given one more vote of weight W: no better (Stack
Overflow -0.002, how-to answers -0.032), so not used; completeness is only shown.


### All questions  (n = 141 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.349 [0.283, 0.418] | baseline | 0.245 | 0.27 | 0.47 | 0.55 | 0.79 | 0.286 | 0 / 0 | 0.0 |
| what | 0.362 [0.293, 0.431] | +0.013 (p=0.3932) | 0.260 | 0.28 | 0.48 | 0.55 | 0.74 | 0.291 | 0 / 0 | 0.0 |
| how | 0.126 [0.084, 0.171] | -0.223 (p=0.0004) | 0.022 | 0.07 | 0.21 | 0.28 | 0.48 | 0.058 | 0 / 0 | 0.0 |
| how+complete0.5 | 0.119 [0.078, 0.165] | -0.230 (p=0.0004) | 0.033 | 0.06 | 0.18 | 0.26 | 0.48 | 0.057 | 0 / 0 | 0.0 |
| how+complete1 | 0.118 [0.077, 0.164] | -0.231 (p=0.0004) | 0.033 | 0.06 | 0.18 | 0.26 | 0.44 | 0.055 | 0 / 0 | 0.0 |

### Stack Overflow questions  (n = 110 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.229 [0.166, 0.298] | baseline | 0.096 | 0.15 | 0.35 | 0.45 | 0.74 | 0.143 | 0 / 0 | 0.0 |
| what | 0.241 [0.176, 0.310] | +0.012 (p=0.5048) | 0.112 | 0.15 | 0.37 | 0.43 | 0.68 | 0.146 | 0 / 0 | 0.0 |
| how | 0.150 [0.101, 0.206] | -0.079 (p=0.0600) | 0.017 | 0.08 | 0.25 | 0.35 | 0.59 | 0.067 | 0 / 0 | 0.0 |
| how+complete0.5 | 0.148 [0.097, 0.203] | -0.081 (p=0.0600) | 0.038 | 0.08 | 0.23 | 0.33 | 0.58 | 0.070 | 0 / 0 | 0.0 |
| how+complete1 | 0.147 [0.095, 0.202] | -0.082 (p=0.0600) | 0.038 | 0.08 | 0.23 | 0.32 | 0.54 | 0.070 | 0 / 0 | 0.0 |

### Stack Overflow questions whose answer is learn  (n = 1 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.000 [0.000, 0.000] | baseline | 0.000 | 0.00 | 0.00 | 0.00 | 1.00 | 0.000 | 0 / 0 | 0.0 |
| what | 0.000 [0.000, 0.000] | +0.000 (p=1.0000) | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | 0 / 0 | 0.0 |
| how | 0.333 [0.333, 0.333] | +0.333 (p=1.0000) | 0.000 | 0.00 | 1.00 | 1.00 | 1.00 | 0.268 | 0 / 0 | 0.0 |
| how+complete0.5 | 0.000 [0.000, 0.000] | +0.000 (p=1.0000) | 0.000 | 0.00 | 0.00 | 0.00 | 1.00 | 0.000 | 0 / 0 | 0.0 |
| how+complete1 | 0.000 [0.000, 0.000] | +0.000 (p=1.0000) | 0.000 | 0.00 | 0.00 | 0.00 | 1.00 | 0.000 | 0 / 0 | 0.0 |

### Stack Overflow questions whose answer is do  (n = 13 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.282 [0.109, 0.487] | baseline | 0.011 | 0.15 | 0.46 | 0.62 | 0.85 | 0.070 | 0 / 0 | 0.0 |
| what | 0.192 [0.038, 0.385] | -0.090 (p=1.0000) | 0.000 | 0.08 | 0.31 | 0.31 | 0.31 | 0.036 | 0 / 0 | 0.0 |
| how | 0.281 [0.138, 0.444] | -0.001 (p=1.0000) | 0.048 | 0.08 | 0.46 | 0.69 | 0.85 | 0.130 | 0 / 0 | 0.0 |
| how+complete0.5 | 0.250 [0.077, 0.470] | -0.032 (p=1.0000) | 0.009 | 0.15 | 0.31 | 0.46 | 0.77 | 0.070 | 0 / 0 | 0.0 |
| how+complete1 | 0.250 [0.071, 0.462] | -0.032 (p=1.0000) | 0.009 | 0.15 | 0.31 | 0.46 | 0.62 | 0.070 | 0 / 0 | 0.0 |

### Stack Overflow questions whose answer is lookup  (n = 95 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.226 [0.159, 0.299] | baseline | 0.110 | 0.15 | 0.35 | 0.44 | 0.73 | 0.156 | 0 / 0 | 0.0 |
| what | 0.253 [0.183, 0.329] | +0.027 (p=0.1409) | 0.129 | 0.17 | 0.39 | 0.45 | 0.75 | 0.165 | 0 / 0 | 0.0 |
| how | 0.132 [0.079, 0.192] | -0.094 (p=0.0164) | 0.014 | 0.08 | 0.22 | 0.29 | 0.56 | 0.057 | 0 / 0 | 0.0 |
| how+complete0.5 | 0.137 [0.085, 0.194] | -0.090 (p=0.0432) | 0.043 | 0.07 | 0.22 | 0.32 | 0.56 | 0.072 | 0 / 0 | 0.0 |
| how+complete1 | 0.135 [0.083, 0.194] | -0.091 (p=0.0432) | 0.043 | 0.07 | 0.22 | 0.31 | 0.53 | 0.071 | 0 / 0 | 0.0 |

### Stack Overflow questions whose answer is understand  (n = 1 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.000 [0.000, 0.000] | baseline | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | 0 / 0 | 0.0 |
| what | 0.000 [0.000, 0.000] | +0.000 (p=1.0000) | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | 0 / 0 | 0.0 |
| how | 0.000 [0.000, 0.000] | +0.000 (p=1.0000) | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | 0 / 0 | 0.0 |
| how+complete0.5 | 0.000 [0.000, 0.000] | +0.000 (p=1.0000) | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | 0 / 0 | 0.0 |
| how+complete1 | 0.000 [0.000, 0.000] | +0.000 (p=1.0000) | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | 0 / 0 | 0.0 |

### Idea questions  (n = 6 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.133 [0.017, 0.300] | baseline | 0.133 | 0.00 | 0.33 | 0.50 | 0.83 | 0.153 | 0 / 0 | 0.0 |
| what | 0.206 [0.086, 0.352] | +0.073 (p=1.0000) | 0.206 | 0.00 | 0.33 | 0.83 | 0.83 | 0.213 | 0 / 0 | 0.0 |
| how | 0.194 [0.000, 0.528] | +0.061 (p=1.0000) | 0.194 | 0.17 | 0.17 | 0.33 | 0.50 | 0.133 | 0 / 0 | 0.0 |
| how+complete0.5 | 0.083 [0.000, 0.250] | -0.050 (p=1.0000) | 0.083 | 0.00 | 0.17 | 0.17 | 0.50 | 0.045 | 0 / 0 | 0.0 |
| how+complete1 | 0.083 [0.000, 0.250] | -0.050 (p=1.0000) | 0.083 | 0.00 | 0.17 | 0.17 | 0.50 | 0.023 | 0 / 0 | 0.0 |

### Name lookups  (n = 25 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.928 [0.844, 1.000] | baseline | 0.928 | 0.88 | 1.00 | 1.00 | 1.00 | 0.946 | 0 / 0 | 0.0 |
| what | 0.928 [0.844, 1.000] | +0.000 (p=1.0000) | 0.928 | 0.88 | 1.00 | 1.00 | 1.00 | 0.946 | 0 / 0 | 0.0 |
| how | 0.000 [0.000, 0.000] | -0.928 (p=0.0004) | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | 0 / 0 | 0.0 |
| how+complete0.5 | 0.000 [0.000, 0.000] | -0.928 (p=0.0004) | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | 0 / 0 | 0.0 |
| how+complete1 | 0.000 [0.000, 0.000] | -0.928 (p=0.0004) | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | 0 / 0 | 0.0 |

## Final, test split (run once)

### Plain search before (your copies as downloaded) against plain search now (what), organized, with guides and examples


### All questions  (n = 312 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.393 [0.346, 0.441] | baseline | 0.244 | 0.31 | 0.49 | 0.61 | 0.77 | 0.326 | 0 / 0 | 0.0 |
| organized | 0.396 [0.347, 0.444] | +0.003 (p=0.7103) | 0.252 | 0.31 | 0.51 | 0.60 | 0.73 | 0.303 | 0 / 0 | 0.0 |

### Stack Overflow questions  (n = 245 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.267 [0.222, 0.315] | baseline | 0.079 | 0.18 | 0.38 | 0.53 | 0.71 | 0.183 | 0 / 0 | 0.0 |
| organized | 0.269 [0.224, 0.315] | +0.001 (p=0.9063) | 0.086 | 0.17 | 0.40 | 0.52 | 0.68 | 0.152 | 0 / 0 | 0.0 |

### Stack Overflow questions whose answer is learn  (n = 9 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.222 [0.000, 0.556] | baseline | 0.000 | 0.22 | 0.22 | 0.22 | 0.67 | 0.049 | 0 / 0 | 0.0 |
| organized | 0.000 [0.000, 0.000] | -0.222 (p=0.4982) | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | 0 / 0 | 0.0 |

### Stack Overflow questions whose answer is do  (n = 18 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.188 [0.058, 0.344] | baseline | 0.027 | 0.11 | 0.28 | 0.50 | 0.61 | 0.100 | 0 / 0 | 0.0 |
| organized | 0.185 [0.037, 0.370] | -0.003 (p=0.9700) | 0.056 | 0.17 | 0.22 | 0.22 | 0.22 | 0.048 | 0 / 0 | 0.0 |

### Stack Overflow questions whose answer is lookup  (n = 218 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.276 [0.227, 0.325] | baseline | 0.086 | 0.18 | 0.39 | 0.55 | 0.72 | 0.195 | 0 / 0 | 0.0 |
| organized | 0.287 [0.239, 0.335] | +0.011 (p=0.1915) | 0.092 | 0.18 | 0.43 | 0.56 | 0.74 | 0.167 | 0 / 0 | 0.0 |

### Idea questions  (n = 12 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.250 [0.056, 0.472] | baseline | 0.250 | 0.17 | 0.33 | 0.42 | 0.75 | 0.216 | 0 / 0 | 0.0 |
| organized | 0.311 [0.100, 0.561] | +0.061 (p=0.2478) | 0.311 | 0.25 | 0.50 | 0.50 | 0.67 | 0.255 | 0 / 0 | 0.0 |

### Name lookups  (n = 55 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.982 [0.955, 1.000] | baseline | 0.982 | 0.96 | 1.00 | 1.00 | 1.00 | 0.987 | 0 / 0 | 0.0 |
| organized | 0.982 [0.955, 1.000] | +0.000 (p=1.0000) | 0.982 | 0.96 | 1.00 | 1.00 | 1.00 | 0.987 | 0 / 0 | 0.0 |

### Now: plain search over every entry (before), what, how

On the 27 Stack Overflow questions whose answer is a tutorial or how-to (learn 9, do 18), search how
scores 0.27 (9 x 0.407 + 18 x 0.203) against 0.19 for plain search as it was: too few questions to
be sure. Most questions (218 of 245) link a reference page: how is not their search.


### All questions  (n = 312 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.396 [0.349, 0.445] | baseline | 0.243 | 0.32 | 0.50 | 0.60 | 0.77 | 0.312 | 0 / 0 | 0.0 |
| what | 0.396 [0.348, 0.445] | -0.000 (p=0.9864) | 0.252 | 0.31 | 0.51 | 0.60 | 0.73 | 0.303 | 0 / 0 | 0.0 |
| how | 0.151 [0.119, 0.186] | -0.245 (p=0.0004) | 0.024 | 0.09 | 0.24 | 0.31 | 0.46 | 0.073 | 0 / 0 | 0.0 |
| how+complete0.5 | 0.156 [0.122, 0.192] | -0.240 (p=0.0004) | 0.014 | 0.10 | 0.23 | 0.29 | 0.46 | 0.071 | 0 / 0 | 0.0 |
| how+complete1 | 0.156 [0.122, 0.191] | -0.240 (p=0.0004) | 0.014 | 0.10 | 0.23 | 0.28 | 0.43 | 0.071 | 0 / 0 | 0.0 |

### Stack Overflow questions  (n = 245 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.274 [0.229, 0.322] | baseline | 0.079 | 0.18 | 0.40 | 0.52 | 0.73 | 0.166 | 0 / 0 | 0.0 |
| what | 0.269 [0.224, 0.315] | -0.005 (p=0.6753) | 0.086 | 0.17 | 0.40 | 0.52 | 0.68 | 0.152 | 0 / 0 | 0.0 |
| how | 0.191 [0.152, 0.233] | -0.083 (p=0.0016) | 0.029 | 0.11 | 0.30 | 0.39 | 0.57 | 0.092 | 0 / 0 | 0.0 |
| how+complete0.5 | 0.198 [0.157, 0.242] | -0.076 (p=0.0018) | 0.017 | 0.13 | 0.29 | 0.36 | 0.57 | 0.088 | 0 / 0 | 0.0 |
| how+complete1 | 0.197 [0.156, 0.241] | -0.076 (p=0.0016) | 0.017 | 0.13 | 0.29 | 0.36 | 0.54 | 0.088 | 0 / 0 | 0.0 |

### Stack Overflow questions whose answer is learn  (n = 9 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.222 [0.000, 0.556] | baseline | 0.000 | 0.22 | 0.22 | 0.22 | 0.67 | 0.049 | 0 / 0 | 0.0 |
| what | 0.000 [0.000, 0.000] | -0.222 (p=1.0000) | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | 0 / 0 | 0.0 |
| how | 0.407 [0.130, 0.704] | +0.185 (p=1.0000) | 0.056 | 0.33 | 0.44 | 0.56 | 0.67 | 0.136 | 0 / 0 | 0.0 |
| how+complete0.5 | 0.030 [0.000, 0.073] | -0.192 (p=1.0000) | 0.000 | 0.00 | 0.00 | 0.22 | 0.56 | 0.016 | 0 / 0 | 0.0 |
| how+complete1 | 0.016 [0.000, 0.048] | -0.206 (p=1.0000) | 0.000 | 0.00 | 0.00 | 0.11 | 0.56 | 0.008 | 0 / 0 | 0.0 |

### Stack Overflow questions whose answer is do  (n = 18 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.177 [0.050, 0.341] | baseline | 0.027 | 0.11 | 0.22 | 0.44 | 0.72 | 0.102 | 0 / 0 | 0.0 |
| what | 0.185 [0.019, 0.370] | +0.008 (p=1.0000) | 0.056 | 0.17 | 0.22 | 0.22 | 0.22 | 0.048 | 0 / 0 | 0.0 |
| how | 0.203 [0.076, 0.357] | +0.026 (p=1.0000) | 0.026 | 0.11 | 0.33 | 0.50 | 0.83 | 0.128 | 0 / 0 | 0.0 |
| how+complete0.5 | 0.165 [0.037, 0.326] | -0.013 (p=1.0000) | 0.019 | 0.11 | 0.28 | 0.33 | 0.61 | 0.055 | 0 / 0 | 0.0 |
| how+complete1 | 0.165 [0.037, 0.326] | -0.013 (p=1.0000) | 0.019 | 0.11 | 0.28 | 0.33 | 0.39 | 0.055 | 0 / 0 | 0.0 |

### Stack Overflow questions whose answer is lookup  (n = 218 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.284 [0.235, 0.335] | baseline | 0.086 | 0.19 | 0.42 | 0.54 | 0.73 | 0.177 | 0 / 0 | 0.0 |
| what | 0.287 [0.238, 0.337] | +0.003 (p=0.7967) | 0.092 | 0.18 | 0.43 | 0.56 | 0.74 | 0.167 | 0 / 0 | 0.0 |
| how | 0.181 [0.142, 0.224] | -0.103 (p=0.0004) | 0.028 | 0.11 | 0.29 | 0.37 | 0.55 | 0.087 | 0 / 0 | 0.0 |
| how+complete0.5 | 0.208 [0.163, 0.255] | -0.076 (p=0.0045) | 0.017 | 0.13 | 0.31 | 0.37 | 0.57 | 0.094 | 0 / 0 | 0.0 |
| how+complete1 | 0.208 [0.164, 0.254] | -0.076 (p=0.0045) | 0.017 | 0.13 | 0.31 | 0.37 | 0.56 | 0.094 | 0 / 0 | 0.0 |

### Idea questions  (n = 12 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.253 [0.061, 0.478] | baseline | 0.253 | 0.17 | 0.42 | 0.42 | 0.67 | 0.222 | 0 / 0 | 0.0 |
| what | 0.311 [0.094, 0.561] | +0.058 (p=0.4981) | 0.311 | 0.25 | 0.50 | 0.50 | 0.67 | 0.255 | 0 / 0 | 0.0 |
| how | 0.033 [0.000, 0.083] | -0.219 (p=0.3760) | 0.033 | 0.00 | 0.17 | 0.17 | 0.25 | 0.027 | 0 / 0 | 0.0 |
| how+complete0.5 | 0.021 [0.000, 0.062] | -0.232 (p=0.3760) | 0.021 | 0.00 | 0.08 | 0.08 | 0.17 | 0.038 | 0 / 0 | 0.0 |
| how+complete1 | 0.021 [0.000, 0.062] | -0.232 (p=0.3760) | 0.021 | 0.00 | 0.08 | 0.08 | 0.17 | 0.038 | 0 / 0 | 0.0 |

### Name lookups  (n = 55 questions)

| System | MRR@10 [95% CI] | Δ MRR vs baseline (p, Holm) | strict MRR | R@1 | R@5 | R@10 | R@50 | nDCG@10 | ms p50 / p95 | GPU GB |
|---|---|---|---|---|---|---|---|---|---|---|
| before | 0.973 [0.936, 1.000] | baseline | 0.973 | 0.95 | 1.00 | 1.00 | 1.00 | 0.980 | 0 / 0 | 0.0 |
| what | 0.982 [0.955, 1.000] | +0.009 (p=1.0000) | 0.982 | 0.96 | 1.00 | 1.00 | 1.00 | 0.987 | 0 / 0 | 0.0 |
| how | 0.000 [0.000, 0.000] | -0.973 (p=0.0004) | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | 0 / 0 | 0.0 |
| how+complete0.5 | 0.000 [0.000, 0.000] | -0.973 (p=0.0004) | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | 0 / 0 | 0.0 |
| how+complete1 | 0.000 [0.000, 0.000] | -0.973 (p=0.0004) | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 | 0 / 0 | 0.0 |

## Search how, T2 (2026-10-12), dev split, your data organized by version 3

How mode is its own entries (learn, do, examples) and the API objects, fused with every entry
(eval/results-usability.md has the candidates). Paired with how mode as it was:

| questions | how as it was | how now | Δ [95% CI] | p |
|---|---|---|---|---|
| Stack Overflow (113) | 0.202 | 0.263 | +0.061 [+0.010, +0.117] | 0.029 |
| … whose answer is learn or do (14) | 0.261 | 0.290 | +0.029 [−0.124, +0.223] | 0.80 |
| … whose answer is lookup (98) | 0.196 | 0.262 | +0.067 [+0.012, +0.123] | 0.022 |
| Ideas (7) | 0.187 | 0.181 | −0.006 | 0.88 |
| Names (21) | 0.000 | 0.938 | +0.938 | <0.001 |

Plain search is not changed (0.211 on Stack Overflow, names 0.938).
