"""
DPDPA Audit Toolkit — scoring, risk and gap derivation.

Scoring model
-------------
Each in-scope control is scored 0-4 against the anchored descriptors in the
library (0, 2 and 4 are defined; 1 and 3 are intermediate positions). A control
may instead be marked "NA", which removes it from the denominator entirely
rather than scoring it zero — an important distinction, because scoring an
inapplicable control as zero understates maturity and manufactures a gap.

    control maturity  = score / 4
    domain maturity   = Σ(score × weight) / Σ(4 × weight)   over scored controls
    overall maturity  = Σ(domain maturity × domain weight) / Σ(domain weight)
                        over domains with at least one scored control

Domain-level weighting is used for the overall figure rather than a flat
control average, so that a domain with many controls (Security, nine) does not
mechanically dominate one with few but weighty ones (Consent Manager, three).

Risk model
----------
    residual risk = severity_rank × (4 − score)      range 0-16

Severity ranks critical=4, high=3, medium=2, low=1. Risk is a function of both
how serious the obligation is and how far short the entity falls, so a minor
gap in a critical control and a total gap in a low-severity one are separated.
Unscored controls carry no risk figure; they are reported as unassessed, which
is a scope limitation rather than a finding.

Penalty exposure
----------------
Reported as the aggregate of the statutory MAXIMA attaching to the Schedule
entries engaged by controls that fall below the substantially-compliant
threshold. This is an exposure ceiling under the Schedule, not a prediction of
any penalty: s.33(2) requires the Board to have regard to gravity,
proportionality and mitigation, and any actual penalty would be a fraction of
the ceiling. Presented so that the reader can see which entries are engaged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from .core import (
    Assessment,
    Control,
    Library,
    SEVERITY_RANK,
    maturity_band,
)

__all__ = [
    "SUBSTANTIALLY_COMPLIANT",
    "ControlResult",
    "DomainResult",
    "Results",
    "Gap",
    "score_assessment",
    "build_gap_register",
    "risk_band",
    "priority_for",
]

# A control at 3 or above is treated as substantially in place. Below 3 it
# yields a gap. 3 is the "minor gaps remain" anchor, so this threshold reports
# a gap wherever the auditor could not conclude the obligation was met.
SUBSTANTIALLY_COMPLIANT = 3

RISK_BANDS = [
    (12, 17, "Critical"),
    (8, 12, "High"),
    (4, 8, "Medium"),
    (1, 4, "Low"),
    (0, 1, "None"),
]

PRIORITY_RULES = [
    ("P1", 12, 30, "Immediate — remediate within 30 days"),
    ("P2", 8, 60, "High — remediate within 60 days"),
    ("P3", 4, 90, "Medium — remediate within 90 days"),
    ("P4", 0, 180, "Low — remediate within 180 days"),
]


def risk_band(risk: Optional[int]) -> str:
    if risk is None:
        return "Not assessed"
    for lo, hi, name in RISK_BANDS:
        if lo <= risk < hi:
            return name
    return "Critical"


def priority_for(risk: int) -> tuple:
    """Return (priority_code, days_to_due, description) for a risk score."""
    for code, threshold, days, desc in PRIORITY_RULES:
        if risk >= threshold:
            return (code, days, desc)
    return PRIORITY_RULES[-1][0], PRIORITY_RULES[-1][2], PRIORITY_RULES[-1][3]


# --------------------------------------------------------------------------


@dataclass
class ControlResult:
    control: Control
    in_scope: bool
    scope_reason: str
    score: Optional[int]
    not_applicable: bool
    finding: str
    evidence: List[str]
    evidence_ref: str
    owner: str
    target_date: str
    auditor_note: str
    act_ref: str
    rule_citation: str
    rule_status: Optional[str]
    penalty: Optional[Dict[str, Any]]

    @property
    def assessed(self) -> bool:
        return self.score is not None

    @property
    def risk(self) -> Optional[int]:
        if self.score is None:
            return None
        return SEVERITY_RANK[self.control.severity] * (4 - self.score)

    @property
    def risk_band(self) -> str:
        return risk_band(self.risk)

    @property
    def maturity_pct(self) -> Optional[float]:
        return None if self.score is None else round(self.score / 4 * 100, 1)

    @property
    def is_gap(self) -> bool:
        return self.score is not None and self.score < SUBSTANTIALLY_COMPLIANT

    @property
    def status_label(self) -> str:
        if not self.in_scope:
            return "Out of scope"
        if self.not_applicable:
            return "Not applicable"
        if self.score is None:
            return "Not assessed"
        if self.score >= 4:
            return "Compliant"
        if self.score >= SUBSTANTIALLY_COMPLIANT:
            return "Substantially compliant"
        if self.score >= 2:
            return "Partially compliant"
        return "Non-compliant"


@dataclass
class DomainResult:
    code: str
    name: str
    order: int
    weight: float
    scope_question: str
    why_it_matters: str
    results: List[ControlResult] = field(default_factory=list)

    @property
    def scored(self) -> List[ControlResult]:
        return [r for r in self.results if r.assessed]

    @property
    def in_scope_results(self) -> List[ControlResult]:
        return [r for r in self.results if r.in_scope and not r.not_applicable]

    @property
    def maturity_pct(self) -> Optional[float]:
        s = self.scored
        if not s:
            return None
        num = sum(r.score * r.control.weight for r in s)
        den = sum(4 * r.control.weight for r in s)
        return round(num / den * 100, 1) if den else None

    @property
    def band(self) -> str:
        return maturity_band(self.maturity_pct)[0]

    @property
    def gaps(self) -> List[ControlResult]:
        return [r for r in self.results if r.is_gap]

    @property
    def unassessed(self) -> List[ControlResult]:
        return [r for r in self.results if r.in_scope and not r.not_applicable and not r.assessed]

    @property
    def max_risk(self) -> int:
        risks = [r.risk for r in self.scored if r.risk is not None]
        return max(risks) if risks else 0

    @property
    def critical_gap_count(self) -> int:
        return sum(1 for r in self.gaps if r.control.severity == "critical")


@dataclass
class Results:
    library: Library
    assessment: Assessment
    domains: List[DomainResult]

    # -- aggregate scoring ----------------------------------------------
    @property
    def all_results(self) -> List[ControlResult]:
        return [r for d in self.domains for r in d.results]

    @property
    def scored(self) -> List[ControlResult]:
        return [r for r in self.all_results if r.assessed]

    @property
    def overall_maturity_pct(self) -> Optional[float]:
        contributing = [d for d in self.domains if d.maturity_pct is not None]
        if not contributing:
            return None
        num = sum(d.maturity_pct * d.weight for d in contributing)
        den = sum(d.weight for d in contributing)
        return round(num / den, 1) if den else None

    @property
    def overall_band(self) -> tuple:
        return maturity_band(self.overall_maturity_pct)

    @property
    def in_scope_count(self) -> int:
        return sum(len(d.in_scope_results) for d in self.domains)

    @property
    def out_of_scope_count(self) -> int:
        return sum(1 for r in self.all_results if not r.in_scope)

    @property
    def na_count(self) -> int:
        return sum(1 for r in self.all_results if r.not_applicable)

    @property
    def assessed_count(self) -> int:
        return len(self.scored)

    @property
    def unassessed(self) -> List[ControlResult]:
        return [r for d in self.domains for r in d.unassessed]

    @property
    def coverage_pct(self) -> float:
        total = self.in_scope_count
        return round(self.assessed_count / total * 100, 1) if total else 0.0

    @property
    def gaps(self) -> List[ControlResult]:
        return [r for r in self.all_results if r.is_gap]

    def gap_counts_by_severity(self) -> Dict[str, int]:
        out = {k: 0 for k in ("critical", "high", "medium", "low")}
        for r in self.gaps:
            out[r.control.severity] += 1
        return out

    def gap_counts_by_risk_band(self) -> Dict[str, int]:
        out = {k: 0 for k in ("Critical", "High", "Medium", "Low", "None")}
        for r in self.gaps:
            out[r.risk_band] = out.get(r.risk_band, 0) + 1
        return out

    def status_counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for r in self.all_results:
            out[r.status_label] = out.get(r.status_label, 0) + 1
        return out

    # -- penalty exposure ------------------------------------------------
    def penalty_exposure(self) -> Dict[str, Any]:
        """Schedule entries engaged by controls falling below the threshold."""
        engaged: Dict[int, Dict[str, Any]] = {}
        for r in self.gaps:
            if not r.penalty:
                continue
            e = r.penalty["entry"]
            rec = engaged.setdefault(e, {
                "entry": e,
                "breach": r.penalty["breach"],
                "provision": r.penalty["provision"],
                "label": r.penalty["label"],
                "max_inr_crore": r.penalty.get("max_penalty_inr_crore"),
                "controls": [],
            })
            rec["controls"].append(r.control.id)
        entries = sorted(engaged.values(), key=lambda x: -(x["max_inr_crore"] or 0))
        total = sum(e["max_inr_crore"] or 0 for e in entries)
        return {
            "entries": entries,
            "aggregate_max_inr_crore": round(total, 3),
            "basis": (
                "Aggregate of the statutory maxima under the Schedule to the DPDP Act, 2023 "
                "for those entries engaged by controls scored below "
                f"{SUBSTANTIALLY_COMPLIANT} of 4."
            ),
            "caveat": (
                "This is a ceiling under the Schedule, not an estimate of any penalty that "
                "would in fact be imposed. Section 33(2) requires the Board to have regard to "
                "the nature and gravity of the breach, its duration and repetitive nature, the "
                "type of personal data affected, mitigating action and its timeliness and "
                "effectiveness, and proportionality. Documented, prompt remediation is an "
                "express mitigating factor."
            ),
        }

    def domain_by_code(self, code: str) -> Optional[DomainResult]:
        for d in self.domains:
            if d.code == code:
                return d
        return None

    def top_risks(self, n: int = 10) -> List[ControlResult]:
        return sorted(
            self.gaps,
            key=lambda r: (-(r.risk or 0), -SEVERITY_RANK[r.control.severity], r.control.id),
        )[:n]


# --------------------------------------------------------------------------


def score_assessment(lib: Library, assessment: Assessment) -> Results:
    """Apply the profile and responses to the library and compute all results."""
    profile = assessment.profile
    domains: List[DomainResult] = []

    for dom in lib.ordered_domains():
        dr = DomainResult(
            code=dom.code, name=dom.name, order=dom.order, weight=dom.weight,
            scope_question=dom.scope_question, why_it_matters=dom.why_it_matters,
        )
        for ctrl in lib.controls_in(dom.code):
            in_scope = ctrl.applies_to(profile)
            resp = assessment.responses.get(ctrl.id)
            score = resp.numeric if (resp and in_scope) else None
            if score is not None:
                score = max(0, min(4, int(score)))
            dr.results.append(ControlResult(
                control=ctrl,
                in_scope=in_scope,
                scope_reason=ctrl.scope_reason(profile),
                score=score,
                not_applicable=bool(resp and resp.not_applicable),
                finding=(resp.finding if resp else ""),
                evidence=list(resp.evidence) if resp else [],
                evidence_ref=(resp.evidence_ref if resp else ""),
                owner=(resp.owner if resp else ""),
                target_date=(resp.target_date if resp else ""),
                auditor_note=(resp.auditor_note if resp else ""),
                act_ref=ctrl.act_ref,
                rule_citation=lib.rule_citation_text(ctrl),
                rule_status=lib.rule_status(ctrl),
                penalty=lib.penalty_for(ctrl),
            ))
        domains.append(dr)

    return Results(library=lib, assessment=assessment, domains=domains)


# --------------------------------------------------------------------------


@dataclass
class Gap:
    ref: str
    control_id: str
    domain_code: str
    domain_name: str
    title: str
    severity: str
    score: int
    risk: int
    risk_band: str
    priority: str
    due_date: str
    act_ref: str
    rule_citation: str
    penalty_label: str
    finding: str
    target_state: str
    owner: str
    evidence_ref: str

    def as_row(self) -> List[Any]:
        return [self.ref, self.control_id, self.domain_name, self.title, self.severity,
                self.score, self.risk, self.risk_band, self.priority, self.due_date,
                self.act_ref, self.rule_citation, self.penalty_label, self.finding,
                self.target_state, self.owner, self.evidence_ref]


GAP_COLUMNS = ["Gap ref", "Control", "Domain", "Control title", "Severity", "Score",
               "Risk", "Risk band", "Priority", "Target date", "Act reference",
               "Rules reference", "Penalty exposure", "Finding", "Required target state",
               "Owner", "Evidence ref"]


def build_gap_register(results: Results, base_date: Optional[str] = None) -> List[Gap]:
    """Derive an ordered, prioritised gap register from scored results.

    The 'required target state' for each gap is the library's own level-4
    descriptor, so remediation is expressed as the standard the control defines
    rather than as free-text advice invented per engagement.
    """
    start = date.fromisoformat(base_date or results.assessment.assessment_date)
    gaps: List[Gap] = []

    ordered = sorted(
        results.gaps,
        key=lambda r: (-(r.risk or 0), -SEVERITY_RANK[r.control.severity], r.control.id),
    )

    for i, r in enumerate(ordered, start=1):
        risk = r.risk or 0
        code, days, _desc = priority_for(risk)
        due = r.target_date or (start + timedelta(days=days)).isoformat()
        dom = results.domain_by_code(r.control.domain)
        gaps.append(Gap(
            ref=f"G{i:03d}",
            control_id=r.control.id,
            domain_code=r.control.domain,
            domain_name=dom.name if dom else r.control.domain,
            title=r.control.title,
            severity=r.control.severity.capitalize(),
            score=r.score if r.score is not None else 0,
            risk=risk,
            risk_band=r.risk_band,
            priority=code,
            due_date=due,
            act_ref=r.act_ref,
            rule_citation=r.rule_citation,
            penalty_label=(r.penalty["label"] if r.penalty else "—"),
            finding=r.finding or "(no finding recorded)",
            target_state=r.control.target_state,
            owner=r.owner or "(unassigned)",
            evidence_ref=r.evidence_ref or "—",
        ))
    return gaps
