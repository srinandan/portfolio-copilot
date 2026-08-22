#!/usr/bin/env python3
"""Generate the sample Form W-2 PDF fixture used to exercise W-2 Document AI ingestion.

The data mirrors the deterministic values produced by the offline MockW2Parser
(pkg/documentai/mock.go) for the fictional demo persona "Alex Mercer" (demo_user),
so the same numbers appear whether the PDF is parsed by GCP Document AI or served
by the mock in tests/dev.

All values are FICTITIOUS test data (fake SSN/EIN, fictional employer/employee).
This is not a real tax document.

Usage:
    python3 scripts/generate_w2_sample.py [output.pdf]
Default output: testdata/w2_alex_mercer.pdf

Requires: reportlab  (pip install reportlab)
"""
import sys
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch  # noqa: F401 (kept for readability of coordinates)

PAGE_W, PAGE_H = letter  # 612 x 792 points

# --- Fixture data (matches pkg/documentai/mock.go MockW2Parser) -----------------
TAX_YEAR = "2025"
SSN = "123-45-4589"          # fictitious; last 4 (4589) matches SSNMasked "***-**-4589"
EIN = "12-3456789"           # fictitious
CONTROL_NUMBER = "W2-DEMO-0001"

EMPLOYER_NAME = "Acme Corporation"
EMPLOYER_ADDR = ["500 Roadrunner Way", "San Jose, CA 95110"]

EMPLOYEE_NAME = "Alex Mercer"
# California address — matches the CA state withholding (boxes 15-17) and SF locality (box 20).
EMPLOYEE_ADDR = ["1024 Mission Street", "San Francisco, CA 94103"]

BOX1_WAGES = "220,000.00"
BOX2_FED_TAX = "38,450.00"
BOX3_SS_WAGES = "168,600.00"
BOX4_SS_TAX = "10,453.20"
BOX5_MEDICARE_WAGES = "220,000.00"
BOX6_MEDICARE_TAX = "3,190.00"
BOX7_SS_TIPS = ""
BOX8_ALLOCATED_TIPS = ""
BOX10_DEP_CARE = ""
BOX11_NONQUAL = ""

BOX12 = [
    ("a", "D", "23,000.00"),   # 401(k) elective deferral
    ("b", "W", "4,150.00"),    # Employer HSA contribution
    ("c", "", ""),
    ("d", "", ""),
]

# Box 13 checkboxes: statutory employee, retirement plan, third-party sick pay
BOX13 = {"statutory": False, "retirement": True, "sick_pay": False}

BOX14 = [("CA SDI", "1,378.48")]

# Box 15-20 state / local
STATE = "CA"
STATE_ID = "123-4567-8"
BOX16_STATE_WAGES = "220,000.00"
BOX17_STATE_TAX = "18,250.00"
BOX18_LOCAL_WAGES = "220,000.00"
BOX19_LOCAL_TAX = "0.00"
BOX20_LOCALITY = "San Francisco"


