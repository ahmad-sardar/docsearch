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

# Misspelled API names (Index.rank_typo)

An API name the query misspells by up to 2 letters (missing, extra, wrong or two swapped;
1 for names of 4-5 characters, none below), looked up only when no name is spelled exactly
like the query, with its own vote in the fusion. Weight chosen on dev; test run once with
fresh typos (seeds 2027, 2028). Search time unchanged (~60 ms).

| Set | off | weight 1 | **weight 2** | weight 3 |
|---|---|---|---|---|
| dev, all (354) | 0.359 | 0.359 | 0.359 | 0.359 |
| names + 1 typo (240) | 0.512 | 0.821 | **0.905** | 0.903 |
| names + 2 typos (240) | 0.346 | 0.787 | **0.880** | 0.881 |

| Test (run once) | off | weight 2 | difference [95% CI] | p |
|---|---|---|---|---|
| test, all (768) | 0.361 | 0.362 | +0.001 [+0.000, +0.003] | 1.0 |
| test names (171) | 0.911 | 0.916 | +0.005 [+0.000, +0.015] | 1.0 |
| names + 1 typo (171) | 0.516 | **0.884** | +0.367 [+0.306, +0.429] | <0.001 |
| names + 2 typos (171) | 0.326 | **0.867** | +0.540 [+0.478, +0.603] | <0.001 |

# Misspelled words (docsearch/spelling.py)

A word the docs never use is compared with the ~52,000 words they do use, through letters
(edits, similarity), letter pieces (shared trigrams) and sound (Metaphone, NYSIIS, Soundex,
Match Rating codes), and how common each candidate is. The weights are fit on real human
misspellings: the Birkbeck spelling error corpus and Wikipedia's list of common misspellings,
21,245 misspellings of 4,106 words the docs use (eval/spelling.py; fit on dev words, 30%).

Correcting single words (14,595 misspellings of the other words):

| Lens | right word first | in top 3 | 1 letter off | 2 letters off | 3+ letters off |
|---|---|---|---|---|---|
| letters: fewest edits, then most common | 48.0% | 60.7% | 82% | 51% | 11% |
| + letter pieces | 53.9% | 68.0% | 84% | 57% | 20% |
| + sound (Metaphone, NYSIIS) | 59.4% | 72.9% | 87% | 64% | 27% |
| **+ Soundex, Match Rating (used)** | **60.8%** | **73.4%** | 87% | 66% | 30% |

Searching (prototype, dev): replacing misspelled words by the best guess, or by the top 2,
did not help reliably and slightly hurt correct queries; searching the typed and the
corrected query and fusing the two did. That is what the search does. Benchmark questions
with real misspellings of their words (all such words of a question at once):

| | misspelled questions: off | on | difference [95% CI] | p | correct questions: off -> on |
|---|---|---|---|---|---|
| dev (152 / 354) | 0.219 | 0.230 | +0.012 [-0.005, +0.030] | 0.20 | 0.357 -> 0.356 |
| **test (547 / 768)** | **0.193** | **0.206** | **+0.013 [+0.003, +0.023]** | **0.011** | 0.364 -> 0.363 |

The same questions spelled right score 0.234 (test): the correction recovers about a third
of what misspellings cost. A search with a misspelled word takes ~6 ms more (median).
