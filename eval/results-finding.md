# Finding the docs (search add NAME): 81 popular packages

What `search add` would read for each package, its plan only (no pages read): the docs it
finds, how it confirms they are the package's own, and the parts it adds. Runs: before T5
(`eval/runs/finding-before-t5.json`), after T5 (`eval/runs/finding-t5.json`).

## T5: trusted paths, fewer requests (2026-10-14)

| | sphinx | website | Hugging Face's copy | README only | nothing |
|---|---|---|---|---|---|
| before | 54 | 16 | — | 6 | 5 |
| after | 58 | 17 | 4 | 2 | 0 |

What changed, package by package:

| package | before | after | why |
|---|---|---|---|
| transformers, datasets, accelerate, diffusers | nothing (rate limited) | Hugging Face's own copy of the docs, one download | hfdocs.py |
| tensorflow | www.tensorflow.org/community/contribute/ | www.tensorflow.org/ | contributing pages are never docs |
| numba | README | numba.readthedocs.io | its home page (PyPI's) links them |
| onnx | README | onnx.ai/onnx/ | the folder named for it on its home site; its repository names the site |
| attrs | nothing (a crash: `[x]` read as an IPv6 address) | www.attrs.org | fixed |
| openai, anthropic | README | developers.openai.com/api/reference/, platform.claude.com/docs/en/api/ | its PyPI description links them |
| selenium | www.selenium.dev (the whole site) | its Python API docs (selenium.dev/selenium/docs/api/py/) | its PyPI description links them |
| opencv-python | README | README, saying why | docs.opencv.org shows a bot check: not got around |
| gradio | README | README | its docs are drawn by JavaScript and list no pages for programs |

No package found worse. Left for T6: openai lists one guide twice; Hugging Face's "Learn" (its
courses) is offered as a guide of every library.

Hugging Face's copy, read for real (transformers, in a scratch folder): `_versions.yml`, then
`v5.19.0.zip` (57 MB): 753 pages, 14,007 entries (API objects by their headings' ids), the
site's outline, in 79 s; no page of huggingface.co asked for.

The rest of T5 (notes/fetching-policy.md): requests paced by the site's own RateLimit header;
a long pause it asks for stops the download, kept, to go on after it; robots.txt as RFC 9309
(a 5xx means nothing is read); the survey asks once per list and less; `search add NAME`
uses packages.toml's address for it.

## T6: guides are docs sites, never twice (2026-10-14)

A guide is taken from the docs' header only by the name it gives itself (the whole of its
link's text, or a menu item's first words: "User guide", "Tutorials", "Learn", "Cookbook"),
only if it is a docs site (a Sphinx inventory, a search index, llms.txt, or a page that says
what built it or where its docs begin; not a site with only a sitemap), never these docs at
another version, and once. Its pages come from its own list.

| package | before (T5's run) | after |
|---|---|---|
| pytest, scrapy | + the same docs at `en/latest/` | one part |
| vllm | + `en/latest/` | one part (and its pages beside its API inventory, as before) |
| pymongo | + "Learn more" → mongodb.com/solutions/ | none |
| scipy | + "Installing" → scipy.org | none |
| tensorflow | + Install, Learn, Tutorials, Learn ML, Guide | none (its docs are the whole site now: T5) |
| polars | "User guide": 1,440 pages (the host's sitemap: other API versions) | "User guide": 87 pages (its search index) |
| openai | Learn, Cookbook, Learn again | Cookbook, Learn |
| transformers, datasets, accelerate, diffusers | + "Learn" → huggingface.co/learn/ (courses) | none (no docs site there) |
| numpy | Learn → numpy.org/numpy-tutorials/ | the same |
| langchain | docs.langchain.com (from PyPI) | the same |
