"""
DPDPA Audit Toolkit — core domain model.

Loads the control library, applies the company profile to determine which
controls are in scope, and holds the assessment state.

Design notes
------------
* The control library is data, not code. Everything in controls/*.yaml can be
  edited without touching this module.
* Applicability is declarative: a control names the profile flags it requires
  and those that exclude it. Every flag referenced anywhere in the library must
  be declared in PROFILE_FLAGS, and load_library() enforces that — a typo in a
  flag name is a load-time error rather than a control silently dropping out of
  scope.
* Nothing here invents a statutory citation. Rules citations come from
  citations.yaml and carry their verification status through to every output.
"""

from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any, Dict, List, Optional

import yaml

__all__ = [
    "PROFILE_FLAGS",
    "SEVERITY_RANK",
    "SCORE_LABELS",
    "NOT_APPLICABLE",
    "Control",
    "Domain",
    "Library",
    "CompanyProfile",
    "Response",
    "Assessment",
    "load_library",
]

# --------------------------------------------------------------------------
# Profile flags
# --------------------------------------------------------------------------
# Every flag a control may reference in `applicability`. Keys are flag names;
# values are (default, description). Defaults are deliberately conservative:
# where a flag widens scope it defaults to True, so an unconsidered flag
# produces a larger audit rather than a silently narrower one. Flags that
# remove obligations (the exemptions) default to False, so an exemption is
# never assumed.
PROFILE_FLAGS: Dict[str, tuple] = {
    "is_sdf": (
        False,
        "Notified by the Central Government as a Significant Data Fiduciary under s.10(1). "
        "Set True only on actual notification, not on self-assessment.",
    ),
    "processes_children_data": (
        True,
        "Processes personal data of individuals under 18, or of persons with a lawful guardian. "
        "Defaults True because age is rarely reliably excluded.",
    ),
    "processes_employee_data": (
        True,
        "Processes personal data of employees, workers or contractors.",
    ),
    "uses_consent_manager": (
        False,
        "Receives or manages consent through a registered Consent Manager under s.6(7).",
    ),
    "is_consent_manager": (
        False,
        "The entity itself acts as a Consent Manager and requires registration under s.6(8).",
    ),
    "has_pre_commencement_data": (
        True,
        "Holds personal data processed on the basis of consent given before commencement, "
        "engaging the retrospective notice duty under s.5(2).",
    ),
    "regulated_sector": (
        False,
        "Subject to sectoral regulation that may impose stricter localisation or transfer "
        "requirements preserved by s.16(2) — banking, payments, insurance, telecom, securities, health.",
    ),
    "claims_exemption": (
        False,
        "Claims any exemption under s.17, including the class-based route in s.17(3).",
    ),
    "startup_exempt_s8_3": (
        False,
        "Exempt from s.8(3) as a notified class under s.17(3). Requires actual notification.",
    ),
    "startup_exempt_s8_7": (
        False,
        "Exempt from s.8(7) as a notified class under s.17(3). Requires actual notification.",
    ),
    "startup_exempt_s11": (
        False,
        "Exempt from s.11 as a notified class under s.17(3). Requires actual notification.",
    ),
}

SEVERITY_RANK: Dict[str, int] = {"critical": 4, "high": 3, "medium": 2, "low": 1}

NOT_APPLICABLE = "NA"

SCORE_LABELS: Dict[int, str] = {
    0: "Absent — no capability",
    1: "Initial — ad hoc, undocumented",
    2: "Developing — partial, inconsistent",
    3: "Managed — substantially in place, minor gaps",
    4: "Optimised — complete, evidenced, tested",
}

MATURITY_BANDS = [
    (0.0, 20.0, "Absent", "Little or no capability. Fundamental obligations are unaddressed."),
    (20.0, 40.0, "Initial", "Isolated activity without programme structure. Exposure is broad."),
    (40.0, 60.0, "Developing", "Core obligations addressed; significant gaps remain in evidence and coverage."),
    (60.0, 80.0, "Managed", "Programme substantially in place. Residual gaps are specific and tractable."),
    (80.0, 100.01, "Optimised", "Obligations met, evidenced and tested, with continuing assurance."),
]


