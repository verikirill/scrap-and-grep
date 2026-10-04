"""A digest by email: the Markdown export as HTML and as plain text, the DOCX
attached.

The letter is made of the same files the reader downloads, so it says exactly
what the export says. Text from articles and from the model is escaped in the
Markdown already (render.markdown._escape); the only tags in it are the
renderer's own, so the HTML may keep them.
"""

import asyncio
import re
import smtplib
import ssl
from email.message import EmailMessage
from html import escape

from markdown_it import MarkdownIt
from markdown_it.rules_core import StateCore

from radar.config import Settings
from radar.logging import get_logger
from radar.render.docx import render_docx
from radar.render.markdown import format_date, gitlab_anchor, render_markdown
from radar.views import DigestView

log = get_logger(__name__)

DOCX_TYPE = ("application", "vnd.openxmlformats-officedocument.wordprocessingml.document")
MAX_ADDRESS = 254
_FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n+", re.DOTALL)
# One address and nothing a header could be smuggled in with: no spaces, line
# breaks, commas, brackets or quotes.
_NOT_IN_ADDRESS = r"\s@,;:<>\"'()\[\]\\"
_ADDRESS = re.compile(rf"[^{_NOT_IN_ADDRESS}]+@[^{_NOT_IN_ADDRESS}.]+(\.[^{_NOT_IN_ADDRESS}.]+)+")

_STYLE = """
body { margin: 0; background: #f4f5f8; color: #1b1d22;
  font: 15px/1.55 -apple-system, "Segoe UI", Roboto, Arial, sans-serif; }
.letter { max-width: 760px; margin: 0 auto; padding: 24px; background: #ffffff; }
h1 { font-size: 24px; line-height: 1.25; margin: 0 0 12px; }
h2 { font-size: 19px; margin: 28px 0 8px; border-bottom: 1px solid #e2e4ea; padding-bottom: 4px; }
h3 { font-size: 16px; margin: 20px 0 4px; }
a { color: #2547c4; }
table { border-collapse: collapse; margin: 8px 0; width: 100%; }
th, td { border: 1px solid #e2e4ea; padding: 4px 8px; text-align: left; vertical-align: top; }
th { background: #f4f5f8; }
blockquote { margin: 8px 0; padding: 4px 12px; border-left: 3px solid #b8bfd3; color: #4a4f5c; }
.foot { margin-top: 28px; color: #6b7080; font-size: 13px; }
"""


class MailError(Exception):
    """The letter cannot go out. The message is written for the reader."""


def _heading_ids(state: StateCore) -> None:
    """Headings get the ids GitLab gives them, so the contents at the top of
    a specialist's digest link inside the letter as they do in the file."""
    seen: dict[str, int] = {}
    for index, token in enumerate(state.tokens):
        if token.type != "heading_open":
            continue
        inline = state.tokens[index + 1]
        words = "".join(child.content for child in inline.children or [] if child.type == "text")
        token.attrSet("id", gitlab_anchor(words, seen))


_MARKDOWN = MarkdownIt("commonmark", {"html": True}).enable("table")
_MARKDOWN.core.ruler.push("heading_ids", _heading_ids)


def allowed_domains(settings: Settings) -> set[str]:
    return {part.strip().lower() for part in settings.mail_domains.split(",") if part.strip()}


def checked_address(address: str, settings: Settings) -> str:
    """One plain address the company allows, or a `MailError`."""
    address = address.strip()
    if len(address) > MAX_ADDRESS or not _ADDRESS.fullmatch(address):
        raise MailError("Это не похоже на адрес почты.")
    domains = allowed_domains(settings)
    if domains and address.rsplit("@", 1)[1].lower() not in domains:
        raise MailError(f"Выпуск можно отправить только на адреса {', '.join(sorted(domains))}.")
    return address


def subject(view: DigestView) -> str:
    title = view.title or f"Дайджест для профиля «{view.profile_name}»"
    period = f"{format_date(view.period_start)} - {format_date(view.period_end)}"
    return f"{title} ({period})"


def html_body(view: DigestView, markdown: str) -> str:
    """The Markdown export as an HTML letter, without its YAML front matter."""
    body = _MARKDOWN.render(_FRONT_MATTER.sub("", markdown))
    return (
        '<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        f"<title>{escape(subject(view))}</title><style>{_STYLE}</style></head>"
        f'<body><div class="letter">{body}'
        '<p class="foot">Выпуск Scrap&amp;Grep. Тот же текст - во вложении DOCX.</p>'
        "</div></body></html>"
    )


def attachment_name(view: DigestView) -> str:
    return f"digest-{view.period_end:%Y-%m-%d}-{view.id.hex[-6:]}.docx"


def letter(view: DigestView, to: str, settings: Settings) -> EmailMessage:
    """The digest as a letter to one checked address."""
    markdown = render_markdown(view)
    message = EmailMessage()
    message["Subject"] = subject(view)
    message["From"] = settings.smtp_from
    message["To"] = checked_address(to, settings)
    message.set_content(markdown)
    message.add_alternative(html_body(view, markdown), subtype="html")
    maintype, subtype = DOCX_TYPE
    message.add_attachment(
        render_docx(view), maintype=maintype, subtype=subtype, filename=attachment_name(view)
    )
    return message


def _send(message: EmailMessage, settings: Settings) -> None:
    timeout = settings.smtp_timeout_seconds
    client: smtplib.SMTP
    if settings.smtp_security == "ssl":
        client = smtplib.SMTP_SSL(
            settings.smtp_host,
            settings.smtp_port,
            timeout=timeout,
            context=ssl.create_default_context(),
        )
    else:
        client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout)
    with client:
        if settings.smtp_security == "starttls":
            client.starttls(context=ssl.create_default_context())
        if settings.smtp_user:
            client.login(settings.smtp_user, settings.smtp_password)
        client.send_message(message)


async def send(message: EmailMessage, settings: Settings) -> None:
    """Hand the letter to the company's mail server."""
    try:
        await asyncio.to_thread(_send, message, settings)
    except (smtplib.SMTPException, OSError) as exc:
        log.warning("mail_not_sent", error=type(exc).__name__)
        raise MailError("Почтовый сервер не принял письмо. Попробуйте позже.") from exc
