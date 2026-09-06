"""
DPDPA Audit Toolkit — formal Word audit report generator.

Produces a signed-report-shaped deliverable: title page, document control,
contents field, executive summary, scope and methodology, applicability
determination, obligation-by-obligation findings, a landscape gap register,
a prioritised remediation roadmap, limitations, a sign-off block, and appendices
covering the unverified Rules citations and the penalty Schedule.

Implementation note
-------------------
Built on python-docx rather than docx-js so that the delivered toolkit is pure
Python and runs with `pip install -r requirements.txt` alone. The trade-off is
that the table of contents is written as a Word TOC field which populates on
first open (or on F9) rather than being pre-rendered.
"""

from __future__ import annotations

import os
import re
from datetime import date
from typing import Any, Dict, List, Optional

from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from .core import SCORE_LABELS
from .scoring import PRIORITY_RULES, Results, SUBSTANTIALLY_COMPLIANT, build_gap_register

BODY_FONT = "Times New Roman"
HEAD_FONT = "Arial"

NAVY = RGBColor(0x1F, 0x35, 0x52)
SLATE = RGBColor(0x44, 0x54, 0x6A)
RED = RGBColor(0xC0, 0x00, 0x00)
GREY = RGBColor(0x60, 0x60, 0x60)

F_HEAD = "1F3552"
F_SUB = "EEF2F7"
F_0 = "F8D7D7"
F_2 = "FDECC8"
F_3 = "E4EFDC"
F_4 = "D2E7C4"
F_NA = "EDEDED"

SEV_FILL = {"Critical": "F8D7D7", "High": "FDE2D0", "Medium": "FDECC8", "Low": "EDEDED"}


# ---------------------------------------------------------------- helpers
def _fld(paragraph, instr: str, placeholder: str = " ") -> None:
    """Insert a Word field code (used for page numbers and the TOC)."""
    run = paragraph.add_run()
    b = OxmlElement("w:fldChar")
    b.set(qn("w:fldCharType"), "begin")
    i = OxmlElement("w:instrText")
    i.set(qn("xml:space"), "preserve")
    i.text = instr
    s = OxmlElement("w:fldChar")
    s.set(qn("w:fldCharType"), "separate")
    t = OxmlElement("w:t")
    t.text = placeholder
    e = OxmlElement("w:fldChar")
    e.set(qn("w:fldCharType"), "end")
    for el in (b, i, s, t, e):
        run._r.append(el)


def _shade(cell, fill: str) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def _repeat_header(row) -> None:
    trPr = row._tr.get_or_add_trPr()
    h = OxmlElement("w:tblHeader")
    h.set(qn("w:val"), "true")
    trPr.append(h)


def _no_split(row) -> None:
    trPr = row._tr.get_or_add_trPr()
    c = OxmlElement("w:cantSplit")
    trPr.append(c)


def _cell(cell, text: Any, *, bold: bool = False, size: int = 9, fill: Optional[str] = None,
          color: Optional[RGBColor] = None, align: Optional[str] = None,
          font: str = HEAD_FONT, italic: bool = False) -> None:
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after = Pt(1)
    if align == "center":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif align == "right":
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = p.add_run("" if text is None else str(text))
    r.font.name = font
    r.font.size = Pt(size)
    r.bold = bold
    r.italic = italic
    if color is not None:
        r.font.color.rgb = color
    if fill:
        _shade(cell, fill)


_TWIPS_PER_CM = 566.93

# Schema order in CT_TblPrBase — w:tblW must precede all of these.
_TBLW_SUCCESSORS = ("w:jc", "w:tblCellSpacing", "w:tblInd", "w:tblBorders", "w:shd",
                    "w:tblLayout", "w:tblCellMar", "w:tblLook", "w:tblCaption",
                    "w:tblDescription")


def _grid(t, widths: List[float]) -> None:
    """Pin the table's column grid and total width.

    python-docx writes an equal-width w:tblGrid when the table is created and
    setting cell widths does not update it. Word tolerates that; LibreOffice
    honours the grid over the cell widths and lays the table out evenly, which
    makes narrow columns swallow long prose. Rewriting the grid and declaring a
    fixed layout is what actually makes the requested widths take effect.
    """
    tbl = t._tbl
    tblPr = tbl.tblPr

    for el in tblPr.findall(qn("w:tblW")):
        tblPr.remove(el)
    tblW = OxmlElement("w:tblW")
    tblW.set(qn("w:w"), str(int(sum(widths) * _TWIPS_PER_CM)))
    tblW.set(qn("w:type"), "dxa")
    anchor = None
    for name in _TBLW_SUCCESSORS:
        found = tblPr.find(qn(name))
        if found is not None:
            anchor = found
            break
    if anchor is None:
        tblPr.append(tblW)
    else:
        anchor.addprevious(tblW)

    old = tbl.find(qn("w:tblGrid"))
    if old is not None:
        tbl.remove(old)
    grid = OxmlElement("w:tblGrid")
    for w in widths:
        gc = OxmlElement("w:gridCol")
        gc.set(qn("w:w"), str(int(w * _TWIPS_PER_CM)))
        grid.append(gc)
    tblPr.addnext(grid)


def _usable_cm(doc) -> float:
    """Text width of the section currently being written to."""
    s = doc.sections[-1]
    return float(s.page_width.cm - s.left_margin.cm - s.right_margin.cm)


def _table(doc, cols: int, widths: List[float], headers: Optional[List[str]] = None,
           *, size: int = 9) -> Any:
    if len(widths) != cols:
        raise ValueError(f"{cols} columns but {len(widths)} widths")
    # Widths are authored as proportions and scaled to the live section's text
    # width, so a table cannot silently overflow the page or leave a gutter, and
    # the same declarations work in the landscape sections.
    scale = _usable_cm(doc) / sum(widths)
    widths = [round(w * scale, 3) for w in widths]
    t = doc.add_table(rows=0, cols=cols)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    _grid(t, widths)
    if headers:
        row = t.add_row()
        _repeat_header(row)
        for i, h in enumerate(headers):
            _cell(row.cells[i], h, bold=True, size=size, fill=F_HEAD,
                  color=RGBColor(0xFF, 0xFF, 0xFF), align="center")
    for r in t.rows:
        for i, w in enumerate(widths):
            r.cells[i].width = Cm(w)
    t._widths = widths  # type: ignore[attr-defined]
    return t