def maturity_band(pct: Optional[float]) -> tuple:
    """Return (band_name, description) for a maturity percentage."""
    if pct is None:
        return ("Not assessed", "No applicable controls were assessed.")
    for lo, hi, name, desc in MATURITY_BANDS:
        if lo <= pct < hi:
            return (name, desc)
    return ("Optimised", MATURITY_BANDS[-1][3])


# --------------------------------------------------------------------------
# Library objects
# --------------------------------------------------------------------------


@dataclass
class Control:
    id: str
    domain: str
    title: str
    obligation: str
    act_ref: str
    audit_question: str
    test_procedure: str
    evidence_expected: List[str]
    scoring: Dict[str, str]
    severity: str
    weight: float = 1.0
    rule_slot: Optional[str] = None
    penalty_entry: Optional[int] = None
    applicability: Dict[str, List[str]] = field(default_factory=dict)
    note: Optional[str] = None
    citation_caution: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def severity_rank(self) -> int:
        return SEVERITY_RANK[self.severity]

    @property
    def target_state(self) -> str:
        """The level-4 descriptor, which doubles as the remediation target."""
        return self.scoring.get("4", "")

    def applies_to(self, profile: "CompanyProfile") -> bool:
        requires = self.applicability.get("requires") or []
        excluded = self.applicability.get("excluded_if") or []
        if any(not profile.flag(f) for f in requires):
            return False
        if any(profile.flag(f) for f in excluded):
            return False
        return True

    def scope_reason(self, profile: "CompanyProfile") -> str:
        """Human-readable explanation of why a control is out of scope."""
        requires = self.applicability.get("requires") or []
        excluded = self.applicability.get("excluded_if") or []
        unmet = [f for f in requires if not profile.flag(f)]
        hit = [f for f in excluded if profile.flag(f)]
        parts = []
        if unmet:
            parts.append("requires " + ", ".join(unmet))
        if hit:
            parts.append("excluded by " + ", ".join(hit))
        return "; ".join(parts) if parts else "in scope"


@dataclass
class Domain:
    code: str
    order: int
    name: str
    weight: float
    scope_question: str
    why_it_matters: str


@dataclass
class Library:
    domains: Dict[str, Domain]
    controls: Dict[str, Control]
    citations: Dict[str, Any]
    version: str = "1.0.0"

    # -- citation helpers ------------------------------------------------
    def rule_slot(self, key: Optional[str]) -> Optional[Dict[str, Any]]:
        if not key:
            return None
        return self.citations["rule_slots"].get(key)

    def rule_citation_text(self, control: Control) -> str:
        """Rendered Rules citation for a control, or an explicit verification marker."""
        slot = self.rule_slot(control.rule_slot)
        if slot is None:
            return "—"
        if slot.get("citation"):
            return str(slot["citation"])
        return "[Rules citation to be verified]"

    def rule_status(self, control: Control) -> Optional[str]:
        slot = self.rule_slot(control.rule_slot)
        return slot.get("status") if slot else None

    def penalty_for(self, control: Control) -> Optional[Dict[str, Any]]:
        if control.penalty_entry is None:
            return None
        for e in self.citations["penalty_schedule"]["entries"]:
            if e["entry"] == control.penalty_entry:
                return e
        return None

    def unverified_slots(self) -> List[Dict[str, Any]]:
        """Rule slots still awaiting verification, with the controls relying on them."""
        out = []
        for key, slot in self.citations["rule_slots"].items():
            if slot.get("status") == "VERIFY_AGAINST_NOTIFIED_RULES":
                users = sorted(c.id for c in self.controls.values() if c.rule_slot == key)
                out.append({"key": key, "subject": slot.get("subject", ""),
                            "note": slot.get("note"), "controls": users})
        return out

    def ordered_domains(self) -> List[Domain]:
        return sorted(self.domains.values(), key=lambda d: d.order)

    def controls_in(self, domain_code: str) -> List[Control]:
        return sorted((c for c in self.controls.values() if c.domain == domain_code),
                      key=lambda c: c.id)

    def in_scope(self, profile: "CompanyProfile") -> List[Control]:
        return [c for c in sorted(self.controls.values(), key=lambda c: c.id)
                if c.applies_to(profile)]


