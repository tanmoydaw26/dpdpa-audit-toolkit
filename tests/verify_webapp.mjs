/*
 * Verify the workbench's scoring engine against the Python engine.
 *
 *   node tests/verify_webapp.mjs output/DPDPA_Audit_Workbench.html sample.json
 *
 * The engine in the app is a port of dpdpa_audit/scoring.py, and a port is a
 * second implementation whether or not it is called one. This harness lifts the
 * shipped code out of the built HTML — not a copy of it — runs it over the same
 * assessment file, and prints a payload shaped like `score --json` so the two
 * can be compared field by field. Anything that drifts fails the build.
 */
import { readFileSync } from "node:fs";

const [htmlPath, samplePath] = process.argv.slice(2);
const html = readFileSync(htmlPath, "utf8");

function slice(tag) {
  const a = html.indexOf(`// <<<${tag}`);
  const b = html.indexOf(`// ${tag}>>>`);
  if (a < 0 || b < 0) throw new Error(`no ${tag} block in ${htmlPath}`);
  return html.slice(a, b);
}

const src = slice("DATA") + "\n" + slice("ENGINE") + `
DATA.byId = {};
for (const c of DATA.controls) DATA.byId[c.id] = c;
export { DATA, scoreAssessment, buildGapRegister, appliesTo, ruleCitationText };
`;

const mod = await import(
  "data:text/javascript;base64," + Buffer.from(src, "utf8").toString("base64")
);

const a = JSON.parse(readFileSync(samplePath, "utf8"));
const r = mod.scoreAssessment(a);
const gaps = mod.buildGapRegister(r, a.assessment_date);

const payload = {
  entity: a.profile.legal_name,
  assessment_date: a.assessment_date,
  library_version: mod.DATA.library_version,
  overall_maturity_pct: r.overall_maturity_pct,
  overall_band: r.overall_band[0],
  controls_total: mod.DATA.controls.length,
  controls_in_scope: r.in_scope_count,
  controls_assessed: r.assessed_count,
  coverage_pct: r.coverage_pct,
  gap_count: gaps.length,
  gaps_by_severity: r.gap_counts_by_severity,
  status_counts: r.status_counts,
  domains: r.domains.map(d => ({
    code: d.code, name: d.name, weight: d.weight,
    maturity_pct: d.maturity_pct, band: d.band,
    in_scope: d.in_scope_results.length, assessed: d.scored.length,
    gaps: d.gaps.length, max_risk: d.max_risk,
  })),
  penalty_exposure: r.penalty_exposure,
  unverified_rule_slots: mod.DATA.unverified_keys,
  gap_register: gaps.map(g => [
    g.ref, g.control_id, g.domain_name, g.title, g.severity, g.score, g.risk,
    g.risk_band, g.priority, g.due_date, g.act_ref, g.rule_citation,
    g.penalty_label, g.finding, g.target_state, g.owner, g.evidence_ref,
  ]),
};

process.stdout.write(JSON.stringify(payload, null, 2));
