"""Registration, sign-in, guest access and the current account."""

import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from radar.api.deps import (
    CacheDep,
    CurrentUser,
    OptionalUser,
    SessionDep,
    SettingsDep,
    rate_limit,
    user_rate_limit,
)
from radar.api.schemas import AvatarOut, LoginIn, MeOut, PasswordIn, RegisterIn, UserOut
from radar.api.uploads import read_limited
from radar.auth import service
from radar.auth import sessions as auth_sessions
from radar.auth.passwords import verify_password
from radar.avatars import MAX_BYTES as AVATAR_MAX_BYTES
from radar.avatars import AvatarError, normalize
from radar.config import Settings
from radar.db.models import ForgottenReader, Profile, Resume, User, UserAvatar
from radar.events import enabled as events_enabled
from radar.logging import get_logger
from radar.recsys.service import forget_taste
from radar.text import stable_hash

router = APIRouter(prefix="/auth", tags=["auth"])
log = get_logger(__name__)

_auth_limit = Depends(rate_limit("auth", lambda settings: settings.auth_rate_limit_per_minute))
# Decoding a picture costs CPU: a few uploads a minute is plenty.
_avatar_limit = Depends(
    user_rate_limit("avatar", lambda settings: settings.resume_rate_limit_per_minute)
)
AVATAR_PATH = "/api/v1/auth/me/avatar"
_DECODING = asyncio.Semaphore(2)

# One wording for an unknown address and a wrong password: the answer must not
# reveal which addresses are registered.
_BAD_CREDENTIALS = "Неверная почта или пароль."
_TOO_MANY_ATTEMPTS = HTTPException(
    status.HTTP_429_TOO_MANY_REQUESTS,
    detail="Слишком много неудачных попыток входа, повторите через минуту.",
    headers={"Retry-After": "60"},
)


def _set_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        auth_sessions.COOKIE_NAME,
        token,
        max_age=settings.session_ttl_days * 24 * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        auth_sessions.COOKIE_NAME,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_admin=user.is_admin,
        is_demo=user.is_demo,
    )


@router.post("/register", status_code=status.HTTP_201_CREATED, dependencies=[_auth_limit])
async def register(
    payload: RegisterIn, response: Response, session: SessionDep, settings: SettingsDep
) -> UserOut:
    if not settings.registration_open:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Регистрация закрыта.")
    email = service.normalize_email(payload.email)
    if email is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Проверьте адрес почты.")
    try:
        user = await service.register(
            session,
            email=email,
            password=payload.password,
            display_name=payload.display_name.strip(),
        )
    except service.EmailTakenError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Аккаунт с такой почтой уже есть."
        ) from exc
    _set_cookie(
        response, await auth_sessions.start(session, user, settings.session_ttl_days), settings
    )
    log.info("user_registered", user_id=str(user.id))
    return _user_out(user)


@router.post("/login", dependencies=[_auth_limit])
async def login(
    payload: LoginIn,
    response: Response,
    session: SessionDep,
    cache: CacheDep,
    settings: SettingsDep,
) -> UserOut:
    email = service.normalize_email(payload.email)
    if email is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=_BAD_CREDENTIALS)
    # Only failed attempts count against an address, so its owner, who knows
    # the password, is not locked out by someone else's guessing.
    failures = f"auth-email:{stable_hash(email)}"
    if await cache.is_over_limit(failures, settings.auth_rate_limit_per_minute):
        raise _TOO_MANY_ATTEMPTS
    user = await service.authenticate(session, email=email, password=payload.password)
    if user is None:
        await cache.hit_rate_limit(failures, settings.auth_rate_limit_per_minute)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=_BAD_CREDENTIALS)
    _set_cookie(
        response, await auth_sessions.start(session, user, settings.session_ttl_days), settings
    )
    return _user_out(user)


