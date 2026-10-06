# The spelling ranker: exact vs trigram candidates

`Index.rank_edit` scores titles against the query with rapidfuzz's WRatio, for typos.
Scoring all ~211,000 titles took ~120 ms (on all cores). The trigram version scores only
the 5,000 titles that share the most three-letter pieces with the query (as Postgres's
pg_trgm does): ~5 ms. Measured with the whole search pipeline (MRR@10, paired tests).

The benchmark has no misspelled queries, so a typo set was made: each name lookup with one
random typo (a letter deleted, inserted, replaced, or two swapped).

## Choice (dev split, and typos on all name lookups, seed 3)

| Spelling ranker | dev (354) | dev SO (277) | dev names (69) | names + 1 typo (240) |
|---|---|---|---|---|
| exact, all titles | 0.358 | 0.220 | 0.940 | 0.509 |
| trigram, 20,000 kept | 0.361 (p=0.50) | 0.224 (p=0.50) | 0.940 | 0.509 (p=1.0) |
| **trigram, 5,000 kept** | 0.359 (p=0.50) | 0.223 (p=0.51) | 0.940 | 0.512 (p=0.30) |
| none (ranker off) | 0.360 (p=0.57) | 0.224 (p=0.52) | 0.937 | **0.456 (p<0.001)** |

The ranker matters for typos only, and the 5,000-title version is as good as exact.

## Confirmation (test split, fresh typos, seed 2026; run once)

| Set | exact | trigram 5,000 | difference [95% CI] | p |
|---|---|---|---|---|
| test, all (768) | 0.362 | 0.361 | -0.001 [-0.002, +0.001] | 0.39 |
| test SO (575) | 0.202 | 0.201 | -0.001 [-0.003, +0.002] | 0.48 |
| test names (171) | 0.911 | 0.911 | 0.000 | 1.0 |
| test names + 1 typo (171) | 0.562 | 0.566 | +0.003 [-0.007, +0.014] | 0.53 |

Whole search, median: 144 ms -> 56 ms (search page: 150 -> 75 ms).

Typo'd names are found first only about half the time with either version (MRR ~0.5):
a weakness of the search as a whole, not of this change.
