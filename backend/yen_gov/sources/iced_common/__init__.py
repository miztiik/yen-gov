"""Shared infrastructure for any ICED (NITI Aayog) ingest.

The single ICED API host (``https://icedapi.niti.gov.in`` and ``/v1``) backs
the entire dashboard at ``https://iced.niti.gov.in``. Every endpoint returns
the same envelope: a JSON-encoded base64 string carrying an OpenSSL/CryptoJS
``Salted__`` AES-256-CBC payload. The full reverse-engineering writeup -
algorithm, key derivation, where the passphrase lives in the public Angular
bundle, why this is obfuscation rather than security - is in
``docs/architecture/backend/iced-api.md``.

The legacy network client (``client.IcedClient``) was retired in B4-pt2.3
per parent plan section 21.4 ("network-fetch code is deleted; ingest reads
local TCPD / source CSV"). What remains is the pure-Python crypto / entity /
endpoint catalogue (decrypts are still useful when an operator hands a
captured ciphertext to a fixture-based reingest helper).

Public surface (post-pt2.3):

- :func:`crypto.decrypt_response` - decode the API's encrypted JSON payload.
- :data:`entities.ENTITY_MAP`    - ICED state-name -> ECI state-id mapping.
- :data:`endpoints.ENDPOINT_CATALOGUE` - 259-endpoint registry from bundle recon.
"""

from .crypto import (
    PASSPHRASE,
    ICEDShapeError,
    decrypt_cryptojs_openssl,
    decrypt_response,
)
from .entities import ENTITY_MAP, fy_to_period, coerce_numeric, lookup_entity
from . import parser_kit

__all__ = (
    "parser_kit",
    "PASSPHRASE",
    "ICEDShapeError",
    "decrypt_cryptojs_openssl",
    "decrypt_response",
    "ENTITY_MAP",
    "fy_to_period",
    "coerce_numeric",
    "lookup_entity",
)

