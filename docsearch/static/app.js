// docsearch: search as you type, read the docs, never leave the page.
// Everything comes from the docsearch server on this computer; nothing here goes online.
// All text from the server is inserted with textContent, except the docs HTML itself,
// which the server allowlist-filtered; the Content-Security-Policy blocks any script in it.
"use strict";

const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const state = {
  q: "", srcs: new Set(), active: {}, items: [], total: 0, sel: -1,   // srcs: package groups
  view: null,                 // {type: "entry", id} | {type: "page", path, at} | {type: "home"}
  searchCtl: null, docCtl: null, openTimer: null, typeTimer: null, sources: [],
};
const el = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
};

async function getJSON(url, ctl) {
  const r = await fetch(url, { signal: ctl ? ctl.signal : undefined });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.statusText);
  return r.json();
}

// ---- start -------------------------------------------------------------------------
init();

async function init() {
  const info = await getJSON("/api/info");
  state.sources = info.sources;
  const p = new URLSearchParams(location.search);
  state.q = p.get("q") || "";
  for (const s of state.sources) if (s.default) state.active[s.group] = s.id;
  for (const id of (p.get("src") || "").split(",").filter(Boolean)) {   // e.g. numpy@1.26
    const s = state.sources.find((x) => x.id === id);
    if (s) { state.srcs.add(s.group); state.active[s.group] = s.id; }
  }
  try { if (localStorage.getItem("wrapCode") === "1") document.body.classList.add("wrap-code"); } catch (_) {}
  state.ai = p.get("ai") === "1";            // "search ai IDEA" turns AI on; plain "search", off
  $("#ai").setAttribute("aria-pressed", state.ai ? "true" : "false");
  $("#q").value = state.q;
  renderSources();
  bindEvents();
  await search({ openFirst: !p.get("id") && !p.get("page") });
  if (p.get("page")) openPage(p.get("page"), p.get("at"), false);
  else if (p.get("id")) openEntry(+p.get("id"), false);
  else if (!state.q) showHome();
  $("#q").focus();
}

// One button per package; a version menu when several versions are indexed.
function renderSources() {
  const nav = $("#sources");
  nav.textContent = "";
  const groups = {};
  for (const s of state.sources) (groups[s.group] = groups[s.group] || []).push(s);
  for (const [group, versions] of Object.entries(groups)) {
    const active = versions.find((s) => s.id === state.active[group]) || versions[0];
    const b = el("button", null, active.name);
    b.setAttribute("aria-pressed", state.srcs.has(group) ? "true" : "false");
    b.title = `${active.count} entries${active.offline ? ", offline pages" : ""}. Click to search only this package.`;
    b.addEventListener("click", () => {
      state.srcs.has(group) ? state.srcs.delete(group) : state.srcs.add(group);
      renderSources();
      search({ openFirst: !!state.q });
    });
    if (versions.length > 1) {                       // choose the version to search
      const sel = el("select", "ver");
      sel.title = "Docs version";
      for (const v of versions) {
        const o = el("option", null, v.version || v.id.split("@")[1] || "latest");
        if (v.dated) o.title = `No version number published: the docs as downloaded on ${v.version}`;
        o.value = v.id;
        o.selected = v.id === active.id;
        sel.append(o);
      }
      sel.addEventListener("click", (ev) => ev.stopPropagation());
      sel.addEventListener("change", () => {
        state.active[group] = sel.value;
        renderSources();
        search({ openFirst: !!state.q });
      });
      b.append(sel);
    } else if (active.version) {
      const v = el("span", "v", active.version);
      if (active.dated) v.title = `No version number published: the docs as downloaded on ${active.version}`;
      b.append(v);
    }
    nav.append(b);
  }
}

// "numpy 2.5": a source's name and docs version, as on its button.
function sourceLabel(id) {
  const s = state.sources.find((x) => x.id === id);
  return s ? `${s.name} ${s.version}`.trim() : id;
}

// The sources a search covers: the chosen packages (or all), each in its active version.
function searchedSources() {
  const groups = state.srcs.size ? [...state.srcs] : [...new Set(state.sources.map((s) => s.group))];
  return groups.map((g) => state.active[g] || g);
}