def _row(t, values: List[Any], **kw) -> Any:
    r = t.add_row()
    _no_split(r)
    widths = getattr(t, "_widths", None)
    for i, v in enumerate(values):
        _cell(r.cells[i], v, **kw)
        if widths and i < len(widths):
            r.cells[i].width = Cm(widths[i])
    return r


def _blank_row(t) -> Any:
    """Add a row without writing cell content, with grid widths applied."""
    r = t.add_row()
    _no_split(r)
    for i, w in enumerate(getattr(t, "_widths", [])):
        r.cells[i].width = Cm(w)
    return r


def _p(doc, text: str = "", *, style: Optional[str] = None, size: int = 10.5,
       bold: bool = False, italic: bool = False, font: str = BODY_FONT,
       color: Optional[RGBColor] = None, before: int = 0, after: int = 6,
       align: Optional[str] = None, indent: float = 0.0):
    p = doc.add_paragraph(style=style)
    pf = p.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    if indent:
        pf.left_indent = Cm(indent)
    if align == "center":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif align == "justify":
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if text:
        r = p.add_run(text)
        r.font.name = font
        r.font.size = Pt(size)
        r.bold = bold
        r.italic = italic
        if color is not None:
            r.font.color.rgb = color
    return p


def _h(doc, text: str, level: int = 1, *, after: int = 6):
    p = doc.add_heading("", level=level)
    p.paragraph_format.space_before = Pt(14 if level <= 2 else 10)
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    r.font.name = HEAD_FONT
    r.font.color.rgb = NAVY
    r.font.size = Pt({1: 16, 2: 13, 3: 11, 4: 10}.get(level, 10))
    r.bold = True
    return p


def _label_para(doc, label: str, text: str, *, indent: float = 0.0):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.left_indent = Cm(indent)
    a = p.add_run(f"{label}  ")
    a.font.name = HEAD_FONT
    a.font.size = Pt(8.5)
    a.bold = True
    a.font.color.rgb = SLATE
    b = p.add_run(text)
    b.font.name = BODY_FONT
    b.font.size = Pt(10)
    return p


def _bullets(doc, items: List[str], *, size: int = 10.5, numbered: bool = False):
    for it in items:
        p = doc.add_paragraph(style="List Number" if numbered else "List Bullet")
        p.paragraph_format.space_after = Pt(4)
        r = p.add_run(it)
        r.font.name = BODY_FONT
        r.font.size = Pt(size)


def _rule(doc, *, before: int = 4, after: int = 8) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    pPr = p._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "BFBFBF")
    bdr.append(bottom)
    pPr.append(bdr)


def _score_fill(score: Optional[int], applicable: bool = True) -> str:
    if not applicable or score is None:
        return F_NA
    return {0: F_0, 1: F_0, 2: F_2, 3: F_3, 4: F_4}[score]


def _footer(section, text: str) -> None:
    section.footer.is_linked_to_previous = False
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text + "     Page ")
    r.font.name = HEAD_FONT
    r.font.size = Pt(8)
    r.font.color.rgb = GREY
    _fld(p, "PAGE", "1")
    r2 = p.add_run(" of ")
    r2.font.name = HEAD_FONT
    r2.font.size = Pt(8)
    r2.font.color.rgb = GREY
    _fld(p, "NUMPAGES", "1")
    for run in p.runs:
        run.font.name = HEAD_FONT
        run.font.size = Pt(8)
        run.font.color.rgb = GREY


def _pct(v: Optional[float]) -> str:
    return "—" if v is None else f"{v:.1f}%"


def _softbreak(s: str) -> str:
    """Allow long UPPER_SNAKE_CASE identifiers to wrap at the underscores.

    Word and LibreOffice both treat an underscored token as one unbreakable
    word and, in a narrow column, break it mid-word instead
    ("CHILD_CONSENT_VERIFICAT / ION"). A zero-width space after each underscore
    gives the line-breaker a legal break point without changing the text: the
    key still copies and searches as written.
    """
    return s.replace("_", "_​")


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9“'\"(])")


def _abridge(text: str, limit: int) -> str:
    """Shorten to roughly `limit` characters on a sentence boundary.

    A summary table cannot carry a three-sentence finding, but cutting prose
    mid-clause reads as an error rather than as an abridgement. Sentences are
    packed greedily so every cell ends as a grammatical statement, and only a
    single sentence longer than the whole budget is cut on a word boundary. The
    unabridged finding is in section 4 against the control.
    """
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    kept: List[str] = []
    used = 0
    for sentence in _SENTENCE_SPLIT.split(text):
        cost = len(sentence) + (1 if kept else 0)
        if used + cost > limit:
            break
        kept.append(sentence)
        used += cost
    if kept:
        return " ".join(kept)
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + " …"


def _id_list(ids: List[str], keep: int) -> str:
    """Join control IDs, summarising the tail rather than cutting an ID in half."""
    if len(ids) <= keep:
        return ", ".join(ids)
    rest = len(ids) - keep
    return ", ".join(ids[:keep]) + f" and {rest} other{'s' if rest != 1 else ''}"


