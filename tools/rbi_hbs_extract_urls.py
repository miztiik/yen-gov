"""Parse RBI Handbook landing-page accessibility snapshot and extract
{table_number: xlsx_url} mapping for the requested tables."""
from __future__ import annotations
import io, re, sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

snapshot = Path(sys.argv[1])
text = snapshot.read_text(encoding="utf-8", errors="replace")

# Each table in the snapshot is rendered roughly as:
#   - link "Table 108 : State-wise Average Inflation (CPI) - General" [ref=eN]
#   - link "Document - Table 108 : ... 12 kb" [ref=eM]:
#       /url: https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/108T_<hex>.XLSX
# We capture: for every table N found, the FIRST .XLSX URL whose filename starts
# with that number followed by "T_". Iterate all matches in document order.

# Build position map: every .XLSX URL with its preceding "Table N :" caption.
url_rx = re.compile(r"(rbidocs\.rbi\.org\.in/rdocs/Publications/DOCs/(\d+)T_[0-9A-F]+\.XLSX)")
seen: dict[str, str] = {}  # table_number -> https url
for m in url_rx.finditer(text):
    tnum = m.group(2)
    url = "https://" + m.group(1)
    if tnum not in seen:
        seen[tnum] = url

wanted = [int(x) for x in sys.argv[2:]]
for n in wanted:
    key = str(n)
    print(f"  {n:>4}: {seen.get(key, '<<MISSING>>')}")
