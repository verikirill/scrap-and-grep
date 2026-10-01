"""Bot tokens at rest: encrypted with a key derived from RADAR_SECRET_KEY.

A bot token is a password to the bot: whoever has it can post as the bot to
every channel it administers. It is encrypted before it reaches the
database, never returned by the API, and kept out of logs.
"""

import base64
import re

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from radar.config import get_settings

TOKEN_RE = re.compile(r"^(\d{5,15}):[A-Za-z0-9_-]{30,64}$")
_INFO = b"radar telegram bot tokens v1"


class SecretKeyMissing(RuntimeError):
    """RADAR_SECRET_KEY is not set, so tokens cannot be stored or read."""


# The secret is meant to be random (openssl rand -base64 32); this only
# stops an obviously short one.
MIN_SECRET_CHARS = 16


class TokenUnreadable(RuntimeError):
    """The stored token was encrypted with another key."""


def _fernet() -> Fernet:
    secret = get_settings().secret_key
    value = secret.get_secret_value() if secret is not None else ""
    if len(value) < MIN_SECRET_CHARS:
        raise SecretKeyMissing(f"RADAR_SECRET_KEY must be set ({MIN_SECRET_CHARS}+ characters)")
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_INFO).derive(value.encode())
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_token(token: str) -> str:
    return _fernet().encrypt(token.encode()).decode()


def decrypt_token(blob: str) -> str:
    try:
        return _fernet().decrypt(blob.encode()).decode()
    except InvalidToken as exc:
        raise TokenUnreadable("the token was stored under another RADAR_SECRET_KEY") from exc


def token_hint(token: str) -> str:
    """What the interface shows of a token: the bot id and the last characters."""
    bot_id, _, secret = token.partition(":")
    return f"{bot_id}:…{secret[-4:]}"