// ---- searching -----------------------------------------------------------------------
async function search({ openFirst = true, append = false, ai = false } = {}) {
  if (state.searchCtl) state.searchCtl.abort();
  clearTimeout(state.aiTimer);
  const ctl = (state.searchCtl = new AbortController());
  const params = new URLSearchParams({ q: state.q, src: searchedSources().join(","),
                                       offset: append ? state.items.length : 0, limit: 80 });
  if (ai) { params.set("ai", "1"); status(`Ranking with AI… (“${state.q}”)`); }
  let data;
  try { data = await getJSON(`/api/search?${params}`, ctl); } catch (e) { if (e.name !== "AbortError") status(e.message); return; }
  if (append) state.items.push(...data.items);
  else { state.items = data.items; state.sel = -1; $("#results").textContent = ""; $(".results-pane").scrollTop = 0; }
  state.total = data.total;
  renderResults(append ? data.items : state.items, append ? state.items.length - data.items.length : 0);
  const where = state.srcs.size ? searchedSources().join(", ") : "all packages";
  const fixed = data.corrected ? ` · also searched “${data.corrected}”` : "";
  status(state.q ? `${data.total} results for “${state.q}”${fixed} · ${where}${data.ai === "ranked" ? " · ranked with AI" : ""}`
                 : `${data.total} entries · ${where}, in reading order`);
  if (data.error) status(data.error);
  if (data.ai === "not installed") {
    toast("The AI model is not downloaded yet. In a terminal: search setup");
    setAI(false);
  }
  if (!append && openFirst && state.items.length) select(0);
  if (!append && !state.items.length && state.q) showEmpty();
  syncURL(false);
  // With AI on: fast results first; once typing pauses, the model reorders the top results.
  if (!append && !ai && state.ai && state.q) {
    state.aiTimer = setTimeout(() => search({ openFirst, ai: true }), 450);
  }
}

function setAI(on) {
  state.ai = on;
  $("#ai").setAttribute("aria-pressed", on ? "true" : "false");
}

function status(text) { $("#status").textContent = text; }

function renderResults(items, start) {
  const ol = $("#results");
  $(".more", ol)?.remove();
  items.forEach((it, k) => {
    const li = el("li", "r");
    li.setAttribute("role", "option");
    li.dataset.n = start + k;
    li.append(el("span", "n", String(start + k + 1)));
    const name = el("div", "name");
    const cut = it.api ? it.name.lastIndexOf(".") + 1 : 0;
    if (cut > 0) name.append(marked(it.name.slice(0, cut), "path"));
    name.append(marked(it.name.slice(cut), "leaf"));
    name.title = it.name;
    li.append(name);
    const meta = el("div", "meta");
    meta.append(el("span", "kind", it.kind));
    if (state.sources.length > 1 && !state.srcs.size) meta.append(el("span", "src", sourceLabel(it.source)));
    if (it.summary) meta.append(el("span", "sum", it.summary));
    li.append(meta);
    ol.append(li);
  });
  if (state.items.length < state.total) ol.append(el("li", "more", "Scroll for more"));
}

// The parts of a name that match the query words, underlined.
function marked(text, cls) {
  const span = el("span", cls);
  const words = state.q.toLowerCase().split(/[^a-z0-9_]+/).filter((w) => w.length > 1);
  const low = text.toLowerCase();
  const on = new Array(text.length).fill(false);
  for (const w of words) for (let i = low.indexOf(w); i >= 0; i = low.indexOf(w, i + 1)) on.fill(true, i, i + w.length);
  let i = 0;
  while (i < text.length) {
    let j = i;
    while (j < text.length && on[j] === on[i]) j++;
    span.append(on[i] ? el("mark", null, text.slice(i, j)) : document.createTextNode(text.slice(i, j)));
    i = j;
  }
  return span;
}

function select(n, { open = true, scroll = true } = {}) {
  if (n < 0 || n >= state.items.length) return;
  const rows = $$("#results .r");
  rows[state.sel]?.setAttribute("aria-selected", "false");
  state.sel = n;
  rows[n]?.setAttribute("aria-selected", "true");
  if (scroll) rows[n]?.scrollIntoView({ block: "nearest" });
  if (n > state.items.length - 15 && state.items.length < state.total) search({ append: true });
  if (open) {                      // the list moves at once; the doc follows when you pause
    clearTimeout(state.openTimer);
    state.openTimer = setTimeout(() => openEntry(state.items[n].id, false), 70);
  }
}

