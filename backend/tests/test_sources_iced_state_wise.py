"""Pure-parser tests for backend/yen_gov/sources/iced_state_wise/parsers.py.

The decryption helpers are exercised via a CryptoJS-format ciphertext
generated in-test (no network, no fixtures-on-disk). The extraction
helpers are exercised via in-memory dicts shaped exactly like the
decrypted ICED API response (verified against
.runtime/raw/iced/_sample_2024-25_all.json on 2026-05-14).
"""
from __future__ import annotations

import base64
import hashlib
import json

import pytest
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from yen_gov.sources.iced_state_wise.parsers import (
    ENTITY_MAP,
    ICEDShapeError,
    IndicatorSpec,
    PASSPHRASE,
    _evp_bytes_to_key,
    coerce_numeric,
    decrypt_cryptojs_openssl,
    decrypt_response,
    extract_rows,
)


# ---------------------------------------------------------------------------
# Decryption
# ---------------------------------------------------------------------------


def _encrypt_cryptojs_openssl(plaintext: bytes, passphrase: bytes = PASSPHRASE) -> str:
    """Inverse of decrypt_cryptojs_openssl — used to build test fixtures."""
    salt = b"\x01\x02\x03\x04\x05\x06\x07\x08"
    key, iv = _evp_bytes_to_key(passphrase, salt)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    body = cipher.encrypt(pad(plaintext, AES.block_size))
    return base64.b64encode(b"Salted__" + salt + body).decode()


def test_decrypt_roundtrip():
    plain = b'{"hello": "world", "n": 42}'
    enc = _encrypt_cryptojs_openssl(plain)
    out = decrypt_cryptojs_openssl(enc)
    assert out == plain


def test_decrypt_rejects_non_salted_payload():
    bad = base64.b64encode(b"NotSaltd" + b"\x00" * 24).decode()
    with pytest.raises(ICEDShapeError, match="Salted__"):
        decrypt_cryptojs_openssl(bad)


def test_decrypt_response_unwraps_outer_json_string():
    plain = b'{"data": {"states": ["All India"], "X": [1.0]}}'
    enc = _encrypt_cryptojs_openssl(plain)
    server_body = json.dumps(enc).encode()  # the server wraps the b64 string in quotes
    out = decrypt_response(server_body)
    assert out == {"data": {"states": ["All India"], "X": [1.0]}}


# ---------------------------------------------------------------------------
# coerce_numeric
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("475,211.80", 475211.80),
        ("1298817.28", 1298817.28),
        ("-0.94", -0.94),
        ("0", 0.0),
        (123, 123.0),
        (1.5, 1.5),
        ("N.A.", None),
        ("-", None),
        ("", None),
        (None, None),
        ("not a number", None),
    ],
)
def test_coerce_numeric(raw, expected):
    assert coerce_numeric(raw) == expected


# ---------------------------------------------------------------------------
# extract_rows
# ---------------------------------------------------------------------------


def _make_decrypted(states: list[str], series: dict[str, list]) -> dict:
    return {"data": {"states": states, **series}}


def test_extract_rows_basic_flat_list():
    decrypted = _make_decrypted(
        states=["All India", "Andhra Pradesh", "Bihar"],
        series={"Generation": ["1,873.0", "100.5", "-"]},
    )
    out = extract_rows(
        spec=IndicatorSpec(
            indicator_id="energy/state_electricity_generation_mu",
            api_key="Generation",
        ),
        fy_label="2023-24",
        decrypted=decrypted,
    )
    assert out.fy_label == "2023-24"
    rows = list(out.rows)
    assert [(r.entity_id, r.time, r.value) for r in rows] == [
        ("IN", "2023-04", 1873.0),
        ("S01", "2023-04", 100.5),
        # Bihar dropped (value was N.A. sentinel "-")
    ]


def test_extract_rows_handles_dict_subkey():
    decrypted = _make_decrypted(
        states=["All India", "Delhi"],
        series={"Installed Capacity*": {"data": ["2.5", "0.8"], "expand": {}}},
    )
    out = extract_rows(
        spec=IndicatorSpec(
            indicator_id="x/y", api_key="Installed Capacity*", api_key_subkey="data",
        ),
        fy_label="2024-25",
        decrypted=decrypted,
    )
    rows = list(out.rows)
    assert [(r.entity_id, r.value) for r in rows] == [("IN", 2.5), ("U05", 0.8)]


def test_extract_rows_skips_unmapped_entity_names():
    decrypted = _make_decrypted(
        states=["All India", "Multiple States", "Bihar"],
        series={"Generation": ["1.0", "2.0", "3.0"]},
    )
    out = extract_rows(
        spec=IndicatorSpec(indicator_id="x/y", api_key="Generation"),
        fy_label="2024-25",
        decrypted=decrypted,
    )
    eids = [r.entity_id for r in out.rows]
    assert eids == ["IN", "S04"]  # "Multiple States" silently skipped


def test_extract_rows_raises_on_missing_states_list():
    with pytest.raises(ICEDShapeError, match="states"):
        extract_rows(
            spec=IndicatorSpec(indicator_id="x/y", api_key="Generation"),
            fy_label="2024-25",
            decrypted={"data": {"Generation": [1.0]}},
        )


def test_extract_rows_raises_on_length_mismatch():
    decrypted = _make_decrypted(
        states=["All India", "Bihar"], series={"Generation": [1.0]}
    )
    with pytest.raises(ICEDShapeError, match="len="):
        extract_rows(
            spec=IndicatorSpec(indicator_id="x/y", api_key="Generation"),
            fy_label="2024-25",
            decrypted=decrypted,
        )


def test_extract_rows_raises_on_missing_indicator_key():
    decrypted = _make_decrypted(states=["All India"], series={"Other": [1.0]})
    with pytest.raises(ICEDShapeError, match="missing"):
        extract_rows(
            spec=IndicatorSpec(indicator_id="x/y", api_key="Generation"),
            fy_label="2024-25",
            decrypted=decrypted,
        )


def test_extract_rows_period_format():
    decrypted = _make_decrypted(states=["All India"], series={"Generation": [1.0]})
    out = extract_rows(
        spec=IndicatorSpec(indicator_id="x/y", api_key="Generation"),
        fy_label="2017-18",
        decrypted=decrypted,
    )
    assert out.rows[0].time == "2017-04"


def test_extract_rows_rejects_bad_fy_label():
    decrypted = _make_decrypted(states=["All India"], series={"Generation": [1.0]})
    with pytest.raises(ICEDShapeError, match="FY label"):
        extract_rows(
            spec=IndicatorSpec(indicator_id="x/y", api_key="Generation"),
            fy_label="not a year",
            decrypted=decrypted,
        )


# ---------------------------------------------------------------------------
# ENTITY_MAP shape sanity (catches a future ICED rename early)
# ---------------------------------------------------------------------------


def test_entity_map_contains_all_36_entities_plus_all_india():
    assert "All India" in ENTITY_MAP and ENTITY_MAP["All India"] == "IN"
    state_codes = {v for v in ENTITY_MAP.values() if v.startswith("S")}
    ut_codes = {v for v in ENTITY_MAP.values() if v.startswith("U")}
    assert len(state_codes) == 28
    assert len(ut_codes) == 8


def test_entity_map_handles_iced_delhi_naming_quirk():
    # ICED uses "Delhi"; ECI reference data uses "NCT of Delhi" (U05).
    assert ENTITY_MAP["Delhi"] == "U05"
