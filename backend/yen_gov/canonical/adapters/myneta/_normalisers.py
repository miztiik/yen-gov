"""Pure normalisers for the MyNeta affidavit -> canonical candidacy join.

Each function takes a single string and returns a normalised form suitable
for use in an equality-based join key. Functions are pure: deterministic,
no I/O, no globals. Tested in isolation.
"""

from __future__ import annotations

import re

# Honorifics stripped from the LEAD of candidate-name strings only.
# Trailing tokens (e.g. "John Doe Dr.") are kept; the period-strip below
# normalises trailing variants into the same token without needing a list.
_HONORIFIC_PREFIXES: tuple[str, ...] = (
    "dr.",
    "dr ",
    "shri ",
    "shri.",
    "smt.",
    "smt ",
    "mr.",
    "mr ",
    "mrs.",
    "mrs ",
    "ms.",
    "ms ",
    "sri ",
)

# Trailing parenthesised qualifiers in constituency names — e.g.
# "Sant Ravi Das Nagar (Bhadohi)" -> "Sant Ravi Das Nagar",
# "JAMUI (SC)" -> "JAMUI". The qualifier is metadata (reservation, slug
# disambiguator) and is not used in the equality join.
_TRAILING_PAREN_QUAL = re.compile(r"\s*\([^)]*\)\s*$")

# Multi-space collapse used by every normaliser.
_WHITESPACE = re.compile(r"\s+")

# Whitespace around hyphen, used in constituency normalisation only.
# Example: "Barddhaman - Durgapur" -> "barddhaman-durgapur".
_HYPHEN_WS = re.compile(r"\s*-\s*")


def normalise_candidate_name(s: str) -> str:
    """Normalise a candidate name for equality-based joining.

    Operations (in order):
      1. strip leading + trailing whitespace
      2. lowercase
      3. strip a leading honorific prefix from `_HONORIFIC_PREFIXES`
      4. remove all "." chars (collapses "S.P.Y" vs "S P Y" vs "SPY"...
         no — collapses "S.P.Y" -> "spy" and "S.P.Y." -> "spy")
      5. collapse internal whitespace runs to a single space
      6. trim
    """
    if not s:
        return ""
    out = s.strip().lower()
    for prefix in _HONORIFIC_PREFIXES:
        if out.startswith(prefix):
            out = out[len(prefix):].lstrip()
            break
    # Strip dots ("S.P.Y" -> "spy") and backslash-escape noise
    # ("JANARDAN SINGH \\SIGRIWAL\\" -> "janardan singh sigriwal") that
    # crept in from TCPD source dumps. Both are deterministic, not fuzzy.
    out = out.replace(".", "").replace("\\", "")
    out = _WHITESPACE.sub(" ", out).strip()
    return out


def normalise_constituency_name(s: str) -> str:
    """Normalise a PC / AC constituency name for equality-based joining.

    Operations (in order):
      1. strip + lowercase
      2. drop a trailing parenthesised qualifier (e.g. "(SC)", "(Bhadohi)")
      3. remove all "." chars
      4. collapse whitespace around hyphens — "Barddhaman - Durgapur" and
         "BARDHAMAN-DURGAPUR" both fold to "barddhaman-durgapur"
      5. collapse internal whitespace runs
      6. trim
    """
    if not s:
        return ""
    out = s.strip().lower()
    out = _TRAILING_PAREN_QUAL.sub("", out)
    out = out.replace(".", "")
    out = _HYPHEN_WS.sub("-", out)
    out = _WHITESPACE.sub(" ", out).strip()
    return out


def normalise_party_short(s: str) -> str:
    """Normalise a party short-code string for equality-based joining.

    Affidavit "Party" cells carry a mix of ECI short-codes ("BJP", "INC")
    and idiosyncratic single-letter / informal codes ("T" for TRS, "P"
    for some independents). This normaliser does the cheap part only —
    upper-case, strip dots and whitespace. Mapping informal codes to
    canonical short_raw values is handled by the adapter's alias table,
    NOT by this function.
    """
    if not s:
        return ""
    out = s.strip().upper()
    out = out.replace(".", "")
    out = _WHITESPACE.sub("", out)
    return out
