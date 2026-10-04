"""A digest by email: the letter, the address check, the mail server and the API."""

import io
import re
import smtplib
from collections.abc import Iterator
from email import message_from_bytes, policy
from email.message import EmailMessage
from typing import Any, ClassVar
from urllib.parse import unquote

import pytest
from docx import Document

from radar import mail
from radar.config import Settings
from radar.render.markdown import render_markdown
from radar.views import DigestView
from tests.test_accounts_api import (  # noqa: F401  (fixtures)
    api,
    client,
    database,
    finished_digest,
    register,
    seed_articles,
)
from tests.test_render import _item, digest  # noqa: F401  (fixture)


def settings(**values: Any) -> Settings:
    return Settings(_env_file=None, smtp_host="mail.test", smtp_security="none", **values)  # type: ignore[call-arg]


def parsed(message: EmailMessage) -> EmailMessage:
    """The letter as the receiving server reads it."""
    result = message_from_bytes(message.as_bytes(), policy=policy.default)
    assert isinstance(result, EmailMessage)
    return result


def test_the_letter_is_the_markdown_as_text_and_html_with_the_docx_attached(
    digest: DigestView,  # noqa: F811
) -> None:
    digest.topics[0].items.append(
        _item(
            8,
            "Уязвимость в ПЛК Siemens",
            kind="vulnerability",
            priority="high",
            vulnerability={"name": "Обход входа в ПЛК", "fix": "прошивка 4.2"},
        )
    )
    letter = parsed(mail.letter(digest, "analyst@grid.example", settings()))

    plain = letter.get_body(("plain",))
    html = letter.get_body(("html",))
    attachments = list(letter.iter_attachments())
    assert plain is not None
    assert html is not None
    assert letter["To"] == "analyst@grid.example"
    assert letter["Subject"] == "Главное за неделю (23.09.2026 - 30.09.2026)"
    assert plain.get_content() == render_markdown(digest)
    # The front matter is for programs reading the file, not for a reader.
    assert "profile_version: 3" in plain.get_content()
    assert "profile_version" not in html.get_content()
    assert '<a href="https://example.org/a/2">' in html.get_content()
    # The card is a Markdown table in the file and an HTML table in the letter.
    assert "<td>прошивка 4.2</td>" in html.get_content()
    [docx] = attachments
    assert docx.get_filename() == mail.attachment_name(digest)
    assert docx.get_content_type() == "/".join(mail.DOCX_TYPE)
    assert Document(io.BytesIO(docx.get_content())).paragraphs


def test_text_from_articles_stays_text_in_the_letter(digest: DigestView) -> None:  # noqa: F811
    digest.topics[0].items.append(_item(7, "<script>alert(1)</script> в SCADA"))

    html = parsed(mail.letter(digest, "a@grid.example", settings())).get_body(("html",))

    assert html is not None
    assert "<script>" not in html.get_content()
    assert "&lt;script&gt;alert(1)&lt;/script&gt; в SCADA" in html.get_content()


def test_the_contents_link_to_headings_inside_the_letter(digest: DigestView) -> None:  # noqa: F811
    html = parsed(mail.letter(digest, "a@grid.example", settings())).get_body(("html",))

    assert html is not None
    body = html.get_content()
    # A browser percent-decodes the fragment before it looks for the id.
    links = {unquote(link) for link in re.findall(r'href="#([^"]+)"', body)}
    ids = set(re.findall(r' id="([^"]+)"', body))
    assert links
    assert links <= ids


@pytest.mark.parametrize(
    "address",
    [
        pytest.param("", id="empty"),
        pytest.param("analyst", id="no-at"),
        pytest.param("analyst@grid", id="no-domain-dot"),
        pytest.param("analyst@grid..ru", id="empty-label"),
        pytest.param("a@@grid.ru", id="two-ats"),
        pytest.param("a@grid.ru\nBcc: all@grid.ru", id="header-injection"),
        pytest.param("a@grid.ru, b@grid.ru", id="two-addresses"),
        pytest.param("Аналитик <a@grid.ru>", id="display-name"),
        pytest.param("x" * 250 + "@grid.ru", id="too-long"),
    ],
)
def test_an_address_that_is_not_one_plain_mailbox_is_refused(address: str) -> None:
    with pytest.raises(mail.MailError):
        mail.checked_address(address, settings())


def test_a_plain_address_passes() -> None:
    assert mail.checked_address(" a.b+digest@grid-company.ru ", settings()) == (
        "a.b+digest@grid-company.ru"
    )


def test_only_the_companys_domains_when_they_are_set() -> None:
    company = settings(mail_domains="grid.ru, Grid.Example")

    assert mail.checked_address("a@grid.ru", company) == "a@grid.ru"
    assert mail.checked_address("a@GRID.example", company) == "a@GRID.example"
    with pytest.raises(mail.MailError, match=r"grid\.example, grid\.ru"):
        mail.checked_address("a@gmail.com", company)


class FakeServer:
    """smtplib's client as the code under test drives it, recording each step."""

    made: ClassVar[list[FakeServer]] = []

    def __init__(self, host: str, port: int, **options: Any) -> None:
        self.address = (host, port)
        self.secure_from_start = "context" in options
        self.steps: list[str] = []
        FakeServer.made.append(self)

    def __enter__(self) -> FakeServer:
        return self

    def __exit__(self, *exc: object) -> None:
        self.steps.append("quit")

    def starttls(self, **options: Any) -> None:
        self.steps.append("starttls")

    def login(self, user: str, password: str) -> None:
        self.steps.append(f"login {user}")

    def send_message(self, message: EmailMessage) -> None:
        self.steps.append(f"send {message['To']}")


