"""A stand-in for the Telegram Bot API, to try publishing without Telegram.

    radar telegram-mock --port 8089
    RADAR_TELEGRAM_API_URL=http://telegram-mock:8089

It answers the calls the publisher makes, keeps what was sent in memory and
shows it at / the way a channel would. Any token of the right shape is a
bot; any @name is a channel where the bot is an administrator, except:

- @no_rights_channel, where the bot may not post;
- @flaky_channel, which answers 429 to its first message;
- a picture address containing "hotlink" is refused the way Telegram
  refuses a site that blocks hotlinking, so the upload fallback shows.
"""

import hashlib
import itertools
import json
import re
import time
from html import escape
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from radar.publishing.markup import canonical, safe_url, to_classic
from radar.publishing.secrets import TOKEN_RE

_SRC_RE = re.compile(r'src="(https?://[^"]+)"')

app = FastAPI(title="Telegram Bot API mock", docs_url=None, redoc_url=None)

_messages: list[dict[str, Any]] = []
_counter = itertools.count(1)
_calls: dict[str, int] = {}
# Chats the bot looked up, so a later send by numeric id knows their names.
_chats: dict[int, dict[str, Any]] = {}
SEND_METHODS = frozenset(
    {"sendMessage", "sendPhoto", "sendVideo", "sendMediaGroup", "sendRichMessage"}
)


def _ok(result: Any) -> JSONResponse:
    return JSONResponse({"ok": True, "result": result})


def _error(code: int, description: str, retry_after: int | None = None) -> JSONResponse:
    body: dict[str, Any] = {"ok": False, "error_code": code, "description": description}
    if retry_after is not None:
        body["parameters"] = {"retry_after": retry_after}
    return JSONResponse(body, status_code=code)


def _chat(reference: Any) -> dict[str, Any]:
    if isinstance(reference, int) or str(reference).lstrip("-").isdigit():
        chat_id = int(reference)
        return {"id": chat_id, "type": "channel", "title": f"Канал {chat_id}"}
    name = str(reference).removeprefix("@")
    digest = int(hashlib.sha256(name.encode()).hexdigest()[:9], 16)
    return {
        "id": -1_000_000_000_000 - digest,
        "type": "channel",
        "title": name.replace("_", " ").title(),
        "username": name,
    }


def _known_chat(chat_id: int) -> dict[str, Any]:
    return _chats.get(chat_id) or _chat(chat_id)


async def _payload(request: Request) -> dict[str, Any]:
    if request.headers.get("content-type", "").startswith("multipart/"):
        form = await request.form()
        data: dict[str, Any] = {}
        for key, value in form.multi_items():
            if hasattr(value, "read"):
                content = await value.read()
                data[key] = f"uploaded:{len(content)} bytes"
            else:
                try:
                    data[key] = json.loads(value)
                except ValueError:
                    data[key] = value
        return data
    try:
        body = await request.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


@app.post("/bot{token}/{method}")
async def bot_api(token: str, method: str, request: Request) -> JSONResponse:
    if not TOKEN_RE.match(token):
        return _error(401, "Unauthorized")
    bot_id = int(token.split(":", 1)[0])
    payload = await _payload(request)
    if method == "getMe":
        return _ok(
            {
                "id": bot_id,
                "is_bot": True,
                "first_name": "Радар мок",
                "username": f"radar_mock_{bot_id}_bot",
            }
        )
    if method == "getChat":
        chat = _chat(payload.get("chat_id", ""))
        _chats[chat["id"]] = chat
        return _ok(chat)
    if method == "getChatMember":
        chat_id = int(payload.get("chat_id", 0))
        no_rights = _chat("@no_rights_channel")["id"] == chat_id
        status = "member" if no_rights else "administrator"
        return _ok({"status": status, "can_post_messages": not no_rights, "user": {"id": bot_id}})
    if method not in SEND_METHODS:
        return _error(400, f"Bad Request: method {method} is not mocked")
    chat_reference = payload.get("chat_id")
    chat = (
        _chat(chat_reference)
        if isinstance(chat_reference, str)
        else _known_chat(int(chat_reference or 0))
    )
    if chat.get("username") == "flaky_channel":
        _calls["flaky"] = _calls.get("flaky", 0) + 1
        if _calls["flaky"] == 1:
            return _error(429, "Too Many Requests: retry after 3", retry_after=3)
    picture = str(payload.get("photo") or payload.get("video") or "")
    if "hotlink" in picture and not picture.startswith("uploaded:"):
        return _error(400, "Bad Request: wrong type of the web page content")
    message_id = next(_counter)
    stored = {
        "message_id": message_id,
        "date": int(time.time()),
        "chat": chat,
        "method": method,
        "bot": bot_id,
        "payload": payload,
    }
    _messages.append(stored)
    message = {"message_id": message_id, "date": stored["date"], "chat": chat}
    return _ok([message] if method == "sendMediaGroup" else message)


