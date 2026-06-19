"""Tests for load_iced_response (the staged-file decrypt dispatch).

The full-refresh ingest reads operator-staged ICED responses: plain JSON for
feeds like capacity-metatable, the CryptoJS AES envelope for feeds like
powerStatistics. ``load_iced_response`` decrypts only when the body is the
envelope (and ``decrypt`` is asked for), else parses plain JSON. The decrypt
itself is exercised by the crypto round-trip tests; here we pin the routing.
"""
from __future__ import annotations

import pytest

from yen_gov.canonical.adapters.iced_common import crypto
from yen_gov.canonical.adapters.iced_common.crypto import load_iced_response


def test_plain_json_list_str_and_bytes():
    assert load_iced_response("[1, 2, 3]", decrypt=True) == [1, 2, 3]
    assert load_iced_response(b'{"a": 1}', decrypt=True) == {"a": 1}
    assert load_iced_response('  \n[1]', decrypt=True) == [1]  # leading whitespace


def test_decrypt_false_never_decrypts_even_an_envelope():
    # With decrypt=False an envelope-looking string is just a plain JSON
    # string, returned as-is (no AES path).
    assert load_iced_response('"U2FsdGVkX1+abc=="', decrypt=False) == "U2FsdGVkX1+abc=="


def test_envelope_routes_to_decrypt_response(monkeypatch):
    seen = {}

    def _fake(body):
        seen["body"] = body
        return {"decrypted": True}

    monkeypatch.setattr(crypto, "decrypt_response", _fake)
    out = load_iced_response('"U2FsdGVkX1+abc=="', decrypt=True)

    assert out == {"decrypted": True}
    assert seen["body"].lstrip().startswith('"U2FsdGVkX1')


def test_non_envelope_with_decrypt_true_falls_back_to_json(monkeypatch):
    # decrypt=True but a plain payload -> must NOT call decrypt_response.
    def _boom(body):
        raise AssertionError("decrypt_response called on plain JSON")

    monkeypatch.setattr(crypto, "decrypt_response", _boom)
    assert load_iced_response('{"status": 1}', decrypt=True) == {"status": 1}
