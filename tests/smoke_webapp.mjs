/*
 * Smoke-test the workbench without a browser.
 *
 *   node tests/smoke_webapp.mjs output/DPDPA_Audit_Workbench.html
 *
 * There is no browser in this environment, so the app's script is run against a
 * DOM stub thin enough to be honest about what it proves: it catches reference
 * errors, throws during boot, and defects in the generated markup — stray
 * "undefined" or "NaN", classes that no rule in the stylesheet matches,
 * unbalanced elements. It does not prove anything about layout or paint.
 */
import { readFileSync } from "node:fs";

const html = readFileSync(process.argv[2], "utf8");

/* ---------------------------------------------------------------- DOM stub */
const byId = new Map();
const nodeList = arr => { arr.forEach = Array.prototype.forEach.bind(arr); return arr; };

function makeEl(id = "", tag = "div") {
  const el = {
    id, tagName: tag.toUpperCase(), _html: "", textContent: "", className: "",
    dataset: {}, type: "", value: "", files: [], style: {}, parentElement: null,
    get innerHTML() { return this._html; },
    set innerHTML(v) { this._html = String(v); },
    setAttribute(k, v) { this["attr_" + k] = v; },
    getAttribute(k) { return this["attr_" + k]; },
    querySelectorAll() { return nodeList([]); },
    querySelector() { return null; },
    classList: { toggle() {}, add() {}, remove() {} },
    focus() {}, click() {}, setSelectionRange() {},
  };
  return el;
}
const document = {
  getElementById(id) {
    if (!byId.has(id)) byId.set(id, makeEl(id));
    return byId.get(id);
  },
  querySelectorAll(sel) {
    if (sel === ".tab") {
      return nodeList(["scope", "field", "find", "cite"].map(v => {
        const e = makeEl("tab-" + v); e.dataset.view = v; return e;
      }));
    }
    return nodeList([]);
  },
  createElement: tag => makeEl("", tag),
};
const alerts = [];
globalThis.document = document;
globalThis.window = { scrollY: 0, scrollTo() {} };
globalThis.localStorage = { getItem: () => null, setItem() {}, };
globalThis.alert = m => alerts.push(m);
globalThis.confirm = () => true;
globalThis.Blob = class { constructor() {} };
globalThis.URL = { createObjectURL: () => "blob:x", revokeObjectURL() {} };
globalThis.FileReader = class { readAsText() {} };

/* ------------------------------------------------------------ run the app */
const open = html.indexOf("<script>");
const close = html.lastIndexOf("</script>");
let src = html.slice(open + "<script>".length, close);
src = src.replace(/^\s*"use strict";/, "");           // module scope is strict already
src += `
export const api = {
  setView, renderScope, renderFindings, renderCitations, renderFieldwork,
  cardHTML, get results(){ return results; }, get state(){ return state; },
  set domainFilter(v){ domainFilter = v; }, set statusFilter(v){ statusFilter = v; },
  exportPayload, blankAssessment, DATA,
};
`;

let api;
try {
  ({ api } = await import(
    "data:text/javascript;base64," + Buffer.from(src, "utf8").toString("base64")
  ));
} catch (e) {
  console.error("FAIL — the app threw during boot:\n" + (e.stack || e.message));
  process.exit(1);
}

/* --------------------------------------------------------------- gathering */
const rendered = {};
const main = document.getElementById("main");
for (const v of ["scope", "field", "find", "cite"]) {
  api.setView(v);
  rendered[v] = main.innerHTML;
}
rendered.spine = document.getElementById("spine").innerHTML;

// Every control's card, including the ones a filter would hide.
api.domainFilter = "ALL"; api.statusFilter = "all";
rendered.allCards = api.results.all.map(api.cardHTML).join("\n");

/* ----------------------------------------------------------------- checks */
const problems = [];
const note = (label, msg) => problems.push(`${label}: ${msg}`);

// 1. placeholders and boot-time junk
if (html.includes("__DATA__") || html.includes("__SAMPLE__"))
  note("build", "an unreplaced template placeholder survived into the output");
if (alerts.length) note("boot", `alert() fired: ${alerts[0]}`);

