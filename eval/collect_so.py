"""Collect a test set from Stack Overflow: real questions whose accepted answer links to
official documentation. The question title is the search; the linked docs page (and its
#section, when given) is the correct answer, judged by the answerer, not by us.

    .venv/bin/python eval/collect_so.py      (needs internet; writes eval/so_questions.json)

Uses the public Stack Exchange API (no key: ~300 requests a day; this uses ~80).
Content is CC BY-SA (Stack Overflow); it is only used here, to measure search quality.
"""
import gzip, html, json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

API = "https://api.stackexchange.com/2.3"
# tag -> (our source, regex for links into its docs)
TAGS = {
    "numpy": ("numpy", r"numpy\.org/doc/"),
    "pandas": ("pandas", r"pandas\.pydata\.org/(pandas-)?docs/"),
    "pytorch": ("torch", r"pytorch\.org/docs/"),
    "scikit-learn": ("scikit-learn", r"scikit-learn\.org/(stable|dev|\d[\d.]*)/"),
    "python": ("python", r"docs\.python\.org/"),
    "rust": ("rust", r"doc\.rust-lang\.org/"),
    "ocaml": ("ocaml", r"ocaml\.org/(manual|api|releases)|caml\.inria\.fr/pub/docs/manual-ocaml"),
    "c++": ("cpp", r"cppreference\.com/w/cpp"),
    "c": ("c", r"cppreference\.com/w/c/"),
    "cuda": ("cuda", r"docs\.nvidia\.com/cuda/"),
    "go": ("go", r"(golang\.org|go\.dev)/(pkg|ref/spec|doc/effective_go)|pkg\.go\.dev/"),
    "javascript": ("javascript", r"developer\.mozilla\.org/[\w-]+/docs/Web/JavaScript/"),
}
LINK = re.compile(r'href="(https?://[^"]+)"')


def get(path, **params):
    params.setdefault("site", "stackoverflow")
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    from docsearch.cli import http_get           # certificate-checked HTTPS (certifi)
    for _ in range(3):
        body = http_get(url, timeout=30)[0]
        data = json.loads(gzip.decompress(body) if body[:2] == b"\x1f\x8b" else body)
        if data.get("backoff"):
            time.sleep(data["backoff"])
        if "items" in data:
            print(f"  quota left {data.get('quota_remaining')}", file=sys.stderr)
            return data["items"]
        time.sleep(2)
    raise RuntimeError(data)


def main():
    out = []
    for tag, (source, pattern) in TAGS.items():
        qs = []
        for page in (1, 2, 3):
            qs += get("/search/advanced", tagged=tag, accepted="True", sort="votes", order="desc",
                      pagesize=100, page=page, filter="default")
            time.sleep(0.5)
        accepted = {q["accepted_answer_id"]: q for q in qs if q.get("accepted_answer_id")}
        ids = list(accepted)
        kept = 0
        for k in range(0, len(ids), 100):
            for a in get(f"/answers/{';'.join(map(str, ids[k:k + 100]))}", filter="withbody", pagesize=100):
                links = [html.unescape(u) for u in LINK.findall(a.get("body", ""))]
                docs = [u for u in links if re.search(pattern, u)]
                if not docs:
                    continue
                q = accepted[a["answer_id"]]
                out.append({"source": source, "tag": tag, "question": html.unescape(q["title"]),
                            "links": list(dict.fromkeys(docs)), "so_id": q["question_id"],
                            "score": q["score"]})
                kept += 1
            time.sleep(0.5)
        print(f"{tag:14} {len(qs):4} top questions with an accepted answer → {kept} link to the docs")
    Path(__file__).with_name("so_questions.json").write_text(json.dumps(out, indent=1))
    print(f"total {len(out)}")


if __name__ == "__main__":
    main()
