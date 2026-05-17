"""Shared infrastructure for any ICED (NITI Aayog) ingest.

The single ICED API host (``https://icedapi.niti.gov.in`` and ``/v1``) backs
the entire dashboard at ``https://iced.niti.gov.in``. Every endpoint returns
the same envelope: a JSON-encoded base64 string carrying an OpenSSL/CryptoJS
``Salted__`` AES-256-CBC payload. The full reverse-engineering writeup —
algorithm, key derivation, where the passphrase lives in the public Angular
bundle, why this is obfuscation rather than security — is in
``docs/architecture/backend/iced-api.md``.

This package keeps that one piece of knowledge in one place so per-page
adapters (state-wise-deep-dive, agriculture-ghg, plant registry, etc.) only
have to choose endpoints and write parsers — never re-derive the crypto
or the entity mapping.

Public surface:

- :func:`crypto.decrypt_response` — decode the API's encrypted JSON payload.
- :class:`client.IcedClient`     — fetch + cache + decrypt one endpoint.
- :data:`entities.ENTITY_MAP`    — ICED state-name → ECI state-id mapping.
- :data:`endpoints.ENDPOINT_CATALOGUE` — 259-endpoint registry from bundle recon.
"""

from .crypto import (
    PASSPHRASE,
    ICEDShapeError,
    decrypt_cryptojs_openssl,
    decrypt_response,
)
from .client import IcedClient, ICEDFetchError
from .entities import ENTITY_MAP, fy_to_period, coerce_numeric, lookup_entity
from . import parser_kit

__all__ = (
    "parser_kit",
    "PASSPHRASE",
    "ICEDShapeError",
    "ICEDFetchError",
    "decrypt_cryptojs_openssl",
    "decrypt_response",
    "IcedClient",
    "ENTITY_MAP",
    "fy_to_period",
    "coerce_numeric",
    "lookup_entity",
)
