"""Finding a package's docs on made-up sites, one of each kind that went wrong before (the
spot check of 81 packages: docs/evaluation/results-finding.md), with no internet: a fake web answers.

    .venv/bin/python tests/sites.py

- Hugging Face's libraries: their docs from Hugging Face's own copy (one file), no page of its
  site asked for (it allows 100 a visitor in five minutes);
- a home page's link "Contribute to the docs" (tensorflow.org's): never the docs;
- a home page that PyPI names, linking docs on another site named for the package (numba's);
- a home page with no docs link, its docs in a folder named for the package (onnx.ai/onnx/);
- docs behind a bot check (docs.opencv.org): not got around; the README, said why;
- and where its release publishes its docs, built (opencv-5.0.0-docs.zip): those, one download,
  read with their Doxygen tag file: every function an entry, a class's page its class's;
- an address you gave (learncpp.com, whose every "not there" takes seconds): each request said,
  with how the site answered; folders guessed only where its page links; nothing asked twice.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
import tempfile
import zipfile
import zlib

if "DOCSEARCH_DATA" not in os.environ:
    os.environ["DOCSEARCH_DATA"] = tempfile.mkdtemp(prefix="docsearch-sites-")

from docsearch import cli  # noqa: E402

WEB: dict[str, dict[str, object]] = {}          # host -> path -> body, or (status, body, headers)
ASKED: list[str] = []


def answer(request):
    import httpx
    ASKED.append(str(request.url))
    got = WEB.get(request.url.host, {}).get(request.url.raw_path.decode())
    if got is None:
        return httpx.Response(404, content=b"<html><body>Not found</body></html>")
    status, body, headers = got if isinstance(got, tuple) else (200, got, {})
    return httpx.Response(status, content=body, headers=headers)


def page(title: str, body: str = "", repo: str = "") -> bytes:
    link = f"<nav><a href='https://github.com/{repo}'>GitHub</a></nav>" if repo else ""
    return (f"<html><head><title>{title}</title></head><body>{link}<main><h1>{title}</h1>"
            f"<p>{title} explained, with words enough to be a page of docs.</p>{body}</main></body></html>").encode()


def inventory(project: str) -> bytes:
    objs = f"index std:doc -1 index.html {project}\nguide std:doc -1 guide.html Guide\n"
    return (f"# Sphinx inventory version 2\n# Project: {project}\n# Version: 1.0\n"
            f"# The remainder of this file is compressed using zlib.\n").encode() + zlib.compress(objs.encode())


def pypi(name: str, urls: dict, description: str = "") -> bytes:
    return json.dumps({"info": {"name": name, "summary": f"{name} does things.", "version": "1.2.0",
                                "project_urls": urls, "description": description,
                                "description_content_type": "text/markdown"},
                       "releases": {"1.2.0": []}}).encode()


def check(ok: bool, what: str) -> None:
    print(("ok    " if ok else "FAIL  ") + what, flush=True)
    if not ok:
        sys.exit(1)


def plan_of(name: str) -> tuple[dict | None, str]:
    """What search add would read for a package, and what it said."""
    said = io.StringIO()
    args = argparse.Namespace(yes=True, workers=2, guide=None)
    with contextlib.redirect_stderr(said), contextlib.redirect_stdout(said):
        try:
            plan = cli.web_docs(name, name, "", "", args, check_copy=False)
        except SystemExit:
            plan = None
    return plan, said.getvalue()


def doxygen_zip() -> bytes:
    """A release's docs as Doxygen builds them: pages, and the tag file naming the API."""
    def html(title: str, body: str) -> str:
        return (f"<html><head><title>CVX: {title}</title></head><body><div class='header'><div class='headertitle'>"
                f"<div class='title'>{title}</div></div></div><div class='contents'>{body}</div></body></html>")
    tag = ("<?xml version='1.0'?><tagfile>"
           "<compound kind='namespace'><name>cvx</name><filename>namespacecvx.html</filename>"
           "<member kind='function'><type>Image</type><name>read</name><anchorfile>group__io.html</anchorfile>"
           "<anchor>ga1</anchor><arglist>(const String &amp;path)</arglist></member></compound>"
           "<compound kind='group'><name>io</name><title>Reading and writing</title><filename>group__io.html</filename>"
           "<class kind='class'>cvx::Image</class></compound>"
           "<compound kind='class'><name>cvx::Image</name><filename>classcvx_1_1Image.html</filename></compound>"
           "<compound kind='page'><name>tutorial_root</name><title>CVX Tutorials</title><filename>tutorial_root.html</filename>"
           "<subpage>tutorial_first.html</subpage></compound>"
           "<compound kind='page'><name>tutorial_first</name><title>Your first image</title>"
           "<filename>tutorial_first.html</filename></compound></tagfile>")
    pages = {
        "index.html": html("CVX", "<p>CVX reads and writes images, in many formats, quickly.</p>"),
        "group__io.html": html("Reading and writing", "<p>Functions to read and write images.</p>"
                               "<a id='ga1'></a><h2 class='memtitle'>read()</h2><div class='memitem'>"
                               "<div class='memproto'>Image cvx::read(const String &amp;path)</div>"
                               "<div class='memdoc'><p>Reads an image from a file and returns it.</p></div></div>"),
        "classcvx_1_1Image.html": html("cvx::Image Class Reference", "<p>An image: its pixels, its size.</p>"),
        "tutorial_root.html": html("CVX Tutorials", "<a href='tutorial_first.html'>Your first image</a>"),
        "tutorial_first.html": html("Your first image", "<h1>What we will do</h1><p>Read an image with read, and show it.</p>"),
    }
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for name, text in pages.items():
            z.writestr(f"doc/html/{name}", text)
        z.writestr("doc/html/cvx.tag", tag)
    return out.getvalue()


