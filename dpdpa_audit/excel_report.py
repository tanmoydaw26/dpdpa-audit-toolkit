"""
DPDPA Audit Toolkit — Excel control matrix workbook.

Produces a live working model, not a static export. The Score column is the only
scoring input; risk, status, gap flags, domain maturity, the overall score and
the penalty-exposure table are all Excel formulas that recalculate when a score
is changed. An audit team can therefore take the workbook, rescore a control and
see the dashboard move without returning to the toolkit.

Sheets
    Instructions   — legend, scoring scale, which cells to edit
    Company Profile— scope inputs and applicability flags
    Control Matrix — one row per control; the live model
    Dashboard      — domain maturity, status counts, penalty exposure
    Evidence Log   — workpaper register with one example row
    Citations      — Act references and Rules-slot verification status

Formula constraints: only Excel-2007-era functions are used (IF, AND, OR, SUM,
SUMIFS, COUNTIFS, ROUND, UPPER) so that LibreOffice recalculation matches Excel.
No array or spilling functions.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from .core import PROFILE_FLAGS, SCORE_LABELS
from .scoring import Results, SUBSTANTIALLY_COMPLIANT

FONT = "Arial"

# palette
NAVY = "1F3552"
SLATE = "44546A"
LIGHT = "EEF2F7"
YELLOW = "FFF2CC"      # cells the user should fill in
GREY = "F2F2F2"
BORDER = "BFBFBF"
RED = "C00000"
AMBER = "BF8F00"
GREEN = "375623"

H_FILL = PatternFill("solid", fgColor=NAVY)
SUB_FILL = PatternFill("solid", fgColor=LIGHT)
IN_FILL = PatternFill("solid", fgColor=YELLOW)
GREY_FILL = PatternFill("solid", fgColor=GREY)

THIN = Side(style="thin", color=BORDER)
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

H_FONT = Font(name=FONT, size=9, bold=True, color="FFFFFF")
B_FONT = Font(name=FONT, size=9, bold=True)
N_FONT = Font(name=FONT, size=9)
S_FONT = Font(name=FONT, size=8, color=SLATE)
TITLE_FONT = Font(name=FONT, size=16, bold=True, color=NAVY)
H2_FONT = Font(name=FONT, size=11, bold=True, color=NAVY)

WRAP = Alignment(wrap_text=True, vertical="top")
WRAP_C = Alignment(wrap_text=True, vertical="center", horizontal="center")
CENTER = Alignment(vertical="center", horizontal="center")

# Control Matrix column map -------------------------------------------------
COLS: List[tuple] = [
    ("A", "Control ID", 11),
    ("B", "Domain", 9),
    ("C", "Domain name", 30),
    ("D", "Control title", 44),
    ("E", "Severity", 11),
    ("F", "Sev rank", 9),
    ("G", "Weight", 8),
    ("H", "In scope", 9),
    ("I", "Scope reason", 26),
    ("J", "Act reference", 26),
    ("K", "Rules reference", 26),
    ("L", "Rules status", 30),
    ("M", "Score (0-4 / NA)", 13),
    ("N", "Scored", 8),
    ("O", "Status", 22),
    ("P", "Risk", 7),
    ("Q", "Risk band", 12),
    ("R", "Gap", 6),
    ("S", "Contribution", 11),
    ("T", "Max contribution", 13),
    ("U", "Finding", 52),
    ("V", "Evidence ref", 18),
    ("W", "Owner", 18),
    ("X", "Target date", 13),
    ("Y", "Obligation", 60),
    ("Z", "Audit question", 60),
    ("AA", "Test procedure", 50),
    ("AB", "Evidence expected", 50),
    ("AC", "Penalty exposure", 26),
    ("AD", "Penalty entry", 11),
    ("AE", "Required target state (level 4)", 70),
]
INPUT_COLS = {"M", "U", "V", "W", "X"}
MATRIX = "Control Matrix"
FIRST_ROW = 2


def _hdr(ws, row: int, cols: List[tuple]) -> None:
    for letter, label, width in cols:
        ws.column_dimensions[letter].width = width
        c = ws[f"{letter}{row}"]
        c.value = label
        c.font = H_FONT
        c.fill = H_FILL
        c.alignment = WRAP_C
        c.border = BOX
    ws.row_dimensions[row].height = 30


def _write_instructions(wb: Workbook, results: Results) -> None:
    ws = wb.create_sheet("Instructions")
    ws.sheet_view.showGridLines = False
    for letter, width in (("A", 3), ("B", 30), ("C", 100)):
        ws.column_dimensions[letter].width = width

    ws["B2"] = "DPDPA Compliance Audit — Control Matrix Workbook"
    ws["B2"].font = TITLE_FONT
    ws["B3"] = (f"Digital Personal Data Protection Act, 2023 · control library v"
                f"{results.library.version} · {len(results.library.controls)} controls "
                f"across {len(results.library.domains)} domains")
    ws["B3"].font = S_FONT

    rows = [
        ("", ""),
        ("HOW TO USE THIS WORKBOOK", ""),
        ("Live model", "This is a working model, not a static export. The Score column on the "
                       "Control Matrix is the only scoring input. Risk, status, gap flags, "
                       "domain maturity, the overall score and the penalty-exposure table are "
                       "formulas and update as soon as a score changes."),
        ("Cells to edit",
         "Yellow cells only. On the Control Matrix these are Score (M), Finding (U), Evidence "
         "ref (V), Owner (W) and Target date (X). On Company Profile they are the value column. "
         "Every other cell is either reference text from the control library or a formula — "
         "overwriting a formula will break the dashboard."),
        ("Scoring scale",
         "The library defines anchored descriptors for 0, 2 and 4; 1 and 3 are intermediate "
         "positions. Score the position you can evidence, not the intent. " +
         " · ".join(f"{k} = {v}" for k, v in SCORE_LABELS.items())),
        ("Not applicable",
         "Enter NA where a control genuinely cannot apply. NA removes the control from the "
         "denominator. Do not score an inapplicable control 0 — that understates maturity and "
         "manufactures a gap that cannot be remediated."),
        ("Out of scope",
         "Controls shown as In scope = No were excluded automatically by the applicability "
         "flags on the Company Profile sheet, with the reason given in column I. Change a flag "
         "and regenerate from the toolkit to bring them into scope."),
        ("Gap threshold",
         f"A control scoring below {SUBSTANTIALLY_COMPLIANT} of 4 is reported as a gap. "
         f"{SUBSTANTIALLY_COMPLIANT} is the 'substantially in place, minor gaps' anchor, so "
         "the register captures every control where the obligation could not be concluded met."),
        ("Risk score",
         "Risk = severity rank × (4 − score), range 0 to 16. Severity ranks are critical 4, "
         "high 3, medium 2, low 1. Risk therefore reflects both the seriousness of the "
         "obligation and how far short the entity falls. Bands: 12+ Critical, 8-11 High, "
         "4-7 Medium, 1-3 Low."),
        ("", ""),
        ("CITATIONS — READ THIS", ""),
        ("Act references",
         "Column J cites the DPDP Act, 2023. These are stated with confidence."),
        ("Rules references",
         "Column K shows '[Rules citation to be verified]' wherever the rule number was not "
         "available when the library was authored. This is deliberate: a wrong statutory "
         "citation in a signed report passes review and reaches the regulator, whereas a blank "
         "one does not. Populate controls/citations.yaml once and every output updates. "
         "The Citations sheet lists each outstanding slot."),
        ("Commencement",
         "The commencement position of individual provisions was not confirmed. Findings are "
         "compliance gaps against the framework as a whole; do not characterise a gap as a "
         "contravention of a provision without first confirming that it is in force."),
        ("", ""),
        ("PENALTY EXPOSURE", ""),
        ("What it shows",
         "The Dashboard aggregates the statutory maxima under the Schedule to the Act for those "
         "entries engaged by controls currently scored below the gap threshold."),
        ("What it is not",
         "It is a ceiling, not a prediction. Section 33(2) requires the Board to have regard to "
         "gravity, duration, the data affected, proportionality and mitigating action. Any "
         "penalty actually imposed would be a fraction of the ceiling, and documented prompt "
         "remediation is an express mitigating factor."),
    ]
    r = 5
    for label, text in rows:
        if label and not text:
            ws[f"B{r}"] = label
            ws[f"B{r}"].font = H2_FONT
            ws[f"B{r}"].fill = SUB_FILL
            ws[f"C{r}"].fill = SUB_FILL
        else:
            ws[f"B{r}"] = label
            ws[f"B{r}"].font = B_FONT
            ws[f"B{r}"].alignment = WRAP
            ws[f"C{r}"] = text
            ws[f"C{r}"].font = N_FONT
            ws[f"C{r}"].alignment = WRAP
            if text:
                ws.row_dimensions[r].height = max(15, 13 * (len(text) // 95 + 1))
        r += 1

    ws[f"B{r+1}"] = "LEGEND"
    ws[f"B{r+1}"].font = H2_FONT
    ws[f"B{r+2}"] = "Yellow fill"
    ws[f"B{r+2}"].font = B_FONT
    ws[f"B{r+2}"].fill = IN_FILL
    ws[f"C{r+2}"] = "Input cell — edit this"
    ws[f"C{r+2}"].font = N_FONT
    ws[f"B{r+3}"] = "White / grey"
    ws[f"B{r+3}"].font = B_FONT
    ws[f"C{r+3}"] = "Reference text or formula — do not overwrite"
    ws[f"C{r+3}"].font = N_FONT


def _write_profile(wb: Workbook, results: Results) -> None:
    ws = wb.create_sheet("Company Profile")
    ws.sheet_view.showGridLines = False
    p = results.assessment.profile
    a = results.assessment
    for letter, width in (("A", 3), ("B", 34), ("C", 62), ("D", 70)):
        ws.column_dimensions[letter].width = width

    ws["B2"] = "Company Profile & Engagement Details"
    ws["B2"].font = TITLE_FONT
    ws["B3"] = "Yellow cells are inputs. Applicability flags determine which controls are in scope."
    ws["B3"].font = S_FONT

    def section(row: int, title: str) -> int:
        ws[f"B{row}"] = title
        ws[f"B{row}"].font = H2_FONT
        for col in "BCD":
            ws[f"{col}{row}"].fill = SUB_FILL
        return row + 1

    def kv(row: int, k: str, v: Any, note: str = "") -> int:
        ws[f"B{row}"] = k
        ws[f"B{row}"].font = B_FONT
        ws[f"B{row}"].alignment = WRAP
        c = ws[f"C{row}"]
        c.value = "" if v is None else v
        c.font = N_FONT
        c.fill = IN_FILL
        c.border = BOX
        c.alignment = WRAP
        if note:
            ws[f"D{row}"] = note
            ws[f"D{row}"].font = S_FONT
            ws[f"D{row}"].alignment = WRAP
            ws.row_dimensions[row].height = max(15, 12 * (len(note) // 68 + 1))
        return row + 1

    r = section(5, "ENTITY")
    r = kv(r, "Legal name", p.legal_name)
    r = kv(r, "Trading name", p.trading_name)
    r = kv(r, "Sector", p.sector)
    r = kv(r, "Registered office", p.registered_office)
    r = kv(r, "Headcount", p.headcount)
    r = kv(r, "Data Principals (approx.)", p.data_principal_count)
    r = kv(r, "Business description", p.business_description)

    r = section(r + 1, "ENGAGEMENT")
    r = kv(r, "Assessment date", a.assessment_date)
    r = kv(r, "Auditor", a.auditor_name)
    r = kv(r, "Firm", a.auditor_firm)
    r = kv(r, "Engagement reference", a.engagement_ref)
    r = kv(r, "Scope statement", a.scope_statement)

    r = section(r + 1, "APPLICABILITY FLAGS")
    ws[f"B{r}"] = "Flag"
    ws[f"C{r}"] = "Value"
    ws[f"D{r}"] = "Meaning"
    for col in "BCD":
        ws[f"{col}{r}"].font = H_FONT
        ws[f"{col}{r}"].fill = H_FILL
        ws[f"{col}{r}"].alignment = WRAP_C
    r += 1
    dv = DataValidation(type="list", formula1='"Yes,No"', allow_blank=False)
    ws.add_data_validation(dv)
    eff = p.effective_flags()
    for name, (_default, desc) in PROFILE_FLAGS.items():
        ws[f"B{r}"] = name
        ws[f"B{r}"].font = N_FONT
        c = ws[f"C{r}"]
        c.value = "Yes" if eff[name] else "No"
        c.font = B_FONT
        c.fill = IN_FILL
        c.border = BOX
        c.alignment = CENTER
        dv.add(c)
        ws[f"D{r}"] = desc
        ws[f"D{r}"].font = S_FONT
        ws[f"D{r}"].alignment = WRAP
        ws.row_dimensions[r].height = max(15, 12 * (len(desc) // 68 + 1))
        r += 1

    ws[f"B{r+1}"] = ("Note: changing a flag here does not re-filter the Control Matrix. "
                     "Update the profile in the toolkit and regenerate, so that scope changes "
                     "are recorded in the assessment file rather than only in the workbook.")
    ws[f"B{r+1}"].font = S_FONT
    ws[f"B{r+1}"].alignment = WRAP
    ws.merge_cells(f"B{r+1}:D{r+2}")


def _write_matrix(wb: Workbook, results: Results) -> int:
    ws = wb.create_sheet(MATRIX)
    _hdr(ws, 1, COLS)
    ws.freeze_panes = "E2"

    dv = DataValidation(type="list", formula1='"0,1,2,3,4,NA"', allow_blank=True,
                        showDropDown=False)
    dv.error = "Enter a whole number 0-4, or NA where the control cannot apply."
    dv.errorTitle = "Invalid score"
    ws.add_data_validation(dv)

    row = FIRST_ROW
    for d in results.domains:
        for res in d.results:
            c = res.control
            vals: Dict[str, Any] = {
                "A": c.id,
                "B": c.domain,
                "C": d.name,
                "D": c.title,
                "E": c.severity.capitalize(),
                "F": f"=IF(E{row}=\"Critical\",4,IF(E{row}=\"High\",3,IF(E{row}=\"Medium\",2,1)))",
                "G": c.weight,
                "H": "Yes" if res.in_scope else "No",
                "I": res.scope_reason,
                "J": res.act_ref,
                "K": res.rule_citation,
                "L": res.rule_status or "—",
                "M": ("" if res.score is None and not res.not_applicable
                      else ("NA" if res.not_applicable else res.score)),
                "N": f'=IF(OR(H{row}="No",M{row}="",UPPER(M{row})="NA"),0,1)',
                "O": (f'=IF(H{row}="No","Out of scope",'
                      f'IF(UPPER(M{row})="NA","Not applicable",'
                      f'IF(M{row}="","Not assessed",'
                      f'IF(M{row}>=4,"Compliant",'
                      f'IF(M{row}>={SUBSTANTIALLY_COMPLIANT},"Substantially compliant",'
                      f'IF(M{row}>=2,"Partially compliant","Non-compliant"))))))'),
                "P": f'=IF(N{row}=0,"",F{row}*(4-M{row}))',
                "Q": (f'=IF(P{row}="","",IF(P{row}>=12,"Critical",'
                      f'IF(P{row}>=8,"High",IF(P{row}>=4,"Medium",'
                      f'IF(P{row}>=1,"Low","None")))))'),
                "R": f'=IF(AND(N{row}=1,M{row}<{SUBSTANTIALLY_COMPLIANT}),1,0)',
                "S": f'=IF(N{row}=0,"",M{row}*G{row})',
                "T": f'=IF(N{row}=0,"",4*G{row})',
                "U": res.finding,
                "V": res.evidence_ref,
                "W": res.owner,
                "X": res.target_date,
                "Y": c.obligation,
                "Z": c.audit_question,
                "AA": c.test_procedure,
                "AB": " · ".join(c.evidence_expected),
                "AC": (res.penalty["label"] if res.penalty else "—"),
                "AD": (c.penalty_entry if c.penalty_entry is not None else ""),
                "AE": c.target_state,
            }
            for letter, _label, _w in COLS:
                cell = ws[f"{letter}{row}"]
                cell.value = vals[letter]
                cell.font = N_FONT
                cell.border = BOX
                cell.alignment = WRAP
                if letter in INPUT_COLS:
                    cell.fill = IN_FILL
                elif letter in ("F", "N", "O", "P", "Q", "R", "S", "T"):
                    cell.fill = GREY_FILL
                if letter in ("F", "G", "M", "N", "P", "R", "S", "T", "AD"):
                    cell.alignment = WRAP_C
            if not res.in_scope:
                for letter, _l, _w in COLS:
                    ws[f"{letter}{row}"].font = Font(name=FONT, size=9, color="808080",
                                                     italic=True)
            ws[f"M{row}"].font = Font(name=FONT, size=11, bold=True)
            dv.add(ws[f"M{row}"])
            ws.row_dimensions[row].height = 42
            row += 1

    last = row - 1
    ws.auto_filter.ref = f"A1:AE{last}"
    return last


def _write_dashboard(wb: Workbook, results: Results, last: int) -> None:
    ws = wb.create_sheet("Dashboard", 0)
    ws.sheet_view.showGridLines = False
    for letter, width in (("A", 3), ("B", 34), ("C", 13), ("D", 13), ("E", 13),
                          ("F", 13), ("G", 15), ("H", 15), ("I", 40)):
        ws.column_dimensions[letter].width = width

    M = f"'{MATRIX}'!"
    dom_r, sev_r, gap_r, con_r, max_r, sta_r, pen_r = (
        f"{M}$B${FIRST_ROW}:$B${last}", f"{M}$E${FIRST_ROW}:$E${last}",
        f"{M}$R${FIRST_ROW}:$R${last}", f"{M}$S${FIRST_ROW}:$S${last}",
        f"{M}$T${FIRST_ROW}:$T${last}", f"{M}$O${FIRST_ROW}:$O${last}",
        f"{M}$AD${FIRST_ROW}:$AD${last}",
    )

    ws["B2"] = "DPDPA Compliance Dashboard"
    ws["B2"].font = TITLE_FONT
    p = results.assessment.profile
    ws["B3"] = (f"{p.legal_name or '(entity)'} · assessed "
                f"{results.assessment.assessment_date} · all figures recalculate from the "
                f"Control Matrix")
    ws["B3"].font = S_FONT

    # -- headline -------------------------------------------------------
    ws["B5"] = "OVERALL MATURITY"
    ws["B5"].font = H2_FONT
    ws["B5"].fill = SUB_FILL
    for col in "CDEFGHI":
        ws[f"{col}5"].fill = SUB_FILL

    ws["B6"] = "Weighted maturity score"
    ws["B6"].font = B_FONT
    # domain rows are written below at DOM_START; overall uses helper columns G/H
    ws["B7"] = "Maturity band"
    ws["B7"].font = B_FONT
    ws["B8"] = "Assessment coverage"
    ws["B8"].font = B_FONT
    ws["B9"] = "Controls in scope / assessed"
    ws["B9"].font = B_FONT
    ws["B10"] = "Total gaps identified"
    ws["B10"].font = B_FONT
    ws["B11"] = "Critical-severity gaps"
    ws["B11"].font = B_FONT

    # -- domain table ---------------------------------------------------
    DOM_START = 15
    ws[f"B{DOM_START - 1}"] = "MATURITY BY DOMAIN"
    ws[f"B{DOM_START - 1}"].font = H2_FONT
    ws[f"B{DOM_START - 1}"].fill = SUB_FILL
    for col in "CDEFGHI":
        ws[f"{col}{DOM_START - 1}"].fill = SUB_FILL

    heads = ["Domain", "Weight", "In scope", "Assessed", "Gaps", "Maturity",
             "Wtd num.", "Wtd den.", "Band"]
    for i, h in enumerate(heads):
        c = ws.cell(row=DOM_START, column=2 + i, value=h)
        c.font = H_FONT
        c.fill = H_FILL
        c.alignment = WRAP_C
        c.border = BOX

    r = DOM_START + 1
    first_dom = r
    for d in results.domains:
        code = d.code
        ws.cell(row=r, column=2, value=f"{code} — {d.name}").font = N_FONT
        ws.cell(row=r, column=3, value=d.weight).font = N_FONT
        ws.cell(row=r, column=4, value=f'=COUNTIFS({dom_r},"{code}",{M}$H${FIRST_ROW}:$H${last},"Yes")').font = N_FONT
        ws.cell(row=r, column=5, value=f'=COUNTIFS({dom_r},"{code}",{M}$N${FIRST_ROW}:$N${last},1)').font = N_FONT
        ws.cell(row=r, column=6, value=f'=COUNTIFS({dom_r},"{code}",{gap_r},1)').font = N_FONT
        ws.cell(row=r, column=7,
                value=(f'=IF(SUMIFS({max_r},{dom_r},"{code}")=0,"",'
                       f'SUMIFS({con_r},{dom_r},"{code}")/SUMIFS({max_r},{dom_r},"{code}"))')
                ).font = B_FONT
        ws.cell(row=r, column=8, value=f'=IF(G{r}="","",G{r}*C{r})').font = N_FONT
        ws.cell(row=r, column=9, value=f'=IF(G{r}="","",C{r})').font = N_FONT
        ws.cell(row=r, column=10,
                value=(f'=IF(G{r}="","Not assessed",IF(G{r}>=0.8,"Optimised",'
                       f'IF(G{r}>=0.6,"Managed",IF(G{r}>=0.4,"Developing",'
                       f'IF(G{r}>=0.2,"Initial","Absent")))))')).font = N_FONT
        ws.cell(row=r, column=6).alignment = CENTER
        for col in range(2, 11):
            ws.cell(row=r, column=col).border = BOX
            if col in (4, 5, 6):
                ws.cell(row=r, column=col).alignment = CENTER
        ws.cell(row=r, column=7).number_format = "0.0%"
        r += 1
    last_dom = r - 1

    tot = r
    ws.cell(row=tot, column=2, value="TOTAL / WEIGHTED").font = B_FONT
    ws.cell(row=tot, column=4, value=f'=SUM(D{first_dom}:D{last_dom})').font = B_FONT
    ws.cell(row=tot, column=5, value=f'=SUM(E{first_dom}:E{last_dom})').font = B_FONT
    ws.cell(row=tot, column=6, value=f'=SUM(F{first_dom}:F{last_dom})').font = B_FONT
    ws.cell(row=tot, column=7,
            value=f'=IF(SUM(I{first_dom}:I{last_dom})=0,"",SUM(H{first_dom}:H{last_dom})/SUM(I{first_dom}:I{last_dom}))'
            ).font = B_FONT
    ws.cell(row=tot, column=7).number_format = "0.0%"
    for col in range(2, 11):
        ws.cell(row=tot, column=col).fill = SUB_FILL
        ws.cell(row=tot, column=col).border = BOX
        if col in (4, 5, 6, 7):
            ws.cell(row=tot, column=col).alignment = CENTER

    # headline formulas now that the table exists
    ws["C6"] = f"=G{tot}"
    ws["C6"].number_format = "0.0%"
    ws["C6"].font = Font(name=FONT, size=20, bold=True, color=NAVY)
    ws["C7"] = (f'=IF(C6="","Not assessed",IF(C6>=0.8,"Optimised",IF(C6>=0.6,"Managed",'
                f'IF(C6>=0.4,"Developing",IF(C6>=0.2,"Initial","Absent")))))')
    ws["C7"].font = B_FONT
    ws["C8"] = f'=IF(D{tot}=0,"",E{tot}/D{tot})'
    ws["C8"].number_format = "0.0%"
    ws["C8"].font = B_FONT
    ws["C9"] = f'=D{tot}&" / "&E{tot}'
    ws["C9"].font = B_FONT
    ws["C10"] = f"=F{tot}"
    ws["C10"].font = B_FONT
    ws["C11"] = f'=COUNTIFS({gap_r},1,{sev_r},"Critical")'
    ws["C11"].font = Font(name=FONT, size=11, bold=True, color=RED)
    for row_ in range(6, 12):
        ws[f"C{row_}"].alignment = CENTER
        ws[f"C{row_}"].border = BOX
    ws["I6"] = ("Weighted by domain, so a domain with many controls does not mechanically "
                "dominate one with few but weighty ones.")
    ws["I6"].font = S_FONT
    ws["I6"].alignment = WRAP
    ws.merge_cells("I6:I9")

    # -- status + severity ----------------------------------------------
    r = last_dom + 4
    ws[f"B{r}"] = "STATUS SUMMARY"
    ws[f"B{r}"].font = H2_FONT
    ws[f"B{r}"].fill = SUB_FILL
    for col in "CDEFGHI":
        ws[f"{col}{r}"].fill = SUB_FILL
    r += 1
    for label in ["Compliant", "Substantially compliant", "Partially compliant",
                  "Non-compliant", "Not assessed", "Not applicable", "Out of scope"]:
        ws[f"B{r}"] = label
        ws[f"B{r}"].font = N_FONT
        ws[f"C{r}"] = f'=COUNTIFS({sta_r},"{label}")'
        ws[f"C{r}"].font = B_FONT
        ws[f"C{r}"].alignment = CENTER
        ws[f"C{r}"].border = BOX
        r += 1

    r += 1
    ws[f"B{r}"] = "GAPS BY SEVERITY"
    ws[f"B{r}"].font = H2_FONT
    ws[f"B{r}"].fill = SUB_FILL
    for col in "CDEFGHI":
        ws[f"{col}{r}"].fill = SUB_FILL
    r += 1
    for label, colour in (("Critical", RED), ("High", AMBER), ("Medium", SLATE), ("Low", GREEN)):
        ws[f"B{r}"] = label
        ws[f"B{r}"].font = N_FONT
        ws[f"C{r}"] = f'=COUNTIFS({gap_r},1,{sev_r},"{label}")'
        ws[f"C{r}"].font = Font(name=FONT, size=10, bold=True, color=colour)
        ws[f"C{r}"].alignment = CENTER
        ws[f"C{r}"].border = BOX
        r += 1

    # -- penalty exposure ------------------------------------------------
    r += 1
    ws[f"B{r}"] = "PENALTY EXPOSURE — SCHEDULE ENTRIES ENGAGED"
    ws[f"B{r}"].font = H2_FONT
    ws[f"B{r}"].fill = SUB_FILL
    for col in "CDEFGHI":
        ws[f"{col}{r}"].fill = SUB_FILL
    r += 1
    for i, h in enumerate(["Schedule entry", "Provision", "Max (INR cr)", "Gaps", "Engaged",
                           "Exposure (INR cr)", "", "", "Breach"]):
        c = ws.cell(row=r, column=2 + i, value=h)
        c.font = H_FONT
        c.fill = H_FILL
        c.alignment = WRAP_C
        c.border = BOX
    r += 1
    pen_first = r
    for e in results.library.citations["penalty_schedule"]["entries"]:
        maxv = e.get("max_penalty_inr_crore")
        ws.cell(row=r, column=2, value=f"Entry {e['entry']}").font = N_FONT
        ws.cell(row=r, column=3, value=e["provision"]).font = N_FONT
        ws.cell(row=r, column=4, value=(maxv if maxv is not None else "n/a")).font = N_FONT
        ws.cell(row=r, column=5, value=f'=COUNTIFS({gap_r},1,{pen_r},{e["entry"]})').font = N_FONT
        ws.cell(row=r, column=6, value=f'=IF(E{r}>0,"Yes","No")').font = B_FONT
        ws.cell(row=r, column=7,
                value=(f'=IF(AND(E{r}>0,ISNUMBER(D{r})),D{r},0)')).font = N_FONT
        ws.cell(row=r, column=10, value=e["breach"]).font = S_FONT
        ws.cell(row=r, column=10).alignment = WRAP
        for col in list(range(2, 8)) + [10]:
            ws.cell(row=r, column=col).border = BOX
            if col in (4, 5, 6, 7):
                ws.cell(row=r, column=col).alignment = CENTER
        ws.row_dimensions[r].height = 26
        r += 1
    ws.cell(row=r, column=2, value="AGGREGATE CEILING").font = B_FONT
    ws.cell(row=r, column=7, value=f"=SUM(G{pen_first}:G{r-1})").font = Font(
        name=FONT, size=11, bold=True, color=RED)
    ws.cell(row=r, column=7).alignment = CENTER
    for col in range(2, 8):
        ws.cell(row=r, column=col).fill = SUB_FILL
        ws.cell(row=r, column=col).border = BOX
    r += 2
    ws[f"B{r}"] = results.penalty_exposure()["caveat"]
    ws[f"B{r}"].font = S_FONT
    ws[f"B{r}"].alignment = WRAP
    ws.merge_cells(f"B{r}:I{r+3}")


def _write_evidence_log(wb: Workbook, results: Results) -> None:
    ws = wb.create_sheet("Evidence Log")
    cols = [("A", "Workpaper ref", 15), ("B", "Control ID(s)", 16), ("C", "Evidence obtained", 46),
            ("D", "Type", 16), ("E", "Source / provided by", 26), ("F", "Date obtained", 14),
            ("G", "Tested by", 16), ("H", "Conclusion", 44), ("I", "File location", 34)]
    _hdr(ws, 1, cols)
    ws.freeze_panes = "A2"
    example = ["WP-001", "CON-07", "Export of consent artefacts for 3 sampled Data Principals, "
               "showing purpose set, timestamp, interface and notice version",
               "System export", "Head of Engineering", results.assessment.assessment_date,
               "(auditor)", "Artefacts retrieved for all 3; notice version present. No exception.",
               "/audit/wp/001-consent-export.csv"]
    for i, v in enumerate(example):
        c = ws.cell(row=2, column=1 + i, value=v)
        c.font = Font(name=FONT, size=9, italic=True, color=SLATE)
        c.alignment = WRAP
        c.border = BOX
    ws.row_dimensions[2].height = 40
    ws["A3"] = "↑ example row — overwrite or delete. Rows below are for your entries."
    ws["A3"].font = S_FONT
    for row in range(4, 60):
        for col in range(1, 10):
            c = ws.cell(row=row, column=col)
            c.fill = IN_FILL
            c.border = BOX
            c.font = N_FONT
            c.alignment = WRAP
    ws.auto_filter.ref = "A1:I59"


def _write_citations(wb: Workbook, results: Results) -> None:
    ws = wb.create_sheet("Citations")
    ws.sheet_view.showGridLines = False
    lib = results.library
    for letter, width in (("A", 3), ("B", 38), ("C", 74), ("D", 34), ("E", 26)):
        ws.column_dimensions[letter].width = width

    ws["B2"] = "Citation Register"
    ws["B2"].font = TITLE_FONT
    ws["B3"] = lib.citations["meta"]["act_long_name"]
    ws["B3"].font = S_FONT

    r = 5
    ws[f"B{r}"] = "PENALTY SCHEDULE — s.33 read with the Schedule"
    ws[f"B{r}"].font = H2_FONT
    ws[f"B{r}"].fill = SUB_FILL
    for col in "CDE":
        ws[f"{col}{r}"].fill = SUB_FILL
    r += 1
    for i, h in enumerate(["Entry", "Breach", "Provision", "Maximum"]):
        c = ws.cell(row=r, column=2 + i, value=h)
        c.font = H_FONT
        c.fill = H_FILL
        c.alignment = WRAP_C
        c.border = BOX
    r += 1
    for e in lib.citations["penalty_schedule"]["entries"]:
        ws.cell(row=r, column=2, value=f"Entry {e['entry']}").font = N_FONT
        ws.cell(row=r, column=3, value=e["breach"]).font = N_FONT
        ws.cell(row=r, column=4, value=e["provision"]).font = N_FONT
        ws.cell(row=r, column=5, value=e["label"]).font = N_FONT
        for col in range(2, 6):
            ws.cell(row=r, column=col).alignment = WRAP
            ws.cell(row=r, column=col).border = BOX
        ws.row_dimensions[r].height = 28
        r += 1

    r += 2
    ws[f"B{r}"] = "DPDP RULES — SLOTS AWAITING VERIFICATION"
    ws[f"B{r}"].font = H2_FONT
    ws[f"B{r}"].fill = SUB_FILL
    for col in "CDE":
        ws[f"{col}{r}"].fill = SUB_FILL
    r += 1
    ws[f"B{r}"] = ("Populate the citation for each slot in controls/citations.yaml and set its "
                   "status to VERIFIED_RULES. Every deliverable then updates from that single "
                   "edit. Until then these citations are deliberately blank rather than "
                   "reconstructed.")
    ws[f"B{r}"].font = S_FONT
    ws[f"B{r}"].alignment = WRAP
    ws.merge_cells(f"B{r}:E{r+1}")
    r += 3
    for i, h in enumerate(["Slot key", "Subject matter the Rules address", "Act anchor",
                           "Controls relying on it"]):
        c = ws.cell(row=r, column=2 + i, value=h)
        c.font = H_FONT
        c.fill = H_FILL
        c.alignment = WRAP_C
        c.border = BOX
    r += 1
    for slot in lib.unverified_slots():
        raw = lib.citations["rule_slots"][slot["key"]]
        ws.cell(row=r, column=2, value=slot["key"]).font = B_FONT
        ws.cell(row=r, column=3, value=slot["subject"]).font = N_FONT
        ws.cell(row=r, column=4, value=raw.get("anchors_act", "—")).font = N_FONT
        ws.cell(row=r, column=5, value=", ".join(slot["controls"]) or "—").font = N_FONT
        for col in range(2, 6):
            ws.cell(row=r, column=col).alignment = WRAP
            ws.cell(row=r, column=col).border = BOX
        ws.row_dimensions[r].height = max(28, 12 * (len(slot["subject"]) // 72 + 1))
        r += 1


def build_workbook(results: Results, path: str) -> str:
    """Write the control matrix workbook. Returns the path written."""
    wb = Workbook()
    wb.remove(wb.active)
    _write_instructions(wb, results)
    _write_profile(wb, results)
    last = _write_matrix(wb, results)
    _write_dashboard(wb, results, last)
    _write_evidence_log(wb, results)
    _write_citations(wb, results)
    wb.move_sheet("Instructions", offset=-4)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    wb.save(path)
    return path
