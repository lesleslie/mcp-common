"""Tests for mcp_common.signing (Phase 4 / spec §4.11)."""
from __future__ import annotations

import json

from mcp_common.signing import SkillsSigner


def test_generate_then_sign_then_verify():
    signer = SkillsSigner.generate()
    payload = {"name": "test-skill", "version": "1.0.0"}
    sig = signer.sign(payload)
    assert isinstance(sig, str) and len(sig) > 0
    assert signer.verify(payload, sig) is True


def test_verify_rejects_tampered_payload():
    signer = SkillsSigner.generate()
    payload = {"name": "test-skill", "version": "1.0.0"}
    sig = signer.sign(payload)
    tampered = {"name": "test-skill", "version": "1.0.1"}
    assert signer.verify(tampered, sig) is False


def test_sign_then_verify_with_string_payload():
    signer = SkillsSigner.generate()
    payload = "skill body as string"
    sig = signer.sign(payload)
    assert signer.verify(payload, sig) is True


def test_sign_then_verify_with_bytes_payload():
    signer = SkillsSigner.generate()
    payload = b"binary-skill-body"
    sig = signer.sign(payload)
    assert signer.verify(payload, sig) is True


def test_dict_sign_uses_canonical_json():
    signer = SkillsSigner.generate()
    payload = {"b": 2, "a": 1}
    sig = signer.sign(payload)
    # Both {"a":1,"b":2} and {"b":2,"a":1} should produce the same sig
    # because _sign canonicalizes via sort_keys.
    assert signer.verify({"a": 1, "b": 2}, sig) is True