def web() -> None:
    hf = "/datasets/hf-doc-build/doc-build/resolve/main/hflib/"
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("hflib/v1.2.0/en/index.md", "# HFLib\n\nIt does things.\n")
    WEB["pypi.org"] = {
        "/pypi/hflib/json": pypi("hflib", {"Documentation": "https://huggingface.co/docs/hflib/index",
                                           "Source": "https://github.com/hf/hflib"}),
        "/pypi/tflike/json": pypi("tflike", {"Homepage": "https://tflike.example/",
                                             "Source": "https://github.com/tf/tflike"}),
        "/pypi/numx/json": pypi("numx", {"Homepage": "https://numx.example/"}),
        "/pypi/onnxlike/json": pypi("onnxlike", {"Homepage": "https://onnxlike.example/",
                                                 "Source": "https://github.com/onnx/onnxlike"}),
        "/pypi/cvlike/json": pypi("cvlike", {"Homepage": "https://github.com/cv/cvlike"},
                                  "# cvlike\n\nThe [documentation](https://docs.cvlike.example/master/) is online.\n"),
    }
    WEB["api.github.com"] = {"/repos/hf/hflib": json.dumps({"full_name": "hf/hflib", "homepage": ""}).encode(),
                             "/repos/tf/tflike": json.dumps({"full_name": "tf/tflike", "homepage": ""}).encode(),
                             "/repos/onnx/onnxlike": json.dumps({"full_name": "onnx/onnxlike",
                                                                 "homepage": "https://onnxlike.example/onnxlike/"}).encode(),
                             "/repos/cv/cvlike": json.dumps({"full_name": "cv/cvlike", "homepage": ""}).encode()}
    WEB["huggingface.co"] = {
        "/docs/hflib/index": page("HFLib", "", "hf/hflib"),
        hf + "_versions.yml": b"- version: main\n- version: v1.2.0\n",
        hf + "v1.2.0.zip": archive.getvalue(),
    }
    WEB["tflike.example"] = {
        "/": page("TFLike", "<a href='/community/contribute/docs'>Contribute to the docs</a> "
                            "<a href='/docs/'>Documentation</a>", "tf/tflike"),
        "/community/contribute/docs": page("Contribute to the docs", "", "tf/tflike"),
        "/docs/": page("TFLike documentation", "", "tf/tflike"),
        "/docs/objects.inv": inventory("TFLike"),
    }
    WEB["numx.example"] = {"/": page("Numx", "<a href='https://numx.readthedocs.io/en/stable/'>Documentation</a>")}
    WEB["numx.readthedocs.io"] = {"/en/stable/": page("Numx docs"), "/en/stable/objects.inv": inventory("Numx")}
    WEB["onnxlike.example"] = {"/": page("ONNXLike", "<a href='/about.html'>About</a>"),
                               "/onnxlike/": page("ONNXLike docs", "", "onnx/onnxlike"),
                               "/onnxlike/objects.inv": inventory("ONNXLike")}
    challenge = (403, b"<html><head><title>Just a moment...</title></head></html>",
                 {"cf-mitigated": "challenge", "server": "cloudflare"})
    WEB["docs.cvlike.example"] = {"/master/": challenge, "/master/objects.inv": challenge}
    docs = doxygen_zip()
    WEB["pypi.org"]["/pypi/cvx/json"] = pypi("cvx", {"Homepage": "https://github.com/cvorg/cvx-python"},
                                             "# cvx\n\nSee [the docs](https://docs.cvx.example/master/) and "
                                             "[the library](https://github.com/cvorg/cvx).\n")
    WEB["api.github.com"]["/repos/cvorg/cvx-python"] = json.dumps({"full_name": "cvorg/cvx-python", "homepage": ""}).encode()
    WEB["api.github.com"]["/repos/cvorg/cvx-python/releases?per_page=30"] = b"[]"
    WEB["api.github.com"]["/repos/cvorg/cvx/releases?per_page=30"] = json.dumps([
        {"tag_name": "1.2.0", "draft": False, "prerelease": False,
         "assets": [{"name": "cvx-1.2.0-docs.zip", "size": len(docs),
                     "browser_download_url": "https://github.com/cvorg/cvx/releases/download/1.2.0/cvx-1.2.0-docs.zip"}]},
        {"tag_name": "1.1.0", "draft": False, "prerelease": False, "assets": []}]).encode()
    WEB["github.com"] = {"/cvorg/cvx/releases/download/1.2.0/cvx-1.2.0-docs.zip": docs}
    WEB["docs.cvx.example"] = {"/master/": challenge, "/master/objects.inv": challenge}


