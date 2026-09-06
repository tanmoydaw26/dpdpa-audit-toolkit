# DPDPA Audit Toolkit

An end-to-end audit of an organisation against India's **Digital Personal Data
Protection Act, 2023**, producing an audit-ready report. Ninety controls across
seventeen domains, each anchored to a section of the Act, scored on a defined
maturity scale, and rolled up into a weighted maturity figure, a residual-risk
register and a prioritised remediation roadmap.

The toolkit ships in three forms over one shared control library, so the same
engagement can be run from a browser, a terminal or a spreadsheet and produce
the same numbers:

| | What it is | Who it suits |
|---|---|---|
| **Workbench** | `output/DPDPA_Audit_Workbench.html` — one self-contained file, opens by double-clicking, no server and no network | fieldwork, and walking a client through their own position |
| **Toolkit** | `python -m dpdpa_audit` — scoping interview, control-by-control assessment, scoring, report generation | repeatable engagements, version control, CI |
| **Workbook** | `output/*_DPDPA_Control_Matrix.xlsx` — control matrix, evidence log and a dashboard of live formulas | clients who want to see the arithmetic and edit it |

The deliverable is a formal Word report: executive summary, scope and
methodology, applicability determination, obligation-by-obligation findings with
evidence references, gap register, risk ratings, remediation roadmap, sign-off
page and three appendices.

Everything is pre-filled with one worked example — **KavachPay**, a fictional
Indian lending and payments company notified as a Significant Data Fiduciary —
scored end to end so that every feature has something in it to look at. Clear it
and the same machinery runs a real engagement.

---

## Install and run

```bash
pip install -r requirements.txt

python -m dpdpa_audit validate                       # check the library loads
python -m dpdpa_audit score  samples/sample_assessment.json
python -m dpdpa_audit report samples/sample_assessment.json --out-dir output
python3 webapp/build_webapp.py                       # build the browser app
python -m unittest discover -s tests -q              # 85 tests
```

A real engagement is four commands:

```bash
python -m dpdpa_audit init   --out engagement.json   # scoping interview
python -m dpdpa_audit assess engagement.json         # fieldwork, control by control
python -m dpdpa_audit score  engagement.json         # maturity, risk, exposure
python -m dpdpa_audit report engagement.json --out-dir output
```

`init` runs a scoping interview; `init --blank` skips it and writes the
conservative defaults for editing by hand or in the browser. `assess` saves after
every control, so it can be interrupted and resumed with `--only-unscored`, or
narrowed with `--domain SEC --domain BRC`. `score --json` and `citations --json`
emit machine-readable output for a pipeline, and `report --format docx` writes
just the report.

The assessment file is plain JSON and is the only piece of state. The workbench
reads and writes the same format, so fieldwork can be done in the browser and
the report generated from the terminal, or the reverse.

---

## The citation policy

This is the part of the toolkit that most needs explaining, because it is a
deliberate constraint rather than an omission.

**Citations to the Act are populated.** Every control names the section it tests
— s.5 for notice, s.6 for consent, s.8(5) for safeguards, s.9 for children,
s.10 for Significant Data Fiduciaries, and so on — together with the entry in
the Schedule that carries the penalty for breaching it.

**Citations to the DPDP Rules are held as named slots and left visibly empty.**
The Rules could not be verified against their notified text in the environment
this toolkit was built in. Rather than write a rule number that looks
authoritative and might be wrong, each of the 21 Rules citations is a slot
recording *what the Rules govern* — breach intimation, retention periods, consent
manager registration — with the status `VERIFY_AGAINST_NOTIFIED_RULES` and no
number. Anywhere a citation would appear, the deliverables print
`[Rules citation to be verified]`; the workbench prints a ruled blank, so an
unverified citation *looks* unverified rather than looking like a citation.

A findings register that quietly contains a wrong rule number is worse than one
that is honest about what has not been checked, because the reader cannot tell
the difference. Two tests enforce this:
`test_no_slot_carries_a_rule_number_while_unverified` and
`test_unverified_slots_render_as_a_placeholder` make it a build failure to slip a
plausible-looking number in.

**To fill them in**, edit `controls/citations.yaml` — one file, one place:

```yaml
rule_slots:
  BREACH_INTIMATION:
    subject: Form, contents and timing of intimation of a personal data breach
    anchors_act: s.8(6)
    status: VERIFIED_RULES          # was VERIFY_AGAINST_NOTIFIED_RULES
    citation: "Rule NN(N), DPDP Rules"
```

Rebuild and every deliverable picks it up: the control cards, the workbook's
Citations sheet, the per-control statutory basis in the report, and Appendix A,
which disappears as the slots are filled. `python -m dpdpa_audit citations` prints
the worklist with the subject matter and the controls that depend on each slot.

One slot, `RESEARCH_ARCHIVING_STANDARDS` (s.17(2)(b)), is defined but referenced
by no control. It is reserved: if the entity claims the research or archiving
exemption, the standards prescribed under it become testable and a control can
be added without inventing a new citation structure. `validate` reports it as
reserved but unreferenced so it is not mistaken for a loose end.

---

## How the scoring works

**Each in-scope control is scored 0–4** against descriptors in the library.
Only **0, 2 and 4 are written**; 1 and 3 are the intermediate positions between
them. This is deliberate. Anchoring three points and asking the auditor to
interpolate produces more consistent scoring than writing five descriptions that
blur into each other, and it is honest about where judgement sits. The workbench
renders this directly: 0, 2 and 4 are solid stops on the scale, 1 and 3 are
smaller dashed ticks.