# ---------------------------------------------------------------- sections
def _title_page(doc, results: Results) -> None:
    a = results.assessment
    p = results.assessment.profile
    for _ in range(3):
        _p(doc, after=0)
    _p(doc, "PRIVATE AND CONFIDENTIAL", size=9, bold=True, font=HEAD_FONT,
       color=RED, align="center", after=30)
    _p(doc, a.report_title, size=26, bold=True, font=HEAD_FONT, color=NAVY,
       align="center", after=6)
    _p(doc, "Digital Personal Data Protection Act, 2023", size=13, font=HEAD_FONT,
       color=SLATE, align="center", after=26)
    _rule(doc, after=20)
    _p(doc, p.legal_name, size=17, bold=True, font=HEAD_FONT, align="center", after=2)
    if p.trading_name and p.trading_name != p.legal_name:
        _p(doc, f"trading as {p.trading_name}", size=11, italic=True, align="center", after=4)
    _p(doc, p.sector, size=10, color=SLATE, align="center", after=30)

    t = _table(doc, 2, [5.2, 9.8])
    for k, v in [
        ("Report date", date.today().isoformat()),
        ("Assessment date", a.assessment_date),
        ("Engagement reference", a.engagement_ref or "—"),
        ("Prepared by", a.auditor_name or "—"),
        ("Firm", a.auditor_firm or "—"),
        ("Control library version", f"v{results.library.version} "
                                    f"({len(results.library.controls)} controls, "
                                    f"{len(results.library.domains)} domains)"),
        ("Controls in scope", str(results.in_scope_count)),
        ("Overall maturity", f"{_pct(results.overall_maturity_pct)} — {results.overall_band[0]}"),
    ]:
        r = _row(t, [k, v], size=10)
        _cell(r.cells[0], k, bold=True, size=10, fill=F_SUB)
        _cell(r.cells[1], v, size=10)

    _p(doc, after=24)
    _p(doc, "This report has been prepared for the internal use of the addressee. It contains "
            "findings about the security and compliance posture of the entity and should be "
            "handled accordingly. It is not an assurance report and expresses no audit opinion.",
       size=9, italic=True, color=SLATE, align="center")


def _doc_control(doc, results: Results) -> None:
    a = results.assessment
    _h(doc, "Document control", 1)
    t = _table(doc, 4, [2.4, 3.4, 5.4, 3.8],
               ["Version", "Date", "Description", "Author"])
    _row(t, ["1.0", a.assessment_date, "Final report issued to management", a.auditor_name])
    _row(t, ["0.2", a.assessment_date,
             "Draft for management response and factual accuracy review", a.auditor_name])
    _row(t, ["0.1", a.assessment_date, "Initial draft — fieldwork complete", a.auditor_name])

    _p(doc, after=10)
    _h(doc, "Distribution", 2)
    t = _table(doc, 2, [7.5, 7.5], ["Recipient", "Basis"])
    _row(t, ["Board of Directors", "Oversight of the compliance programme"])
    _row(t, ["Audit and Risk Committee", "Consideration of findings and remediation plan"])
    _row(t, ["Chief Executive Officer", "Accountability for the response"])
    _row(t, ["Head of Legal & Compliance", "Owner of the remediation plan"])
    _row(t, ["Chief Information Security Officer", "Owner of the security findings"])

    _p(doc, after=10)
    _h(doc, "Contents", 2)
    _p(doc, "The table of contents below is a field. If it appears empty, select it and press "
            "F9, or open the document in Word and accept the prompt to update fields.",
       size=9, italic=True, color=SLATE, after=8)
    p = doc.add_paragraph()
    _fld(p, 'TOC \\o "1-3" \\h \\z \\u', "Right-click and choose Update Field.")


