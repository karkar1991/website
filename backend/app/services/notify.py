"""Telegram notifications for finance events (optional).

Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to enable. Failures are logged and never
break the request that triggered them.
"""
import json
import logging
import urllib.request

from ..config import settings

log = logging.getLogger("member_admin.notify")


def enabled() -> bool:
    return bool(settings.telegram_bot_token and settings.telegram_chat_id)


def send(text: str) -> None:
    if not enabled():
        return
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = json.dumps({"chat_id": settings.telegram_chat_id, "text": text, "parse_mode": "HTML",
                          "disable_web_page_preview": True}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10).read()
    except Exception as e:  # noqa: BLE001
        log.warning("Telegram notify failed: %s", e)


def money(v) -> str:
    return f"{v:,.2f}".rstrip("0").rstrip(".")