@router.post("/demo", dependencies=[_auth_limit])
async def demo_login(response: Response, session: SessionDep, settings: SettingsDep) -> UserOut:
    """Enter as a guest: a fresh throwaway account with the example profiles.

    Lets a reviewer try everything without registering, without seeing or
    changing what other visitors did. Off when `RADAR_DEMO_LOGIN=false`.
    """
    if not settings.demo_login:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Вход без регистрации отключён.")
    guest = await service.create_guest(session)
    _set_cookie(
        response, await auth_sessions.start(session, guest, settings.session_ttl_days), settings
    )
    log.info("guest_created", user_id=str(guest.id))
    return _user_out(guest)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request, session: SessionDep, cache: CacheDep, settings: SettingsDep
) -> Response:
    token = request.cookies.get(auth_sessions.COOKIE_NAME)
    if token:
        await auth_sessions.end(session, cache, token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_cookie(response, settings)
    return response


@router.get("/me")
async def me(user: OptionalUser, session: SessionDep) -> MeOut | None:
    """Who is signed in. A visitor gets `null`, not an error: "nobody" is a
    normal answer to this question."""
    if user is None:
        return None
    profiles = await session.scalar(
        select(func.count()).select_from(Profile).where(Profile.user_id == user.id)
    )
    resume_status = await session.scalar(select(Resume.status).where(Resume.user_id == user.id))
    avatar_at = await session.scalar(
        select(UserAvatar.updated_at).where(UserAvatar.user_id == user.id)
    )
    return MeOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_admin=user.is_admin,
        is_demo=user.is_demo,
        profiles=int(profiles or 0),
        resume_status=resume_status,
        avatar_url=_avatar_url(avatar_at),
    )


def _avatar_url(updated_at: datetime | None) -> str | None:
    # A new picture gets a new address, so the old one may be cached for good.
    return f"{AVATAR_PATH}?v={int(updated_at.timestamp() * 1_000_000)}" if updated_at else None


@router.put("/me/avatar", dependencies=[_avatar_limit])
async def set_avatar(request: Request, user: CurrentUser, session: SessionDep) -> AvatarOut:
    """Take a picture as the raw request body and keep a small square copy of it."""
    data = await read_limited(
        request, AVATAR_MAX_BYTES, f"Картинка больше {AVATAR_MAX_BYTES // 1_000_000} МБ."
    )
    try:
        # Decoding is CPU work: off the event loop, other requests keep moving,
        # and only a couple at a time, so a burst of uploads cannot eat the memory.
        async with _DECODING:
            image = await asyncio.to_thread(normalize, data)
    except AvatarError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc
    values = {"image": image, "updated_at": func.now()}
    updated_at = await session.scalar(
        insert(UserAvatar)
        .values(user_id=user.id, **values)
        .on_conflict_do_update(index_elements=["user_id"], set_=values)
        .returning(UserAvatar.updated_at)
    )
    await session.commit()
    return AvatarOut(avatar_url=_avatar_url(updated_at))


@router.delete("/me/avatar", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_avatar_limit])
async def delete_avatar(user: CurrentUser, session: SessionDep) -> Response:
    await session.execute(delete(UserAvatar).where(UserAvatar.user_id == user.id))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me/avatar")
async def get_avatar(user: CurrentUser, session: SessionDep) -> Response:
    """The signed-in reader's own picture; nobody else's is served."""
    image = await session.scalar(select(UserAvatar.image).where(UserAvatar.user_id == user.id))
    if image is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Картинки нет.")
    return Response(
        content=image,
        media_type="image/webp",
        # The address carries the version: the browser may keep it as long as it likes.
        headers={
            "Cache-Control": "private, max-age=31536000, immutable",
            # One browser, two accounts: the cookie decides whose picture it is.
            "Vary": "Cookie",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/me/delete", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_auth_limit])
async def delete_account(
    payload: PasswordIn,
    user: CurrentUser,
    session: SessionDep,
    cache: CacheDep,
    settings: SettingsDep,
) -> Response:
    """Delete the account with everything it owns: profiles, digests, the
    resume facts, every recorded signal and its events. Asks for the password again; a
    guest has none and is deleted at once."""
    if not user.is_demo:
        stored = await session.scalar(select(User.password_hash).where(User.id == user.id))
        matches, _ = await verify_password(payload.password, stored)
        if not matches:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Неверный пароль.")
    await auth_sessions.end_all(session, cache, user.id)
    # Owned rows go with the account through ON DELETE CASCADE.
    await session.execute(delete(User).where(User.id == user.id))
    if events_enabled():
        # In the same transaction: the request to forget the reader's events
        # cannot be lost. The event writer carries it out within a minute.
        session.add(ForgottenReader(user_id=user.id))
    await session.commit()
    await forget_taste(cache, user.id)
    log.info("user_deleted", user_id=str(user.id))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_cookie(response, settings)
    return response