def load_library(controls_dir: str) -> Library:
    """Load and validate the control library from a directory of YAML files."""
    dpath = os.path.join(controls_dir, "domains.yaml")
    cpath = os.path.join(controls_dir, "citations.yaml")
    for p in (dpath, cpath):
        if not os.path.exists(p):
            raise FileNotFoundError(f"required library file missing: {p}")

    with open(dpath, encoding="utf-8") as fh:
        dom_raw = yaml.safe_load(fh)
    domains = {}
    for d in dom_raw["domains"]:
        domains[d["code"]] = Domain(
            code=d["code"], order=int(d["order"]), name=d["name"],
            weight=float(d.get("weight", 1.0)),
            scope_question=d.get("scope_question", "").strip(),
            why_it_matters=d.get("why_it_matters", "").strip(),
        )

    with open(cpath, encoding="utf-8") as fh:
        citations = yaml.safe_load(fh)
    slots = citations.get("rule_slots", {})

    controls: Dict[str, Control] = {}
    files = sorted(glob.glob(os.path.join(controls_dir, "[0-9][0-9]_*.yaml")))
    if not files:
        raise FileNotFoundError(f"no control files matched {controls_dir}/NN_*.yaml")

    errors: List[str] = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        for c in data.get("controls", []):
            cid = c.get("id")
            if not cid:
                errors.append(f"{os.path.basename(f)}: control with no id")
                continue
            if cid in controls:
                errors.append(f"duplicate control id {cid}")
                continue
            if c["domain"] not in domains:
                errors.append(f"{cid}: unknown domain {c['domain']}")
            if c.get("rule_slot") and c["rule_slot"] not in slots:
                errors.append(f"{cid}: unknown rule_slot {c['rule_slot']}")
            if c.get("severity") not in SEVERITY_RANK:
                errors.append(f"{cid}: invalid severity {c.get('severity')!r}")
            sk = sorted(str(k) for k in (c.get("scoring") or {}))
            if sk != ["0", "2", "4"]:
                errors.append(f"{cid}: scoring must define anchors 0, 2 and 4 (found {sk})")
            app = c.get("applicability") or {}
            for bucket in ("requires", "excluded_if"):
                for flagname in app.get(bucket) or []:
                    if flagname not in PROFILE_FLAGS:
                        errors.append(f"{cid}: undeclared profile flag {flagname!r} in {bucket}")
            controls[cid] = Control(
                id=cid, domain=c["domain"], title=c["title"],
                obligation=" ".join(c["obligation"].split()),
                act_ref=c["act_ref"],
                audit_question=" ".join(c["audit_question"].split()),
                test_procedure=" ".join(c.get("test_procedure", "").split()),
                evidence_expected=list(c.get("evidence_expected") or []),
                scoring={str(k): " ".join(str(v).split()) for k, v in c["scoring"].items()},
                severity=c["severity"], weight=float(c.get("weight", 1.0)),
                rule_slot=c.get("rule_slot"), penalty_entry=c.get("penalty_entry"),
                applicability=app,
                note=" ".join(c["note"].split()) if c.get("note") else None,
                citation_caution=(" ".join(c["citation_caution"].split())
                                  if c.get("citation_caution") else None),
                raw=c,
            )

    if errors:
        raise ValueError("control library failed validation:\n  - " + "\n  - ".join(errors))

    return Library(domains=domains, controls=controls, citations=citations,
                   version=str(dom_raw.get("meta", {}).get("library_version", "1.0.0")))


# --------------------------------------------------------------------------
# Company profile
# --------------------------------------------------------------------------


@dataclass
class CompanyProfile:
    legal_name: str = ""
    trading_name: str = ""
    sector: str = ""
    registered_office: str = ""
    headcount: Optional[int] = None
    data_principal_count: Optional[int] = None
    business_description: str = ""
    systems_in_scope: List[str] = field(default_factory=list)
    entities_in_scope: List[str] = field(default_factory=list)
    exclusions: List[str] = field(default_factory=list)
    flags: Dict[str, bool] = field(default_factory=dict)

    def flag(self, name: str) -> bool:
        if name not in PROFILE_FLAGS:
            raise KeyError(f"unknown profile flag: {name}")
        if name in self.flags:
            return bool(self.flags[name])
        return bool(PROFILE_FLAGS[name][0])

    def effective_flags(self) -> Dict[str, bool]:
        return {k: self.flag(k) for k in PROFILE_FLAGS}

    @classmethod
    def blank(cls) -> "CompanyProfile":
        return cls(flags={k: v[0] for k, v in PROFILE_FLAGS.items()})


