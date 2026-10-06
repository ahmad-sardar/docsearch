# docsearch

Search official documentation (Python packages, Python, Rust, OCaml, C, C++, CUDA, Mojo,
MAX, Go, JavaScript, and any docs site you add) from the terminal and read it in Safari,
offline: by name (`np.sum`), by letters in order (`lnsvd`), by meaning (`sum of elements
along an axis`), or with a small AI model on your Mac for questions and ideas.

## Set up (once, on a Mac with Apple silicon)

```bash
git clone <this repository> ~/tools && cd ~/tools
uv sync                        # .venv from uv.lock: exact, hash-checked versions (~300 MB)
.venv/bin/search setup         # the models, then the docs (see below)
echo "alias search='$HOME/tools/.venv/bin/search'" >> ~/.zshrc && source ~/.zshrc
```

The repository holds only code. `search setup` gets everything else, once:

- **Your docs list:** `packages.toml`, copied from `packages.example.toml`. It's yours:
  add or remove docs any time (`search add`, `search remove`, or edit it and run
  `search sync`). It is not in git, so each copy keeps its own list.
- **The two models**, from fixed commits on Hugging Face (the AI model's weights are
  checked against a pinned hash):
  - meaning search: [sentence-transformers/multi-qa-MiniLM-L6-cos-v1](https://huggingface.co/sentence-transformers/multi-qa-MiniLM-L6-cos-v1) (90 MB)
  - search with AI: [mlx-community/Qwen3-Reranker-0.6B-4bit](https://huggingface.co/mlx-community/Qwen3-Reranker-0.6B-4bit) (330 MB)
- **The docs themselves**, downloaded and indexed from their official sites (pages,
  images and indexes: a few GB for the starting list, in `data/`).

After that nothing downloads: searching is offline. Only `search setup`, `add`, `sync`,
`upgrade` and `downgrade` go online, and only to fetch docs (or, in `setup`, the models).

## Use

```bash
search numpy svd         # Safari opens: results on the left, the docs on the right
search pandas mean       # one package
search sum of elements   # no package named: all of them
search ai how do I drop duplicate rows   # an idea or a question: AI reorders the results
search                   # just the search page
search list              # what is indexed, and which docs version
search stop              # stop the background server (it starts again by itself)
```

Before you type, the list shows the docs in reading order: their table of contents, and
each page's sections and API entries top to bottom (numpy's user guide, then its reference;
the Rust Book chapter by chapter). Once you type, results are ranked by how well they match.

The first search starts a small server in the background (on 127.0.0.1 only); later
searches only open a Safari tab, so they are instant. In the page:

| Key | Action |
|---|---|
| type | search as you type |
| ↑ ↓ | choose a result; its documentation shows on the right |
| Enter | the full page (offline copy); links between pages stay in the app |
| Esc | back from a full page, then clear the search |
| / | jump to the search box |
| w | wrap long code lines, or keep them on one line and scroll sideways |
| c | copy the name |

Code blocks and signatures have **Copy** buttons (examples are copied without `>>>` and
output). The buttons above the docs copy the name, the import line or the web address.
Click a package name at the top to search only that package.

Edit `packages.toml` to choose packages and versions, then run `search sync` (or see
Versions below).

## Search with AI

```bash
search ai how do I drop duplicate rows    # ideas and questions: AI on
search pandas drop_duplicates             # names and keywords: AI off, instant
```

`search ai …` opens the page with **AI** on (the button in the page, or ⌘↩ for one
search, does the same). You get the normal results at once; then a small language model on
this Mac (Qwen3-Reranker, 4-bit, run with MLX on the Apple GPU) reads the question with
each of the top 20 results and reorders them. It never writes text: every answer is still
an official docs entry. Results whose name is exactly what you typed (`np.sum`) stay first.

Use it for ideas, not names. On the benchmark in `eval/` (753 held-out questions, mostly
real Stack Overflow questions; `eval/results-test.md`) it puts the right docs higher:
MRR@10 0.35 → 0.42 (p < 0.001), and 0.21 → 0.28 on Stack Overflow questions. For names
it changes nothing, and plain search is instant (0.4 s) while AI takes about 3 s. The
whole page, with the AI model loaded, uses about 2 GB of memory.

The model lives on this Mac in `data/models` (about 330 MB, fetched once by `search
setup`).

## Versions

Every docs name in the page shows its version (`numpy 2.5`, `rust 1.99.0`). Docs that
publish no version number (cppreference, MDN) show the day they were downloaded.

Changing versions goes online, so it is done in the terminal:

```bash
search upgrade                   # every package to its newest docs (checks first: only what changed)
search upgrade numpy             # one package to its newest docs
search downgrade numpy==1.26     # one package to an older version
search upgrade python==3.14      # or to any version you name
```

The new docs are downloaded first; the old ones are deleted only once the new ones are
complete, so a failed download changes nothing. `packages.toml` is updated to match. If a
version has no docs online, docsearch says so (and, for Read the Docs sites, lists the
versions that do). Docs that only exist as the current version (cppreference, MDN, CUDA,
Mojo, MAX, Go) can be upgraded but not downgraded.

To keep two versions side by side instead:

```toml
[packages]
numpy = ["latest", "1.26"]     # packages.toml
```

or `search add numpy==1.26`. A package with several versions gets a version menu on its
button in the page; a search uses one version per package, so results never repeat.

## Adding documentation

```bash
search add numpy                 # a Python package: PyPI tells where its docs are
search add python rust ocaml     # languages and toolkits by name (see: search known)
search add python==3.12          # one version
search add mydocs=https://...    # any docs site (Sphinx, MkDocs, or read as a website)
search add pypi:NAME             # the PyPI package NAME, when NAME is also a language
search known                     # the languages and toolkits that can be added by name
```

`search known` lists: Python, Rust (std, the Book, the Reference), OCaml, C and C++
(cppreference), CUDA, Mojo, MAX, Go and JavaScript (MDN). These names never go through PyPI.

**Wrong docs are not added silently.** When a name could mean another project — docs
titled differently from the name, or a docs site that PyPI does not list and that was
only guessed — docsearch shows what it found and PyPI's own description of the package,
and asks first (`--yes` accepts). Python standard-library modules (e.g. `pathlib`) point
to the Python docs instead of an old PyPI backport. Already added the wrong docs? Click
**Docs…** in the page: it lists every indexed source with its address, and **Remove**
deletes one (also from `packages.toml`). In the terminal: `search remove NAME`.

## How the docs are shown

- **The real documentation HTML**, not a conversion: while indexing, every docs page is
  saved (gzipped, about 10–15 MB per library) and shown with one stylesheet made for
  reading: a column of about 75 characters, system fonts, signatures in a box with one
  parameter per line, "Parameters / Returns / See also" as labelled sections, notes and
  warnings as coloured boxes, maths drawn by Safari (MathML), the libraries' own syntax
  highlighting, and an "On this page" outline.
- **Light or dark** follows the macOS setting. Dark mode uses off-white on dark grey
  (not white on black, which "glows" for people with astigmatism).
- **100% offline, on this Mac.** The "server" is a process on your Mac that only listens
  on 127.0.0.1 (an address that never leaves the machine); Safari is just the renderer.
  Pages and their images are stored while indexing. Links to other websites are shown as
  text (click to copy the address) and cannot be opened. On top of that, every docsearch
  process except `search setup` / `add` / `sync` / `embed` / `upgrade` / `downgrade`
  blocks any network connection that is not to this Mac, so nothing can go online even by
  accident.
- **Safe**: downloaded HTML passes an allowlist (only harmless tags and attributes), and
  the page forbids any script except docsearch's own (Content-Security-Policy). The
  server only answers requests addressed to 127.0.0.1/localhost, and changes nothing
  except when you click **Remove** in the Docs… panel (a request other sites cannot make).

## Layout

| Path | What |
|---|---|
| `pyproject.toml` | project and dependencies |
| `uv.lock` | exact versions of every dependency, with hashes |
| `packages.toml` | your docs list (not in git; `search setup` makes it from `packages.example.toml`) |
| `docsearch/cli.py` | `search`: indexing, ranking, the commands |
| `docsearch/web.py` | the local server behind the Safari page |
| `docsearch/pages.py` | offline pages: the HTML allowlist and storage |
| `docsearch/importers.py` | importers for any docs website and for Rust (rustdoc) |
| `docsearch/sources.py` | the languages and toolkits that can be added by name, and where each publishes its version |
| `docsearch/order.py` | the reading order shown before you type (from the stored pages and the docs' sidebar) |
| `docsearch/embedding.py` | the meaning model, run with MLX on the Apple GPU (no PyTorch) |
| `docsearch/rerank.py` | search with AI: the Qwen3 model (run with MLX, no PyTorch) that reorders the top results |
| `eval/` | the search-quality benchmark (questions, models, statistics); `uv sync --group eval` adds its tools. The questions are Stack Overflow titles (CC BY-SA 4.0), each with its id: stackoverflow.com/q/ID |
| `docsearch/static/` | the page: HTML, stylesheet, script |
| `data/` | downloaded docs, indexes and the two models (not in git; `search setup` fills it) |
| `.venv/` | the environment (not in git; rebuilt by `uv sync`) |
