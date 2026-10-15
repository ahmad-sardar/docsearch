"""Finding a package's docs on made-up sites, one of each kind that went wrong before (the
spot check of 81 packages: eval/results-finding.md), with no internet: a fake web answers.

    .venv/bin/python tests/sites.py

- Hugging Face's libraries: their docs from Hugging Face's own copy (one file), no page of its
  site asked for (it allows 100 a visitor in five minutes);
- a home page's link "Contribute to the docs" (tensorflow.org's): never the docs;
- a home page that PyPI names, linking docs on another site named for the package (numba's);
- a home page with no docs link, its docs in a folder named for the package (onnx.ai/onnx/);
- docs behind a bot check (docs.opencv.org): not got around; the README, said why.
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
    print("all good")


if __name__ == "__main__":
    main()
