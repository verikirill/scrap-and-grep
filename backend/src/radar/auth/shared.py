"""Shared accounts entered with one click on the sign-in page.

A visitor who wants to look around without registering presses a button and
lands in a ready account: a reader with the example profiles, or an
information security analyst. Everyone who presses the button is in the same
account, so it has no password, skips the introduction and cannot be deleted.
"""

from dataclasses import dataclass

from radar.avatars import AvatarPreset

# Service-made addresses live under this domain; registration refuses it.
SERVICE_DOMAIN = "radar.local"


@dataclass(frozen=True, slots=True)
class SharedAccount:
    key: str
    email: str
    display_name: str
    avatar: AvatarPreset
    # Names of the example profiles (radar.seed.DEFAULT_PROFILES) it starts
    # with; empty means all of them.
    profiles: tuple[str, ...] = ()


SHARED_ACCOUNTS: dict[str, SharedAccount] = {
    account.key: account
    for account in (
        SharedAccount(
            key="reader",
            email=f"reader@{SERVICE_DOMAIN}",
            display_name="Читатель",
            avatar="sky",
        ),
        SharedAccount(
            key="analyst",
            email=f"analyst@{SERVICE_DOMAIN}",
            display_name="Аналитик ИБ",
            avatar="red",
            profiles=(
                "Специалист по ИБ АСУ ТП",
                "Руководство и сотрудники: кибербезопасность",
            ),
        ),
    )
}
_SHARED_EMAILS = frozenset(account.email for account in SHARED_ACCOUNTS.values())


def is_shared(email: str) -> bool:
    return email in _SHARED_EMAILS


def is_service_address(email: str) -> bool:
    """A made-up address of a guest, the demo template or a shared account:
    nobody may register it and no mail goes to it."""
    domain = email.rpartition("@")[2]
    return domain == SERVICE_DOMAIN or domain.endswith(f".{SERVICE_DOMAIN}")
