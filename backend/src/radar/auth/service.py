"""Registration, sign-in, guest accounts and the administrator role."""

import re
import uuid
from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from radar.auth import DEMO_EMAIL, GUEST_DOMAIN
from radar.auth.passwords import hash_password, verify_password
from radar.auth.shared import is_service_address
from radar.avatars import random_preset
from radar.db.models import Profile, User

# Deliberately loose: the address is an identifier here, no mail is sent to it.
_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
EMAIL_MAX_LENGTH = 254


class EmailTakenError(Exception):
    pass


def normalize_email(raw: str) -> str | None:
    """Trimmed and lowercased address, or None when it does not look like one."""
    email = raw.strip().lower()
    if len(email) > EMAIL_MAX_LENGTH or not _EMAIL_RE.fullmatch(email):
        return None
    # Guest and shared addresses are made up by the service; nobody may
    # register one or sign in to it with a password.
    if is_service_address(email):
        return None
    return email


async def register(session: AsyncSession, *, email: str, password: str, display_name: str) -> User:
    """Create an account. Two concurrent registrations of one address cannot
    both succeed: the unique index decides, not a check made beforehand.

    A new account is never an administrator; that role is granted by an
    operator (`radar grant-admin`), not by the address someone signs up with.
    """
    password_hash = await hash_password(password)
    row = (
        await session.execute(
            insert(User)
            .values(
                email=email,
                password_hash=password_hash,
                display_name=display_name,
                avatar_preset=random_preset(),
            )
            .on_conflict_do_nothing(index_elements=["email"])
            .returning(User)
        )
    ).scalar_one_or_none()
    if row is None:
        raise EmailTakenError(email)
    return row


async def authenticate(session: AsyncSession, *, email: str, password: str) -> User | None:
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    # The check runs even for an unknown address, against a decoy hash, so the
    # two cases take the same time.
    matches, upgraded = await verify_password(password, user.password_hash if user else None)
    if user is None or not matches:
        return None
    if upgraded is not None:
        user.password_hash = upgraded
    return user


async def create_guest(session: AsyncSession) -> User:
    """A throwaway account with copies of the example profiles.

    Every visitor who presses "try without registering" gets their own guest,
    so nobody can change or read what another visitor did. Guests have no
    password and are deleted by housekeeping after a day.
    """
    guest = User(
        email=f"guest-{uuid.uuid4().hex}@{GUEST_DOMAIN}",
        display_name="Гость",
        is_demo=True,
        avatar_preset=random_preset(),
    )
    session.add(guest)
    await session.flush()
    template = await session.scalar(select(User.id).where(User.email == DEMO_EMAIL))
    if template is not None:
        examples = (
            await session.execute(
                select(Profile)
                .where(Profile.user_id == template)
                .order_by(Profile.created_at, Profile.id)
            )
        ).scalars()
        for example in examples:
            session.add(
                Profile(
                    user_id=guest.id,
                    name=example.name,
                    spec=example.spec,
                    icon=example.icon,
                    color=example.color,
                )
            )
        await session.flush()
    return guest


async def purge_guests(session: AsyncSession, created_before: datetime) -> int:
    """Delete guest accounts older than the cutoff, with everything they own."""
    result = await session.execute(
        delete(User)
        .where(User.is_demo, User.email != DEMO_EMAIL, User.created_at < created_before)
        .returning(User.id)
    )
    return len(result.all())


async def set_admin(session: AsyncSession, email: str, *, is_admin: bool) -> bool:
    """Grant or revoke the administrator role. Returns False for an unknown address."""
    result = await session.execute(
        update(User)
        .where(User.email == email.strip().lower(), User.is_demo.is_(False))
        .values(is_admin=is_admin)
        .returning(User.id)
    )
    return result.first() is not None