# --------------------------------------------------------------------------
# Assessment
# --------------------------------------------------------------------------


@dataclass
class Response:
    control_id: str
    score: Any = None                # 0-4, "NA", or None if not yet assessed
    finding: str = ""                # auditor's observation
    evidence: List[str] = field(default_factory=list)
    evidence_ref: str = ""           # document/workpaper reference
    owner: str = ""                  # remediation owner
    target_date: str = ""            # ISO date
    auditor_note: str = ""

    @property
    def assessed(self) -> bool:
        return self.score is not None

    @property
    def numeric(self) -> Optional[int]:
        if isinstance(self.score, bool) or self.score is None:
            return None
        if isinstance(self.score, str):
            if self.score.strip().upper() == NOT_APPLICABLE:
                return None
            try:
                return int(self.score)
            except ValueError:
                return None
        return int(self.score)

    @property
    def not_applicable(self) -> bool:
        return isinstance(self.score, str) and self.score.strip().upper() == NOT_APPLICABLE


@dataclass
class Assessment:
    profile: CompanyProfile
    responses: Dict[str, Response] = field(default_factory=dict)
    assessment_date: str = field(default_factory=lambda: date.today().isoformat())
    auditor_name: str = ""
    auditor_firm: str = ""
    engagement_ref: str = ""
    report_title: str = "DPDPA Compliance Audit Report"
    scope_statement: str = ""
    limitations: List[str] = field(default_factory=list)
    scoping_assumptions: List[str] = field(default_factory=list)
    library_version: str = ""

    def response(self, control_id: str) -> Response:
        return self.responses.setdefault(control_id, Response(control_id=control_id))

    # -- persistence -----------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["responses"] = {k: asdict(v) for k, v in self.responses.items()}
        d["_schema"] = "dpdpa-audit-assessment/1"
        return d

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Assessment":
        prof_d = dict(d.get("profile") or {})
        prof = CompanyProfile(**{k: v for k, v in prof_d.items()
                                 if k in CompanyProfile.__dataclass_fields__})
        resp = {}
        for cid, r in (d.get("responses") or {}).items():
            r = dict(r)
            r.setdefault("control_id", cid)
            resp[cid] = Response(**{k: v for k, v in r.items()
                                    if k in Response.__dataclass_fields__})
        kwargs = {k: v for k, v in d.items()
                  if k in cls.__dataclass_fields__ and k not in ("profile", "responses")}
        return cls(profile=prof, responses=resp, **kwargs)

    @classmethod
    def load(cls, path: str) -> "Assessment":
        with open(path, encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))

    @classmethod
    def blank_for(cls, lib: Library, profile: Optional[CompanyProfile] = None) -> "Assessment":
        profile = profile or CompanyProfile.blank()
        a = cls(profile=profile, library_version=lib.version)
        for c in lib.in_scope(profile):
            a.response(c.id)
        a.scoping_assumptions = [
            "The commencement position of individual provisions of the DPDP Act, 2023 and the "
            "DPDP Rules has not been confirmed. Findings are expressed as compliance gaps "
            "against the framework as a whole and should not be characterised as "
            "contraventions of provisions that are not yet in force.",
            "DPDP Rules citations recorded as '[Rules citation to be verified]' were not "
            "verifiable at the time of the assessment. See the Unverified Citations appendix.",
        ]
        a.limitations = [
            "This assessment is based on information, documentation and explanations made "
            "available by management and on the tests described for each control. It is not an "
            "assurance engagement and expresses no audit opinion.",
            "Testing was performed on a sample basis. The absence of a finding is not a "
            "representation that no exception exists outside the items tested.",
            "The assessment reflects the position as at the assessment date and does not "
            "address subsequent changes in the entity's processing or in the legal framework.",
            "Nothing in this report constitutes legal advice. Conclusions on the application "
            "of the Act to particular processing should be confirmed with qualified counsel.",
        ]
        return a
