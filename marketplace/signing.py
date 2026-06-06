from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


DEFAULT_KEY_DIR = Path(__file__).resolve().parent / "keys"
PRIVATE_KEY_NAME = "marouba_ed25519_private.pem"
PUBLIC_KEY_NAME = "marouba_ed25519_public.pem"


def default_private_key_path() -> Path:
    return Path(os.environ.get("MAROUBA_SIGNING_KEY", DEFAULT_KEY_DIR / PRIVATE_KEY_NAME))


def public_key_path_for(private_key_path: str | Path | None = None) -> Path:
    if private_key_path is None:
        private_key_path = default_private_key_path()
    return Path(private_key_path).with_name(PUBLIC_KEY_NAME)


def generate_keypair(key_dir: str | Path | None = None) -> tuple[Path, Path]:
    if key_dir is None:
        private_path = default_private_key_path()
        key_dir = private_path.parent
    else:
        key_dir = Path(key_dir)
        private_path = key_dir / PRIVATE_KEY_NAME
    key_dir = Path(key_dir)
    key_dir.mkdir(parents=True, exist_ok=True)
    public_path = private_path.with_name(PUBLIC_KEY_NAME)

    if private_path.exists() and public_path.exists():
        return private_path, public_path

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    private_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return private_path, public_path


def sign_workflow(workflow_path: str | Path, private_key_path: str | Path | None = None) -> Path:
    workflow_path = Path(workflow_path)
    if private_key_path is None:
        private_key_path, _ = generate_keypair()
    private_key = load_private_key(private_key_path)
    public_key = private_key.public_key()
    signature = private_key.sign(workflow_path.read_bytes())

    sig_path = workflow_path.with_suffix(workflow_path.suffix + ".sig")
    sig_path.write_text(
        json.dumps(
            {
                "algorithm": "Ed25519",
                "public_key": b64(
                    public_key.public_bytes(
                        encoding=serialization.Encoding.Raw,
                        format=serialization.PublicFormat.Raw,
                    )
                ),
                "signature": b64(signature),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return sig_path


def verify_workflow(workflow_path: str | Path, sig_path: str | Path) -> bool:
    workflow_path = Path(workflow_path)
    sig_path = Path(sig_path)
    if not workflow_path.exists() or not sig_path.exists():
        return False

    try:
        payload = json.loads(sig_path.read_text(encoding="utf-8"))
        if payload.get("algorithm") != "Ed25519":
            return False
        trusted_public_path = public_key_path_for()
        if not trusted_public_path.exists():
            return False
        trusted_public_key = load_public_key(trusted_public_path)
        trusted_public_bytes = trusted_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        if trusted_public_bytes != unb64(payload["public_key"]):
            return False
        public_key = Ed25519PublicKey.from_public_bytes(trusted_public_bytes)
        public_key.verify(unb64(payload["signature"]), workflow_path.read_bytes())
        return True
    except (InvalidSignature, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False


def load_private_key(private_key_path: str | Path) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(Path(private_key_path).read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("Private key is not Ed25519")
    return key


def load_public_key(public_key_path: str | Path) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(Path(public_key_path).read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError("Public key is not Ed25519")
    return key


def b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def unb64(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"))