// ---- reading ------------------------------------------------------------------------------
async function openEntry(id, push = true) {
  if (state.docCtl) state.docCtl.abort();
  const ctl = (state.docCtl = new AbortController());
  let d;
  try { d = await getJSON(`/api/entry/${id}`, ctl); } catch (e) { if (e.name !== "AbortError") toast(e.message); return; }
  state.view = { type: "entry", id };
  renderDoc({
    crumbs: d.api && d.name.includes(".") ? d.name.split(".").slice(0, -1) : [d.source],
    title: d.api ? d.name.split(".").pop() : d.name, kind: d.kind,
    meta: [`${d.source} ${d.version}`.trim()], html: d.html, web: d.web,
    actions: [
      d.page && { label: "Full page", primary: true, key: "Enter", run: () => openPage(d.page.path, d.page.at) },
      { label: "Copy name", run: () => copy(d.name, "name") },
      d.import && { label: "Copy import", run: () => copy(d.import, "import") },
    ],
  });
  syncURL(push);
}

async function openPage(path, at, push = true) {
  if (state.docCtl) state.docCtl.abort();
  const ctl = (state.docCtl = new AbortController());
  let d;
  try { d = await getJSON(`/api/page?${new URLSearchParams({ path })}`, ctl); } catch (e) { if (e.name !== "AbortError") toast(e.message); return; }
  const from = state.view && state.view.type === "entry" ? state.view : null;
  state.view = { type: "page", path, at };
  renderDoc({
    crumbs: [d.source, ...path.split("/").slice(1, -1)], title: d.title, kind: "page",
    meta: [`${d.source} ${d.version}`.trim(), "offline copy"], html: d.html, web: d.web, page: true,
    actions: [from && { label: "← Back to entry", run: () => history.back() }],
  }, at);
  syncURL(push);
}

function renderDoc(d, at) {
  const doc = $("#doc");
  doc.textContent = "";
  const head = el("header", "doc-head");
  const crumbs = el("div", "crumbs");
  d.crumbs.filter(Boolean).forEach((c) => crumbs.append(el("span", null, c)));
  head.append(crumbs);
  const row = el("div", "title-row");
  row.append(el("h1", null, d.title));
  if (d.kind) row.append(el("span", "pill kind", d.kind));
  d.meta.filter(Boolean).forEach((m) => row.append(el("span", "pill", m)));
  head.append(row);
  const actions = el("div", "actions");
  for (const a of d.actions.filter(Boolean)) {
    const b = el("button", a.primary ? "primary" : null, a.label);
    if (a.key) b.title = `Shortcut: ${a.key}`;
    b.addEventListener("click", a.run);
    actions.append(b);
  }
  const wrap = el("button", null, document.body.classList.contains("wrap-code") ? "Code: wrap" : "Code: scroll");
  wrap.title = "Wrap long code lines, or keep them on one line and scroll sideways (shortcut: w)";
  wrap.addEventListener("click", () => toggleWrap(wrap));
  actions.append(wrap);
  if (d.web) {                                       // offline: the address can be copied, not opened
    const b = el("button", null, "Copy web address");
    b.title = d.web;
    b.addEventListener("click", () => copy(d.web, "web address"));
    actions.append(b);
  }
  head.append(actions);
  doc.append(head);

  const content = el("div", "content");
  content.innerHTML = d.html;                       // allowlist-filtered by the server
  if (d.page) content.querySelector("h1")?.remove(); // the header already shows it
  doc.append(content);
  enhance(content);
  buildToc(content);
  const target = at && content.querySelector(`#${CSS.escape(at)}`);
  if (target) {
    target.scrollIntoView({ block: "start" });
    target.classList.add("flash");
  } else {
    $("#doc-pane").scrollTop = 0;
  }
}