@app.get("/api/messages")
async def messages() -> list[dict[str, Any]]:
    return list(reversed(_messages))


@app.delete("/api/messages")
async def clear() -> dict[str, int]:
    count = len(_messages)
    _messages.clear()
    _calls.clear()
    return {"cleared": count}


def _media(payload: dict[str, Any]) -> str:
    urls = []
    for key in ("photo", "video"):
        if isinstance(payload.get(key), str):
            urls.append(payload[key])
    for item in payload.get("media") or []:
        if isinstance(item, dict) and isinstance(item.get("media"), str):
            urls.append(item["media"])
    preview = (payload.get("link_preview_options") or {}).get("url")
    if preview and not urls:
        urls.append(preview)
    tags = []
    for url in urls:
        if url.startswith("uploaded:"):
            tags.append(f'<div class="upload">{escape(url)}</div>')
        else:
            tags.append(f'<img src="{escape(url)}" loading="lazy" referrerpolicy="no-referrer">')
    return "".join(tags)


def _body(message: dict[str, Any]) -> str:
    payload = message["payload"]
    if message["method"] == "sendRichMessage":
        # Anyone can post to the mock: what it shows is rebuilt from the
        # allowlist, pictures listed separately.
        html = (payload.get("rich_message") or {}).get("html", "")
        pictures = "".join(
            f'<img src="{escape(url)}" loading="lazy" referrerpolicy="no-referrer">'
            for url in _SRC_RE.findall(html)
        )
        return f'{pictures}<div class="rich">{canonical(html)}</div>'
    text = payload.get("caption") or payload.get("text") or ""
    for item in payload.get("media") or []:
        if isinstance(item, dict) and item.get("caption"):
            text = item["caption"]
    buttons = "".join(_button(button) for row in _keyboard(payload) for button in row)
    shown = to_classic(canonical(text.replace(chr(10), "<br>")))
    return f'<div class="text">{shown}</div>{buttons}'


def _keyboard(payload: dict[str, Any]) -> list[list[dict[str, Any]]]:
    return (payload.get("reply_markup") or {}).get("inline_keyboard") or []


def _button(button: dict[str, Any]) -> str:
    text = escape(str(button.get("text", "")))
    url = safe_url(str(button.get("url", "")))
    if url is None:
        return f'<span class="button">{text}</span>'
    return f'<a class="button" href="{escape(url)}">{text}</a>'


# Anyone on the machine can post to the mock, so its page runs no scripts.
_VIEWER_POLICY = "default-src 'none'; img-src https: http: data:; style-src 'unsafe-inline'"


_STYLE = """
body{margin:0;background:#0e1621;color:#e9eef4;font:15px/1.45 system-ui,sans-serif}
main{max-width:560px;margin:0 auto;padding:24px 16px}
h1{font-size:18px}
article{background:#182533;border-radius:14px;margin:0 0 16px;overflow:hidden}
header{padding:10px 14px;display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
header span{color:#7f91a4;font-size:13px}
.meta{margin-left:auto}
img{display:block;width:100%;max-height:420px;object-fit:cover}
.text,.rich{padding:10px 14px 14px;white-space:pre-wrap}
.rich{white-space:normal}
a{color:#6ab3f3}
blockquote{border-left:3px solid #6ab3f3;margin:6px 0;padding:2px 10px}
.button{display:block;margin:0 14px 14px;padding:9px;text-align:center;border-radius:10px;
  background:#2b5278;text-decoration:none}
.upload{padding:40px 14px;background:#22364a;color:#7f91a4;text-align:center}
tg-spoiler{background:#7f91a4;color:transparent;border-radius:4px}
"""


def _card(message: dict[str, Any]) -> str:
    chat = message["chat"]
    name = escape(chat.get("title") or str(chat["id"]))
    username = escape(chat.get("username") or "")
    when = time.strftime("%d.%m %H:%M:%S", time.localtime(message["date"]))
    meta = f"{escape(message['method'])} · #{message['message_id']} · {when}"
    return (
        f'<article><header><b>{name}</b> <span>@{username}</span><span class="meta">{meta}</span>'
        f"</header>{_media(message['payload'])}{_body(message)}</article>"
    )


@app.get("/", response_class=HTMLResponse)
async def viewer() -> HTMLResponse:
    cards = "".join(_card(message) for message in reversed(_messages))
    html = (
        '<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Мок Telegram</title><meta http-equiv="refresh" content="10">'
        f"<style>{_STYLE}</style></head><body><main>"
        f"<h1>Мок Telegram · отправлено: {len(_messages)}</h1>"
        f"{cards or '<p>Пока ничего не отправлено.</p>'}</main></body></html>"
    )
    return HTMLResponse(html, headers={"Content-Security-Policy": _VIEWER_POLICY})
