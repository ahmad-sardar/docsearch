# Usability results

Questions in `eval/usability.json`; run with `eval/usability.py`. Each ticket's run is added below.

# Baseline (T0), before any change
## Usability (2026-10-12, your data)

71 questions in 3 s. A question counts as answered at #1, in the top 3, in the top 5, or missing (not in the top 50).

### By mode

| | questions | #1 | top 3 | top 5 | missing |
|---|---|---|---|---|---|
| how | 44 | 20 | 26 | 28 | 9 |
| what | 27 | 21 | 25 | 25 | 2 |

### By package

| | questions | #1 | top 3 | top 5 | missing |
|---|---|---|---|---|---|
| all packages | 4 | 2 | 4 | 4 | 0 |
| c | 3 | 2 | 2 | 2 | 0 |
| cpp | 8 | 5 | 6 | 6 | 1 |
| cuda | 3 | 1 | 2 | 2 | 0 |
| langchain | 13 | 7 | 7 | 7 | 6 |
| numpy | 10 | 5 | 7 | 7 | 3 |
| pandas | 11 | 7 | 8 | 9 | 1 |
| polars | 7 | 5 | 6 | 7 | 0 |
| python | 12 | 7 | 9 | 9 | 0 |

### Each question

| package | mode | question | rank | first result |
|---|---|---|---|---|
| numpy | what | np.linalg.svd | 1 | numpy.linalg.svd |
| numpy | how | stack two arrays vertically | 1 | Stacking together different arrays (section) |
| numpy | what | difference between a view and a copy | 1 | Copies and views (page) |
| numpy | what | random integers in a range | 3 | numpy.random.RandomState.random_integers |
| numpy | how | save an array to disk and load it back | 1 | Saving and sharing your NumPy arrays (page) |
| numpy | what | np.where with two conditions | 1 | numpy.select |
| numpy | how | find the indices of the maximum value | — | Analyzing the impact of the lockdown on air quality in Delhi |
| pandas | how | group by multiple columns and sum | 6 | Aggregation (section) |
| pandas | how | merge two dataframes on a column | 1 | pandas.merge › Examples |
| pandas | how | read an excel file with several sheets | 1 | ExcelFile class (section) |
| pandas | how | convert a column to datetime | 1 | Using pandas datetime properties (section) |
| pandas | what | drop_duplicates | 3 | pandas.Index.drop_duplicates |
| pandas | how | apply a function to each row | 1 | Series.apply() and DataFrame.apply() (section) |
| pandas | what | rolling mean | 1 | pandas.api.typing.Rolling.mean |
| pandas | how | change the order of columns | — | Column and index locations and names (section) |
| python | how | read a file line by line | 19 | rlcompleter › Examples |
| python | what | dataclass field default_factory | 1 | dataclasses.field |
| python | how | run coroutines concurrently | 13 | asyncio.Task.cancel › Examples |
| python | how | sort a dictionary by value | 1 | Sorting Techniques (page) |
| python | what | what is a context manager | 1 | context manager (term) |
| python | what | f-string format specification | 1 | Format specification mini-language (section) |
| python | how | parse command line arguments | 1 | Command-line arguments (section) |
| python | how | measure how long a function takes | 2 | signal › Examples |
| polars | what | LazyFrame.collect | 1 | polars.LazyFrame.collect |
| polars | how | filter rows by a condition | 1 | polars.DataFrame.filter › Examples |
| polars | how | group by and aggregate | 2 | SELECT › GROUP BY |
| polars | how | read a parquet file | 1 | Parquet › Read |
| polars | what | window function over groups | 1 | Window (page) |
| cpp | what | std::vector::push_back | 1 | std::vector::push_back |
| cpp | how | sort a vector | 12 | std::ranges::partial_sort › Example |
| cpp | what | unique_ptr vs shared_ptr | 1 | std::shared_ptr |
| cpp | how | read a file line by line | 1 | std::getline › Example |
| cpp | what | lambda capture by reference | 1 | Lambda expressions (since C++11) › Lambda capture |
| c | what | printf format specifiers | 1 | printf, fprintf, sprintf, snprintf, printf_s, fprintf_s, spr |
| c | how | copy a string safely | 9 | strdup › Example |
| cuda | what | cudaMalloc | 1 | cudaMalloc |
| cuda | how | launch a kernel | 2 | cuLaunchCooperativeKernelMultiDevice › Examples |
| langchain | how | create an agent with tools | 1 | LangChain v1 migration guide › Tools |
| langchain | how | stream the agent's responses | 1 | How to collect user feedback for Agent Server runs › Call th |
| langchain | how | get structured output from a model | 1 | LangChain v1 migration guide › Structured output |
| langchain | how | add short-term memory to an agent | — | Quickstart › Next steps |
| langchain | how | ask a human to approve a tool call | — | Quickstart |
| langchain | how | retry a tool call that failed | 1 | How to retry failed runs in experiments (Python only) |
| langchain | what | create_agent | — | Agents |
| langchain | what | what is a checkpointer | 1 | Checkpointers |
| langchain | what | init_chat_model | — | Models › Initialize a model |
| langchain | how | memory persistence | — | Learn › Memory |
| all | how | sort a list | 3 | std::list::sort › Example |
| all | what | malloc | 1 | std::malloc |
| all | what | mean of an array | 2 | ARRAY_MEAN (section) |
| all | how | concatenate two dataframes | 1 | Concatenation |
| numpy | how | invert a matrix (new) | — | Notes (section) |
| numpy | what | what is a ufunc (new) | 3 | import_ufunc |
| numpy | how | reshape an array (new) | — | Shape manipulation (section) |
| pandas | how | fill missing values (new) | 1 | Missing data / operations with fill values (section) |
| pandas | what | MultiIndex (new) | 1 | pandas.MultiIndex |
| pandas | how | write a dataframe to a csv file (new) | 4 | Writing to CSV format (section) |
| python | how | make an http request (new) | 2 | wsgiref.simple_server.make_server › Examples |
| python | what | pathlib.Path.glob (new) | 1 | pathlib.Path.glob |
| python | how | run a shell command and capture its output (new) | 1 | subprocess.run › Examples |
| python | how | log messages to a file (new) | 12 | Logging to multiple destinations (section) |
| polars | how | add a new column (new) | 4 | Expression expansion › Column renaming |
| polars | what | pl.col (new) | 1 | polars.col (page) |
| cpp | how | convert a string to an int (new) | — | std::wstring_convert::converted › Example |
| cpp | what | std::optional (new) | 1 | std::optional |
| cpp | how | iterate over a map (new) | 2 | std::unordered_map › Example |
| c | how | allocate an array dynamically (new) | 1 | calloc › Example |
| cuda | how | copy memory from host to device (new) | 11 | cuMemcpy2D › Examples |
| langchain | how | use a different model provider (new) | — | How to define a decision model evaluator › Step 1. Create th |
| langchain | how | add a custom tool (new) | 1 | Managed Deep Agents quickstart › Custom tools |
| langchain | what | what is middleware (new) | 1 | Middleware integrations › Share your middleware |