def _exec_summary(doc, results: Results, gaps: List) -> None:
    _h(doc, "1.  Executive summary", 1)
    prof = results.assessment.profile
    band, band_desc = results.overall_band
    sev = results.gap_counts_by_severity()
    p1 = [g for g in gaps if g.priority == "P1"]
    pe = results.penalty_exposure()

    _h(doc, "1.1  Overall conclusion", 2)
    t = _table(doc, 2, [5.0, 10.0])
    r = _blank_row(t)
    _cell(r.cells[0], _pct(results.overall_maturity_pct), bold=True, size=30,
          fill=F_SUB, color=NAVY, align="center")
    _cell(r.cells[1], f"{band} — {band_desc}", bold=True, size=11)

    _p(doc, after=8)
    _p(doc, f"{prof.legal_name} was assessed against {results.in_scope_count} controls derived "
            f"from the Digital Personal Data Protection Act, 2023 and the DPDP Rules, of which "
            f"{results.assessed_count} were assessed "
            f"({_pct(results.coverage_pct)} coverage). The entity achieved a weighted maturity "
            f"of {_pct(results.overall_maturity_pct)}, placing it in the {band} band. "
            f"{len(results.gaps)} controls fell below the substantially-compliant threshold and "
            f"are reported as gaps, of which {sev['critical']} attach to obligations rated "
            f"critical.", align="justify")

    strongest = max((d for d in results.domains if d.maturity_pct is not None),
                    key=lambda d: d.maturity_pct)
    weakest = sorted((d for d in results.domains if d.maturity_pct is not None),
                     key=lambda d: d.maturity_pct)[:3]
    _p(doc, f"The distribution of maturity is uneven, and that unevenness is the central finding "
            f"of this assessment. {strongest.name} is the strongest area at "
            f"{_pct(strongest.maturity_pct)}, reflecting investment made for other regulatory "
            f"purposes. The weakest areas — "
            + ", ".join(f"{d.name} ({_pct(d.maturity_pct)})" for d in weakest) +
            " — are those where the Act imposes obligations that have no close analogue in the "
            "entity's existing regulatory obligations. The pattern indicates a programme that "
            "has inherited controls rather than one that has been designed against this statute.",
       align="justify")

    _h(doc, "1.2  Results at a glance", 2)
    sc = results.status_counts()
    t = _table(doc, 4, [4.4, 3.1, 4.4, 3.1])
    rows = [
        ("Controls in scope", results.in_scope_count, "Gaps identified", len(results.gaps)),
        ("Controls assessed", results.assessed_count, "— critical severity", sev["critical"]),
        ("Out of scope", results.out_of_scope_count, "— high severity", sev["high"]),
        ("Not applicable", results.na_count, "— medium severity", sev["medium"]),
        ("Compliant", sc.get("Compliant", 0), "— low severity", sev["low"]),
        ("Substantially compliant", sc.get("Substantially compliant", 0),
         "P1 actions (30 days)", len(p1)),
        ("Partially compliant", sc.get("Partially compliant", 0),
         "Schedule entries engaged", len(pe["entries"])),
        ("Non-compliant", sc.get("Non-compliant", 0),
         "Exposure ceiling", f"INR {pe['aggregate_max_inr_crore']:,g} crore"),
    ]
    for a1, b1, c1, d1 in rows:
        r = _row(t, [a1, b1, c1, d1], size=9.5)
        _cell(r.cells[0], a1, size=9.5, fill=F_SUB)
        _cell(r.cells[1], b1, size=9.5, bold=True, align="center")
        _cell(r.cells[2], c1, size=9.5, fill=F_SUB)
        _cell(r.cells[3], d1, size=9.5, bold=True, align="center")

    _h(doc, "1.3  Maturity by domain", 2)
    t = _table(doc, 6, [1.2, 6.0, 1.4, 1.9, 2.1, 2.4],
               ["", "Domain", "Weight", "Maturity", "Band", "Gaps / in scope"])
    for d in results.domains:
        r = _row(t, [d.code, d.name, f"{d.weight:g}", _pct(d.maturity_pct), d.band,
                     f"{len(d.gaps)} of {len(d.in_scope_results)}"])
        _cell(r.cells[0], d.code, bold=True, size=9, align="center", fill=F_SUB)
        _cell(r.cells[2], f"{d.weight:g}", size=9, align="center")
        fill = F_0 if (d.maturity_pct or 0) < 40 else (F_2 if (d.maturity_pct or 0) < 60 else F_3)
        _cell(r.cells[3], _pct(d.maturity_pct), bold=True, size=9, align="center", fill=fill)
        _cell(r.cells[4], d.band, size=9, align="center")
        _cell(r.cells[5], f"{len(d.gaps)} of {len(d.in_scope_results)}", size=9, align="center")
    r = _row(t, ["", "Overall (domain-weighted)", "", _pct(results.overall_maturity_pct),
                 results.overall_band[0], str(len(results.gaps))])
    for i in range(6):
        _cell(r.cells[i], r.cells[i].text, bold=True, size=9, fill=F_SUB,
              align="center" if i != 1 else None)

    _p(doc, "The overall figure is a weighted average of domain maturity, not a flat average of "
            "control scores. Weighting at domain level prevents a domain with many controls from "
            "mechanically dominating one with fewer but weightier obligations.",
       size=9, italic=True, color=SLATE, before=4)

    _h(doc, "1.4  Most significant findings", 2)
    _p(doc, "Ranked by residual risk, being the severity of the obligation multiplied by the "
            "shortfall against it. Each is detailed in section 4 and carries a gap reference in "
            "section 5.", after=8)
    t = _table(doc, 6, [1.5, 1.7, 5.9, 1.5, 1.8, 2.6],
               ["Gap", "Control", "Finding", "Risk", "Priority", "Owner"])
    for g in gaps[:10]:
        short = _abridge(g.finding, 230)
        r = _row(t, [g.ref, g.control_id, short, g.risk, g.priority, g.owner.split(",")[0]])
        _cell(r.cells[0], g.ref, bold=True, size=9, align="center")
        _cell(r.cells[1], g.control_id, size=9, align="center")
        _cell(r.cells[2], short, size=8.5, font=BODY_FONT)
        _cell(r.cells[3], g.risk, bold=True, size=9, align="center",
              fill=SEV_FILL.get(g.risk_band, F_NA))
        _cell(r.cells[4], g.priority, size=9, align="center", bold=True)
        _cell(r.cells[5], g.owner.split(",")[0], size=8.5)

    _h(doc, "1.5  Penalty exposure", 2)
    _p(doc, pe["basis"], align="justify")
    t = _table(doc, 5, [1.9, 5.2, 2.1, 2.6, 3.2],
               ["Entry", "Breach", "Provision", "Maximum", "Controls engaging it"])
    for e in pe["entries"]:
        ctrls = _id_list(e["controls"], 14)
        r = _row(t, [f"Entry {e['entry']}", e["breach"], e["provision"], e["label"], ctrls])
        _cell(r.cells[0], f"Entry {e['entry']}", size=9, align="center", bold=True)
        _cell(r.cells[1], e["breach"], size=8.5, font=BODY_FONT)
        _cell(r.cells[2], e["provision"], size=9, align="center")
        _cell(r.cells[3], e["label"], size=9, bold=True, align="center", fill=F_0)
        _cell(r.cells[4], ctrls, size=8, font=BODY_FONT)
    r = _row(t, ["", "Aggregate ceiling of the entries engaged", "",
                 f"INR {pe['aggregate_max_inr_crore']:,g} crore", ""])
    for i in range(5):
        _cell(r.cells[i], r.cells[i].text, bold=True, size=9, fill=F_SUB,
              align="center" if i in (0, 2, 3) else None)
        if i == 3:
            _cell(r.cells[i], f"INR {pe['aggregate_max_inr_crore']:,g} crore", bold=True,
                  size=9.5, fill=F_SUB, color=RED, align="center")

    _p(doc, pe["caveat"], size=9, italic=True, color=SLATE, before=6, align="justify")

    _h(doc, "1.6  Immediate priorities", 2)
    _p(doc, f"{len(p1)} findings are rated P1 and carry a 30-day remediation target. The "
            f"following actions should be commissioned before the remainder of the plan is "
            f"sequenced, because each either sits behind several other findings or engages one "
            f"of the higher penalty entries in the Schedule.", align="justify")
    _bullets(doc, [f"{g.ref} · {g.control_id} — {g.title}. {g.target_state}"
                   for g in p1[:8]], size=10)
    if len(p1) > 8:
        _p(doc, f"A further {len(p1) - 8} P1 items are listed in section 6.",
           size=9, italic=True, color=SLATE)


