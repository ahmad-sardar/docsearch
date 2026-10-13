# Spot check: what to verify (2026-10-12)

Everything built on this branch since `0de59d4`: organizing (learn, do, look up,
understand), official guides, `search how`, examples, the site survey (lists, Markdown,
coverage, sections, outline). Each item has how it is checked. Results go in
`notes/findings.md`.

Data used:
- **"temp"**: copies made in a scratch folder, never your `data/`.
- **"yours"**: your running page and copies, read only.

## A. Finding the docs (`search add NAME`)
- A1 **A Sphinx package** (numpy): found through its inventory, the right folder and version.
- A2 **A MkDocs site** (httpx), **A3 a Zensical site** (fastapi): found, every page listed.
- A4 **Docusaurus** (litellm), **A5 Next.js** (streamlit): found, versions in the sitemap not counted.
- A6 **langchain**: the API reference and the guide site, both as parts of one copy.
- A7 **Product sites with no docs index** (keras, spacy, tensorflow, selenium, playwright,
  gradio): their docs, not the README; the right folder; what else the site holds kept out.
- A8 **Hugging Face** (transformers): the folder fixed (not `…/index/`).
- A9 **Packages whose docs are only a README** (and those that are not): still right.
- A10 **A site that rate-limits** (Read the Docs, Hugging Face): said so, nothing wrong taken.
- A11 **Docs by address** (`NAME=URL`), A12 **docs nothing confirms**: asked, as before.
- A13 **The 81-package survey, before and after**: how many get real docs, each folder checked.

## B. Reading
- B1 **Coverage**: pages read of pages listed, said when short.
- B2 **Markdown chosen** when the HTML has no text or the site lists Markdown (langchain);
  HTML otherwise (streamlit).
- B3 **Other languages' pages left out by default** (langchain TypeScript). The sections
  question:
  - asked in a terminal;
  - not asked without one;
  - the answer kept in `packages.toml`;
  - not asked again by sync.
- B4 **Other versions' copies** in sitemaps not read (streamlit, vllm).
- B5 **A very large site** (tensorflow, 18,801 pages): the question, the time, stop and continue.
- B6 **MDX** (`<Card>`, `<Tabs>`, `<Callout>`): no raw tags in entries or pages.
- B7 **No page read twice** (HTML and Markdown of one page).
- B8 **Guides from the docs' header** still found (polars' user guide, numpy's tutorials).
- B9 **The second try in the other form** when coverage is short.
- B10 **robots.txt and Crawl-delay** still kept.

## C. Organizing
- C1 **Purposes** on a sample of pages per site: numpy, pandas, Python, C++, polars with its
  guide, langchain, streamlit, fastapi, litellm.
- C2 **Pages about the project left out** (release notes...), none of the docs' own.
- C3 **Folding**:
  - sub-parts, link-only sections, "Next steps", repeated titles;
  - nothing only they had is lost.
- C4 **Organizing from the site's outline** (langchain, streamlit, selenium).
- C5 **The home view**: each package's parts make sense; no junk parts ("index", single pages).
- C6 **The list before you type**: grouped by purpose, in reading order.
- C7 **Migration of copies from before** (organize version 2): once, vectors kept.

## D. Search
- D1 **Names first in plain search** (np.sum, DataFrame.merge, std::vector, itertools.batched).
- D2 **How mode** on how questions (persistence, pivot a table, read a CSV, sort a list): the
  guide or example that answers comes first.
- D3 **"how" as a keyword**: in the box, `search how`, `search ai how`.
- D4 **How mode with nothing to search**: the reference, said so.
- D5 **AI ranking** in both modes.
- D6 **Example entries**: their text, the completeness label right, opening their entry's page.
- D7 **All packages at once**: other packages' pages in the way.
- D8 **Plain search on idea questions** ("what is persistence"): concept pages organized as Do
  are out of plain search.
- D9 **Speed**: a search, a page, `search add`.

## E. The page
- E1 **Home contents** render; each link opens its page.
- E2 **The How button**: its state, the placeholder, the status line.
- E3 **Result tags**: purpose, complete or needs, version.
- E4 **An example entry, a guide page** ("as of"), pages read as Markdown: they show well;
  links stay in the app.
- E5 **`s`** with no source: the message.
- E6 **`search list NAME`**: purposes, left out, the repository.

## F. Your data and its lifecycle
- F1 **Re-adding a copy** that was read badly before (your langchain: 27,969 entries, the new
  one about 10,000): replaced, or refused by the 70%-of-entries rule.
- F2 **`packages.toml`**: `sections` and `guides` round-trip; `search sync`.
- F3 **Offline**: only add, sync, upgrade go online (not the migration, not search).
- F4 **Disk and memory** of the new copies.

## G. Platforms
- G1 **Windows CI** after the page-name fix. G2 **Python 3.11**.

## H. Measured
- H1 **Stack Overflow benchmark** (dev), plain and how: unchanged or better after the survey work.
- H2 **The 81-package survey** (A13): before and after.