## The new langchain copy (temp: the survey's reading), langchain questions
### By package

| | questions | #1 | top 3 | top 5 | missing |
|---|---|---|---|---|---|
| all packages | 4 | 0 | 0 | 0 | 4 |
| langchain | 13 | 12 | 12 | 13 | 0 |

### Each question
| langchain | 13 | 12 | 12 | 13 | 0 |
| langchain | how | create an agent with tools | 1 | Tools |
| langchain | how | stream the agent's responses | 1 | Streaming › Overview |
| langchain | how | get structured output from a model | 1 | Structured output |
| langchain | how | add short-term memory to an agent | 1 | Short-term memory |
| langchain | how | ask a human to approve a tool call | 1 | Human-in-the-loop › Decision types |
| langchain | how | retry a tool call that failed | 1 | How to retry failed runs in experiments (Python only) › Step |
| langchain | what | create_agent | 1 | create_agent |
| langchain | what | what is a checkpointer | 1 | Use the functional API › Manage checkpoints |
| langchain | what | init_chat_model | 1 | init_chat_model |
| langchain | how | memory persistence | 1 | Persistence |
| langchain | how | use a different model provider (new) | 4 | Model providers |
| langchain | how | add a custom tool (new) | 1 | Use tools in a prompt › Add and use tools |
| langchain | what | what is middleware (new) | 1 | Middleware |

# T1: examples, right purpose and real ones only (2026-10-12)

On a copy of your data (`data/index` copied to a scratch folder), organized again by version 3
rules: once, 94 s for the eight copies, nothing downloaded; your `data/` untouched until you run it.

What changed:
- re-organizing kept the page's purpose for examples: numpy's were "look up" (1,460); now an
  example is "do" (or "learn" in a tutorial), wherever it is;