def _scope(doc, results: Results) -> None:
    a = results.assessment
    prof = a.profile
    _h(doc, "2.  Scope, approach and basis of assessment", 1)

    _h(doc, "2.1  Objective and scope", 2)
    _p(doc, a.scope_statement or "—", align="justify")

    _h(doc, "2.2  The entity", 2)
    _p(doc, prof.business_description, align="justify")
    t = _table(doc, 2, [5.0, 10.0])
    for k, v in [("Legal name", prof.legal_name), ("Trading name", prof.trading_name),
                 ("Sector", prof.sector), ("Registered office", prof.registered_office),
                 ("Headcount", f"{prof.headcount:,}" if prof.headcount else "—"),
                 ("Data Principals (approx.)",
                  f"{prof.data_principal_count:,}" if prof.data_principal_count else "—")]:
        r = _row(t, [k, v], size=9.5)
        _cell(r.cells[0], k, bold=True, size=9.5, fill=F_SUB)
        _cell(r.cells[1], v, size=9.5, font=BODY_FONT)

    if prof.entities_in_scope:
        _h(doc, "2.3  Entities within scope", 2)
        _bullets(doc, prof.entities_in_scope, size=10)
    if prof.systems_in_scope:
        _h(doc, "2.4  Systems and processing environments examined", 2)
        _bullets(doc, prof.systems_in_scope, size=10)
    if prof.exclusions:
        _h(doc, "2.5  Exclusions from scope", 2)
        _p(doc, "The following were excluded. Each exclusion narrows the conclusions that can be "
                "drawn from this report and is recorded so that the reader can judge that effect.",
           after=6, align="justify")
        _bullets(doc, prof.exclusions, size=10)

    _h(doc, "2.6  Approach", 2)
    _p(doc, "Each control was assessed by inspection of documentation, walkthrough with the "
            "control owner, and — where the control is capable of substantive test — direct "
            "examination of system behaviour or records. A control was scored on the position "
            "that could be evidenced, not on the intent expressed or the work in progress.",
       align="justify")

    _h(doc, "2.7  Scoring model", 2)
    _p(doc, "Each in-scope control was scored against a five-point anchored scale. The library "
            "defines the descriptors at 0, 2 and 4 for every control; 1 and 3 are intermediate "
            "positions between the adjacent anchors.", after=6, align="justify")
    t = _table(doc, 2, [2.6, 12.4], ["Score", "Meaning"])
    for k, v in SCORE_LABELS.items():
        r = _row(t, [k, v])
        _cell(r.cells[0], k, bold=True, size=11, align="center", fill=_score_fill(k))
        _cell(r.cells[1], v, size=9.5, font=BODY_FONT)
    _p(doc, f"A control scoring below {SUBSTANTIALLY_COMPLIANT} is reported as a gap. Controls "
            f"marked not applicable are removed from the denominator rather than scored zero, "
            f"since scoring an inapplicable obligation zero would understate maturity and "
            f"create a gap that cannot be remediated.", size=9.5, before=4, align="justify")

    _p(doc, "Maturity and risk are computed as follows.", before=6, after=4)
    t = _table(doc, 2, [5.4, 9.6])
    for k, v in [
        ("Control maturity", "score ÷ 4"),
        ("Domain maturity", "Σ(score × control weight) ÷ Σ(4 × control weight)"),
        ("Overall maturity", "Σ(domain maturity × domain weight) ÷ Σ(domain weight)"),
        ("Residual risk", "severity rank × (4 − score), range 0 to 16"),
        ("Severity ranks", "critical 4 · high 3 · medium 2 · low 1"),
        ("Risk bands", "12–16 Critical · 8–11 High · 4–7 Medium · 1–3 Low"),
    ]:
        r = _row(t, [k, v], size=9.5)
        _cell(r.cells[0], k, bold=True, size=9.5, fill=F_SUB)
        _cell(r.cells[1], v, size=9.5)

    _p(doc, "Priority and remediation targets follow directly from residual risk:", before=6,
       after=4)
    t = _table(doc, 3, [2.4, 3.4, 9.2], ["Priority", "Risk score", "Target"])
    for code, threshold, days, desc in PRIORITY_RULES:
        r = _row(t, [code, f"{threshold} and above" if threshold else "below 4",
                     f"{desc} ({days} days)"])
        _cell(r.cells[0], code, bold=True, size=9.5, align="center")
        _cell(r.cells[1], r.cells[1].text, size=9.5, align="center")
        _cell(r.cells[2], f"{desc} ({days} days)", size=9.5, font=BODY_FONT)

    _h(doc, "2.8  Citations and statutory references", 2)
    _p(doc, "Every control cites the provision of the Digital Personal Data Protection Act, 2023 "
            "that gives rise to the obligation. Where the operative detail of an obligation is "
            "left to the DPDP Rules, the control also carries a Rules reference.", align="justify")
    n = len(results.library.unverified_slots())
    if n:
        _p(doc, f"{n} of those Rules references could not be verified against the notified text "
                f"at the time of writing and appear throughout as “[Rules citation to be "
                f"verified]”. They are deliberately left blank rather than reconstructed from "
                f"recollection: a plausible but wrong statutory citation in a signed report "
                f"survives review and reaches the regulator, whereas a visibly blank one does "
                f"not. The subject matter of each is set out in Appendix A, and the finding and "
                f"the Act-level obligation in each case stand independently of the Rules "
                f"reference.", align="justify")


def _applicability(doc, results: Results) -> None:
    _h(doc, "3.  Applicability determination", 1)
    prof = results.assessment.profile
    _p(doc, "Scope was determined by applying the entity's characteristics to the control "
            "library. Each control declares the characteristics it requires and those that "
            "exclude it, so the composition of this audit is reproducible from the flags below.",
       align="justify")

    t = _table(doc, 3, [5.6, 1.9, 7.5], ["Characteristic", "Applies", "Basis and consequence"])
    from .core import PROFILE_FLAGS
    eff = prof.effective_flags()
    for name, (_d, desc) in PROFILE_FLAGS.items():
        yes = eff[name]
        r = _row(t, [name.replace("_", " "), "Yes" if yes else "No", desc])
        _cell(r.cells[0], name.replace("_", " "), size=9, bold=True)
        _cell(r.cells[1], "Yes" if yes else "No", size=9, bold=True, align="center",
              fill=F_3 if yes else F_NA)
        _cell(r.cells[2], desc, size=8.5, font=BODY_FONT)

    oos = [r for r in results.all_results if not r.in_scope]
    _h(doc, "3.1  Controls excluded from scope", 2)
    if not oos:
        _p(doc, "No control was excluded. The full library was assessed.")
    else:
        _p(doc, f"{len(oos)} of {len(results.library.controls)} controls were excluded on the "
                f"basis of the characteristics above. Exclusions are stated so that a reader can "
                f"see what was not examined and why.", after=6, align="justify")
        t = _table(doc, 3, [2.2, 6.8, 6.0], ["Control", "Title", "Reason for exclusion"])
        for r0 in oos:
            r = _row(t, [r0.control.id, r0.control.title, r0.scope_reason.replace("_", " ")])
            _cell(r.cells[0], r0.control.id, bold=True, size=9, align="center")
            _cell(r.cells[1], r0.control.title, size=9, font=BODY_FONT)
            _cell(r.cells[2], r0.scope_reason.replace("_", " "), size=8.5, italic=True)

    if results.unassessed:
        _h(doc, "3.2  In-scope controls not assessed", 2)
        _p(doc, "The following in-scope controls were not assessed. This is a limitation on "
                "coverage rather than a finding; no conclusion should be drawn about them.",
           after=6, align="justify")
        t = _table(doc, 2, [2.6, 12.4], ["Control", "Title"])
        for r0 in results.unassessed:
            _row(t, [r0.control.id, r0.control.title])

    if results.assessment.scoping_assumptions:
        _h(doc, "3.3  Scoping assumptions", 2)
        _bullets(doc, results.assessment.scoping_assumptions, size=10)