@pytest.fixture
def fake_server(monkeypatch: pytest.MonkeyPatch) -> list[FakeServer]:
    FakeServer.made = []
    monkeypatch.setattr(smtplib, "SMTP", FakeServer)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeServer)
    return FakeServer.made


@pytest.mark.parametrize(
    ("security", "user", "port", "steps", "from_start"),
    [
        pytest.param("starttls", "digest", 587, ["starttls", "login digest"], False, id="starttls"),
        pytest.param("ssl", "digest", 465, ["login digest"], True, id="ssl"),
        pytest.param("none", "", 1025, [], False, id="mock-without-login"),
    ],
)
async def test_the_letter_goes_to_the_server_as_the_settings_say(
    fake_server: list[FakeServer],
    digest: DigestView,  # noqa: F811
    security: str,
    user: str,
    port: int,
    steps: list[str],
    from_start: bool,
) -> None:
    config = Settings(  # type: ignore[call-arg]
        _env_file=None,
        smtp_host="mail.test",
        smtp_port=port,
        smtp_security=security,
        smtp_user=user,
    )

    await mail.send(mail.letter(digest, "a@grid.ru", config), config)

    [server] = fake_server
    assert server.address == ("mail.test", port)
    assert server.secure_from_start is from_start
    assert server.steps == [*steps, "send a@grid.ru", "quit"]


async def test_a_server_that_refuses_is_a_message_for_the_reader(
    monkeypatch: pytest.MonkeyPatch,
    digest: DigestView,  # noqa: F811
) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise smtplib.SMTPRecipientsRefused({"a@grid.ru": (550, b"no such user")})

    monkeypatch.setattr(mail, "_send", refuse)

    with pytest.raises(mail.MailError, match="не принял"):
        await mail.send(mail.letter(digest, "a@grid.ru", settings()), settings())


@pytest.fixture
def mail_on(api: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[list[EmailMessage]]:  # noqa: F811
    """A mail server set, faked at the hand-over. Returns the letters handed over."""
    from radar.config import get_settings

    monkeypatch.setenv("RADAR_SMTP_HOST", "mail.test")
    get_settings.cache_clear()
    sent: list[EmailMessage] = []

    async def hand_over(message: EmailMessage, config: Settings) -> None:
        sent.append(message)

    monkeypatch.setattr(mail, "send", hand_over)
    yield sent
    get_settings.cache_clear()


async def test_a_reader_mails_a_finished_digest_to_themselves_or_a_colleague(
    api: str,  # noqa: F811
    mail_on: list[EmailMessage],
) -> None:
    async with register(api, "nina") as owner, register(api, "ivan") as other:
        ids = await seed_articles()
        digest_id = await finished_digest(owner, ids)
        building = await finished_digest(owner, ids, status="running")
        me = (await owner.get("/auth/me")).json()["email"]

        state = (await owner.get(f"/digests/{digest_id}/mail")).json()
        to_self = await owner.post(f"/digests/{digest_id}/mail")
        to_colleague = await owner.post(f"/digests/{digest_id}/mail", json={"to": "boss@grid.ru"})
        smuggled = await owner.post(
            f"/digests/{digest_id}/mail", json={"to": "boss@grid.ru\nBcc: all@grid.ru"}
        )
        not_ready = await owner.post(f"/digests/{building}/mail")
        stolen = await other.post(f"/digests/{digest_id}/mail", json={"to": "x@grid.ru"})

    assert state == {"available": True, "default_to": me, "domains": []}
    assert to_self.json() == {"to": me}
    assert to_colleague.json() == {"to": "boss@grid.ru"}
    assert smuggled.status_code == 400
    assert not_ready.status_code == 409
    assert stolen.status_code == 404
    assert [letter["To"] for letter in mail_on] == [me, "boss@grid.ru"]
    assert all(len(list(letter.iter_attachments())) == 1 for letter in mail_on)


async def test_a_guest_names_the_address_and_the_company_limits_the_domains(
    api: str,  # noqa: F811
    mail_on: list[EmailMessage],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from radar.config import get_settings

    monkeypatch.setenv("RADAR_MAIL_DOMAINS", "grid.ru")
    get_settings.cache_clear()
    async with client(api) as guest:
        await guest.post("/auth/demo")
        digest_id = await finished_digest(guest, await seed_articles())

        state = (await guest.get(f"/digests/{digest_id}/mail")).json()
        nowhere = await guest.post(f"/digests/{digest_id}/mail")
        outside = await guest.post(f"/digests/{digest_id}/mail", json={"to": "x@gmail.com"})
        inside = await guest.post(f"/digests/{digest_id}/mail", json={"to": "x@grid.ru"})

    assert state == {"available": True, "default_to": None, "domains": ["grid.ru"]}
    assert nowhere.status_code == 400
    assert outside.status_code == 400
    assert inside.json() == {"to": "x@grid.ru"}
    assert [letter["To"] for letter in mail_on] == ["x@grid.ru"]


async def test_without_a_mail_server_there_is_no_mail(api: str) -> None:  # noqa: F811
    async with register(api, "olga") as owner:
        digest_id = await finished_digest(owner, await seed_articles())

        state = await owner.get(f"/digests/{digest_id}/mail")
        sent = await owner.post(f"/digests/{digest_id}/mail", json={"to": "a@grid.ru"})

    assert state.json() == {"available": False, "default_to": None, "domains": []}
    assert sent.status_code == 503
