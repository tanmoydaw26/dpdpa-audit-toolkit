"""
DPDPA Audit Toolkit
===================

An end-to-end toolkit for auditing an organisation's compliance with the
Digital Personal Data Protection Act, 2023 and producing an audit-ready report.

    from dpdpa_audit import load_library, Assessment, score_assessment

    lib = load_library("controls")
    a = Assessment.load("samples/sample_assessment.json")
    results = score_assessment(lib, a)
    print(results.overall_maturity_pct, results.overall_band[0])

Citation policy
---------------
DPDP Act, 2023 provisions are cited directly. DPDP Rules citations are held in
controls/citations.yaml as slots; where a slot is unpopulated the toolkit emits
"[Rules citation to be verified]" and lists the slot in an appendix rather than
substituting a plausible rule number. See README.md.
"""

from .core import (  # noqa: F401
    PROFILE_FLAGS,
    SCORE_LABELS,
    SEVERITY_RANK,
    Assessment,
    CompanyProfile,
    Control,
    Domain,
    Library,
    Response,
    load_library,
    maturity_band,
)
from .scoring import (  # noqa: F401
    SUBSTANTIALLY_COMPLIANT,
    ControlResult,
    DomainResult,
    Gap,
    Results,
    build_gap_register,
    priority_for,
    risk_band,
    score_assessment,
)

__version__ = "1.0.0"
