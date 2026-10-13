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