- an example is an "Examples" part, code shown in use (a `>>>` session with its results, a whole
  C/C++ program), or code the docs present as one ("For example:", "Example:", "Run this code");
  not a struct's definition or a grammar in a description;
- cppreference's "This section is incomplete: no example" sections are not examples;
- each example says first what its entry is ("Returns the indices of the maximum values along
  an axis."): its code seldom does;
- found on the way: a section reached by its Sphinx label held only its first paragraph (Python's
  "Reading and writing files": 111 letters of 8,385). Now the whole section; copies you have are
  cut again from their stored pages.

Examples per copy:

| copy | before | after | gone, read |
|---|---|---|---|
| python | 1,477 | 1,199 | 278 description code (`__import__`'s equivalent code, IDL grammar…) |
| numpy | 1,477 (1,460 look up) | 1,432 (all do) | C structs |
| cpp | 3,947 | 3,001 | 928 placeholders; "a possible implementation", data-race code |
| c | 424 | 412 | 12 placeholders |
| cuda | 57 | 3 | 54 struct and enum definitions |
| pandas, polars, langchain | 2,133, 1,289, 93 | same | — |

Python, 20 examples drawn at random and read: 20 are examples. 2 show a method's example under its
class (`asyncio.StreamWriter`: `drain`; `socket.socket`: `recvmsg_into`), since a class's entry
holds its methods' text. 1 said "Parameters" first (fixed: a heading is not the sentence).

### Usability, by mode

| | questions | #1 | top 3 | top 5 | missing |
|---|---|---|---|---|---|
| how, before | 44 | 20 | 26 | 28 | 9 |
| how, T1 | 44 | 25 | 31 | 35 | 6 |
| what, before | 27 | 21 | 25 | 25 | 2 |
| what, T1 | 27 | 20 | 25 | 25 | 2 |

The ticket's targets ("how", numpy, Python):

| question | wanted | before | T1 |
|---|---|---|---|
| find the indices of the maximum value | `numpy.argmax › Examples` | — | 5 (`numpy.ma.argmax` first) |
| stack two arrays vertically | `numpy.vstack › Examples` | — | 3 |
| save an array to disk and load it back | `numpy.save › Examples` | — | 2 |
| read a file line by line | "Reading and writing files" | 43 | 1 |

Questions whose rank changed (rank of the wanted answer; `eval/runs/usability-t1.json`):

| package | mode | question | before | T1 | first now |
|---|---|---|---|---|---|
| numpy | how | find the indices of the maximum value | — | 1 | numpy.ma.argmax › Examples |
| numpy | how | reshape an array | — | 1 | numpy.reshape › Examples |
| numpy | how | invert a matrix | — | 6 | numpy.invert › Examples (bitwise: wrong) |
| python | how | read a file line by line | 19 | 1 | Reading and writing files (section) |
| python | how | measure how long a function takes | 2 | 1 | timeit › Examples |
| python | how | make an http request | 2 | 1 | http.client.HTTPConnection.request › Examples |
| python | how | run coroutines concurrently | 13 | 4 | asyncio.Task.cancel › Examples |
| python | how | log messages to a file | 12 | 19 | Logging to multiple destinations (section) |
| python | what | f-string format specification | 1 | 2 | string.templatelib.Interpolation.format_spec |
| pandas | how | group by multiple columns and sum | 6 | 2 | Aggregation (section) |
| pandas | how | write a dataframe to a csv file | 4 | 3 | Writing to CSV format (section) |
| pandas | how | merge two dataframes on a column | 1 | 4 | Merging (section) |
| cpp | how | sort a vector | 12 | 3 | std::stable_sort › Example |
| cpp | how | iterate over a map | 2 | 1 | std::map::begin › Example |
| cpp | how | read a file line by line | 1 | 2 | std::ftell › Example |
| cpp | how | convert a string to an int | — | 33 | std::wstring_convert::from_bytes › Example |
| c | how | copy a string safely | 9 | 5 | copysign › Example |
| cuda | how | launch a kernel | 2 | 1 | cuLaunchKernel › Examples |
| cuda | how | copy memory from host to device | 11 | — | cuOccupancyMaxPotentialBlockSize › Examples |
| numpy | what | what is a ufunc | 3 | 2 | import_ufunc |

Read with care:
- "Merging", "Aggregation", "Writing to CSV format" are pandas' user-guide sections that answer
  the question; the wanted names ("merge", "groupby", "to_csv") do not match them, so these
  count as lower than they are. The questions were left as written.
- CUDA's copy is its API reference: its 54 "examples" were struct definitions, and how mode
  found cudaMemcpy through them. With 3 real examples, how mode has almost nothing to search
  there. T2 (how mode finds the function) is the fix, not fake examples.

### Stack Overflow dev questions (eval/bench.py), paired, before → T1

MRR@10, the same 141 questions on both, each answered by its own copy; paired randomization test.

| questions | search | before | T1 | change | p |
|---|---|---|---|---|---|
| Stack Overflow (113) | plain (what) | 0.218 | 0.211 | −0.007 | 0.18 |
| Stack Overflow (113) | how | 0.157 | 0.202 | +0.045 | 0.055 |
| Stack Overflow (113) | every entry | 0.230 | 0.250 | +0.021 | 0.13 |
| Names (21) | plain (what) | 0.938 | 0.938 | 0 | 1.0 |
| Ideas (7) | plain (what) | 0.214 | 0.214 | 0 | 1.0 |

Names unchanged; plain search within noise (the questions that moved, both ways, are close
calls among API names: numpy.unique_*, atleast_1d).

# T2: how mode finds the function that does it (2026-10-12)

The same copy as T1 (your data organized by version 3). Each candidate measured on the
usability questions and on the Stack Overflow dev questions in how mode (MRR@10, paired with
"as it was", bootstrap 95% interval of the difference, randomization test):

| how mode | usability how (44): #1 / top 3 / top 5 / missing | Stack Overflow (113) | names (21) |
|---|---|---|---|
| (c) as it was: learn and do only | 25 / 31 / 35 / 6 | 0.202 | 0 |
| (a) learn, do, examples and API objects | 25 / 33 / 33 / 6 | 0.261 (+0.059 [+0.008, +0.114], p=0.033) | 0.938 |
| (b) everything, fused with learn and do | 25 / 33 / 39 / 1 | 0.223 (+0.021 [−0.001, +0.045], p=0.081) | 0.153 |
| **(d) everything, fused with (a)** | **27 / 33 / 35 / 2** | **0.263 (+0.061 [+0.010, +0.117], p=0.029)** | **0.938** |
| (f) (a) fused with learn and do | 28 / 33 / 37 / 5 | 0.217 (+0.015, p=0.167) | — |
| (g) all three lists fused | 26 / 32 / 36 / 4 | 0.226 (+0.024 [+0.001, +0.048], p=0.055) | 0.261 |

Kept: (d). Search how ranks tutorials, guides, how-tos, examples and API objects first (two
votes), and explanations and reference prose after (one), so the function that does it is
found. It is the only candidate meeting all of the ticket's conditions:
- the S1 answers in the top 3: argmax #1, vstack #1, np.save #1, timeit #1, asyncio.gather #2,
  std::sort #3 (as it was: gather #4);
- usability in how mode better (#1 25 → 27, missing 6 → 2);
- Stack Overflow questions whose answer is a how-to (14): 0.261 → 0.290 (p=0.80), no drop;
- plain search unchanged (it is not touched).

Questions that changed from T1 (`eval/runs/usability-t2.json`):

| package | question | T1 | T2 | first now |
|---|---|---|---|---|
| pandas | group by multiple columns and sum | 2 | 1 | pandas.api.typing.DataFrameGroupBy.sum |
| python | run coroutines concurrently | 4 | 2 | asyncio.eager_task_factory |
| all | sort a list | 3 | 1 | polars.Expr.list.sort › Examples: a false match ("list.sort"); Python's list.sort is #3, Sorting Techniques #9 (T4) |
| polars | add a new column | 4 | 1 | polars.DataFrame.with_columns |
| cuda | copy memory from host to device | — | 1 | cudaMemcpyPeer |
| cpp | convert a string to an int | 33 | 25 | std::to_string |
| python | log messages to a file | 19 | 13 | Logging to multiple destinations (section) |
| langchain | add short-term memory / approve a tool call / memory persistence / model provider | — | 4 / 7 / 3 / 18 | (your old langchain copy's guides are labeled look up: T8, T10) |
| python | read a file line by line | 1 | 7 | fileinput.filelineno |
| cuda | launch a kernel | 1 | 8 | CU_GRAPH_KERNEL_NODE_PORT_LAUNCH_ORDER |
| c | copy a string safely | 5 | — | copysign › Example |
| numpy | invert a matrix | 6 | 7 | numpy.invert › Examples |

Worse: three answers that were first now lose to API names close to the words (fileinput's
functions, CUDA's launch enum constants, C's copysign). Speed: how mode searches twice, 66 ms
a search (median) against 34 ms for plain search.

# T3: one result per thing (2026-10-12)

- **One section reached by two labels is one entry** (same page, same title, same text), kept at
  the docs' own label (`#io-parquet`, what cross-references and links elsewhere use) rather
  than the id its heading got from its words (`#parquet`). Organizing version 4 folded pandas
  433, Python 58, langchain 198, CUDA 2, numpy 1; no vector made again.
- **Two results of one name say where each is**, by the first of these that tells them all
  apart: the page's title (pandas' Sorting: "Comparison with R", "Essential basic
  functionality"), the folder (polars' GroupBy: reference/dataframe, reference/lazyframe; C's
  strndup: c/string/byte, c/experimental/dynamic), the parameters (CUDA's cudaMallocAsync
  overloads). 121 results in the usability run's top 10 now carry it.
- **A heading said twice on a page has two places**: Markdown pages (`#example`,
  `#example-1`, cut by the page's own headings, so `## x` in a code block is not one) and the
  copies kept of HTML pages (keras). Your copies other than langchain share no anchor.

Repeated results in the usability run's top 10 (same name, same place): 26 questions before,
13 now, all in your langchain copy, which holds most pages twice (as `.md` and as HTML, 9,304
entries) and both languages: it is replaced in T10.

Usability: how 27 / 33 / 35 / 2, what 20 / 25 / 25 / 2 (as T2); three ranks moved by one
(merge 4 → 5, coroutines 2 → 3, to_csv 3 → 2). Stack Overflow dev, paired with T2 (141
questions): plain +0.001 (p=1.0), how +0.004 (p=0.57), names 0.938 both.

# T4: your project's packages first (2026-10-12)

Searching every package from a project now ranks: what is named exactly as asked first
(`malloc` from a Python project: C's and C++'s malloc stay on top), then the project's own
packages, then the other docs of its languages (and docs of no language, git's), then the rest.
Each known language's docs say their language (sources.py); packages from PyPI are Python.
Searching one package is unchanged.

Usability (a question with `language` is asked from a project using every package of that
language you have): the four cross-package questions 3 / 4 / 4 / 0 (#1 / top 3 / top 5 /
missing), as before. "sort a list" from a Python project:

| project | #1 | #2 | #3 |
|---|---|---|---|
| none | polars.Expr.list.sort › Examples | std::forward_list::sort (C++) | list.sort |
| python, numpy, pandas, polars | polars.Expr.list.sort › Examples | list.sort | polars.Series.list.sort › Examples |
| python, numpy, pandas | list.sort | Sorting Techniques | sorted |

C++ no longer comes before Python's answers. Still open (not a language question): "remove
duplicates from a list" gives pandas' drop_duplicates first and no answer from Python's own docs.
The Stack Overflow benchmark searches one package at a time: not affected.

# T10: replace a copy by coverage; your data (2026-10-14)

A new download replaces the copy you have when it read nine in ten of the pages its site's own
lists name (and under 5% failed), whatever its count of entries; the 70%-of-entries rule is
kept only where nothing says how many pages there are.

Your data:
- **langchain** replaced (your old copy: 26,216 entries, its pages twice, both languages, its
  root broken as "https://"): `search add pypi:langchain` read its API reference
  (reference.langchain.com, 116 pages) and docs.langchain.com as its official guide (1,428
  Python pages; 221 TypeScript ones left out): 1,546 of 1,544 listed pages, 8,680 entries,
  vectors made. The 70% rule would have refused it; coverage took it. packages.toml's line was
  changed from `{ url = "https://docs.langchain.com" }` (the guide only) to `"latest"` (as PyPI
  names its docs, the guide with them). The old copy is backed up outside data/.
- **Guides**: numpy has its tutorials, polars its user guide; pandas, Python, C, C++ and CUDA
  link no guide outside their docs. Organized again to version 6 (nothing downloaded).

Usability on your data, now (all of T1-T10):

| | how: #1 / top 3 / top 5 / missing | what: #1 / top 3 / top 5 / missing |
|---|---|---|
| baseline (T0) | 20 / 26 / 28 / 9 | 21 / 25 / 25 / 2 |
| now | 29 / 35 / 36 / 2 | 22 / 27 / 27 / 0 |

langchain: 11 of 13 first (was 7), none missing (was 6). "What is a checkpointer" is #3 (was
#1 on the old copy, by the word in another page's name; its concept page is still not first:
S6 open). "Use a different model provider": #7 (was missing).
