"""Registration, sign-in, guest and shared accounts, and the current account."""

import asyncio
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from radar.api.deps import (
    CacheDep,
    CurrentUser,
    OptionalUser,
    SessionDep,
    SettingsDep,
    rate_limit,
    user_rate_limit,
)
from radar.api.schemas import (
    AvatarOut,
    AvatarPresetIn,
    FeedOrder,
    FeedView,
    LoginIn,
    MeOut,
    OnboardedOut,
    PasswordIn,
    RegisterIn,
    SettingsIn,
    SettingsOut,
    UserOut,
)
from radar.api.uploads import read_limited
from radar.auth import service
from radar.auth import sessions as auth_sessions
from radar.auth.passwords import verify_password
from radar.auth.shared import SHARED_ACCOUNTS, is_shared
from radar.avatars import MAX_BYTES as AVATAR_MAX_BYTES
from radar.avatars import AvatarError, AvatarPreset, normalize, preset_for
from radar.config import Settings
from radar.db.models import ForgottenReader, Profile, Resume, User, UserAvatar
from radar.events import enabled as events_enabled
from radar.logging import get_logger
from radar.recsys.service import forget_taste
from radar.seed import ensure_shared_account
from radar.text import stable_hash

router = APIRouter(prefix="/auth", tags=["auth"])
log = get_logger(__name__)

_auth_limit = Depends(rate_limit("auth", lambda settings: settings.auth_rate_limit_per_minute))
# Decoding a picture costs CPU: a few uploads a minute is plenty.
_avatar_limit = Depends(
    user_rate_limit("avatar", lambda settings: settings.resume_rate_limit_per_minute)
)
_write_limit = Depends(user_rate_limit("write", lambda settings: settings.rate_limit_per_minute))
AVATAR_PATH = "/api/v1/auth/me/avatar"
_DECODING = asyncio.Semaphore(2)