// Long signatures one parameter per line; copy buttons on code; links stay in the app.
function enhance(root) {
  for (const dt of $$("dt.sig", root)) {
    const params = $$(":scope > em.sig-param", dt);
    for (const p of params) {                  // name=default: give the default its own colour
      if (p.querySelector(".default_value")) continue;
      const t = p.textContent, eq = t.indexOf("=");
      if (eq > 0) { p.textContent = t.slice(0, eq + 1); p.append(el("span", "default_value", t.slice(eq + 1))); }
    }

    if (dt.textContent.length > 64 && params.length > 1) {
      for (const p of params) { p.before(document.createElement("br")); p.before(el("span", "indent")); }
      const parens = $$(":scope > .sig-paren", dt);
      parens[parens.length - 1]?.before(document.createElement("br"));
    }
    const b = el("button", "copy-btn", "Copy");
    b.title = "Copy this signature";
    b.addEventListener("click", (ev) => { ev.stopPropagation(); copy(sigText(dt), "signature"); });
    dt.append(b);
  }
  for (const block of $$("div.highlight", root)) {
    const b = el("button", "copy-btn", "Copy");
    b.title = "Copy the code (without >>> prompts and output)";
    b.addEventListener("click", () => copy(codeText(block.querySelector("pre")), "code"));
    block.append(b);
  }
  for (const x of $$(".ext-link", root)) {   // links to other websites: offline, so copy-only
    if (!x.textContent.trim()) { x.remove(); continue; }
    x.title = `${x.title}\n(offline: click to copy the address)`;
  }
  for (const img of $$("img", root)) {      // an image that was not stored: show its description
    img.addEventListener("error", () => img.replaceWith(el("span", "offline-image", img.alt ? `image: ${img.alt}` : "image")));
  }
  $$("p.rubric", root).forEach((p, k) => { if (!p.id) p.id = `rubric-${k}`; });
  $$("dl.field-list > dt", root).forEach((dt, k) => { if (!dt.id) dt.id = `field-${k}`; });
}

function sigText(dt) {
  const c = dt.cloneNode(true);
  c.querySelector(".copy-btn")?.remove();
  return c.textContent.replace(/\s+/g, " ").replace(/\(\s+/, "(").replace(/\s+\)/, ")").trim();
}

// Code as you would type it: examples lose their >>> prompts and printed output.
function codeText(pre) {
  const text = pre.textContent;
  const lines = text.split("\n");
  if (!lines.some((l) => l.startsWith(">>> "))) return text.replace(/\n$/, "");
  return lines.filter((l) => l.startsWith(">>> ") || l.startsWith("... "))
              .map((l) => l.slice(4)).join("\n");
}

