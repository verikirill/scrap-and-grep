"""A finished digest sent by email, as the reader's own letter or to a colleague."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from radar import mail
from radar.api.deps import CurrentUser, SessionDep, SettingsDep, user_rate_limit
from radar.auth import DEMO_EMAIL, GUEST_DOMAIN
from radar.auth.sessions import AuthUser
from radar.config import Settings
from radar.logging import get_logger
from radar.store import digests as digest_store
from radar.views import digest_view

router = APIRouter(tags=["mail"])
log = get_logger(__name__)

_mail_limit = Depends(user_rate_limit("mail", lambda settings: settings.mail_rate_limit_per_minute))


class MailState(BaseModel):
    # False when the server has no mail server set: the button is not shown.
    available: bool
    # The reader's own address, offered first; none for a guest.
    default_to: str | None = None
    # Domains the company allows; empty allows any.
    domains: list[str] = []


class MailRequest(BaseModel):
    # None sends the digest to the reader's own address.
    to: str | None = Field(default=None, max_length=mail.MAX_ADDRESS)


class MailSent(BaseModel):
    to: str


def _own_address(user: AuthUser) -> str | None:
    """A guest's and the demo account's addresses are not real mailboxes."""
    if user.email.endswith(f"@{GUEST_DOMAIN}") or user.email == DEMO_EMAIL:
        return None
    return user.email


def _state(user: AuthUser, settings: Settings) -> MailState:
    if not settings.smtp_host:
        return MailState(available=False)
    return MailState(
        available=True,
        default_to=_own_address(user),
        domains=sorted(mail.allowed_domains(settings)),
    )


@router.get("/digests/{digest_id}/mail")
async def get_mail(
    digest_id: uuid.UUID, session: SessionDep, settings: SettingsDep, user: CurrentUser
) -> MailState:
    """Whether the digest can be sent from this server, and where to by default."""
    if await digest_store.get(session, digest_id, user_id=user.id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Дайджест не найден.")
    return _state(user, settings)


@router.post("/digests/{digest_id}/mail", dependencies=[_mail_limit])
async def send_mail(
    digest_id: uuid.UUID,
    session: SessionDep,
    settings: SettingsDep,
    user: CurrentUser,
    payload: MailRequest | None = None,
) -> MailSent:
    """Send a finished digest: HTML and plain text of its Markdown, the DOCX attached."""
    if not settings.smtp_host:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="Почта на этом сервере не настроена."
        )
    digest = await digest_store.get(session, digest_id, user_id=user.id, full=True)
    if digest is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Дайджест не найден.")
    if digest.status != digest_store.STATUS_DONE:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Дайджест ещё не готов.")
    to = (payload.to if payload is not None else None) or _own_address(user)
    if not to:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Укажите адрес почты.")
    hidden = await digest_store.hidden_card_fields(session, digest)
    try:
        message = mail.letter(digest_view(digest, hidden), to, settings)
    except mail.MailError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    try:
        await mail.send(message, settings)
    except mail.MailError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    # The domain, not the address: logs are read by more people than letters.
    log.info("digest_mailed", digest_id=str(digest_id), domain=to.rsplit("@", 1)[1])
    return MailSent(to=to)