def _findings(doc, results: Results, gaps: List) -> None:
    gap_by_control = {g.control_id: g for g in gaps}
    _h(doc, "4.  Detailed findings by obligation", 1)
    _p(doc, "Findings are presented in the order of the control library. Each control records the "
            "obligation, its statutory basis, what was tested, the score awarded, the finding, "
            "and — where a gap arises — the target state the control defines and the gap "
            "reference under which it is tracked in section 5.", align="justify")

    for d in results.domains:
        _h(doc, f"4.{d.order}  {d.code} — {d.name}", 2)
        _p(doc, d.why_it_matters, italic=True, size=10, color=SLATE, align="justify")
        _label_para(doc, "SCOPE QUESTION", d.scope_question)
        summary = (f"Domain maturity {_pct(d.maturity_pct)} ({d.band}). "
                   f"{len(d.in_scope_results)} controls in scope, {len(d.scored)} assessed, "
                   f"{len(d.gaps)} gaps of which {d.critical_gap_count} attach to critical "
                   f"obligations. Highest residual risk in the domain is {d.max_risk} of 16.")
        _label_para(doc, "RESULT", summary)
        _rule(doc, before=2, after=6)

        for res in d.results:
            c = res.control
            _h(doc, f"{c.id}   {c.title}", 3, after=4)

            t = _table(doc, 7, [1.6, 4.0, 1.7, 1.8, 1.8, 1.5, 3.2])
            r = _blank_row(t)
            hdrs = ["Score", "Status", "Risk", "Risk band", "Severity", "Weight",
                    "Evidence ref"]
            for i, h in enumerate(hdrs):
                _cell(r.cells[i], h, bold=True, size=7.5, fill=F_HEAD,
                      color=RGBColor(0xFF, 0xFF, 0xFF), align="center")
            vals = [
                ("NA" if res.not_applicable
                 else ("—" if res.score is None else f"{res.score} of 4")),
                res.status_label,
                ("—" if res.risk is None else f"{res.risk} of 16"),
                res.risk_band if res.assessed else "—",
                c.severity.capitalize(), f"{c.weight:g}",
                res.evidence_ref or "—",
            ]
            r2 = _blank_row(t)
            for i, v in enumerate(vals):
                _cell(r2.cells[i], v, size=9, align="center", bold=(i in (0, 1, 2)))
            _shade(r2.cells[0], _score_fill(res.score, res.in_scope and not res.not_applicable))
            if res.assessed and res.risk is not None:
                _shade(r2.cells[2], SEV_FILL.get(res.risk_band, F_NA))

            _p(doc, after=2)
            _label_para(doc, "OBLIGATION", c.obligation)
            cite = f"{c.act_ref}"
            if res.rule_citation and res.rule_citation != "—":
                cite += f"  ·  Rules: {res.rule_citation}"
            if res.penalty:
                cite += f"  ·  Penalty: {res.penalty['label']} (Schedule entry {res.penalty['entry']})"
            _label_para(doc, "STATUTORY BASIS", cite)
            _label_para(doc, "TESTED BY", c.test_procedure)

            if not res.in_scope:
                _label_para(doc, "SCOPE", f"Out of scope — {res.scope_reason.replace('_', ' ')}. "
                                          f"Not assessed and excluded from all scoring.")
                _rule(doc, before=4, after=6)
                continue
            if res.not_applicable:
                _label_para(doc, "APPLICABILITY", "Marked not applicable. Excluded from the "
                                                  "maturity denominator.")
            if res.finding:
                _label_para(doc, "FINDING", res.finding)
            elif res.assessed:
                _label_para(doc, "FINDING", "(no finding recorded)")
            else:
                _label_para(doc, "FINDING", "Not assessed. No conclusion is drawn.")
            if c.note:
                _label_para(doc, "NOTE", c.note)
            g = gap_by_control.get(c.id)
            if g:
                _label_para(doc, "TARGET STATE", c.target_state)
                _label_para(doc, "TRACKED AS",
                            f"{g.ref} · priority {g.priority} · target date {g.due_date} · "
                            f"owner {g.owner}")
            _rule(doc, before=4, after=6)


