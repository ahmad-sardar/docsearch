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
