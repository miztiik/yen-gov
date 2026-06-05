"""Build the trimmed-real PRI fixture workbook for the LGD parser golden test.

Run once to (re)generate ``pri_andhra_pradesh_FIXTURE.xlsx`` next to this script.
The rows are byte-copied from the real Andhra Pradesh PRI export (2026-06-05
snapshot), trimmed to two ACs that exercise the adversarial cases the parser
must survive (plan section 0c.8):

- AC 3166 (Amalapuram, ECI 163): wholly inside district 747 -> is_primary path.
- AC 3167 (Gannavaram, ECI 165): spans district 747 (2 villages) + district 510
  (1 village) -> the multi-district / plurality is_primary fan-out.
- Both nest in PC 411 (ECI 9) -> the AC->parent-PC fold.
- District census codes carry a leading-zero string ("000", "547") -> locks the
  no-integer-coercion discipline for the registers (codes are read off the CSV
  registers, never the XLSX, but the fixture mirrors the real magnitudes).

Keeping the builder (not just the binary) means the fixture is regenerable and
auditable; the committed ``.xlsx`` is what the test reads (no openpyxl write at
test time).
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

TITLE = (
    "State Of Andhra Pradesh Parliament Constituency and Assembly Constituency "
    "along with coverage details PRI"
)
HEADER = [
    "S.No.", "Parliament Constituency code", "Parliament Constituency ECI Code",
    "Parliament Constituency Name", "Assembly Constituency Code",
    "Assembly Constituency ECI Code", "Assembly Constituency Name",
    "District Code", "District Name", "District Census 2011 Code",
    "Subdistrict Code", "Subdistrict Name", "Subdistrict Census 2011 Code",
    "Village Code", "Village Name", "Village Census 2011 Code",
    "Rural Localbody Code", "Rural LocalbodyName", "Block Code", "Block Name",
]

# (SNo, PCcode, PCeci, PCname, ACcode, ACeci, ACname, Distcode, Distname,
#  Distcensus, SubDcode, SubDname, SubDcensus, Vcode, Vname, Vcensus, RLBcode,
#  RLBname, Blockcode, Blockname) - trimmed-real AP rows.
ROWS = [
    (1, 411, 9, "Amalapuram", 3166, 163, "Amalapuram", 747,
     "Dr. B.R. Ambedkar Konaseema", "000", 4940, "Allavaram", "04940",
     587861, "Allavaram", "587861", 198997, "Allavaram", 4868, "Allavaram"),
    (2, 411, 9, "Amalapuram", 3166, 163, "Amalapuram", 747,
     "Dr. B.R. Ambedkar Konaseema", "000", 4940, "Allavaram", "04940",
     587862, "Kodurupadu", "587862", 199007, "Kodurupadu", 4868, "Allavaram"),
    (63, 411, 9, "Amalapuram", 3167, 165, "Gannavaram", 747,
     "Dr. B.R. Ambedkar Konaseema", "000", 4941, "Mummidivaram", "04941",
     587900, "Gannavaram A", "587900", 199100, "Gannavaram", 4869, "Mummidivaram"),
    (64, 411, 9, "Amalapuram", 3167, 165, "Gannavaram", 747,
     "Dr. B.R. Ambedkar Konaseema", "000", 4941, "Mummidivaram", "04941",
     587901, "Gannavaram B", "587901", 199101, "Gannavaram", 4869, "Mummidivaram"),
    (135, 411, 9, "Amalapuram", 3167, 165, "Gannavaram", 510, "Krishna", "547",
     5001, "Gannavaram", "05001", 590000, "Krishna Edge", "590000", 200000,
     "Krishna LB", 5000, "Gannavaram Block"),
]


def build(out_path: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "parlimentConstituencyAndAssembl"
    ws.append([TITLE] + [None] * (len(HEADER) - 1))
    ws.append(HEADER)
    for row in ROWS:
        ws.append(list(row))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return out_path


if __name__ == "__main__":
    target = Path(__file__).parent / "Parliment_PRI_andhra_pradesh_FIXTURE.xlsx"
    build(target)
    print(f"wrote {target}")
