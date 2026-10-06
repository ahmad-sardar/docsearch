"""End-to-end check on a fresh machine (the Windows CI runs this): index a small folder of
docs, search it through the server (by name, typo, meaning and with AI), read a stored
page, then remove the docs while the server still runs.

    uv run python tests/smoke.py

Everything goes to a temporary folder (DOCSEARCH_DATA, and a packages.toml there). The
models are downloaded into it the first time, unless DOCSEARCH_DATA already has them.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

if "DOCSEARCH_DATA" not in os.environ:
    os.environ["DOCSEARCH_DATA"] = tempfile.mkdtemp(prefix="docsearch-smoke-")

from docsearch import cli, rerank, web  # noqa: E402

PAGES = {
    "index.html": ("Mini docs", "Welcome to the mini library. It shows how docs are searched."),
    "api/frames.html": ("frames.drop_duplicates",
                        "Return a table with duplicate rows removed. Rows that repeat an earlier row are "
                        "dropped, so every row is unique. Use keep to choose which copy stays."),
    "api/arrays.html": ("arrays.svd",
                        "Singular value decomposition of a matrix: factors it into U, S and V."),
    "con.html": ("Console output", "How the library prints to the console. A device name on Windows."),
    "aux/notes.html": ("Notes", "Extra notes, stored under a folder whose name Windows reserves."),
}


def check(ok: bool, what: str) -> None:
    print(("ok    " if ok else "FAIL  ") + what, flush=True)
    if not ok:
        web.stop()
        sys.exit(1)


def server_log() -> None:
    if web.LOG.exists():
        print("--- server.log\n" + web.LOG.read_text(encoding="utf-8", errors="replace")[-4000:])


def get(port: int, path: str, **params) -> dict:
    url = f"http://127.0.0.1:{port}{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=600) as r:
        return json.loads(r.read())


def main() -> None:
    data = Path(os.environ["DOCSEARCH_DATA"])
    cli.CONFIG = data / "packages.toml"
    docs = data / "mini-docs"
    for rel, (title, text) in PAGES.items():
        f = docs / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f"<html><head><title>{title}</title></head><body><main><h1>{title}</h1>"
                     f"<p>{text}</p></main></body></html>", encoding="utf-8")
    print(f"data in {data}; models on the {'GPU (MLX)' if cli.use_mlx() else 'processor (numpy)'}")
    if rerank.model_dir() is None:
        rerank.download()
    cli.main(["add", f"mini={docs}"])
    check((cli.HOME / "mini" / "emb.npy").exists(), "indexed, with vectors")

    port = web.start()
    try:
        def top(q: str, **kw) -> list[str]:
            return [it["name"] for it in get(port, "/api/search", q=q, src="mini", **kw)["items"]]
        check(top("drop_duplicates")[:1] == ["frames.drop_duplicates"], "search by name")
        check(top("drop_duplciates")[:1] == ["frames.drop_duplicates"], "search with a typo")
        check(top("remove repeated rows")[:1] == ["frames.drop_duplicates"], "search by meaning")
        r = get(port, "/api/search", q="how do i factor a matrix", src="mini", ai="1")
        check(r["ai"] == "ranked" and r["items"][0]["name"] == "arrays.svd", "search ai")
        for q in ("Console output", "Notes"):
            hit = get(port, "/api/search", q=q, src="mini")["items"][0]
            entry = get(port, f"/api/entry/{hit['id']}")
            check(q in json.dumps(entry), f"stored page of '{q}' (a name Windows reserves)")
        cli.main(["remove", "mini"])                 # while the server still runs
        check(not (cli.HOME / "mini").exists(), "removed while the server runs")
    finally:
        web.stop()
    print("all good")


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        server_log()
        raise