def _gap_register(doc, results: Results, gaps: List) -> None:
    """Landscape section — the register is too wide to be legible in portrait."""
    sec = doc.add_section(WD_SECTION.NEW_PAGE)
    w, h = sec.page_width, sec.page_height
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = h, w
    sec.left_margin = sec.right_margin = Cm(1.6)
    sec.top_margin = sec.bottom_margin = Cm(1.8)
    _footer(sec, results.assessment.profile.legal_name)

    _h(doc, "5.  Gap register", 1)
    _p(doc, f"{len(gaps)} gaps, ordered by residual risk. Target dates are derived from the "
            f"priority band and run from the assessment date "
            f"({results.assessment.assessment_date}) unless a date was agreed with the control "
            f"owner during fieldwork. The target state in each case is the level-4 descriptor "
            f"the control library defines, so remediation is measured against the same standard "
            f"the control was scored against. Findings are abridged to fit this register; the "
            f"finding as recorded is set out against the control in section 4.", align="justify")

    widths = [1.4, 1.6, 3.2, 5.6, 1.4, 1.2, 1.5, 1.6, 2.2, 3.4]
    t = _table(doc, 10, widths,
               ["Ref", "Control", "Domain", "Finding", "Sev", "Risk", "Priority",
                "Target date", "Statutory basis", "Owner"], size=8)
    for g in gaps:
        # 440 characters is roughly the height of the tallest cell already in the
        # row; at this budget 54 of the 60 sample findings appear in full.
        fin = _abridge(g.finding, 440)
        r = _row(t, [g.ref, g.control_id, g.domain_name, fin, g.severity, g.risk,
                     g.priority, g.due_date, g.act_ref, g.owner], size=8)
        _cell(r.cells[0], g.ref, bold=True, size=8, align="center")
        _cell(r.cells[1], g.control_id, size=8, align="center")
        _cell(r.cells[2], g.domain_name, size=7.5)
        _cell(r.cells[3], fin, size=7.5, font=BODY_FONT)
        _cell(r.cells[4], g.severity, size=7.5, align="center",
              fill=SEV_FILL.get(g.severity, F_NA))
        _cell(r.cells[5], g.risk, bold=True, size=8.5, align="center",
              fill=SEV_FILL.get(g.risk_band, F_NA))
        _cell(r.cells[6], g.priority, bold=True, size=8, align="center")
        _cell(r.cells[7], g.due_date, size=7.5, align="center")
        _cell(r.cells[8], g.act_ref, size=7, align="center")
        _cell(r.cells[9], g.owner, size=7)


def _roadmap(doc, results: Results, gaps: List) -> None:
    sec = doc.add_section(WD_SECTION.NEW_PAGE)
    w, h = sec.page_width, sec.page_height
    sec.orientation = WD_ORIENT.PORTRAIT
    sec.page_width, sec.page_height = h, w
    sec.left_margin = sec.right_margin = Cm(2.2)
    sec.top_margin = sec.bottom_margin = Cm(2.0)
    _footer(sec, results.assessment.profile.legal_name)

    _h(doc, "6.  Remediation roadmap", 1)
    _p(doc, "Actions are grouped by priority band. Within a band, items are ordered by residual "
            "risk. The roadmap is expressed as target states rather than implementation designs: "
            "how each is achieved is a matter for the owner, but the standard to be reached is "
            "fixed by the control.", align="justify")

    _p(doc, "Sequencing note: several findings sit behind others. Retention and erasure "
            "(RET), rights fulfilment (RGT) and consent withdrawal (CON) all depend on the same "
            "underlying capability — the ability to locate every copy of a Data Principal's data "
            "and act on it. Commissioning that capability once will close a disproportionate "
            "share of the register, and it should be scheduled ahead of items that merely "
            "document existing practice.", before=4, align="justify")

    for code, threshold, days, desc in PRIORITY_RULES:
        band_gaps = [g for g in gaps if g.priority == code]
        if not band_gaps:
            continue
        _h(doc, f"6.{code[-1]}  {code} — {desc}", 2)
        _p(doc, f"{len(band_gaps)} items. Residual risk "
                f"{min(g.risk for g in band_gaps)} to {max(g.risk for g in band_gaps)} of 16.",
           size=9.5, italic=True, color=SLATE, after=6)
        t = _table(doc, 5, [1.4, 1.7, 7.4, 2.1, 2.4],
                   ["Ref", "Control", "Required target state", "Target date", "Owner"])
        for g in band_gaps:
            r = _row(t, [g.ref, g.control_id, g.target_state, g.due_date, g.owner])
            _cell(r.cells[0], g.ref, bold=True, size=8.5, align="center")
            _cell(r.cells[1], g.control_id, size=8.5, align="center")
            _cell(r.cells[2], g.target_state, size=8.5, font=BODY_FONT)
            _cell(r.cells[3], g.due_date, size=8.5, align="center")
            _cell(r.cells[4], g.owner, size=8)


def _closing(doc, results: Results) -> None:
    a = results.assessment
    _h(doc, "7.  Basis, limitations and responsibilities", 1)
    _h(doc, "7.1  Limitations", 2)
    _bullets(doc, a.limitations, size=10)
    _h(doc, "7.2  Responsibilities", 2)
    _p(doc, "Compliance with the Digital Personal Data Protection Act, 2023 is the "
            "responsibility of the Data Fiduciary. The Act places accountability on the entity "
            "for processing carried out on its behalf, including by processors, and that "
            "accountability is not transferred by this assessment or by any contract with a "
            "service provider. Our responsibility was limited to performing the procedures "
            "described in section 2 and reporting the findings in sections 4 to 6.",
       align="justify")
    _p(doc, "This report does not constitute legal advice. Where a finding turns on the "
            "construction of a provision, or on whether particular processing falls within a "
            "legitimate use, the position should be confirmed with qualified counsel before "
            "action is taken or a position is asserted to a regulator.", align="justify")

    _h(doc, "7.3  Sign-off", 2)
    _p(doc, "The findings in this report have been discussed with the control owners named in "
            "section 5 and with management. Management's responses, where they differ from the "
            "findings recorded here, are appended separately.", after=16, align="justify")

    t = _table(doc, 2, [7.5, 7.5], ["Prepared by", "Accepted by"])
    r = _row(t, ["", ""])
    for i, (name, role) in enumerate([(a.auditor_name, a.auditor_firm),
                                      ("", "For and on behalf of the entity")]):
        cell = r.cells[i]
        cell.text = ""
        for label, val, gap_before in [("Signature", "", 26), ("Name", name, 10),
                                       ("Position / firm", role, 10), ("Date", "", 10)]:
            p = cell.add_paragraph()
            p.paragraph_format.space_before = Pt(gap_before)
            p.paragraph_format.space_after = Pt(0)
            run = p.add_run(f"{label}: ")
            run.font.name = HEAD_FONT
            run.font.size = Pt(8.5)
            run.bold = True
            run.font.color.rgb = SLATE
            run2 = p.add_run(val or "  " + "_" * 34)
            run2.font.name = BODY_FONT
            run2.font.size = Pt(9.5)
        if cell.paragraphs and not cell.paragraphs[0].runs:
            cell.paragraphs[0]._p.getparent().remove(cell.paragraphs[0]._p)


