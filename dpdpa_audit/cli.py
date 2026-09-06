"""
DPDPA Audit Toolkit — command line interface.

    python -m dpdpa_audit init      --out engagement.json
    python -m dpdpa_audit assess    engagement.json           # interactive fieldwork
    python -m dpdpa_audit score     engagement.json
    python -m dpdpa_audit report    engagement.json --out-dir output
    python -m dpdpa_audit citations                            # verification worklist
    python -m dpdpa_audit validate                            # library integrity

Every command takes --controls (default: ./controls), so the same CLI drives a
tailored library. The commands are deliberately separable: scoping, fieldwork,
scoring and reporting are distinct acts in an audit and each leaves the
assessment file as the only piece of state, which is plain JSON and diffable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from datetime import date
from typing import List, Optional

from .core import (
    NOT_APPLICABLE,
    PROFILE_FLAGS,
    SCORE_LABELS,
    Assessment,
    CompanyProfile,
    Library,
    load_library,
)
from .scoring import build_gap_register, score_assessment

DEFAULT_CONTROLS = "controls"
_WRAP = 88


# ------------------------------------------------------------------ utilities
def _out(*parts: str) -> None:
    print(*parts)


def _rule(char: str = "-", width: int = 76) -> None:
    print(char * width)


def _wrap(text: str, indent: str = "  ") -> str:
    return textwrap.fill(" ".join(text.split()), width=_WRAP,
                         initial_indent=indent, subsequent_indent=indent)


def _die(msg: str, code: int = 2) -> "None":
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def _library(args) -> Library:
    try:
        return load_library(args.controls)
    except FileNotFoundError:
        _die(f"no control library at {args.controls!r} — pass --controls")
    except ValueError as exc:
        _die(f"the control library did not validate:\n{exc}")
    raise AssertionError("unreachable")


def _load(path: str) -> Assessment:
    if not os.path.exists(path):
        _die(f"no assessment file at {path!r} — run 'init' first")
    try:
        return Assessment.load(path)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        _die(f"{path!r} is not a readable assessment file: {exc}")
    raise AssertionError("unreachable")


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        got = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        print()
        return default
    return got or default


def _ask_bool(prompt: str, default: bool) -> bool:
    d = "Y/n" if default else "y/N"
    while True:
        got = _ask(f"{prompt} ({d})", "").lower()
        if not got:
            return default
        if got in ("y", "yes"):
            return True
        if got in ("n", "no"):
            return False
        print("  answer y or n")


def _ask_list(prompt: str) -> List[str]:
    print(f"{prompt} (one per line, blank line to finish)")
    items: List[str] = []
    while True:
        try:
            line = input("  - ").strip()
        except EOFError:
            print()
            break
        if not line:
            break
        items.append(line)
    return items


# ---------------------------------------------------------------- cmd: init
def cmd_init(args) -> int:
    lib = _library(args)
    if os.path.exists(args.out) and not args.force:
        _die(f"{args.out!r} already exists — pass --force to overwrite")

    if args.blank:
        profile = CompanyProfile.blank()
        assessment = Assessment.blank_for(lib, profile)
        assessment.save(args.out)
        _out(f"wrote a blank engagement to {args.out}")
        _out("Fill in the profile block, then run 'assess' to score the controls.")
        return 0

    _out("Scoping interview. Enter to accept the default in brackets.")
    _rule()
    profile = CompanyProfile.blank()
    profile.legal_name = _ask("Legal name of the Data Fiduciary")
    profile.trading_name = _ask("Trading or brand name", profile.legal_name)
    profile.sector = _ask("Sector")
    profile.registered_office = _ask("Registered office")
    head = _ask("Headcount", "")
    profile.headcount = int(head) if head.isdigit() else None
    dps = _ask("Approximate number of Data Principals", "")
    profile.data_principal_count = int(dps) if dps.isdigit() else None
    profile.business_description = _ask("One-line description of the processing")

    _rule()
    _out("Applicability. These answers determine which controls are in scope,")
    _out("so the composition of the audit is reproducible from them.")
    for name, (default, description) in PROFILE_FLAGS.items():
        _out("")
        _out(_wrap(description, indent="  "))
        profile.flags[name] = _ask_bool(f"  {name}", default)

    _rule()
    profile.entities_in_scope = _ask_list("Entities within scope")
    profile.systems_in_scope = _ask_list("Systems and processing environments examined")
    profile.exclusions = _ask_list("Exclusions from scope")

    assessment = Assessment.blank_for(lib, profile)
    assessment.assessment_date = _ask("Assessment date (ISO)", date.today().isoformat())
    assessment.auditor_name = _ask("Auditor name")
    assessment.auditor_firm = _ask("Auditor firm")
    assessment.engagement_ref = _ask("Engagement reference")

    assessment.save(args.out)
    in_scope = len(lib.in_scope(profile))
    _rule("=")
    _out(f"wrote {args.out}")
    _out(f"{in_scope} of {len(lib.controls)} controls are in scope on these answers.")
    _out(f"Next: python -m dpdpa_audit assess {args.out}")
    return 0


# -------------------------------------------------------------- cmd: assess
def _print_control(ctrl, lib: Library, n: int, total: int) -> None:
    _rule("=")
    _out(f"[{n}/{total}]  {ctrl.id}   {ctrl.title}")
    _out(f"         severity {ctrl.severity} · weight {ctrl.weight:g}")
    _rule()
    _out("OBLIGATION")
    _out(_wrap(ctrl.obligation))
    cite = ctrl.act_ref
    rules = lib.rule_citation_text(ctrl)
    if rules and rules != "—":
        cite += f"  ·  Rules: {rules}"
    pen = lib.penalty_for(ctrl)
    if pen:
        cite += f"  ·  Penalty: {pen['label']} (Schedule entry {pen['entry']})"
    _out("STATUTORY BASIS")
    _out(_wrap(cite))
    _out("AUDIT QUESTION")
    _out(_wrap(ctrl.audit_question))
    _out("TEST PROCEDURE")
    _out(_wrap(ctrl.test_procedure))
    if ctrl.evidence_expected:
        _out("EVIDENCE EXPECTED")
        for e in ctrl.evidence_expected:
            _out(_wrap(f"· {e}", indent="  "))
    _out("SCORING")
    for level in ("0", "2", "4"):
        if level in ctrl.scoring:
            _out(_wrap(f"{level} = {ctrl.scoring[level]}", indent="  "))
    _out("  1 and 3 are the intermediate positions between these anchors.")
    if ctrl.note:
        _out("NOTE")
        _out(_wrap(ctrl.note))
    _rule()


def cmd_assess(args) -> int:
    lib = _library(args)
    a = _load(args.file)
    in_scope = lib.in_scope(a.profile)
    if args.domain:
        wanted = {d.upper() for d in args.domain}
        unknown = wanted - set(lib.domains)
        if unknown:
            _die(f"unknown domain code(s): {', '.join(sorted(unknown))}")
        in_scope = [c for c in in_scope if c.domain in wanted]
    if args.only_unscored:
        in_scope = [c for c in in_scope if not a.response(c.id).assessed]

    if not in_scope:
        _out("Nothing to assess with those filters.")
        return 0

    _out(f"{len(in_scope)} controls to work through. "
         f"Enter a score 0-4, '{NOT_APPLICABLE}', 's' to skip, or 'q' to save and quit.")
    total = len(in_scope)
    for i, ctrl in enumerate(in_scope, start=1):
        r = a.response(ctrl.id)
        _print_control(ctrl, lib, i, total)
        current = "" if r.score in (None, "") else str(r.score)
        while True:
            got = _ask("SCORE", current).strip()
            low = got.lower()
            if low in ("q", "quit"):
                a.save(args.file)
                _out(f"saved {args.file}")
                return 0
            if low in ("s", "skip", ""):
                got = None
                break
            if low == NOT_APPLICABLE.lower():
                got = NOT_APPLICABLE
                break
            if got.isdigit() and 0 <= int(got) <= 4:
                got = int(got)
                break
            print(f"  0-4, '{NOT_APPLICABLE}', 's' or 'q'")
        if got is None:
            continue
        r.score = got
        if isinstance(got, int):
            _out(f"  {got} = {SCORE_LABELS[got]}")
        r.finding = _ask("FINDING", r.finding)
        r.evidence_ref = _ask("EVIDENCE REF", r.evidence_ref)
        if isinstance(got, int) and got < 3:
            r.owner = _ask("REMEDIATION OWNER", r.owner)
            r.target_date = _ask("AGREED TARGET DATE (ISO, blank = derive from priority)",
                                 r.target_date)
        a.save(args.file)

    _rule("=")
    _out(f"saved {args.file}")
    _out(f"Next: python -m dpdpa_audit score {args.file}")
    return 0


# --------------------------------------------------------------- cmd: score
def cmd_score(args) -> int:
    lib = _library(args)
    a = _load(args.file)
    results = score_assessment(lib, a)
    gaps = build_gap_register(results)

    if args.json:
        payload = {
            "entity": a.profile.legal_name,
            "assessment_date": a.assessment_date,
            "library_version": lib.version,
            "overall_maturity_pct": results.overall_maturity_pct,
            "overall_band": results.overall_band[0],
            "controls_total": len(lib.controls),
            "controls_in_scope": results.in_scope_count,
            "controls_assessed": results.assessed_count,
            "coverage_pct": results.coverage_pct,
            "gap_count": len(gaps),
            "gaps_by_severity": results.gap_counts_by_severity(),
            "status_counts": results.status_counts(),
            "domains": [
                {"code": d.code, "name": d.name, "weight": d.weight,
                 "maturity_pct": d.maturity_pct, "band": d.band,
                 "in_scope": len(d.in_scope_results), "assessed": len(d.scored),
                 "gaps": len(d.gaps), "max_risk": d.max_risk}
                for d in results.domains
            ],
            "penalty_exposure": results.penalty_exposure(),
            "unverified_rule_slots": [s["key"] for s in lib.unverified_slots()],
        }
        print(json.dumps(payload, indent=2))
        return 0

    band, band_desc = results.overall_band
    _rule("=")
    _out(f"{a.profile.legal_name or '(entity not named)'} — DPDP Act, 2023 compliance")
    _out(f"assessed {a.assessment_date} against control library v{lib.version}")
    _rule("=")
    _out(f"OVERALL   {results.overall_maturity_pct}%   {band}")
    _out(_wrap(band_desc))
    _out("")
    _out(f"  controls in library   {len(lib.controls)}")
    _out(f"  in scope              {results.in_scope_count}"
         f"   (out of scope {results.out_of_scope_count}, marked NA {results.na_count})")
    _out(f"  assessed              {results.assessed_count}"
         f"   (coverage {results.coverage_pct}%)")
    sev = results.gap_counts_by_severity()
    _out(f"  gaps                  {len(gaps)}"
         f"   (critical {sev['critical']}, high {sev['high']}, "
         f"medium {sev['medium']}, low {sev['low']})")
    _out("")
    _out(f"  {'DOMAIN':<47}{'WT':>5}{'MATURITY':>10}{'BAND':>14}{'GAPS':>6}")
    _rule(width=82)
    for d in results.domains:
        pct = "—" if d.maturity_pct is None else f"{d.maturity_pct:.1f}%"
        name = f"{d.code} — {d.name}"
        _out(f"  {name[:47]:<47}{d.weight:>5.1f}{pct:>10}{d.band:>14}{len(d.gaps):>6}")
    _rule(width=82)

    if results.unassessed:
        _out("")
        _out(f"{len(results.unassessed)} in-scope controls are unassessed and are reported "
             f"as a scope limitation, not as a finding:")
        _out(_wrap(", ".join(r.control.id for r in results.unassessed)))

    pe = results.penalty_exposure()
    if pe["entries"]:
        _out("")
        _out(f"PENALTY EXPOSURE (statutory ceiling)   INR {pe['aggregate_max_inr_crore']:g} crore")
        for e in pe["entries"]:
            n = len(e["controls"])
            _out(f"  entry {e['entry']}  {e['provision']:<14}{e['label']:<24}"
                 f"[{n} control{'s' if n != 1 else ''}]")
        _out(_wrap(pe["caveat"]))

    _out("")
    _out("TOP RESIDUAL RISKS")
    for g in gaps[:10]:
        _out(f"  {g.ref}  {g.control_id:<8}risk {g.risk:>2}/16  {g.priority}  "
             f"due {g.due_date}  {g.title[:44]}")

    slots = lib.unverified_slots()
    if slots:
        _out("")
        _out(_wrap(f"{len(slots)} Rules citations are unverified. Findings rest on the Act, "
                   f"which is cited; run 'citations' for the worklist.", indent=""))
    return 0


# -------------------------------------------------------------- cmd: report
def cmd_report(args) -> int:
    lib = _library(args)
    a = _load(args.file)
    results = score_assessment(lib, a)
    os.makedirs(args.out_dir, exist_ok=True)
    slug = "".join(ch if ch.isalnum() else "_"
                   for ch in (a.profile.trading_name or a.profile.legal_name
                              or "engagement")).strip("_") or "engagement"
    written: List[str] = []

    want_docx = args.format in ("all", "docx")
    want_xlsx = args.format in ("all", "xlsx")

    if want_docx:
        from .word_report import build_report
        written.append(build_report(
            results, os.path.join(args.out_dir, f"{slug}_DPDPA_Audit_Report.docx")))
    if want_xlsx:
        from .excel_report import build_workbook
        written.append(build_workbook(
            results, os.path.join(args.out_dir, f"{slug}_DPDPA_Control_Matrix.xlsx")))

    for p in written:
        _out(f"wrote {p}")
    if want_docx:
        _out("The table of contents is a Word field: open the report and press F9, "
             "or accept the update prompt, to populate it.")
    return 0


# ----------------------------------------------------------- cmd: citations
def cmd_citations(args) -> int:
    lib = _library(args)
    slots = lib.unverified_slots()
    if args.json:
        print(json.dumps(slots, indent=2))
        return 0
    if not slots:
        _out("All Rules citations in the library are marked verified.")
        return 0
    _out(f"{len(slots)} Rules citations await verification against the notified text.")
    _out(_wrap("Each is a slot in controls/citations.yaml. Populate 'citation' and set "
               "'status: VERIFIED_RULES' and every deliverable updates from that one edit.",
               indent=""))
    for s in slots:
        raw = lib.citations["rule_slots"][s["key"]]
        _rule()
        _out(s["key"])
        _out(_wrap(f"subject   {s['subject']}"))
        _out(_wrap(f"act       {raw.get('anchors_act', '—')}"))
        _out(_wrap(f"controls  {', '.join(s['controls']) or '(none)'}"))
    _rule()
    for src in lib.citations["meta"].get("primary_sources_to_check") or []:
        _out(f"  verify against: {src}")
    return 0


# ------------------------------------------------------------ cmd: validate
def cmd_validate(args) -> int:
    lib = _library(args)
    _out(f"control library v{lib.version} at {args.controls!r} validated.")
    _out(f"  domains   {len(lib.domains)}")
    _out(f"  controls  {len(lib.controls)}")
    by_dom = {d.code: len(lib.controls_in(d.code)) for d in lib.ordered_domains()}
    for code, n in by_dom.items():
        _out(f"    {code:<5}{n:>3}  {lib.domains[code].name}")
    sev = {}
    for c in lib.controls.values():
        sev[c.severity] = sev.get(c.severity, 0) + 1
    _out("  severity  " + ", ".join(f"{k} {v}" for k, v in sorted(sev.items())))
    slots = lib.citations["rule_slots"]
    used = {c.rule_slot for c in lib.controls.values() if c.rule_slot}
    unused = sorted(set(slots) - used)
    _out(f"  rule slots {len(slots)} defined, {len(used)} referenced, "
         f"{len(lib.unverified_slots())} unverified")
    if unused:
        _out(_wrap(f"reserved but unreferenced: {', '.join(unused)}"))
    return 0


# ------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dpdpa_audit",
        description="Audit an organisation against the Digital Personal Data "
                    "Protection Act, 2023 and produce an audit-ready report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            typical run
              python -m dpdpa_audit init --out engagement.json
              python -m dpdpa_audit assess engagement.json
              python -m dpdpa_audit score engagement.json
              python -m dpdpa_audit report engagement.json --out-dir output
            """),
    )
    p.add_argument("--controls", default=DEFAULT_CONTROLS,
                   help="directory holding the control library (default: %(default)s)")
    sub = p.add_subparsers(dest="command", required=True)

    i = sub.add_parser("init", help="scope an engagement and write an assessment file")
    i.add_argument("--out", default="engagement.json")
    i.add_argument("--blank", action="store_true",
                   help="write an unpopulated file instead of running the interview")
    i.add_argument("--force", action="store_true", help="overwrite an existing file")
    i.set_defaults(func=cmd_init)

    a = sub.add_parser("assess", help="work through the in-scope controls")
    a.add_argument("file")
    a.add_argument("--domain", action="append",
                   help="restrict to a domain code; repeatable")
    a.add_argument("--only-unscored", action="store_true",
                   help="skip controls already scored")
    a.set_defaults(func=cmd_assess)

    s = sub.add_parser("score", help="compute maturity, risk and penalty exposure")
    s.add_argument("file")
    s.add_argument("--json", action="store_true", help="machine-readable output")
    s.set_defaults(func=cmd_score)

    r = sub.add_parser("report", help="generate the Word report and Excel matrix")
    r.add_argument("file")
    r.add_argument("--out-dir", default="output")
    r.add_argument("--format", choices=("all", "docx", "xlsx"), default="all")
    r.set_defaults(func=cmd_report)

    c = sub.add_parser("citations", help="list Rules citations awaiting verification")
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=cmd_citations)

    v = sub.add_parser("validate", help="load and check the control library")
    v.set_defaults(func=cmd_validate)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
