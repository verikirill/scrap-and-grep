"""A post as stored and edited, and the Bot API calls that publish it."""

from html import escape
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from radar.publishing.markup import (
    CAPTION_LIMIT,
    RICH_LIMIT,
    TEXT_LIMIT,
    canonical,
    safe_url,
    to_classic,
    to_rich,
    visible_length,
)
from radar.publishing.settings import PostFormat

MAX_MEDIA = 10
MAX_BUTTONS = 4


def _web_url(value: str) -> str:
    url = safe_url(value)
    if url is None or not url.startswith(("http://", "https://")):
        raise ValueError("an http or https address")
    return url


class Media(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["photo", "video"] = "photo"
    url: str = Field(max_length=2000)

    _check_url = field_validator("url")(lambda cls, value: _web_url(value))


class Button(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1, max_length=64)
    url: str = Field(max_length=2000)

    _check_url = field_validator("url")(lambda cls, value: _web_url(value))


class PostContent(BaseModel):
    """What a post says and shows. `html` is the safe subset of markup.py;
    whatever arrives is rebuilt from the allowlist on the way in."""

    model_config = ConfigDict(frozen=True)

    format: PostFormat = "classic"
    html: str = Field(max_length=RICH_LIMIT * 2)
    media: tuple[Media, ...] = Field(default=(), max_length=MAX_MEDIA)
    buttons: tuple[Button, ...] = Field(default=(), max_length=MAX_BUTTONS)
    # A link preview card for a classic post without media (the article's own
    # picture and title, drawn by Telegram).
    preview_url: str | None = Field(default=None, max_length=2000)
    caption_above_media: bool = False
    silent: bool = False
    protect: bool = False

    @field_validator("html")
    @classmethod
    def _safe(cls, value: str) -> str:
        return canonical(value)

    @field_validator("preview_url")
    @classmethod
    def _preview(cls, value: str | None) -> str | None:
        return _web_url(value) if value else None

    def classic_text(self) -> str:
        return to_classic(self.html)

    def length(self) -> int:
        """Characters against the limit of the way this post will be sent."""
        if self.format == "rich":
            return visible_length(to_rich(self.html))
        return visible_length(self.classic_text())

    def limit(self) -> int:
        if self.format == "rich":
            return RICH_LIMIT
        return CAPTION_LIMIT if len(self.media) == 1 else TEXT_LIMIT

    def problems(self) -> list[str]:
        """Why Telegram would refuse the post, in words for the editor."""
        found = []
        if not self.html.strip() and not self.media:
            found.append("Пост пустой.")
        if self.length() > self.limit():
            found.append(f"Текст длиннее {self.limit()} знаков: {self.length()}.")
        if self.format == "classic" and len(self.media) > 1 and self.buttons:
            found.append("К альбому Telegram не прикрепляет кнопки.")
        return found


def _keyboard(buttons: tuple[Button, ...]) -> dict[str, Any] | None:
    if not buttons:
        return None
    return {"inline_keyboard": [[{"text": button.text, "url": button.url}] for button in buttons]}


def _rich_html(content: PostContent) -> str:
    media = "".join(
        f'<video src="{escape(item.url)}"/>'
        if item.kind == "video"
        else f'<img src="{escape(item.url)}"/>'
        for item in content.media
    )
    if len(content.media) > 1:
        media = f"<tg-slideshow>{media}</tg-slideshow>"
    buttons = "".join(
        f'<tg-button type="url" url="{escape(button.url)}">{escape(button.text)}</tg-button>'
        for button in content.buttons
    )
    return media + to_rich(content.html) + (f"<p>{buttons}</p>" if buttons else "")


def requests_for(content: PostContent, chat_id: int) -> list[tuple[str, dict[str, Any]]]:
    """The Bot API calls that publish the post, in order. Several only when a
    caption does not fit under its media: the media goes first, the text after."""
    common: dict[str, Any] = {"chat_id": chat_id, "disable_notification": content.silent}
    if content.format == "rich":
        return [("sendRichMessage", {**common, "rich_message": {"html": _rich_html(content)}})]

    protected = {**common, "protect_content": content.protect}
    text = content.classic_text()
    keyboard = _keyboard(content.buttons)
    markup = {"reply_markup": keyboard} if keyboard else {}

    if len(content.media) > 1:
        items: list[dict[str, Any]] = [
            {"type": item.kind, "media": item.url} for item in content.media
        ]
        items[0] |= {"caption": text, "parse_mode": "HTML"}
        if content.caption_above_media:
            items[0]["show_caption_above_media"] = True
        return [("sendMediaGroup", {**protected, "media": items})]

    if len(content.media) == 1:
        item = content.media[0]
        if visible_length(text) <= CAPTION_LIMIT:
            method = "sendVideo" if item.kind == "video" else "sendPhoto"
            return [
                (
                    method,
                    {
                        **protected,
                        item.kind: item.url,
                        "caption": text,
                        "parse_mode": "HTML",
                        "show_caption_above_media": content.caption_above_media,
                        **markup,
                    },
                )
            ]
        # Too long for a caption: the picture becomes a large preview above
        # the text, which allows 4096 characters.
        preview = {
            "url": item.url,
            "prefer_large_media": True,
            "show_above_text": not content.caption_above_media,
        }
        return [
            (
                "sendMessage",
                {
                    **protected,
                    "text": text,
                    "parse_mode": "HTML",
                    "link_preview_options": preview,
                    **markup,
                },
            )
        ]

    if content.preview_url:
        preview = {"url": content.preview_url, "prefer_large_media": True, "show_above_text": True}
    else:
        preview = {"is_disabled": True}
    return [
        (
            "sendMessage",
            {
                **protected,
                "text": text,
                "parse_mode": "HTML",
                "link_preview_options": preview,
                **markup,
            },
        )
    ]


def without_media(content: PostContent) -> PostContent:
    """The same post when Telegram could not take the picture: the article's
    own preview card stands in, if there is one."""
    return content.model_copy(update={"media": ()})