// 2. rendered markup defects
//    "undefined" is matched only where a value was interpolated, never in prose:
//    several control descriptors legitimately say "timescales are undefined".
const LEAKS = [
  [/>\s*(undefined|NaN|null)\s*</, "an interpolated value rendered as"],
  [/="\s*(undefined|NaN)\s*"/, "an attribute rendered as"],
  [/\b(undefined|NaN|null)\s*%/, "a percentage rendered as"],
  [/\[object Object\]/, "an object rendered as"],
  [/\bof\s+undefined\b/, "a count rendered as"],
];
for (const [name, frag] of Object.entries(rendered)) {
  if (!frag || frag.length < 100) { note(name, `rendered only ${frag.length} characters`); continue; }
  for (const [re, why] of LEAKS) {
    const m = re.exec(frag);
    if (m) note(name, `${why} "${m[1] || m[0]}" — …${frag.slice(Math.max(0, m.index - 70), m.index + 50).replace(/\s+/g, " ")}…`);
  }
  // Unbalanced elements. Void and self-closing tags are excluded.
  const void_ = new Set(["input", "br", "hr", "img", "meta", "link", "col", "source"]);
  const stack = [];
  for (const m of frag.matchAll(/<(\/?)([a-z][a-z0-9]*)\b[^>]*?(\/?)>/gi)) {
    const [, closing, tag, selfClose] = m;
    const t = tag.toLowerCase();
    if (void_.has(t) || selfClose) continue;
    if (closing) {
      if (stack.pop() !== t) { note(name, `unbalanced </${t}>`); break; }
    } else stack.push(t);
  }
  if (stack.length) note(name, `unclosed <${stack.join(">, <")}>`);
}

// 3. every class used in the markup has a rule in the stylesheet
const style = html.slice(html.indexOf("<style>"), html.indexOf("</style>"));
const defined = new Set([...style.matchAll(/\.(-?[_a-zA-Z][\w-]*)/g)].map(m => m[1]));
const used = new Set();
for (const frag of Object.values(rendered))
  for (const m of frag.matchAll(/class="([^"]+)"/g))
    for (const c of m[1].split(/\s+/)) if (c) used.add(c);
const orphans = [...used].filter(c => !defined.has(c)).sort();
if (orphans.length) note("css", `classes with no rule: ${orphans.join(", ")}`);

// 4. the citation policy has to survive into the markup
const unver = api.DATA.unverified_keys;
if (!rendered.cite.includes("VERIFY_AGAINST_NOTIFIED_RULES"))
  note("citations", "the unverified status is not shown in the Citations view");
if (!rendered.allCards.includes("to be verified"))
  note("citations", "no card shows the unverified-slot marker");
for (const frag of [rendered.allCards, rendered.cite]) {
  // A plausible rule number must never appear for a slot that is unverified.
  for (const key of unver) {
    const slot = api.DATA.citations.rule_slots[key];
    if (slot.citation) note("citations", `${key} is unverified but carries a citation`);
  }
}
if (/[Rr]ule\s+\d+/.test(rendered.allCards.replace(/\[Rules citation to be verified\]/g, "")))
  note("citations", "a bare rule number appears on a control card");

// 5. round-trip: the export must be loadable by the Python toolkit
const p = api.exportPayload();
if (p._schema !== "dpdpa-audit-assessment/1") note("export", "wrong _schema");
for (const k of ["profile", "responses", "assessment_date", "library_version", "limitations"])
  if (!(k in p)) note("export", `export is missing ${k}`);
const rf = ["control_id", "score", "finding", "evidence", "evidence_ref", "owner", "target_date", "auditor_note"];
for (const [cid, r] of Object.entries(p.responses)) {
  const extra = Object.keys(r).filter(k => !rf.includes(k));
  if (extra.length) { note("export", `${cid} carries fields the toolkit does not read: ${extra}`); break; }
}
const blank = api.blankAssessment();
if (Object.keys(blank.responses).length === 0) note("new", "a new assessment has no responses to fill");

// 6. the app must not depend on browser storage for correctness
if (!/try\s*\{[^}]*localStorage/.test(html))
  note("storage", "localStorage is used without a try/catch guard");

/* ----------------------------------------------------------------- report */
const sizes = Object.entries(rendered).map(([k, v]) => `${k} ${(v.length / 1024).toFixed(0)}KB`).join(" · ");
console.log(`rendered: ${sizes}`);
console.log(`css: ${used.size} classes used, all defined`);
console.log(`controls rendered: ${api.results.all.length} · gaps ${api.results.gaps.length} · ` +
            `overall ${api.results.overall_maturity_pct}% ${api.results.overall_band[0]}`);
if (problems.length) {
  console.error(`\nFAIL — ${problems.length} problem(s):`);
  for (const p2 of problems) console.error("  · " + p2);
  process.exit(1);
}
console.log("OK");
