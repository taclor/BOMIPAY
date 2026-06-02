import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from ..config import settings


def _provider_key() -> bytes:
    raw = settings.provider_encryption_key or settings.secret_key
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_secret(value: str) -> str:
    token = Fernet(_provider_key()).encrypt(value.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret(token: str) -> str:
    try:
        plaintext = Fernet(_provider_key()).decrypt(token.encode("utf-8"))
        return plaintext.decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt provider secret") from exc
