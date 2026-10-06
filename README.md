# docsearch

search docs from your terminal. read them in safari. offline.

reading documentation is hard. it's spread over a dozen sites, each with its own layout,
its own search box, its own idea of where things go. you know the function exists, you
just can't remember what it's called or which page it's on.

sure, an llm can write the code for you. but sometimes you want to write it yourself and
just need to look things up fast. for a forgetful brain like mine. without leaving the
terminal.

so: type what you remember, get the official docs.

```bash
search np.sum                             # by name
search lnsvd                              # by a few letters
search dataframe.mrege                    # typos are fine
search sum of elements along an axis      # by meaning
search ai how do i drop duplicate rows    # a question, ranked by a small local model
```

safari opens with results on the left and the docs on the right. that's it.

![docsearch: "matrix" in the cuda docs, ranked with ai](docs/screenshot.png)

## what's in it

python packages (numpy, pandas, torch, scikit-learn, scipy, anything on pypi), plus
python, rust, c, c++, go, javascript, ocaml, cuda, mojo, max and git. add whatever else
you want.

everything runs on your mac. once the docs are downloaded, nothing goes online.

## install

needs a mac with apple silicon and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/ahmad-sardar/docsearch ~/tools && cd ~/tools
uv sync
.venv/bin/search setup        # downloads the models and the docs, once. takes a while.
echo "alias search='$HOME/tools/.venv/bin/search'" >> ~/.zshrc && source ~/.zshrc
```

your list of docs lives in `packages.toml`. edit it and run `search sync`.

## use

```bash
search numpy svd              # just numpy
search                        # open the page
search list                   # what you have, and which version
search stop                   # stop the background server
```

in the page:

| key | does |
|---|---|
| type | search |
| ↑ ↓ | pick a result |
| enter | open the full page |
| esc | back |
| / | jump to the search box |
| w | wrap long code lines |
| c | copy the name |

before you type anything, the list shows the docs in reading order, like a table of
contents.

### search tricks

- `"drop_duplicates"` in quotes: exact match only
- `/^numpy\.linalg\./` between slashes: regex on names
- `search -e drop_duplicates`: exact match from the terminal (the shell eats quotes)
- `search ai ...`: for questions and ideas. a small model on your mac reorders the top
  results. slower (~3 s), better for "how do i...". plain search is better for names.

## adding docs

```bash
search add polars                        # a pypi package
search add rust go                       # languages, see: search known
search add mydocs=https://docs.example.com/
search add mydocs=~/Downloads/docs.zip   # docs you downloaded yourself
search remove polars
```

## versions

```bash
search upgrade                 # everything to latest
search upgrade numpy           # one package
search downgrade numpy==1.26   # an older one
```

want two versions side by side? `numpy = ["latest", "1.26"]` in `packages.toml`.

## saving tutorials

found a good article? keep it.

```bash
search save https://realpython.com/python-f-strings/
search save https://docs.python.org/3/tutorial/classes.html --series   # and the next parts
search save URL --to rust-stuff                                        # your own folder
```

it keeps the article, drops the ads and menus, and makes it searchable with everything else.

## when downloads fail

it tells you why (site down, blocked, moved, needs javascript...) and what to try. your
existing docs are never touched until a new download fully works. if a site won't let
programs in, download the docs yourself and `search add name=/path/to/folder`.

## safe

- offline after setup. the search can't reach the internet even by accident.
- downloaded pages are stripped of scripts before you see them.
- models come from fixed versions and are checked by hash. no pickle files.

## how good is the search

measured, not guessed. see `eval/` if you care.

## license

MIT. use it however you like. (`eval/so_questions.json` has stack overflow titles, which
stay cc by-sa 4.0.)

## contributors

- [@ahmad-sardar](https://github.com/ahmad-sardar)
- claude (anthropic), co-author