def _appendices(doc, results: Results) -> None:
    lib = results.library
    _h(doc, "Appendix A — Rules citations awaiting verification", 1)
    slots = lib.unverified_slots()
    if not slots:
        _p(doc, "All Rules citations in this report have been verified against the notified text.")
    else:
        _p(doc, f"{len(slots)} Rules references in the control library could not be verified "
                f"against the notified text when this report was prepared. Each is listed below "
                f"with the subject matter it addresses, the provision of the Act it sits under, "
                f"and the controls that rely on it.", align="justify")
        _p(doc, "The finding recorded against each affected control rests on the obligation in "
                "the Act, which is cited and verified. The outstanding item is the specific rule "
                "number and its operative detail — a period, a form, a threshold. Two "
                "consequences follow. Where a Rule prescribes a period, this report does not "
                "assert what that period is; and where a Rule may narrow or expand an "
                "obligation, the finding should be re-read once the citation is confirmed. "
                "Populating each citation in controls/citations.yaml updates every deliverable, "
                "this appendix included.", size=10, align="justify")
        t = _table(doc, 4, [3.9, 5.4, 2.3, 3.4],
                   ["Slot", "Subject matter the Rules address", "Act anchor", "Controls relying"])
        for s in slots:
            raw = lib.citations["rule_slots"][s["key"]]
            r = _row(t, [s["key"], s["subject"], raw.get("anchors_act", "—"),
                         ", ".join(s["controls"]) or "—"])
            _cell(r.cells[0], _softbreak(s["key"]), bold=True, size=8)
            _cell(r.cells[1], s["subject"], size=8.5, font=BODY_FONT)
            _cell(r.cells[2], raw.get("anchors_act", "—"), size=8, align="center")
            _cell(r.cells[3], ", ".join(s["controls"]) or "—", size=8)
        srcs = lib.citations["meta"].get("primary_sources_to_check") or []
        if srcs:
            _p(doc, "Primary sources against which these should be verified:", before=8, after=4,
               bold=True, size=9.5)
            _bullets(doc, srcs, size=9.5)

    _h(doc, "Appendix B — Penalty Schedule reference", 1)
    ps = lib.citations["penalty_schedule"]
    _p(doc, "Section 33 read with the Schedule to the Act. Reproduced so that the exposure "
            "figures in section 1.5 can be traced to their basis.", align="justify")
    t = _table(doc, 4, [1.9, 6.4, 2.4, 4.3],
               ["Entry", "Breach", "Provision", "Maximum penalty"])
    for e in ps["entries"]:
        r = _row(t, [f"Entry {e['entry']}", e["breach"], e["provision"], e["label"]])
        _cell(r.cells[0], f"Entry {e['entry']}", bold=True, size=9, align="center")
        _cell(r.cells[1], e["breach"], size=8.5, font=BODY_FONT)
        _cell(r.cells[2], e["provision"], size=9, align="center")
        _cell(r.cells[3], e["label"], size=9, bold=True)
    note = ps.get("determination_factors_note")
    if note:
        _p(doc, note, size=9, italic=True, color=SLATE, before=6, align="justify")

    _h(doc, "Appendix C — Control inventory and scores", 1)
    _p(doc, f"All {len(lib.controls)} controls in library v{lib.version}, with the score awarded. "
            f"Provided so that the reader can see the whole population, including the controls "
            f"that raised no finding.", align="justify")
    t = _table(doc, 6, [1.9, 5.5, 1.9, 1.3, 2.3, 1.4],
               ["Control", "Title", "Sev", "Score", "Status", "Risk"])
    for d in results.domains:
        r = _blank_row(t)
        # The domain banner spans the ID and title columns: the code and name do
        # not fit in the ID column alone and would otherwise wrap to four lines,
        # leaving a tall band of empty cells across the rest of the row. The
        # result spans Status and Risk for the same reason — the band names
        # ("Optimised", "Developing") do not fit the numeric Risk column.
        _cell(r.cells[0].merge(r.cells[1]), f"{d.code} — {d.name}",
              bold=True, size=9, fill=F_SUB)
        for i in (2, 3):
            _cell(r.cells[i], "", fill=F_SUB)
        band = "—" if d.maturity_pct is None else f"{_pct(d.maturity_pct)} — {d.band}"
        _cell(r.cells[4].merge(r.cells[5]), band,
              bold=True, size=9, fill=F_SUB, align="center")
        for res in d.results:
            score = ("NA" if res.not_applicable
                     else ("—" if res.score is None else res.score))
            sev = res.control.severity.capitalize()
            rr = _row(t, [res.control.id, res.control.title, sev,
                          score, res.status_label,
                          "—" if res.risk is None else res.risk])
            _cell(rr.cells[0], res.control.id, size=8.5, align="center")
            _cell(rr.cells[1], res.control.title, size=8.5, font=BODY_FONT)
            _cell(rr.cells[2], sev, size=8, align="center")
            _cell(rr.cells[3], score, bold=True, size=9, align="center",
                  fill=_score_fill(res.score, res.in_scope and not res.not_applicable))
            _cell(rr.cells[4], res.status_label, size=8, align="center")
            _cell(rr.cells[5], "—" if res.risk is None else res.risk, size=8.5, align="center")


# ---------------------------------------------------------------- entry point
def build_report(results: Results, path: str) -> str:
    """Write the formal Word audit report. Returns the path written."""
    doc = Document()

    st = doc.styles["Normal"]
    st.font.name = BODY_FONT
    st.font.size = Pt(10.5)
    st.paragraph_format.space_after = Pt(6)
    rpr = st.element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.append(rf)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rf.set(qn(attr), BODY_FONT)

    sec = doc.sections[0]
    sec.left_margin = sec.right_margin = Cm(2.2)
    sec.top_margin = sec.bottom_margin = Cm(2.0)
    _footer(sec, results.assessment.profile.legal_name)

    gaps = build_gap_register(results)

    _title_page(doc, results)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    _doc_control(doc, results)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    _exec_summary(doc, results, gaps)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    _scope(doc, results)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    _applicability(doc, results)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    _findings(doc, results, gaps)
    _gap_register(doc, results, gaps)      # landscape section
    _roadmap(doc, results, gaps)           # back to portrait
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    _closing(doc, results)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    _appendices(doc, results)

    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    doc.save(path)
    return path
