"""
Build the standalone audit workbench from the control library.

    python3 webapp/build_webapp.py --out output/DPDPA_Audit_Workbench.html

The app is a single HTML file with the library, the scoring constants and the
worked example inlined, so it opens from a file:// path with no server, no
network and no build step for whoever receives it.

Why generate rather than hand-write the data: the workbench, the CLI, the
workbook and the Word report must all report the same numbers from the same
90 controls. The library stays the single source and every consumer is built
from it, so a control edited in controls/*.yaml cannot be stale in one
deliverable and current in another. The same applies to the scoring constants
below — they are read out of dpdpa_audit rather than restated in JavaScript.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from dpdpa_audit.core import (  # noqa: E402
    MATURITY_BANDS,
    PROFILE_FLAGS,
    SEVERITY_RANK,
    Assessment,
    load_library,
)
from dpdpa_audit.scoring import (  # noqa: E402
    PRIORITY_RULES,
    RISK_BANDS,
    SUBSTANTIALLY_COMPLIANT,
    score_assessment,
)

TEMPLATE = os.path.join(HERE, "app_template.html")


def control_payload(c) -> dict:
    return {
        "id": c.id,
        "domain": c.domain,
        "title": c.title,
        "obligation": c.obligation,
        "act_ref": c.act_ref,
        "audit_question": c.audit_question,
        "test_procedure": c.test_procedure,
        "evidence_expected": c.evidence_expected,
        "scoring": c.scoring,
        "severity": c.severity,
        "weight": c.weight,
        "rule_slot": c.rule_slot,
        "penalty_entry": c.penalty_entry,
        "applicability": {k: list(v or []) for k, v in (c.applicability or {}).items()},
        "note": c.note,
        "citation_caution": c.citation_caution,
    }


def build_data(lib, sample: Assessment) -> dict:
    # The penalty framing text is taken from the engine that produced it rather
    # than retyped, so the ceiling-not-a-prediction caveat cannot drift.
    pe = score_assessment(lib, sample).penalty_exposure()
    blank = Assessment.blank_for(lib)

    return {
        "library_version": lib.version,
        "substantially_compliant": SUBSTANTIALLY_COMPLIANT,
        "severity_rank": SEVERITY_RANK,
        "maturity_bands": [list(b) for b in MATURITY_BANDS],
        "risk_bands": [list(b) for b in RISK_BANDS],
        "priority_rules": [list(r) for r in PRIORITY_RULES],
        "profile_flags": [
            {"name": name, "default": bool(default), "description": desc}
            for name, (default, desc) in PROFILE_FLAGS.items()
        ],
        "domains": [asdict(d) for d in lib.ordered_domains()],
        "controls": [control_payload(c) for c in
                     sorted(lib.controls.values(), key=lambda c: c.id)],
        "citations": lib.citations,
        "unverified_keys": [s["key"] for s in lib.unverified_slots()],
        "penalty_basis": pe["basis"],
        "penalty_caveat": pe["caveat"],
        "default_limitations": blank.limitations,
        "default_scoping_assumptions": blank.scoping_assumptions,
    }


def inject(template: str, token: str, payload) -> str:
    """Substitute a JSON payload for a /*__TOKEN__*/ placeholder.

    </script> inside a string literal would end the script element early, and
    U+2028/U+2029 are line terminators in JavaScript but not in JSON, so both
    are escaped. json.dumps already escapes the rest.
    """
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    blob = (blob.replace("</", "<\\/")
                .replace(" ", "\\u2028")
                .replace(" ", "\\u2029"))
    marker = f"/*__{token}__*/null"
    if marker not in template:
        raise SystemExit(f"template has no {marker} placeholder")
    return template.replace(marker, blob)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--controls", default=os.path.join(ROOT, "controls"))
    ap.add_argument("--sample", default=os.path.join(ROOT, "samples", "sample_assessment.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "output", "DPDPA_Audit_Workbench.html"))
    ap.add_argument("--no-sample", action="store_true",
                    help="ship without the worked example; the app opens blank")
    args = ap.parse_args(argv)

    lib = load_library(args.controls)
    sample = Assessment.load(args.sample)

    with open(TEMPLATE, encoding="utf-8") as fh:
        html = fh.read()

    data = build_data(lib, sample)
    html = inject(html, "DATA", data)
    html = inject(html, "SAMPLE", None if args.no_sample else sample.to_dict())

    title = (f"DPDP Act audit workbench — {sample.profile.trading_name}"
             if not args.no_sample and sample.profile.trading_name
             else "DPDP Act audit workbench")
    html = html.replace("<title>DPDP Act audit workbench</title>",
                        f"<title>{title}</title>")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(html)

    size = os.path.getsize(args.out)
    print(f"wrote {args.out}  ({size / 1024:.0f} KB)")
    print(f"  {len(data['controls'])} controls · {len(data['domains'])} domains · "
          f"library v{data['library_version']}")
    print(f"  {len(data['unverified_keys'])} Rules citations render as unverified slots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
