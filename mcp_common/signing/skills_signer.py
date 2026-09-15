"""Ed25519 signing/verification for skill publication.

Per spec §4.11 — ``Crackerjack`` signs skills before publication so
downstream consumers can verify provenance. The signer is a small
class wrapper around the ``cryptography`` library's ed25519 primitives.

Refs:
- docs/superpowers/specs/2026-09-14-dhara-mcp-decomposition-design.md §4.11
- docs/audits/2026-09-15-decomposition-final-review.md §2.1 W4
"""

from __future__ import annotations

import base64
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import BaseModel, Field


class SkillsSigner(BaseModel):
    """Ed25519 signer for skill canonical schemas.

    Owns a private/public key pair. ``sign(payload)`` returns a base64
    signature suitable for inclusion in ``SkillCanonicalSchema.signature``.
    ``verify(payload, signature)`` checks a signature against the
    public key.
    """

    private_key_b64: str = Field(
        ..., description="Base64-encoded ed25519 private key seed"
    )
    public_key_b64: str = Field(..., description="Base64-encoded ed25519 public key")

    @classmethod
    def generate(cls) -> SkillsSigner:
        """Generate a fresh keypair."""
        priv = Ed25519PrivateKey.generate()
        pub = priv.public_key()
        return cls(
            private_key_b64=base64.b64encode(priv.private_bytes_raw()).decode("ascii"),
            public_key_b64=base64.b64encode(pub.public_bytes_raw()).decode("ascii"),
        )

    def _private_key(self) -> Ed25519PrivateKey:
        return Ed25519PrivateKey.from_private_bytes(
            base64.b64decode(self.private_key_b64)
        )

    def _public_key(self) -> Ed25519PublicKey:
        return Ed25519PublicKey.from_public_bytes(base64.b64decode(self.public_key_b64))

    def sign(self, payload: dict[str, Any] | str | bytes) -> str:
        """Sign a payload; return base64-encoded signature."""
        if isinstance(payload, dict):
            import json

            payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        sig = self._private_key().sign(payload)
        return base64.b64encode(sig).decode("ascii")

    def verify(self, payload: dict[str, Any] | str | bytes, signature_b64: str) -> bool:
        """Verify a signature; return True on success, False on failure."""
        if isinstance(payload, dict):
            import json

            payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        try:
            self._public_key().verify(base64.b64decode(signature_b64), payload)
            return True
        except InvalidSignature:
            return False


__all__ = ["SkillsSigner"]
