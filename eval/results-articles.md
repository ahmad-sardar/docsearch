# Saved articles: general extraction (docsearch/article.py)

`search save` takes an article's text out of the site around it. The first version named
clutter it had met (ad labels, "nav-button" classes...); it was replaced by a general
method after Mozilla's Readability (Firefox's Reader View): link density, sentences of
their own, code and data tables kept, a standard list of "unlikely" container names.

14 pages from different kinds of sites, against trafilatura as an independent reference
(`uv run --with trafilatura python eval/articles.py`); recall and precision of 4-word runs:

| page | old recall | old precision | **new recall** | **new precision** | code blocks |
|---|---|---|---|---|---|
| realpython.com (tutorial, ads) | 0.98 | 0.97 | 0.97 | **1.00** | 45 = 45 |
| learncpp.com (lesson, prev/next box) | 1.00 | 0.99 | 1.00 | 0.99 | 8 = 8 |
| jvns.ca (blog) | 1.00 | 1.00 | 0.99 | 1.00 | 10 = 10 |
| docs.python.org (Sphinx howto) | 1.00 | 0.98 | 1.00 | 0.98 | 28 = 28 |
| developer.mozilla.org (guide) | 0.95 | 0.95 | **0.98** | **0.99** | 29 = 29 |
| digitalocean.com (built by JavaScript) | 0.22 | 0.28 | 0.22 | **0.78** | refused: no text of its own |
| martinfowler.com (long article) | 1.00 | 0.95 | 1.00 | **0.97** | 0 |
| paulgraham.com (plain HTML) | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| en.wikipedia.org | 0.97 | 0.91 | 0.96 | **0.94** | 3 = 3 |
| w3schools.com (ads, menus) | 0.99 | 0.96 | 0.99 | **0.98** | 0 |
| blog.rust-lang.org | 1.00 | 0.97 | 0.99 | **1.00** | 2 = 2 |
| freecodecamp.org | 1.00 | 0.99 | 1.00 | 0.99 | 49 = 49 |
| go.dev/blog | 0.99 | 1.00 | 0.99 | 1.00 | 12 = 12 |
| danluu.com | 1.00 | 0.95 | 1.00 | 0.95 | 0 |
| **median** | 1.00 | 0.97 | 0.99 | **0.99** | |
| **worst** | 0.22 | 0.28 | 0.22 | **0.78** | |

What the new method leaves out that the reference keeps: Wikipedia's "See also" link list
(navigation; Reader View drops it too). A page whose text is drawn by JavaScript
(DigitalOcean: 37 words of article) is reported as such by `search save`, not saved.
