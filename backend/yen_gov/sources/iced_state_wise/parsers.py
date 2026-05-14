"""Pure parsers for the ICED state-wise deep-dive API.

Two responsibilities:

1. ``decrypt_cryptojs_openssl`` — turn the base64 CryptoJS payload the
   API returns into the underlying JSON bytes. Standard CryptoJS
   ``CryptoJS.AES.decrypt(ciphertext, passphrase)`` reproduction:
   payload begins with ``Salted__`` + 8-byte salt; key+IV derived via
   OpenSSL ``EVP_BytesToKey`` with MD5 (key=32 bytes, iv=16 bytes);
   AES-256-CBC, PKCS7 padded. Verified against the live endpoint
   2026-05-14.

2. ``extract_rows`` — given a single decrypted FY response and an
   indicator spec, walk the parallel ``states`` / indicator-key arrays
   and emit canonical ``ParsedRow`` objects (entity_id, time, value).

No I/O. No pydantic. ``ingest`` lives one layer up.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad


# Hardcoded in the Angular bundle (env config module).
PASSPHRASE = b"AHten@VP0W3R"


class ICEDShapeError(ValueError):
    """The API response no longer matches what the parsers expect.

    Raised loudly rather than emitting zero rows: a silent coverage
    drop would lie to the citizen.
    """


# ---------------------------------------------------------------------------
# Decryption
# ---------------------------------------------------------------------------


def _evp_bytes_to_key(passphrase: bytes, salt: bytes, key_len: int = 32, iv_len: int = 16) -> tuple[bytes, bytes]:
    """OpenSSL ``EVP_BytesToKey`` with MD5 (CryptoJS default)."""
    out = b""
    prev = b""
    while len(out) < key_len + iv_len:
        prev = hashlib.md5(prev + passphrase + salt).digest()
        out += prev
    return out[:key_len], out[key_len : key_len + iv_len]


def decrypt_cryptojs_openssl(b64_ciphertext: str, passphrase: bytes = PASSPHRASE) -> bytes:
    """Decrypt the API's base64 payload, returning the raw JSON bytes."""
    raw = base64.b64decode(b64_ciphertext)
    if raw[:8] != b"Salted__":
        raise ICEDShapeError(
            f"missing CryptoJS OpenSSL Salted__ prefix; got {raw[:16]!r}. "
            f"The endpoint may have changed format; re-run recon."
        )
    salt = raw[8:16]
    body = raw[16:]
    key, iv = _evp_bytes_to_key(passphrase, salt)
    try:
        return unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(body), AES.block_size)
    except (ValueError, KeyError) as e:
        raise ICEDShapeError(
            f"AES decrypt/unpad failed ({e!r}). Either the passphrase has "
            f"rotated upstream (was AHten@VP0W3R as of 2026-05-14) or the "
            f"payload format changed."
        )


def decrypt_response(server_body: bytes | str) -> dict[str, Any]:
    """Decrypt and JSON-decode the full API response body.

    The server returns a JSON string (i.e. the ciphertext wrapped in
    double quotes). We accept either the raw HTTP body or the already-
    parsed string form.
    """
    if isinstance(server_body, (bytes, bytearray)):
        outer = json.loads(server_body)
    else:
        outer = json.loads(server_body) if server_body.startswith('"') else server_body
    if not isinstance(outer, str):
        raise ICEDShapeError(
            f"expected the API to return a JSON-encoded string; got {type(outer).__name__}"
        )
    plain = decrypt_cryptojs_openssl(outer)
    return json.loads(plain)


# ---------------------------------------------------------------------------
# Indicator extraction
# ---------------------------------------------------------------------------


def _fy_to_period(fy_label: str) -> str:
    """Canonicalise the API's ``YYYY-YY`` FY label to ``YYYY-04`` (start-of-FY)."""
    m = re.match(r"^(\d{4})-(\d{2})$", fy_label)
    if not m:
        raise ICEDShapeError(f"FY label {fy_label!r} does not match YYYY-YY")
    return f"{int(m.group(1)):04d}-04"


# Numeric value parsing. ICED returns:
#   "475,211.80"  - Indian-grouped decimal
#   "1298817.28"  - plain decimal (sometimes)
#   "-0.94"       - negatives
#   "N.A."        - null sentinel
#   "-"           - null sentinel (rare)
#   ""            - null sentinel
_NULL_TOKENS = frozenset({"", "-", "N.A.", "NA", "n.a.", "na", "..", "...", "*"})


