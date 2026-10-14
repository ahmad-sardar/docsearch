# Tickets (2026-10-12)

Order: the measure first, then what you feel in search, then reading and organizing, then your
data and release.

Each ticket ends with tests, a measurement, and a commit when you say. "Usability score" means
`eval/usability.py`: per question, the rank of the wanted answer; reported as #1, top 3,
top 5, missing.

| # | Ticket | Fixes | Size |
|---|---|---|---|
| T0 | Usability measure | — | S |
| T1 | Examples: right purpose, real examples only | S2, S3, S8 | M |
| T2 | How mode finds the function that does it | S1 | M |
| T3 | One result per thing | S5, O7 | S |
| T4 | Your project's packages first | S4 | S |
| T5 | Finding the docs: trusted paths, fewer requests | D1–D4 | M |
| T6 | Guides: docs sites only, never twice | G1–G3 | M |
| T7 | Reading: complete lists, sections everywhere | R1, R2 | S |
| T8 | Organizing by the site's structure | O1–O6, S6 | L |
| T9 | Markdown API references | S7 | M |
| T10 | Replace a copy by coverage; your data | X1 | S |
| T11 | Release | P1 | S |

### T0 Usability measure
- **Deliverables:**
  - `eval/usability.py`;
  - `eval/usability.json`: this run's ~60 questions plus 20 written before any change, each
    with package, mode and wanted answer;
  - `eval/results-usability.md`: the baseline on your current data.
- **Done when:** the baseline table exists; re-running gives the same numbers.

### T1 Examples: right purpose, real examples only (done: `eval/results-usability.md`)
- **Change:**
  - re-organizing keeps an example's purpose (do, or learn in a tutorial);
  - an example is an "Examples" part, or code the docs present as one, not every code block;
  - placeholders dropped;
  - organizing rules version 3: your numpy fixed once, nothing downloaded.
- **Deliverables:** `organize.py` and `examples.py` changes; tests.
- **Done when:**
  - no example is "look up" in any copy;
  - argmax's, vstack's and np.save's examples are in the how-mode top 5;
  - "Reading and writing files" is in the how-mode top 5 for "how read a file line by line";
  - Python's example count is reported, with 20 read by hand.

### T2 How mode finds the function that does it (done: `eval/results-usability.md`)
- **Change:** three candidates, measured, one kept:
  - (a) how = learn + do + examples + API objects;
  - (b) how = everything, guides and examples ranked first;
  - (c) as now.
- **Deliverables:** `cli.Index.search` / `MODES`; results added to `eval/results-usability.md`
  and `eval/results-organized.md`.
- **Done when:**
  - the S1 answers are in the how-mode top 3;
  - the usability score in how mode improves;
  - Stack Overflow how mode does not drop on how-to answers;
  - plain search is unchanged (names within 0.01).

### T3 One result per thing (done: `eval/results-usability.md`)
- **Change:**
  - one Sphinx section reached by two labels (same page, same heading) is one entry;
  - one name on two pages is told apart (`std::vector<bool>`) or shown once;
  - repeated headings get their own anchors.
- **Done when:** no repeated result in the usability run; anchors are unique per page.

### T4 Your project's packages first (done: `eval/results-usability.md`)
- **Change:** searching all packages puts the packages of your project (its languages: Python,
  C++…) first. Others follow, never mixed into the first results.
- **Done when:** the cross-package usability questions have their language's answer first.
  Searching one package is unchanged.

### T5 Finding the docs: trusted paths, fewer requests (done: `eval/results-finding.md`, `notes/fetching-policy.md`)
- **Change:**
  - **The survey:**
    - its requests never mark a place unreached;
    - a 429 means fewer lists;
    - it stops at the first complete list.
  - **A home page's docs links:**
    - only links that name docs: a `docs.` host, a `/docs` path, or the whole link text Docs,
      Documentation, API, Reference, User guide;
    - never contribute, community, blog or about pages.
  - **A PyPI home page** vouches for its docs links on other hosts.
  - **`search add NAME`** uses its packages.toml entry.
- **Done when:**
  - transformers, datasets, accelerate and diffusers are found (or "try later", never
    nothing);
  - tensorflow is not in `/community/`;
  - numba is found; onnx and opencv are found or the reason is said;
  - a re-run of the 81-package docs-finding is no worse anywhere.

### T6 Guides: docs sites only, never twice
- **Change:**
  - a guide link's whole text must name a guide;
  - a guide must be a docs site (an inventory, a search index, llms.txt, or a page saying its
    generator);
  - not a version sibling;
  - a guide's site holding other docs is read from the guide's own list;
  - the same rules for PyPI-named parts.
- **Done when:**
  - pytest, scrapy and vllm have one part;
  - pymongo and scipy get no marketing parts;
  - polars' guide is 86 pages;
  - numpy's tutorials and langchain's guide are still found.

### T7 Reading: complete lists, sections everywhere
- **Change:**
  - expected pages only from complete lists;
  - the sections question for every part, once per site, kept per site in packages.toml;
  - a terminal test.
- **Done when:**
  - keras says no false shortfall;
  - in a terminal, langchain's guide asks its sections, keeps the answer, and sync does not
    ask again;
  - without a terminal it says what it chose.

### T8 Organizing by the site's structure
- **Change:**
  - **labels pass only through contents and outline**, not by address;
  - **place-name sections** label only their own page;
  - **the home view:**
    - a guide site's parts are its top sections;
    - no empty, "index" or address-named parts;
    - each part counts its own purpose;
  - **left out:** blog and tag pages, and changelogs whatever their title starts with;
  - **concept sections of guides go to understand**, measured and kept only if it helps S6.
- **Done when** (the same temp copies):
  - litellm's and spacy's purposes look like their sidebars, 20 pages each read by hand;
  - langchain's parts are its sections;
  - the earlier good sites are unchanged (fastapi, streamlit, httpx, numpy, Python);
  - "what is a checkpointer" improves or the option is dropped.

### T9 Markdown API references
- **Change:**
  - a page titled as the last part of its address is an API entry named from the address
    (`langchain.agents.create_agent`);
  - its Signature, Description, Properties fold into it;
  - its examples come from its code.
- **Done when:**
  - `langchain.agents.create_agent` and `create_agent` give it #1;
  - no "› Signature" results;
  - langchain has example entries.

### T10 Replace a copy by coverage; your data
- **Change:** a re-download replaces the copy you have when it read ≥ 90% of the listed pages
  with under 5% failed. The 70% rule applies only when coverage is unknown.
- **Then, with you at your terminal:** `search add langchain` (sections question), then
  `search sync`.
- **Done when:** your langchain is the new one; the others have their guides and outlines; the
  usability run on your data is re-done.

### T11 Release
- **Deliverables:**
  - `tests/sites.py` (made-up sites of each failing kind) and the new tests, all in CI;
  - README updated;
  - `notes/findings.md` updated, each finding fixed or why not;
  - push.
- **Done when:**
  - CI is green on Windows and Python 3.11–3.14;
  - the Stack Overflow test split is run once;
  - you or I have looked at the page in the browser.
