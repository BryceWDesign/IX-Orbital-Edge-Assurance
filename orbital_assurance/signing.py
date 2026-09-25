"""Ed25519 signing utilities for evaluation evidence.

The bundled demo identities are deterministic so the example bundle is reproducible.
They are not secret and MUST NOT be used for operational trust. Production-like
evaluations should inject separately generated keys and protect private material.
"""
from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .core import canonical, require


@dataclass(frozen=True)
class SigningIdentity:
    name: str
    private_key: Ed25519PrivateKey

    @property
    def public_key(self) -> Ed25519PublicKey:
        return self.private_key.public_key()

    @property
    def public_key_raw(self) -> bytes:
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    @property
    def key_id(self) -> str:
        return hashlib.sha256(self.public_key_raw).hexdigest()

    def descriptor(self) -> dict[str, str]:
        return {
            "algorithm": "Ed25519",
            "identity": self.name,
            "key_id": self.key_id,
            "public_key_b64": base64.b64encode(self.public_key_raw).decode("ascii"),
        }


def deterministic_demo_identity(name: str) -> SigningIdentity:
    seed = hashlib.sha256(("IX-OEA-v2-demo-key::" + name).encode("utf-8")).digest()
    return SigningIdentity(name=name, private_key=Ed25519PrivateKey.from_private_bytes(seed))


def sign_payload(identity: SigningIdentity, payload: Any) -> dict[str, str]:
    signature = identity.private_key.sign(canonical(payload))
    return {
        **identity.descriptor(),
        "signature_b64": base64.b64encode(signature).decode("ascii"),
    }


def verify_signature(payload: Any, signature: dict[str, Any]) -> bool:
    require(signature.get("algorithm") == "Ed25519", "unsupported signature algorithm")
    raw_public = base64.b64decode(signature["public_key_b64"], validate=True)
    raw_sig = base64.b64decode(signature["signature_b64"], validate=True)
    require(hashlib.sha256(raw_public).hexdigest() == signature.get("key_id"), "signature key id mismatch")
    Ed25519PublicKey.from_public_bytes(raw_public).verify(raw_sig, canonical(payload))
    return True