def main(out_path: str) -> None:
    c = canvas.Canvas(out_path, pagesize=letter)
    c.setTitle("Sample Form W-2 (Wage and Tax Statement) - FICTITIOUS TEST DATA")
    c.setAuthor("Portfolio Copilot test fixtures")
    c.setSubject("Fictitious sample W-2 for Document AI ingestion tests")

    def top_y(dist_from_top: float) -> float:
        """Convert a distance-from-top into a reportlab (bottom-left origin) y."""
        return PAGE_H - dist_from_top

    def cell(x, yt, w, h, label=None, value=None, value_size=11, label_size=6,
             value_dx=4, bold_value=False):
        """Draw a rectangular box with a small top-left label and a value."""
        c.setLineWidth(0.7)
        c.rect(x, top_y(yt) - h, w, h, stroke=1, fill=0)
        if label:
            c.setFont("Helvetica", label_size)
            c.drawString(x + 3, top_y(yt) - 9, label)
        if value:
            c.setFont("Helvetica-Bold" if bold_value else "Helvetica", value_size)
            c.drawString(x + value_dx, top_y(yt) - h + 6, value)

    # ---- Header ---------------------------------------------------------------
    c.setFont("Helvetica-Bold", 15)
    c.drawString(40, top_y(46), "Form W-2  Wage and Tax Statement")
    c.setFont("Helvetica", 9)
    c.drawString(40, top_y(60), "Department of the Treasury - Internal Revenue Service")
    c.setFont("Helvetica-Bold", 15)
    c.drawRightString(PAGE_W - 40, top_y(46), TAX_YEAR)
    c.setFont("Helvetica", 8)
    c.drawRightString(PAGE_W - 40, top_y(60), "OMB No. 1545-0008")

    # SAMPLE banner so this is never mistaken for a genuine record.
    c.setFont("Helvetica-Bold", 9)
    c.setFillGray(0.35)
    c.drawCentredString(PAGE_W / 2, top_y(46),
                        "SAMPLE - FICTITIOUS DATA - NOT A REAL TAX DOCUMENT")
    c.setFillGray(0.0)

    # ---- Layout geometry ------------------------------------------------------
    left_x = 40
    left_w = 300
    right_x = left_x + left_w          # 340
    right_w = (PAGE_W - 40) - right_x  # ~232
    col_w = right_w / 2                # money boxes are paired
    row_h = 34
    top = 78                           # first grid row distance-from-top

    # ---- Left column: a, b, c, d, e/f ----------------------------------------
    y = top
    cell(left_x, y, left_w, 24,
         label="a  Employee's social security number", value=SSN, value_size=12)
    y += 24
    cell(left_x, y, left_w, 24,
         label="b  Employer identification number (EIN)", value=EIN, value_size=12)
    y += 24
    # Box c: employer name & address (multi-line)
    cell(left_x, y, left_w, 52, label="c  Employer's name, address, and ZIP code")
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left_x + 6, top_y(y) - 22, EMPLOYER_NAME)
    c.setFont("Helvetica", 9)
    c.drawString(left_x + 6, top_y(y) - 34, EMPLOYER_ADDR[0])
    c.drawString(left_x + 6, top_y(y) - 45, EMPLOYER_ADDR[1])
    y += 52
    cell(left_x, y, left_w, 22,
         label="d  Control number", value=CONTROL_NUMBER, value_size=10)
    y += 22
    # Box e/f: employee name & address (multi-line)
    cell(left_x, y, left_w, 62,
         label="e/f  Employee's name, address, and ZIP code")
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left_x + 6, top_y(y) - 24, EMPLOYEE_NAME)
    c.setFont("Helvetica", 9)
    c.drawString(left_x + 6, top_y(y) - 38, EMPLOYEE_ADDR[0])
    c.drawString(left_x + 6, top_y(y) - 50, EMPLOYEE_ADDR[1])

    # ---- Right column: boxes 1-14 --------------------------------------------
    def money_pair(yt, l1, v1, l2, v2):
        cell(right_x, yt, col_w, row_h, label=l1, value=v1, value_dx=6)
        cell(right_x + col_w, yt, col_w, row_h, label=l2, value=v2, value_dx=6)

    ry = top
    money_pair(ry, "1  Wages, tips, other comp.", BOX1_WAGES,
               "2  Federal income tax withheld", BOX2_FED_TAX); ry += row_h
    money_pair(ry, "3  Social security wages", BOX3_SS_WAGES,
               "4  Social security tax withheld", BOX4_SS_TAX); ry += row_h
    money_pair(ry, "5  Medicare wages and tips", BOX5_MEDICARE_WAGES,
               "6  Medicare tax withheld", BOX6_MEDICARE_TAX); ry += row_h
    money_pair(ry, "7  Social security tips", BOX7_SS_TIPS,
               "8  Allocated tips", BOX8_ALLOCATED_TIPS); ry += row_h
    money_pair(ry, "9", "", "10  Dependent care benefits", BOX10_DEP_CARE); ry += row_h

    # Box 11 + Box 12a
    cell(right_x, ry, col_w, row_h, label="11  Nonqualified plans", value=BOX11_NONQUAL)
    b12a = BOX12[0]
    cell(right_x + col_w, ry, col_w, row_h,
         label="12a  Code", value=f"{b12a[1]}   {b12a[2]}", value_dx=6)
    ry += row_h

    # Box 13 checkboxes + Box 12b
    cell(right_x, ry, col_w, row_h, label="13")
    c.setFont("Helvetica", 6.5)
    checks = [
        ("Statutory employee", BOX13["statutory"]),
        ("Retirement plan", BOX13["retirement"]),
        ("Third-party sick pay", BOX13["sick_pay"]),
    ]
    cy = top_y(ry) - 15
    for text, on in checks:
        bx = right_x + 6
        c.rect(bx, cy - 1, 6, 6, stroke=1, fill=0)
        if on:
            c.setFont("Helvetica-Bold", 7)
            c.drawString(bx + 0.6, cy - 0.4, "X")
            c.setFont("Helvetica", 6.5)
        c.drawString(bx + 10, cy, text)
        cy -= 9
    b12b = BOX12[1]
    cell(right_x + col_w, ry, col_w, row_h,
         label="12b  Code", value=f"{b12b[1]}   {b12b[2]}", value_dx=6)
    ry += row_h

    # Box 14 Other + Box 12c
    b14_label = "  ".join(f"{lbl} {amt}" for lbl, amt in BOX14)
    cell(right_x, ry, col_w, row_h, label="14  Other", value=b14_label,
         value_size=9, value_dx=6)
    cell(right_x + col_w, ry, col_w, row_h, label="12c  Code", value="")
    ry += row_h

    # ---- Bottom full-width state/local table (boxes 15-20) --------------------
    grid_bottom = max(y + 62, ry) + 6
    sy = grid_bottom
    sh = 30
    # column layout: State | Employer state ID | 16 wages | 17 tax | 18 local | 19 local tax | 20 locality
    cols = [
        ("15  State", STATE, 55),
        ("Employer's state ID no.", STATE_ID, 95),
        ("16  State wages, tips, etc.", BOX16_STATE_WAGES, 80),
        ("17  State income tax", BOX17_STATE_TAX, 72),
        ("18  Local wages, tips, etc.", BOX18_LOCAL_WAGES, 80),
        ("19  Local income tax", BOX19_LOCAL_TAX, 70),
        ("20  Locality name", BOX20_LOCALITY, 80),
    ]
    cx = left_x
    total_w = PAGE_W - 40 - left_x
    scale = total_w / sum(w for _, _, w in cols)
    for label, value, w in cols:
        cw = w * scale
        cell(cx, sy, cw, sh, label=label, label_size=5.5, value=value,
             value_size=9, value_dx=4)
        cx += cw

    # ---- Footer ---------------------------------------------------------------
    c.setFont("Helvetica-Oblique", 7)
    c.setFillGray(0.4)
    c.drawString(left_x, top_y(sy + sh + 14),
                 "Fictitious sample generated for Portfolio Copilot Document AI "
                 "ingestion tests. Persona: Alex Mercer (demo_user). Do not use as a real W-2.")
    c.setFillGray(0.0)

    c.showPage()
    c.save()


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    default_out = repo_root / "testdata" / "w2_alex_mercer.pdf"
    out = sys.argv[1] if len(sys.argv) > 1 else str(default_out)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    main(out)
    print(f"Wrote {out}")
