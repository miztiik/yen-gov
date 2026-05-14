"""Probe ICED state-wise deep-dive API and decrypt the CryptoJS payload.

Discovery (recorded 2026-05-14 via integrated browser):

* Endpoint: https://icedapi.niti.gov.in/analytics/stateWiseDeepDive
  Query: year=YYYY-YY&state=Comma,Separated,State,Names
  Returns: a JSON-encoded **string** -- a CryptoJS OpenSSL-format
  AES-256-CBC ciphertext, base64-encoded, prefixed with "Salted__".
* Decryption passphrase (extracted from main.cb0bb1d44638969b.js,
  module 92340 / N.KEY): "AHten@VP0W3R".

Why CryptoJS OpenSSL format:
  base64-decoded payload starts with the 8 bytes "Salted__" followed by
  an 8-byte salt, then ciphertext. Key+IV derived via OpenSSL
  EVP_BytesToKey with MD5, AES-256 key (32 bytes) + IV (16 bytes).
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import sys
import urllib.parse
import urllib.request

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PASSPHRASE = b"AHten@VP0W3R"


def _evp_bytes_to_key(passphrase: bytes, salt: bytes, key_len: int = 32, iv_len: int = 16) -> tuple[bytes, bytes]:
    """OpenSSL EVP_BytesToKey using MD5 (CryptoJS default)."""
    out = b""
    prev = b""
    while len(out) < key_len + iv_len:
        prev = hashlib.md5(prev + passphrase + salt).digest()
        out += prev
    return out[:key_len], out[key_len : key_len + iv_len]


def decrypt_cryptojs_openssl(b64_ciphertext: str, passphrase: bytes = PASSPHRASE) -> bytes:
    raw = base64.b64decode(b64_ciphertext)
    if raw[:8] != b"Salted__":
        raise ValueError(f"missing OpenSSL Salted__ prefix; got {raw[:16]!r}")
    salt = raw[8:16]
    body = raw[16:]
    key, iv = _evp_bytes_to_key(passphrase, salt)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(body), AES.block_size)


def fetch_deep_dive(year: str, states: list[str]) -> dict:
    qs = urllib.parse.urlencode({"year": year, "state": ",".join(states)}, quote_via=urllib.parse.quote)
    url = f"https://icedapi.niti.gov.in/analytics/stateWiseDeepDive?{qs}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Origin": "https://iced.niti.gov.in",
            "Referer": "https://iced.niti.gov.in/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
            ),
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
    # Server returns a JSON-quoted string; strip the surrounding quotes via json.loads.
    ciphertext = json.loads(body)
    if not isinstance(ciphertext, str):
        return {"_raw": ciphertext}  # already plaintext JSON?
    plain = decrypt_cryptojs_openssl(ciphertext)
    return json.loads(plain)


def main() -> None:
    import pathlib

    states = [
        "All India",
        "Andaman and Nicobar Islands", "Andhra Pradesh", "Arunachal Pradesh", "Assam",
        "Bihar", "Chandigarh", "Chhattisgarh",
        "Dadra and Nagar Haveli and Daman and Diu",
        "Delhi", "Goa", "Gujarat", "Haryana", "Himachal Pradesh",
        "Jammu and Kashmir", "Jharkhand", "Karnataka", "Kerala",
        "Lakshadweep", "Ladakh", "Madhya Pradesh", "Maharashtra",
        "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha",
        "Puducherry", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
        "Telangana", "Tripura", "Uttarakhand", "Uttar Pradesh", "West Bengal",
    ]
    out_dir = pathlib.Path(".runtime/raw/iced")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"FY 2024-25, ALL {len(states)} entities")
    data = fetch_deep_dive("2024-25", states)
    target = out_dir / "_sample_2024-25_all.json"
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {target.as_posix()}  ({target.stat().st_size:,} bytes)")

    payload = data.get("data", data) if isinstance(data, dict) else data
    if isinstance(payload, dict):
        returned_states = payload.get("states")
        print(f"states in response: len={len(returned_states) if returned_states else 'N/A'}")
        if returned_states:
            missing = [s for s in states if s not in returned_states]
            extra = [s for s in returned_states if s not in states]
            print(f"missing: {missing}")
            print(f"extra:   {extra}")
        # Sample one indicator full row
        gdp = payload.get("GDP (Base: 2011-12) Constant Price")
        if gdp:
            print(f"\nGDP constant len={len(gdp)}, sample first 6 = {gdp[:6]}")


if __name__ == "__main__":
    main()
