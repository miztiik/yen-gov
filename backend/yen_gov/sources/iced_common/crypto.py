"""ICED CryptoJS-OpenSSL AES-256-CBC decryption.

What the API returns
--------------------
Every endpoint under ``https://icedapi.niti.gov.in`` (and ``/v1``) responds
with HTTP 200 and a body of the form ``"U2FsdGVkX1...=="`` — a JSON string
literal whose contents are base64. Decode that base64 and the first eight
bytes are the ASCII ``Salted__`` magic; the next eight are the salt; the rest
is AES-256-CBC ciphertext with PKCS#7 padding.

Key derivation
--------------
OpenSSL ``EVP_BytesToKey`` with MD5, single iteration. This is what
``CryptoJS.AES.decrypt(b64, "passphrase")`` does internally when given a
string passphrase rather than a raw key. Replicated here in ~10 lines so we
have no JS runtime dependency.

Where the passphrase lives
--------------------------
Hardcoded in the site's Angular main bundle as ``KEY:"AHten@VP0W3R"`` (env
config module, observed offset 5,815,108 in
``main.cb0bb1d44638969b.js``, recon 2026-05-14). The bundle is shipped to
every browser that opens the site, so the passphrase has the same secrecy
properties as a hardcoded JS constant: none. The decryption call site is
``extractData(i){const u=b.AES.decrypt(i,U);return JSON.parse(u.toString(b.enc.Utf8))||{}}``.

This is obfuscation, not security. We use it because (a) the site
itself trusts client-side decryption, (b) all data shown in the site is
public, (c) reproducing the (publicly published) algorithm is more honest
than scraping the rendered DOM. Full rationale + ethics discussion lives in
``docs/architecture/backend/iced-api.md`` and ADR-0028.

Test vector
-----------
``decrypt_response(b'"U2FsdGVkX1+..."')`` for ``/websiteLastUpdated`` returns
``{"status":1,"data":[{"id":1,"updated_at":"2026-04-28T..."}]}`` (verified
2026-05-14).
"""
from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad


PASSPHRASE: bytes = b"AHten@VP0W3R"
"""Hardcoded in the Angular bundle. See module docstring for provenance."""


class ICEDShapeError(ValueError):
    """The API response no longer matches what we expect.

    Raised on missing ``Salted__`` prefix, AES unpad failures, non-string
    outer envelopes, or downstream shape violations. We fail loudly rather
    than silently emit zero rows: a quiet coverage drop would lie to
    citizens.
    """


def _evp_bytes_to_key(
    passphrase: bytes,
    salt: bytes,
    *,
    key_len: int = 32,
    iv_len: int = 16,
) -> tuple[bytes, bytes]:
    """OpenSSL ``EVP_BytesToKey`` with MD5 (the CryptoJS default).

    Iterates ``MD5(prev || passphrase || salt)`` until ``key_len + iv_len``
    bytes are produced; first ``key_len`` are the AES key, next ``iv_len``
    are the IV. Single iteration, no PBKDF2 iteration count.
    """
    out = b""
    prev = b""
    while len(out) < key_len + iv_len:
        prev = hashlib.md5(prev + passphrase + salt).digest()
        out += prev
    return out[:key_len], out[key_len : key_len + iv_len]


def decrypt_cryptojs_openssl(
    b64_ciphertext: str,
    passphrase: bytes = PASSPHRASE,
) -> bytes:
    """Decrypt one base64 CryptoJS-OpenSSL envelope to its plaintext bytes."""
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
    except (ValueError, KeyError) as exc:
        raise ICEDShapeError(
            f"AES decrypt/unpad failed ({exc!r}). Either the passphrase has "
            f"rotated upstream (was {PASSPHRASE!r} as of 2026-05-14) or the "
            f"payload format changed."
        )


def decrypt_response(server_body: bytes | str) -> Any:
    """Decrypt and JSON-decode the full API response body.

    The server returns a JSON string literal (the ciphertext wrapped in
    double quotes). Accepts either the raw HTTP body bytes or the already-
    parsed string form. Returns whatever JSON structure was inside —
    typically ``{"status": 1, "data": ...}`` but a few endpoints return a
    bare list or scalar.
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
