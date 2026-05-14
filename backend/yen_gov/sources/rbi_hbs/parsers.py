"""Cell-value coercion and year-label parsing helpers used by every
RBI Handbook ingest script.

These are the genuinely-duplicated primitives — three copies of essentially
the same regex + the same null-sentinel set lived in the per-tool scripts
before the extraction. Higher-level table walkers (state-as-row × FY-as-col,
multi-base time series, peak-paired sub-columns, T142-style grouped sheets)
stay in their callers because each handles a different RBI table layout and
abstracting over them would invite a flag-soup signature.

Sentinel values RBI uses for "missing" across both publications:
``-``, ``.``, empty string, ``*``, ``NA``, ``n.a.``, ``—`` (em-dash).

Year-label conventions:
- Fiscal year is published as ``YYYY-YY`` (e.g. ``2014-15``); we map it to
  ``YYYY-04`` to anchor it on April (the FY start).
- Pension and budget tables suffix recent years with revision tier, e.g.
  ``2024-25 (RE)`` (Revised Estimate) or ``2025-26 (BE)`` (Budget Estimate).
  The suffix is stripped at parse time; tier is conveyed in the indicator's
  ``notes`` field instead.
- Calendar year is a bare 4-digit int or string (e.g. ``2014``); mapped to
  itself (``"2014"``).
"""
from __future__ import annotations

import re

_FY_RX = re.compile(r"^(\d{4})-(\d{2,4})(?:\s*\([A-Z]+\))?(?:\*+)?$")
_CY_RX = re.compile(r"^\d{4}$")


def coerce_value(v: object) -> float | None:
    """Convert an Excel cell value to ``float`` or ``None``.

    Treats RBI's missing-value sentinels (``-``, ``.``, ``*``, ``NA``,
    ``n.a.``, ``—``, empty) as missing. Strips embedded thousands commas.
    """
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if s in ("-", ".", "", "*", "NA", "n.a.", "—"):
            return None
        try:
            return float(s.replace(",", ""))
        except ValueError:
            return None
    return None


def fy_label_to_time(label: object) -> str | None:
    """Map a fiscal-year cell label to our canonical ``time`` string.

    ``"2014-15"`` → ``"2014-04"``. Bare year ints (1900..2100) map to the
    April of that year. Returns ``None`` for anything else.
    """
    if isinstance(label, int) and 1900 <= label <= 2100:
        return f"{label}-04"
    if not isinstance(label, str):
        return None
    s = label.strip()
    m = _FY_RX.match(s)
    if m:
        return f"{m.group(1)}-04"
    return None


def cy_label_to_time(label: object) -> str | None:
    """Map a calendar-year cell label to our canonical ``time`` string.

    Used by tables where columns are years like ``2007, 2008, ...`` (e.g.
    HBS-IS Table 143's "as-at-end-March YYYY" snapshot columns).
    Strict 4-digit int or 4-digit string; returns ``None`` for FY labels.
    """
    if isinstance(label, int) and 1900 <= label <= 2100:
        return str(label)
    if isinstance(label, str) and _CY_RX.match(label.strip()):
        return label.strip()
    return None


def year_label_to_time(label: object, calendar: bool) -> str | None:
    """Combined FY/CY parser used by tables that mix both grains across sheets.

    With ``calendar=False`` behaves like :func:`fy_label_to_time`; with
    ``calendar=True`` returns ``"YYYY"`` for any 4-digit year. Used by the
    inflation/pension/health ingest where some workbooks publish CY rows
    inside what is otherwise an FY-shaped table.
    """
    if isinstance(label, int) and 1900 <= label <= 2100:
        return str(label) if calendar else f"{label}-04"
    if not isinstance(label, str):
        return None
    s = label.strip()
    m = _FY_RX.match(s)
    if m:
        return f"{m.group(1)}-04"
    if _CY_RX.match(s):
        return s if calendar else f"{s}-04"
    return None
