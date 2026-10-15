# Getting docs without breaking a site's policy (2026-10-12)

Why: Hugging Face answered `429 Too Many Requests` while docsearch surveyed and read its docs
(D1). The question is how to get a site's docs within what it allows, not around it.

## What the sites and standards say

- **Hugging Face** ([Hub rate limits](https://huggingface.co/docs/hub/en/rate-limits)): web pages
  on huggingface.co allow **100 requests per 5 minutes** per IP address for anonymous users
  (200 for a free account). Files from repositories (`/resolve/`) allow 3,000. Every answer
  carries `RateLimit: "pages";r=<left>;t=<seconds to reset>` and `RateLimit-Policy: "fixed
  window";"pages";q=100;w=300` (the IETF draft "RateLimit header fields for HTTP"). Their
  advice: spread requests out, and prefer file downloads to page requests.
  Its robots.txt allows everything; the rate limit is the policy.
- **Hugging Face's own copy of its docs**: every library's built docs, one zip per version, in
  the dataset [hf-doc-build/doc-build](https://huggingface.co/datasets/hf-doc-build/doc-build)
  (staff point people there to [download all the docs](https://discuss.huggingface.co/t/how-to-download-all-the-docs/51669)).
  About 60 libraries: transformers, datasets, accelerate, diffusers, peft, trl, tokenizers,
  huggingface_hub, smolagents... Checked (safetensors, 1.2 MB): each page as **Markdown**
  (API pages fully written out: signatures, parameters, returns, examples, `[[anchor]]` ids),
  as HTML, the site's outline (`_toctree.yml`), `llms.txt`, `llms-full.txt`, and
  `_versions.yml`. transformers v5.9.0 is one 66 MB file: **1 request instead of ~760**.
- **Robots exclusion** ([RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html)): a robots.txt
  that answers 4xx means no rules; one that answers **5xx or cannot be reached means "assume
  complete disallow"**; cache it at most 24 h. Crawl-delay is not in the standard (docsearch
  keeps it anyway).
- **Read the Docs** ([API v3](https://docs.readthedocs.com/platform/stable/api/v3.html)): 5
  unauthenticated API requests a minute; a version may offer its HTML as one zip
  (`/_/downloads/<lang>/<version>/htmlzip/`), but only if the project turned it on
  (requests, numba: 404).
- **Python** ([download](https://docs.python.org/3/download.html)): the whole docs of a version
  as one HTML zip (`archives/python-3.15-docs-html.zip`).
- **Mintlify sites** (docs.langchain.com): `llms-full.txt`, the whole docs in one file
  ([Mintlify](https://mintlify.com/docs/ai/llmstxt)).
- **Polite crawling, generally** ([AWS guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/web-crawling-system-esg-data/best-practices.html),
  [slatecave](https://slatecave.net/blog/being-a-polite-crawler-on-the-web)): a User-Agent
  that says who you are and where to read about you; robots.txt; few connections per host;
  slow down on 429/503 and keep Retry-After; conditional requests (ETag, Last-Modified) so
  unchanged pages are not sent again; an API or a download over pages when there is one.

## What docsearch did

- Pages: robots.txt kept, Crawl-delay kept, slows down on 429/503, Retry-After kept (at most
  60 s), one host's requests paced over all threads. A User-Agent without a contact.
- The survey asked for every list a site might have (up to 30 sitemap files), each retried 3
  times on a 429: on huggingface.co, enough to spend the 100 pages before reading began.
- A robots.txt that did not answer (5xx, no connection) was taken as "everything allowed".
- `RateLimit` headers were not read: it learned of the limit only from 429s.

## Done (T5)

1. **One official download over many pages, where the publisher offers one**: Hugging Face's
   libraries from hf-doc-build (docsearch/hfdocs.py): `_versions.yml`, then one zip of the
   version you use (else main for a newer one); Markdown pages, API objects by their headings'
   ids, the outline from `_toctree.yml`. transformers 5.19.0: 753 pages, 14,007 entries, one
   57 MB download in 79 s, no page asked for (it was 763 pages, into the 100-a-5-minutes limit).
2. **Paced by the site's own numbers**: `RateLimit` (`r=` left, `t=` to the reset) spreads what
   is left over the window; at none, or a 429, every request waits for the reset (up to 5
   minutes, said). Retry-After kept up to 5 minutes.
3. **Slow, and in pieces**: a site asking for a longer pause (Retry-After: an hour) stops the
   download; what was read is kept, and the same command goes on after that time. An update
   (`search sync`) that stops goes on the same way (its new copy is kept in staging).
4. **The survey asks less**: one try per list; a site that says "too many" is asked nothing more
   in the survey, and not marked unreachable for it; the sitemaps only when the site's own list
   (llms.txt, search index) is not there.
5. **robots.txt as RFC 9309**: answering 5xx or not reached, nothing is read from that site in
   this run, said so; 4xx, no rules.

6. **A release's published docs** (2026-10-14): where the docs site refuses programs (OpenCV's
   docs.opencv.org: a Cloudflare bot check) or none is found, the built docs the project's
   GitHub release publishes for that version (`opencv-5.0.0-docs.zip`, 127 MB: one download
   from GitHub, the project's own), before the README. Doxygen docs are read with their tag
   file (docsearch/doxygen.py). OpenCV 5.0.0: 33,370 entries, every function and class, the
   tutorials (Python and C++; the Java, Clojure, Android, iOS and JavaScript ones left out).

Not done:
- **User-Agent with a contact address** (`+https://github.com/ahmad-sardar/docsearch`): good
  practice, but it sends your GitHub address to every site; your call.
- **Conditional requests** (ETag / If-Modified-Since) so `search sync` gets only changed pages:
  a larger change; later.
- **Other one-file sources** (Python's HTML zip, Read the Docs' htmlzip where a project has it,
  Mintlify's `llms-full.txt`): plausible; each to be measured before it replaces page reading.
