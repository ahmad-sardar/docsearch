"""Misspelled words in a query: the docs' own words they most likely mean.

A word the docs never use ("dooplicates", "concatinate", "arguement") is compared with every
word they do use, through three lenses:

- letters: edits (missing, extra, wrong, swapped letters) and overall similarity;
- letter pieces: the three-letter pieces two words share (long words keep most of them
  even when misspelled in several places);
- sound: phonetic codes (Metaphone, NYSIIS, Soundex, Match Rating), so a word spelled the
  way it sounds ("dikshunary") finds the word it sounds like;

and how common the candidate is in the docs. The weights of these signals were fit on real
human misspellings (the Birkbeck corpus and Wikipedia's list; eval/spelling.py, dev words
only): on other words, the right word comes first 61% of the time and in the top 3 73%,
against 48% and 61% for edits and frequency alone. The search then looks for both the query
as typed and the corrected one, and fuses the two (Index.search).
"""
from __future__ import annotations

import math
import re
from collections import defaultdict

import numpy as np

FEATURES = ("edits", "edits_per_letter", "similarity", "shared_pieces", "same_first_letter", "length_change",
            "log_frequency", "same_metaphone", "same_nysiis", "metaphone_similarity", "same_soundex",
            "same_match_rating", "nysiis_similarity")
# Fit by eval/spelling.py on the dev words (softmax regression over the candidates):
# standardized features (MEAN, SCALE) times WEIGHTS gives each candidate's score.
MEAN = [3.64369, 0.5649, 0.53933, 0.17184, 0.40855, 0.24234, 3.42872, 0.0183, 0.0122, 0.6315, 0.05281, 0.0079, 0.604]
SCALE = [0.64412, 0.19509, 0.16311, 0.15304, 0.49031, 0.20721, 2.13195, 0.13337, 0.10936, 0.16378, 0.22436, 0.08832,
         0.16919]
WEIGHTS = [-0.8306, 1.72099, 1.67324, 0.50566, 0.43082, -0.44661, 0.5586, -0.01637, -0.05009, 0.94525, 0.12457, 0.0565,
           1.05421]
MIN_FREQUENCY = 3          # words in fewer entries are not offered as corrections
MIN_LENGTH = 4             # shorter words are never corrected (too many look-alikes)


def pieces(s: str) -> set[str]:
    s = f"  {s} "
    return {s[k:k + 3] for k in range(len(s) - 2)}


class Speller:
    """Corrections from a vocabulary {word: number of entries using it}."""

    def __init__(self, frequency: dict[str, int]) -> None:
        import jellyfish
        self.jf = jellyfish
        self.known = frequency
        self.words = [w for w, n in frequency.items() if n >= MIN_FREQUENCY and re.fullmatch(r"[a-z]{3,}", w)]
        self.freq = np.array([frequency[w] for w in self.words], np.float64)
        self.codes = [(jellyfish.metaphone(w), jellyfish.nysiis(w), jellyfish.soundex(w),
                       jellyfish.match_rating_codex(w)) for w in self.words]
        self.by_metaphone: dict[str, list[int]] = defaultdict(list)
        self.by_nysiis: dict[str, list[int]] = defaultdict(list)
        for k, (m, n, _, _) in enumerate(self.codes):
            self.by_metaphone[m].append(k)
            self.by_nysiis[n].append(k)
        self.metaphones = list(self.by_metaphone)
        self.pieces = [pieces(w) for w in self.words]
        self.cache: dict = {}

    def needs_correction(self, word: str) -> bool:
        return len(word) >= MIN_LENGTH and word.isalpha() and self.known.get(word, 0) == 0

    def candidates(self, word: str) -> tuple[list[str], np.ndarray]:
        """Likely words and their features: the most similar in letters, those within two
        edits, and those that sound the same (or one sound apart); common ones first."""
        from rapidfuzz import fuzz, process
        from rapidfuzz.distance import OSA
        sim = process.cdist(self.words, [word], scorer=fuzz.ratio, dtype=np.uint8, workers=-1)[:, 0]
        edits = process.cdist(self.words, [word], scorer=OSA.distance, score_cutoff=3, dtype=np.uint8, workers=-1)[:, 0]

        def common(ids, n):
            return sorted(ids, key=lambda k: -self.freq[k])[:n]
        cand = set(np.argpartition(-sim.astype(np.int32), 120)[:120].tolist())
        cand |= set(common(np.flatnonzero(edits <= 2).tolist(), 40))
        m, n, sx, mr = (self.jf.metaphone(word), self.jf.nysiis(word), self.jf.soundex(word),
                        self.jf.match_rating_codex(word))
        cand |= set(common(self.by_metaphone.get(m, []), 40)) | set(common(self.by_nysiis.get(n, []), 40))
        for code, _, _ in process.extract(m, self.metaphones, scorer=OSA.distance, score_cutoff=1, limit=None):
            cand |= set(common(self.by_metaphone[code], 10))
        cand = sorted(cand)
        mine = pieces(word)
        rows = []
        for k in cand:
            w, (cm, cn, csx, cmr) = self.words[k], self.codes[k]
            rows.append([int(edits[k]), edits[k] / len(word), sim[k] / 100,
                         2 * len(mine & self.pieces[k]) / (len(mine) + len(self.pieces[k])),
                         float(word[0] == w[0]), abs(len(word) - len(w)) / len(word), math.log(self.freq[k]),
                         float(cm == m), float(cn == n), fuzz.ratio(cm, m) / 100, float(csx == sx), float(cmr == mr),
                         fuzz.ratio(cn, n) / 100])
        return [self.words[k] for k in cand], np.array(rows, np.float32)

    def suggest(self, word: str, k: int = 3) -> list[tuple[str, float]]:
        """The k most likely intended words, with their probability among the candidates."""
        if (word, k) in self.cache:
            return self.cache[word, k]
        words, feats = self.candidates(word)
        z = ((feats - np.array(MEAN, np.float32)) / np.array(SCALE, np.float32)) @ np.array(WEIGHTS, np.float32)
        p = np.exp(z - z.max())
        p /= p.sum()
        if len(self.cache) > 10000:
            self.cache.clear()
        out = self.cache[word, k] = [(words[j], float(p[j])) for j in np.argsort(-p)[:k]]
        return out

    def correct(self, query: str) -> str:
        """The query with each word the docs never use replaced by its likeliest meaning
        (the rest kept as typed)."""
        if WEIGHTS is None:
            return query

        def fix(m: re.Match) -> str:
            low = m.group(0).lower()
            return self.suggest(low, 1)[0][0] if self.needs_correction(low) else m.group(0)
        return re.sub(r"[A-Za-z]+", fix, query)