def coerce_numeric(raw: Any) -> float | None:
    """Convert an ICED cell value to a float, or ``None`` for null tokens."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip()
    if text in _NULL_TOKENS:
        return None
    # Strip thousands separators (Indian or western); the schema stores plain numbers.
    cleaned = text.replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


@dataclass(frozen=True)
class ParsedRow:
    entity_id: str
    time: str
    value: float


@dataclass(frozen=True)
class IndicatorSpec:
    """Locate one indicator column in the decrypted response.

    Args:
        indicator_id: stable namespaced id (e.g. ``energy/state_generation_mu``).
        api_key: exact key in the API ``data`` dict whose value is a list
            parallel to ``states``. For composite ones (Installed Capacity
            with Allocated Shares is a dict {data, expand}) we also accept
            ``api_key_subkey``.
        api_key_subkey: optional sub-field name inside the value if it is
            a dict (e.g. ``"data"``).
    """

    indicator_id: str
    api_key: str
    api_key_subkey: str | None = None


# ICED → ECI/state-id mapping. Keys are the names as they appear in the
# API's ``states`` list; values are entity_ids used throughout the dataset.
ENTITY_MAP: dict[str, str] = {
    "All India": "IN",
    # 28 states (ECI S-codes)
    "Andhra Pradesh": "S01",
    "Arunachal Pradesh": "S02",
    "Assam": "S03",
    "Bihar": "S04",
    "Goa": "S05",
    "Gujarat": "S06",
    "Haryana": "S07",
    "Himachal Pradesh": "S08",
    "Karnataka": "S10",
    "Kerala": "S11",
    "Madhya Pradesh": "S12",
    "Maharashtra": "S13",
    "Manipur": "S14",
    "Meghalaya": "S15",
    "Mizoram": "S16",
    "Nagaland": "S17",
    "Odisha": "S18",
    "Punjab": "S19",
    "Rajasthan": "S20",
    "Sikkim": "S21",
    "Tamil Nadu": "S22",
    "Tripura": "S23",
    "Uttar Pradesh": "S24",
    "West Bengal": "S25",
    "Chhattisgarh": "S26",
    "Jharkhand": "S27",
    "Uttarakhand": "S28",
    "Telangana": "S29",
    # 8 UTs (ECI U-codes). ICED's "Delhi" is ECI's "NCT of Delhi".
    "Andaman and Nicobar Islands": "U01",
    "Chandigarh": "U02",
    "Dadra and Nagar Haveli and Daman and Diu": "U03",
    "Lakshadweep": "U04",
    "Delhi": "U05",
    "Puducherry": "U07",
    "Jammu and Kashmir": "U08",
    "Ladakh": "U09",
}


@dataclass(frozen=True)
class ParsedYear:
    """All rows extracted for one FY × one indicator spec."""

    indicator_id: str
    fy_label: str            # "2024-25"
    rows: tuple[ParsedRow, ...] = field(default_factory=tuple)


def extract_rows(
    *,
    spec: IndicatorSpec,
    fy_label: str,
    decrypted: dict[str, Any],
) -> ParsedYear:
    """Pull one indicator's per-state values out of one decrypted FY response."""
    payload = decrypted.get("data", decrypted)
    if not isinstance(payload, dict):
        raise ICEDShapeError("decrypted response has no top-level dict 'data'")

    states = payload.get("states")
    if not isinstance(states, list) or not states:
        raise ICEDShapeError(f"decrypted FY={fy_label!r} has no 'states' list")

    cell = payload.get(spec.api_key)
    if cell is None:
        raise ICEDShapeError(
            f"FY={fy_label!r} indicator key {spec.api_key!r} missing from response. "
            f"Available top-level keys: {sorted(payload.keys())[:20]}"
        )
    if spec.api_key_subkey is not None:
        if not isinstance(cell, dict) or spec.api_key_subkey not in cell:
            raise ICEDShapeError(
                f"FY={fy_label!r} indicator {spec.api_key!r} expected sub-dict "
                f"with key {spec.api_key_subkey!r}; got {type(cell).__name__}"
            )
        values = cell[spec.api_key_subkey]
    else:
        values = cell

    if not isinstance(values, list):
        raise ICEDShapeError(
            f"FY={fy_label!r} indicator {spec.api_key!r} value is not a list"
        )
    if len(values) != len(states):
        raise ICEDShapeError(
            f"FY={fy_label!r} indicator {spec.api_key!r}: values len={len(values)} "
            f"!= states len={len(states)}"
        )

    period = _fy_to_period(fy_label)
    rows: list[ParsedRow] = []
    for state_name, raw_value in zip(states, values, strict=True):
        entity_id = ENTITY_MAP.get(state_name)
        if entity_id is None:
            # Skip unknown sentinels like "Multiple States" / "Location TBD"
            # rather than failing — those aren't mappable to any geometry.
            continue
        v = coerce_numeric(raw_value)
        if v is None:
            continue
        rows.append(ParsedRow(entity_id=entity_id, time=period, value=v))

    return ParsedYear(
        indicator_id=spec.indicator_id, fy_label=fy_label, rows=tuple(rows)
    )