function buildToc(root) {
  const toc = $("#toc");
  toc.textContent = "";
  const marks = $$("h2[id], h3[id], section[id] > h2, section[id] > h3, dl.field-list > dt, p.rubric, dd dl.py > dt[id]", root);
  const items = [];
  for (const m of marks) {
    const id = m.id || m.parentElement.id;
    if (!id || items.some((i) => i.id === id)) continue;
    const sub = m.matches("dd dl.py > dt");
    let label = sub ? (m.querySelector(".sig-name")?.textContent || m.textContent) : m.textContent;
    label = label.replace(/[¶#:]\s*$/, "").replace(/\s+/g, " ").trim();
    if (label) items.push({ id, label, sub });
  }
  if (items.length < 2) return;
  toc.append(el("h2", null, "On this page"));
  for (const it of items.slice(0, 80)) {
    const a = el("a", it.sub ? "sub" : null, it.label);
    a.href = `#${it.id}`;
    a.addEventListener("click", (ev) => {
      ev.preventDefault();
      document.getElementById(it.id)?.scrollIntoView({ block: "start", behavior: "smooth" });
    });
    toc.append(a);
  }
}

function showHome() {
  state.view = { type: "home" };
  const doc = $("#doc");
  doc.textContent = "";
  const w = el("div", "welcome content");
  w.append(el("h1", null, "Search your documentation"));
  w.append(el("p", "lead", "Type a name, a few letters in order, or describe what you want. Everything here works offline."));
  const t = el("table");
  const rows = [["np.sum, svd, nn.Linear", "an API name (aliases like np, pd work)"], ["lnsvd", "letters in order: numpy.linalg.svd"],
                ["sum of elements along an axis", "a description: search by meaning"], ["↑ ↓", "move through the results"],
                ["Enter", "the full page (offline copy)"], ["Esc", "back, then clear the search"],
                ["/", "jump to the search box"], ["w", "wrap or scroll long code lines"],
                ["c", "copy the name of the current entry"]];
  for (const [k, v] of rows) { const tr = el("tr"); tr.append(el("td", null, k), el("td", null, v)); t.append(tr); }
  w.append(t);
  const p = el("p", null, "Packages: " + state.sources.map((s) => `${s.name} ${s.version} (${s.count})`).join(" · "));
  w.append(p);
  doc.append(w);
  $("#toc").textContent = "";
}

function showEmpty() {
  const doc = $("#doc");
  doc.textContent = "";
  doc.append(el("p", "empty", `Nothing found for “${state.q}”. Try other words, fewer letters, or another package.`));
  $("#toc").textContent = "";
}

// ---- small helpers --------------------------------------------------------------------------
async function copy(text, what) {
  try { await navigator.clipboard.writeText(text); toast(`Copied ${what}`); }
  catch (_) { toast("Copy failed: the browser blocked it"); }
}

function toast(text) {
  const t = $("#toast");
  t.textContent = text;
  t.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => t.classList.remove("show"), 1600);
}

function toggleWrap(button) {
  const on = document.body.classList.toggle("wrap-code");
  try { localStorage.setItem("wrapCode", on ? "1" : "0"); } catch (_) {}
  if (button) button.textContent = on ? "Code: wrap" : "Code: scroll";
  toast(on ? "Long code lines wrap" : "Long code lines scroll sideways");
}

// The address bar keeps the search and what you read: reload, back and forward work.
function syncURL(push) {
  const p = new URLSearchParams();
  if (state.q) p.set("q", state.q);
  if (state.ai) p.set("ai", "1");
  if (state.srcs.size) p.set("src", searchedSources().join(","));
  if (state.view?.type === "entry") p.set("id", state.view.id);
  if (state.view?.type === "page") { p.set("page", state.view.path); if (state.view.at) p.set("at", state.view.at); }
  const url = `/${p.toString() ? "?" + p : ""}`;
  if (url === location.pathname + location.search) return;
  push ? history.pushState(null, "", url) : history.replaceState(null, "", url);
}

// ---- events -----------------------------------------------------------------------------------
// ---- which docs are indexed; remove wrong ones -----------------------------------------------
function openPanel() {
  const table = $("#panel-table");
  table.textContent = "";
  for (const s of state.sources) {
    const tr = el("tr");
    const name = el("td");
    name.append(el("strong", null, s.name), el("div", "about", s.version ? `version ${s.version}` : ""));
    const what = el("td");
    what.append(el("div", null, s.about || ""), el("div", "root", s.root || ""),
                el("div", "about", `${s.count} entries${s.offline ? ", readable offline" : ""} · added ${s.added}`));
    const act = el("td");
    const b = el("button", "remove", "Remove");
    b.title = `Delete the ${s.name} docs from docsearch (and from packages.toml)`;
    b.addEventListener("click", () => removeSource(s, b));
    act.append(b);
    tr.append(name, what, act);
    table.append(tr);
  }
  $("#panel").hidden = false;
  $("#panel-close").focus();
}

async function removeSource(s, button) {
  if (!button.classList.contains("sure")) {       // a second click confirms
    button.classList.add("sure");
    button.textContent = "Click again to remove";
    setTimeout(() => { button.classList.remove("sure"); button.textContent = "Remove"; }, 4000);
    return;
  }
  button.disabled = true;
  button.textContent = "Removing…";
  const r = await fetch("/api/remove", { method: "POST", headers: { "Content-Type": "application/json", "X-Docsearch": "1" },
                                         body: JSON.stringify({ source: s.id }) });
  if (!r.ok) { toast("Could not remove it"); button.disabled = false; button.textContent = "Remove"; return; }
  toast(`Removed ${s.name}; updating the index…`);
  for (let k = 0; k < 60; k++) {                     // the server reloads its index
    await new Promise((res) => setTimeout(res, 500));
    const info = await getJSON("/api/info").catch(() => null);
    if (info && !info.sources.some((x) => x.id === s.id)) { state.sources = info.sources; break; }
  }
  state.srcs.delete(s.group);
  if (state.active[s.group] === s.id) delete state.active[s.group];
  for (const x of state.sources) if (!state.active[x.group] && x.default) state.active[x.group] = x.id;
  renderSources();
  openPanel();
  search({ openFirst: !!state.q });
}

function bindEvents() {
  const input = $("#q");
  $("#manage").addEventListener("click", openPanel);
  $("#ai").addEventListener("click", () => {
    setAI(!state.ai);
    toast(state.ai ? "AI ranking on: the model reorders the top results" : "AI ranking off");
    if (state.q) search({ openFirst: true, ai: state.ai });
  });
  $("#panel-close").addEventListener("click", () => { $("#panel").hidden = true; });
  $("#panel").addEventListener("click", (ev) => { if (ev.target.id === "panel") $("#panel").hidden = true; });
  input.addEventListener("input", () => {
    clearTimeout(state.typeTimer);
    state.typeTimer = setTimeout(() => {
      state.q = input.value.trim();
      search({ openFirst: !!state.q }).then(() => { if (!state.q) showHome(); });
    }, 70);
  });

  $("#results").addEventListener("click", (ev) => {
    const li = ev.target.closest(".r");
    if (li) select(+li.dataset.n, { scroll: false });
  });
  $(".results-pane").addEventListener("scroll", (ev) => {
    const p = ev.currentTarget;
    if (p.scrollTop + p.clientHeight > p.scrollHeight - 300 && state.items.length < state.total) search({ append: true });
  }, { passive: true });

  // links inside the docs: in-app pages stay here, #anchors scroll
  $("#doc").addEventListener("click", (ev) => {
    const ext = ev.target.closest(".ext-link");
    if (ext) { copy(ext.title.split("\n")[0], "web address (docsearch stays offline)"); return; }
    const a = ev.target.closest("a[href]");
    if (!a) return;
    const href = a.getAttribute("href");
    if (href.startsWith("/?")) {
      ev.preventDefault();
      const p = new URLSearchParams(href.slice(2));
      if (p.get("page")) openPage(p.get("page"), p.get("at"));
    } else if (href.startsWith("#")) {
      ev.preventDefault();
      const t = document.getElementById(decodeURIComponent(href.slice(1)));
      if (t) { t.scrollIntoView({ block: "start", behavior: "smooth" }); t.classList.remove("flash"); void t.offsetWidth; t.classList.add("flash"); }
    }
  });

  window.addEventListener("popstate", () => {
    const p = new URLSearchParams(location.search);
    if (p.get("page")) openPage(p.get("page"), p.get("at"), false);
    else if (p.get("id")) openEntry(+p.get("id"), false);
  });

  document.addEventListener("keydown", (ev) => {
    const inInput = ev.target === input;
    if ((ev.metaKey || ev.ctrlKey) && ev.key === "Enter") {   // ⌘↩: rank this search with AI, once
      ev.preventDefault();
      if (state.q) search({ openFirst: true, ai: true });
      return;
    }
    if (ev.metaKey || ev.ctrlKey || ev.altKey) return;
    if (ev.key === "ArrowDown" || (!inInput && ev.key === "j")) {
      ev.preventDefault(); select(Math.min(state.sel + 1, state.items.length - 1));
    } else if (ev.key === "ArrowUp" || (!inInput && ev.key === "k")) {
      ev.preventDefault(); select(Math.max(state.sel - 1, 0));
    } else if (ev.key === "Enter" && state.view?.type === "entry") {
      ev.preventDefault();
      $(".actions .primary")?.click();
    } else if (ev.key === "Escape" && !$("#panel").hidden) {
      $("#panel").hidden = true;
    } else if (ev.key === "Escape") {
      if (state.view?.type === "page") history.back();
      else if (input.value) { input.value = ""; input.dispatchEvent(new Event("input")); }
      else input.blur();
    } else if (ev.key === "/" && !inInput) {
      ev.preventDefault(); input.focus(); input.select();
    } else if (!inInput && ev.key === "w") {
      toggleWrap($$(".actions button").find((b) => b.textContent.startsWith("Code:")));
    } else if (!inInput && ev.key === "c" && state.view?.type === "entry") {
      $$(".actions button").find((b) => b.textContent === "Copy name")?.click();
    } else if (ev.key === "PageDown" || ev.key === "PageUp") {
      ev.preventDefault();
      const pane = $("#doc-pane");
      pane.scrollBy({ top: (ev.key === "PageDown" ? 1 : -1) * pane.clientHeight * 0.85 });
    }
  });
}
