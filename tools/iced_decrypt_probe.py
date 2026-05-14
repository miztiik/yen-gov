"""Verify ICED API decryption: fetch one endpoint, decrypt with the OpenSSL/CryptoJS
"Salted__" envelope using the passphrase recovered from the bundle.
"""
from __future__ import annotations
import base64
import hashlib
import io
import json
import sys
from pathlib import Path

import httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PASSPHRASE = b"AHten@VP0W3R"
API = "https://icedapi.niti.gov.in"

# These are the endpoints we already saw fire from the agriculture page.
PROBES = [
    "/websiteLastUpdated",
    "/whatsNew?path=climate-and-environment%2Fghg-emissions%2Fagriculture",
    "/chart-title",
    "/climate-environment/ghg-emissions/energy",
    "/climate-environment/ghg-emissions/agriculture",  # guessed sibling
]


def evp_bytes_to_key(passphrase: bytes, salt: bytes, key_len: int = 32, iv_len: int = 16) -> tuple[bytes, bytes]:
    """OpenSSL EVP_BytesToKey with MD5, single iteration — matches CryptoJS default."""
    derived = b""
    last = b""
    while len(derived) < key_len + iv_len:
        last = hashlib.md5(last + passphrase + salt).digest()
        derived += last
    return derived[:key_len], derived[key_len:key_len + iv_len]


def decrypt_iced(payload: str) -> dict:
    raw = base64.b64decode(payload)
    if raw[:8] != b"Salted__":
        raise ValueError("Missing Salted__ prefix")
    salt = raw[8:16]
    ct = raw[16:]
    key, iv = evp_bytes_to_key(PASSPHRASE, salt)
    pt = unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(ct), AES.block_size)
    return json.loads(pt.decode("utf-8"))


def main() -> None:
    headers = {
        "User-Agent": "yen-gov/recon (+local; iced verification)",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://iced.niti.gov.in",
        "Referer": "https://iced.niti.gov.in/",
    }
    with httpx.Client(timeout=20.0, headers=headers) as cli:
        for path in PROBES:
            print(f"\n=== GET {API}{path} ===")
            try:
                r = cli.get(API + path)
            except Exception as e:
                print(f"  FETCH-FAIL: {type(e).__name__}: {e}")
                continue
            print(f"  status={r.status_code} ct={r.headers.get('content-type','')}")
            if r.status_code != 200:
                print(f"  body[:200]={r.text[:200]!r}")
                continue
            # Body looks like:  "U2FsdGVkX1+..."  (a JSON-encoded string)
            try:
                payload = r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text
                if isinstance(payload, str) and payload.startswith("U2FsdGVkX1"):
                    data = decrypt_iced(payload)
                    pretty = json.dumps(data, indent=2, ensure_ascii=False)
                    print(f"  DECRYPT-OK  payload-bytes={len(payload)} -> json-bytes={len(pretty)}")
                    print(f"  preview:\n{pretty[:1200]}")
                    if len(pretty) > 1200:
                        print(f"  ...(+{len(pretty)-1200} more bytes)")
                else:
                    print(f"  not-encrypted? body[:200]={str(payload)[:200]!r}")
            except Exception as e:
                print(f"  DECRYPT-FAIL: {type(e).__name__}: {e}  body[:120]={r.text[:120]!r}")


if __name__ == "__main__":
    main()