def main() -> None:
    import httpx
    cli.CONFIG = cli.DATA / "packages.toml"      # (never yours)
    web()
    cli._CLIENT = httpx.Client(transport=httpx.MockTransport(answer), follow_redirects=False)

    plan, said = plan_of("hflib")
    pages = [u for u in ASKED if "huggingface.co/" in u and "/datasets/" not in u]
    check(plan is not None and plan.get("kind") == "hf-archive" and plan.get("archive") == "v1.2.0" and len(pages) <= 2,
          f"Hugging Face: its own copy of the docs, its pages asked for at most twice ({pages})")
    plan, said = plan_of("tflike")
    check(plan is not None and "/community/" not in str(plan.get("root")) and plan.get("root") == "https://tflike.example/docs/",
          f"a home page's \"Contribute to the docs\": never the docs ({plan and plan.get('root')})")
    plan, said = plan_of("numx")
    check(plan is not None and plan.get("root") == "https://numx.readthedocs.io/en/stable/"
          and "the project's home page, links to them" in said,
          f"a home page PyPI names vouches for docs on another site named for the package ({plan and plan.get('root')})")
    plan, said = plan_of("onnxlike")
    check(plan is not None and plan.get("root") == "https://onnxlike.example/onnxlike/",
          f"no docs link on its home page: the folder named for it there ({plan and plan.get('root')})")
    plan, said = plan_of("cvlike")
    check(plan is not None and plan.get("found") == "readme" and "bot check" in said,
          f"docs behind a bot check: not got around; its README, and why ({plan and plan.get('found')})")
    plan, said = plan_of("cvx")
    check(plan is not None and plan.get("kind") == "release-docs" and plan.get("root") == "https://docs.cvx.example/1.2.0/"
          and "publishes its docs" in said,
          f"docs behind a bot check, but its release publishes them, built: those ({plan and plan.get('kind')})")
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        cli.main(["add", "cvx", "--no-embed"])
    sid = next(s for s in cli.indexed() if s.startswith("cvx"))
    got = {e.title: e for e in cli.iter_entries(sid)}
    read = got.get("cvx::read")
    check(read is not None and read.kind == "function" and "Reads an image" in read.text
          and read.location == "https://docs.cvx.example/1.2.0/group__io.html#ga1"
          and got.get("cvx::Image") is not None and got["cvx::Image"].kind == "class"
          and got.get("Your first image") is not None and got["Your first image"].purpose == "learn"
          and not any("docs.cvx.example" in u and "/master/" not in u for u in ASKED),
          f"a release's Doxygen docs: each function an entry at its place on the docs site; a class's page "
          f"its class; a tutorial titled as Doxygen titles it, to learn from ({sorted(got)[:8]})")
    WEB["learn.example"] = {"/": page("Learn X", "".join(f"<p><a href='/lesson-{k}/'>Lesson {k}</a></p>" for k in range(12))
                                     + "<p><a href='/docs/setup'>Setup</a></p>"),
                            **{f"/lesson-{k}/": page(f"Lesson {k}") for k in range(12)}}
    ASKED.clear()
    said = io.StringIO()
    with contextlib.redirect_stderr(said), contextlib.redirect_stdout(said), cli.telling():
        plan = cli.web_docs("learnx", "learnx=https://learn.example/", "", "https://learn.example/",
                            argparse.Namespace(yes=True, workers=2, guide=None), check_copy=False)
    said = said.getvalue()
    guessed = [u for u in ASKED if u.endswith("objects.inv")]
    check(plan is not None and plan.get("root") == "https://learn.example/"
          and sorted(guessed) == ["https://learn.example/docs/objects.inv", "https://learn.example/objects.inv"]
          and not [u for u in set(ASKED) if ASKED.count(u) > 1]
          and "learn.example/objects.inv · not there (404) · " in said and "waiting for the site's answers" in said,
          f"an address you gave: each request said, with the site's answer; folders guessed only where its page "
          f"links (docs/, not stable/); nothing asked twice ({guessed}; {said.splitlines()[-1:]})")
    WEB["pg.example"] = {"/docs/17/": page("PG 17 manual", "".join(f"<p><a href='/docs/17/ch{k}.html'>Chapter {k}</a></p>"
                                                                  for k in range(12))),
                         **{f"/docs/17/ch{k}.html": page(f"Chapter {k}") for k in range(12)}}
    ASKED.clear()
    plan, said = None, io.StringIO()
    with contextlib.redirect_stderr(said), contextlib.redirect_stdout(said):
        plan = cli.web_docs("pg", "pg==17=https://pg.example/docs/17/", "17", "https://pg.example/docs/17/",
                            argparse.Namespace(yes=True, workers=2, guide=None), check_copy=False)
    check(plan is not None and plan.get("root") == "https://pg.example/docs/17/" and "Could not find" not in said.getvalue()
          and not any("/16/" in u or "/current/" in u or "/stable/" in u for u in ASKED)
          and cli.split_spec("pg@17=https://pg.example/docs/17/") == ("pg", "17", "https://pg.example/docs/17/")
          and cli.source_id("pg==17=https://pg.example/docs/17/") == "pg@17",
          f"an address you give, of a version you say: read as that version, no other looked for "
          f"({plan and plan.get('root')}, {said.getvalue().splitlines()[-1:]})")
    print("all good")


if __name__ == "__main__":
    main()
