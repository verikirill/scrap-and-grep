"""Password hashing with Argon2id.

Hashing takes tens of milliseconds of CPU by design, so it runs in a worker
thread and never blocks the event loop.
"""

import asyncio
from functools import lru_cache

from pwdlib import PasswordHash

PASSWORD_MIN_LENGTH = 10
# Argon2 accepts any length; the cap only stops a megabyte-sized "password"
# from being hashed.
PASSWORD_MAX_LENGTH = 128


@lru_cache
def _hasher() -> PasswordHash:
    return PasswordHash.recommended()


@lru_cache
def _decoy_hash() -> str:
    """A valid hash of a value nobody knows.

    Verifying against it costs as much as a real check, so the response time
    does not tell whether an address is registered.
    """
    return _hasher().hash("radar-decoy-" + "x" * 24)


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(_hasher().hash, password)


async def verify_password(password: str, stored: str | None) -> tuple[bool, str | None]:
    """Check a password. Returns (matches, new hash if the stored one is outdated)."""

    def check() -> tuple[bool, str | None]:
        if stored is None:
            _hasher().verify(password, _decoy_hash())
            return False, None
        return _hasher().verify_and_update(password, stored)

    return await asyncio.to_thread(check)