# One wording for an unknown address and a wrong password: the answer must not
# reveal which addresses are registered.
_BAD_CREDENTIALS = "Неверная почта или пароль."
_TOO_MANY_ATTEMPTS = HTTPException(
    status.HTTP_429_TOO_MANY_REQUESTS,
    detail="Слишком много неудачных попыток входа. Попробуйте через минуту.",
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
        is_shared=is_shared(user.email),
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
    changing what other visitors did. On only with `RADAR_DEMO_LOGIN=true`
    or when sign-in is off altogether (`RADAR_AUTH=off`).
    """
    if not settings.demo_login and settings.auth == "on":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Вход без регистрации отключён.")
    guest = await service.create_guest(session)
    _set_cookie(
        response, await auth_sessions.start(session, guest, settings.session_ttl_days), settings
    )
    log.info("guest_created", user_id=str(guest.id))
    return _user_out(guest)


@router.post("/preset/{name}", dependencies=[_auth_limit])
async def preset_login(
    name: str, response: Response, session: SessionDep, settings: SettingsDep
) -> UserOut:
    """Enter a shared account with one click: `reader` (the example profiles)
    or `analyst` (an information security analyst). Everyone who enters gets
    the same account. Off when `RADAR_PRESET_LOGIN=false`."""
    if not settings.preset_login:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Вход в общие аккаунты отключён.")
    account = SHARED_ACCOUNTS.get(name)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Такого общего аккаунта нет.")
    user = await session.scalar(select(User).where(User.email == account.email))
    if user is None:
        # Normally made by the seeding on start; made here when the seeding is off.
        user, _ = await ensure_shared_account(session, account)
    _set_cookie(
        response, await auth_sessions.start(session, user, settings.session_ttl_days), settings
    )
    log.info("shared_account_entered", account=account.key)
    return _user_out(user)


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
    looks = (
        await session.execute(
            select(
                User.feed_view,
                User.feed_order,
                User.folded_sections,
                User.onboarded_at,
                User.avatar_preset,
            ).where(User.id == user.id)
        )
    ).one_or_none()
    return MeOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_admin=user.is_admin,
        is_demo=user.is_demo,
        is_shared=is_shared(user.email),
        profiles=int(profiles or 0),
        resume_status=resume_status,
        avatar_url=_avatar_url(avatar_at),
        avatar_preset=preset_for(user.id, looks.avatar_preset if looks else None),
        feed_view=_feed_view(looks.feed_view if looks else None),
        feed_order=_feed_order(looks.feed_order if looks else None),
        folded_sections=list(looks.folded_sections or []) if looks else [],
        onboarded_at=looks.onboarded_at if looks else None,
    )


def _feed_view(stored: str | None) -> FeedView:
    return "telegram" if stored == "telegram" else "cards"


def _feed_order(stored: str | None) -> FeedOrder:
    return "top" if stored == "top" else "new"


@router.patch("/me/settings", dependencies=[_write_limit])
async def update_settings(
    payload: SettingsIn, user: CurrentUser, session: SessionDep
) -> SettingsOut:
    """The reader's choices about how the app looks, kept with the account."""
    changes = payload.model_dump(exclude_none=True)
    if changes:
        await session.execute(update(User).where(User.id == user.id).values(**changes))
    stored = (
        await session.execute(
            select(User.feed_view, User.feed_order, User.folded_sections).where(User.id == user.id)
        )
    ).one()
    return SettingsOut(
        feed_view=_feed_view(stored.feed_view),
        feed_order=_feed_order(stored.feed_order),
        folded_sections=list(stored.folded_sections or []),
    )


@router.post("/me/onboarded", dependencies=[_write_limit])
async def finish_onboarding(user: CurrentUser, session: SessionDep) -> OnboardedOut:
    """The reader finished or skipped the first-run introduction: it is not
    offered again, in this browser or any other. Repeating keeps the first time."""
    onboarded_at = await session.scalar(
        update(User)
        .where(User.id == user.id)
        .values(onboarded_at=func.coalesce(User.onboarded_at, func.now()))
        .returning(User.onboarded_at)
    )
    if onboarded_at is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Аккаунт не найден.")
    return OnboardedOut(onboarded_at=onboarded_at)


def _avatar_url(updated_at: datetime | None) -> str | None:
    # A new picture gets a new address, so the old one may be cached for good.
    return f"{AVATAR_PATH}?v={int(updated_at.timestamp() * 1_000_000)}" if updated_at else None


@router.put("/me/avatar", dependencies=[_avatar_limit])
async def set_avatar(request: Request, user: CurrentUser, session: SessionDep) -> AvatarOut:
    """Take a picture as the raw request body and keep a small square copy of it."""
    data = await read_limited(
        request, AVATAR_MAX_BYTES, f"Размер файла превышает {AVATAR_MAX_BYTES // 1_000_000} МБ."
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
    return AvatarOut(
        avatar_url=_avatar_url(updated_at), avatar_preset=await _stored_preset(session, user.id)
    )


async def _stored_preset(session: AsyncSession, user_id: uuid.UUID) -> AvatarPreset:
    stored = await session.scalar(select(User.avatar_preset).where(User.id == user_id))
    return preset_for(user_id, stored)


@router.put("/me/avatar-preset", dependencies=[_write_limit])
async def set_avatar_preset(
    payload: AvatarPresetIn, user: CurrentUser, session: SessionDep
) -> AvatarOut:
    """Pick one of the ready pictures. An uploaded photo goes: one picture at a time."""
    await session.execute(
        update(User).where(User.id == user.id).values(avatar_preset=payload.preset)
    )
    await session.execute(delete(UserAvatar).where(UserAvatar.user_id == user.id))
    await session.commit()
    return AvatarOut(avatar_url=None, avatar_preset=payload.preset)


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
    guest has none and is deleted at once. A shared account stays: other people
    enter it too."""
    if is_shared(user.email):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Общий аккаунт удалить нельзя: им пользуются и другие.",
        )
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
