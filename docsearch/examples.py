"""Examples, as a unit with what explains them: the "Examples" part of an API entry (numpydoc:
pandas has one on 95% of its entries), cppreference's "Example" section, a guide's section.
Each example entry stays linked to the entry it belongs to (the same place on the same page),
so the official explanation is one step away. Plain search finds the entry (its examples are
in it); search how finds the examples.

Whether an example is complete is measured from its code, never guessed:
- Python: the names it uses that it never defines or imports (`ast`): "needs df (from
  earlier)", "needs import polars as pl", "needs from itertools import batched" (the object the
  entry documents). numpy's and pandas' docs say their examples assume `import numpy as np`
  and `import pandas as pd`: for them those count as imported.
- C and C++: a program that includes its headers and has main is complete.
- Other languages: not said.
"""
from __future__ import annotations

import ast
import builtins
import re

from docsearch import cli

HEADING = re.compile(r"^(#{1,6} )?Examples?\s*$")     # numpydoc's rubric, a Markdown heading
FENCE = re.compile(r"```([\w+-]*)\n(.*?)```", re.S)
# the text of numpy's "try it in your browser" buttons, not the docs'
WIDGET = re.compile(r"^(Try it in your browser!|Go BackOpen In Tab)\s*$", re.M)
# aliases the docs themselves say their examples assume (numpy's and pandas' docstring guides)
ASSUMED = {"numpy": {"np"}, "pandas": {"pd", "np"}}
IMPORTS = {"np": "import numpy as np", "pd": "import pandas as pd", "pl": "import polars as pl",
           "plt": "import matplotlib.pyplot as plt", "torch": "import torch", "jnp": "import jax.numpy as jnp"}
NAMES = set(dir(builtins)) | {"__file__", "__name__"}
IPYTHON = re.compile(r"^In \[\d*\]:", re.M)
IPYTHON_LINE = re.compile(r"^(In \[\d*\]:|\s+\.\.\.:) ?(.*)$")      # In [1]: x = 1 / ...: more


def unit(e: cli.Entry) -> str | None:
    """The examples of an API entry, with the text around them: its "Examples" part; else its
    code (each block with the sentence before it), past the signature. None: it has none."""
    text = WIDGET.sub("", e.text)
    lines = text.splitlines()
    at = next((k for k, ln in enumerate(lines) if HEADING.match(ln.strip())), None)
    if at is not None:
        level = len(lines[at]) - len(lines[at].lstrip("#")) if lines[at].startswith("#") else 0
        end = next((k for k in range(at + 1, len(lines)) if level and re.match(rf"#{{1,{level}}} ", lines[k])),
                   len(lines))                       # (to the next heading as high as its own)
        part = "\n".join(lines[at + 1:end]).strip()
        return part if "```" in part else None
    blocks = list(FENCE.finditer(text))
    if blocks and blocks[0].start() < 5:            # (the signature: Sphinx puts it first)
        blocks = blocks[1:]
    blocks = [b for b in blocks if ">>>" in b.group(2) or "\n" in b.group(2).strip()]
    if not blocks:
        return None
    out = []
    for b in blocks:
        before = text[:b.start()].rstrip().rsplit("\n\n", 1)[-1].strip()
        out += ([before] if before and "```" not in before else []) + [b.group(0)]
    return "\n\n".join(out)


def entries_of(entries: list[cli.Entry]) -> list[cli.Entry]:
    """Example entries for the API entries that have examples, each at its entry's place."""
    out = []
    have = {e.title for e in entries}
    for e in entries:
        if e.kind in cli.PAGE_KINDS or e.kind == "example":
            continue
        title = f"{cli.api_name(e.title)} › Examples"
        if title in have or f"{e.title} › Example" in have:     # (cppreference: its own Example section)
            continue
        text = unit(e)
        if text:
            out.append(cli.Entry(title, "example", e.location, text[:cli.PREVIEW_CHARS], e.source,
                                 "learn" if e.purpose == "learn" else "do"))
    return out


# --------------------------------------------------------------------------- complete or not

def python_code(text: str) -> list[str]:
    """The Python of an example's code blocks: doctest lines without their prompts (and not
    their output), or a block as it is."""
    out = []
    for lang, body in FENCE.findall(text):
        if lang and lang not in ("python", "py", "pycon", "python3", "ipython"):
            continue
        if ">>>" in body:
            code = [ln[4:] for ln in body.splitlines() if ln.startswith((">>> ", "... ")) or ln in (">>>", "...")]
            out.append("\n".join(code))
        elif IPYTHON.search(body):                   # IPython's prompts (pandas' user guide)
            out.append("\n".join(m.group(2) for ln in body.splitlines() if (m := IPYTHON_LINE.match(ln))))
        else:
            out.append(body)
    return out


def defined_and_used(tree: ast.AST) -> tuple[set[str], set[str]]:
    defined, used = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            (used if isinstance(node.ctx, ast.Load) else defined).add(node.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            defined |= {(a.asname or a.name).split(".")[0] for a in node.names}
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, ast.arg):
            defined.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            defined.add(node.name)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            defined.add(node.name)
    return defined, used


def needs(text: str, lang: str = "", package: str = "", name: str = "") -> dict | None:
    """What an example needs that it does not have: {"complete": True} or {"needs": [...]};
    None when it has no code this can read. `package`: the docs' package (their assumed
    imports); `name`: the API object the entry documents (numpy.sum)."""
    if lang in ("c", "cpp") or re.search(r"```(cpp|c|c\+\+)\n", text):
        code = "\n".join(body for _, body in FENCE.findall(text))
        if not code.strip():
            return None
        if "#include" in code and re.search(r"\bmain\s*\(", code):
            return {"complete": True}
        return {"needs": ["a main function" if "#include" in code else "#include and main"]}
    blocks = python_code(text)
    trees = []
    for code in blocks:
        try:
            trees.append(ast.parse(code))
        except SyntaxError:
            continue
    if not trees:
        return None
    defined, used = set(), set()
    for tree in trees:
        d, u = defined_and_used(tree)
        defined |= d
        used |= u
    missing = sorted(used - defined - NAMES - ASSUMED.get(package, set()))
    if not missing:
        return {"complete": True}
    module, _, leaf = name.rpartition(".")
    said = []
    for n in missing:
        if n in IMPORTS:
            said.append(IMPORTS[n])
        elif n == leaf and module:
            said.append(f"from {module} import {n}")
        elif n == (module or name).split(".")[0]:
            said.append(f"import {n}")
        else:
            said.append(f"{n} (from earlier)")
    return {"needs": said}
