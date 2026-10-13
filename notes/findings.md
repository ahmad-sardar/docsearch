# Findings (2026-10-12)

From the spot check (`notes/spot-check.md`; temp copies of 15 packages; the 81-package
docs-finding run) and the usability run (about 60 real questions on your page and on the new
langchain copy, each result read). Evidence is from those runs.

## What works
- **Names, in every package:**
  - `np.linalg.svd`, `drop_duplicates`, `LazyFrame.collect`, `std::vector::push_back`,
    `cudaMalloc`, `create_agent`, `init_chat_model`: #1;
  - Stack Overflow name lookups unchanged (0.938).
- **How questions the guides answer:**
  - pandas: merge, Excel sheets, datetime, apply;
  - polars: filter, group by, parquet;
  - Python: argparse, sorting;
  - langchain on the new copy: tools, streaming, structured output, short-term memory,
    human-in-the-loop, call limits.
- **"What is…" questions:** view vs copy, context manager, format spec, broadcasting.
- **Reading:**
  - Markdown and MDX (no raw tags);
  - langchain's API reference (0 → 496 entries);
  - coverage: streamlit 405/401, httpx 23/23, spacy 296/295, litellm 1,509/1,500;
  - other versions dropped (streamlit 6,850 → 400).
- **Finding the docs:**
  - README-only 11 → 6 (keras, spacy, selenium, playwright, tensorflow now find sites);
  - Hugging Face's folder fixed.
- **Lifecycle:** the migration kept every copy's vectors; `sections` round-trips through
  `packages.toml`.
- **Speed:** 25–120 ms a search; 2.5 s with AI.

## Search
- **S1 How mode misses one-function answers that plain search ranks #1:**

  | Question | Wanted | Plain | How |
  |---|---|---|---|
  | find the indices of the maximum | argmax | #1 | — |
  | stack arrays vertically | vstack | #1 | — |
  | save an array | np.save | #1 | — |
  | time a function | timeit | #1 | — |
  | run coroutines concurrently | gather | #9 | #13 |
  | sort a vector | std::sort | #5 | #12 |

- **S2 numpy's examples were relabeled "look up"** when its guide was added (re-organizing
  gives examples their page's purpose). They show in plain search (`numpy.sum › Examples` #2 for
  `np.sum`) and are missing from how mode.
- **S3 Python's 1,477 "examples" are any code block in any entry.** They crowd how mode: the
  tutorial's "Reading and writing files" is #43 for "how read a file line by line".
- **S4 All packages at once mixes languages:** "how sort a list" gives C++ `std::list::sort`
  #1 and Python's Sorting Techniques #4; "how remove duplicates from a list" has no Python
  answer.
- **S5 The same thing listed twice:**
  - pandas sections via two Sphinx labels ("Series.apply() and DataFrame.apply()", "Rolling
    window functions", "Pure Python");
  - `cudaMalloc`;
  - `std::vector` (and `std::vector<bool>`).
- **S6 Concept questions in plain search miss guide pages:** "what is a checkpointer" gives env
  vars and an "Agent Server changelog".
- **S7 A Markdown API reference** (reference.langchain.com): every page splits into
  "› Signature", "› Description", "› Properties" results; `langchain.agents.create_agent` does
  not rank `create_agent` first.
- **S8 cppreference placeholders become examples** ("This section is incomplete: no example").
- **S9 (found in T1) A section reached by its Sphinx label holds only its first paragraph:**
  Python's "Reading and writing files" had 111 letters of 8,385 (the label's anchor opens the
  section; the cutter took the next paragraph). Every Sphinx copy.

S2, S3, S8, S9: fixed in T1 (`eval/results-usability.md`).

## Finding the docs
- **D1 Hugging Face** (transformers, datasets, accelerate, diffusers): "rate limited, nothing
  indexed". The survey's extra requests hit huggingface.co's limit, and a 429 aborts the search.
- **D2 tensorflow → `/community/contribute/`:** a home-page link about contributing to the docs
  passes the "lists pages" rule first.
- **D3 Still README-only though docs exist:** numba (home page links numba.readthedocs.io; PyPI
  names no repository), onnx, opencv, gradio.
- **D4 `search add NAME` ignores `url` in packages.toml** (only sync reads it).

## Guides
- **G1 Loose header links taken as guides:**
  - pymongo: "Learn more" → mongodb.com/solutions/;
  - scipy: "Installing" → scipy.org;
  - tensorflow: "Learn ML", and the whole site.
- **G2 The same docs again at another version:** pytest, scrapy, vllm get `en/latest/` next to
  `en/stable/`.
- **G3 A guide site holding other docs read from the host's sitemap:** polars' guide part read
  1,440 pages (other API versions), not 86; polars 3,537 → 5,066 entries.

## Reading
- **R1 "Expected pages" from a partial list:** keras read 1,355 pages against 98 expected.
- **R2 The sections question is never asked for parts:**
  - docs.langchain.com, tensorflow.org;
  - untested in a real terminal.
- **R3 (note)** transformers is slow under rate limits: partial at 306/764 after 368 s;
  continues later.

## Organizing
- **O1 Labels pass to every page under an address:** litellm 7,550 of 9,502 entries "learn"
  (its first page is "Getting Started"); spacy all under "Install spaCy".
- **O2 Place-name sections label their pages:** langchain's "Overview" makes "Create an
  agent", "Set up LangSmith" understand.
- **O3 A guide site is one part:** langchain's guide is one Do part of 6,789 entries, not
  LangGraph, Deep Agents, Deploy…
- **O4 Junk parts on the home view:** "index"; keras "getting-started/faq (0)".
- **O5 Part counts include other purposes:** pandas' API reference shows 4,743 under a Look up
  of 2,622.
- **O6 Not docs, kept:** litellm's blog tag pages; "Agent Server changelog" (the changelog rule
  wants the title to start with it).
- **O7 Repeated headings share one anchor:** langchain 118, keras 32.

## Your data
- **X1 Re-adding your langchain is refused:** the new copy is right but has 9,593 entries vs the
  old 27,969 (pages twice, both languages), and the 70%-of-entries rule keeps the old one.

## Not verified
- **P1 Windows CI and Python 3.11** (needs a push).
- **The page's rendering:** the browser pane refused 127.0.0.1 and localhost; checked through
  the API only.