**"Not applicable" removes a control from the denominator.** It is not a zero.
Scoring an inapplicable obligation as zero understates maturity and manufactures
a gap that no one can remediate.

```
control maturity  = score / 4
domain maturity   = Σ(score × control weight) / Σ(4 × control weight)
overall maturity  = Σ(domain maturity × domain weight) / Σ(domain weight)
```

The overall figure is **domain-weighted, not a flat average of controls**, so
Security with nine controls does not mechanically outvote Consent Manager
obligations with three heavier ones. A test asserts this: zeroing an entire
domain moves the overall figure by exactly that domain's share of the total
weight, whatever the control count inside it.

Domains with no assessed control are left out of the overall figure rather than
counted as zero, for the same reason NA is not a zero.

**Residual risk = severity rank × (4 − score)**, range 0–16, with ranks
critical 4, high 3, medium 2, low 1. Risk is a function of both how serious the
obligation is and how far short the entity falls, which separates a minor gap in
a critical control from a total gap in a minor one. Bands: 12+ Critical, 8–11
High, 4–7 Medium, 1–3 Low. The workbench's risk grid plots severity against
score, so the grid *is* the formula rather than a judgement laid over it.

A control below 3 of 4 yields a **gap**. Gaps are ordered by risk and given a
priority and a target date — P1 30 days, P2 60, P3 90, P4 180 — and each gap's
required target state is the control's own level-4 descriptor, so remediation is
expressed as the standard the library defines rather than as advice invented per
engagement.

**Unassessed in-scope controls are a scope limitation, not a finding.** They
carry no score and no risk figure and are reported as a limitation on the work
performed.

**Penalty exposure is a ceiling, not a prediction.** It is the aggregate of the
statutory maxima under the Schedule for those entries engaged by failing
controls, always printed with the s.33(2) caveat: the Board must have regard to
gravity, duration, repetition, the type of data, mitigating action and
proportionality, and documented prompt remediation is an express mitigating
factor. Any real penalty would be a fraction of the ceiling. The figure is there
to show *which entries are engaged*, which is the useful part.

---

## Scoping is declarative

Which controls apply is decided by eleven profile flags, and each control names
the flags it requires and the flags that exclude it:

```yaml
- id: SDF-03
  applicability:
    requires: [is_sdf]
```

**Flags that widen scope default to on.** Silence produces a larger audit rather
than a quietly narrower one, and every exemption has to be claimed explicitly.
`processes_children_data` defaults to true because age is rarely reliably
excluded; the s.17 exemptions all default to false.

Every flag referenced anywhere in the library must be declared in
`PROFILE_FLAGS`, and the library refuses to load otherwise — a typo in a flag
name is a load-time error rather than a control silently dropping out of scope.
Validation collects every error and reports them together, so one bad edit
doesn't hide the next.

On the sample profile, 87 of 90 controls are in scope. On the conservative
defaults, 79. The Scope view shows the count moving as flags are toggled, and
which controls each flag gates.

---

## Layout

```
controls/            the library — data, not code
  domains.yaml         17 domains with weights and scope questions
  citations.yaml       the single edit point for citations
  01..06_*.yaml        90 controls
dpdpa_audit/
  core.py              library loading, validation, profile, assessment state
  scoring.py           maturity, risk, gaps, penalty exposure
  word_report.py       the formal report
  excel_report.py      the control matrix workbook
  cli.py               init · assess · score · report · citations · validate
webapp/
  app_template.html    the workbench
  build_webapp.py      inlines the library and constants into one HTML file
samples/               the KavachPay worked example
tests/
  test_toolkit.py      85 tests
  verify_webapp.mjs    the browser engine against the Python engine
  smoke_webapp.mjs     the workbench rendered and checked without a browser
```

**The control library is data.** Everything in `controls/*.yaml` can be edited,
extended or replaced without touching Python. `--controls path/to/library` runs
the whole toolkit against a tailored set, which is how a sector-specific or
group-specific control set should be maintained.

---

## Notes on the build

**The workbench is generated, not hand-written.** `build_webapp.py` reads the
YAML library and the scoring constants out of `dpdpa_audit` and inlines them,
so the app cannot report different numbers from the CLI. The browser engine is a
port of `scoring.py`, and a port is a second implementation whether or not it is
called one — `verify_webapp.mjs` lifts the shipped code out of the built HTML,
runs it over the same engagement and compares the result field by field,
including all 60 rows of the gap register. It is part of `python -m unittest`.

**The Word report uses python-docx** rather than the docx-js route, so the whole
toolkit is one language with one dependency set and `report` runs anywhere
Python does.

**The workbook's formulas are live.** openpyxl writes formulas without cached
results, so previewers show blanks until Excel recalculates; the shipped sample
was round-tripped through LibreOffice to embed cached values, and reports zero
formula errors.

**The report's table of contents is a Word field.** Open the report and press F9,
or accept the update prompt, to populate it.

---

## What this is not

This is a compliance assessment instrument. It is not legal advice, and it is
not an assurance engagement — it expresses no audit opinion. Conclusions about
how the Act applies to particular processing should be confirmed with qualified
counsel. Testing is on a sample basis, and the absence of a finding is not a
representation that no exception exists outside the items tested.

The commencement position of individual provisions has not been confirmed, so
findings are expressed as gaps against the framework rather than as
contraventions of provisions that may not yet be in force. Both points travel
with the assessment file as scoping assumptions and print in the report.
