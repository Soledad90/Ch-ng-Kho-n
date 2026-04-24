"""Alert dispatch — Telegram + Discord + email, stdlib only.

Each channel is controlled by env vars. Missing vars = channel skipped.

TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID    -> Telegram Bot API
DISCORD_WEBHOOK_URL                      -> Discord webhook
SMTP_HOST + SMTP_PORT + SMTP_USER +
  SMTP_PASS + ALERT_EMAIL_TO            -> TLS email via smtplib
"""
from __future__ import annotations

import json
import os
import smtplib
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from email.message import EmailMessage


@dataclass
class DispatchResult:
    telegram: str = "skipped"      # skipped | ok | error:<msg>
    discord: str = "skipped"
    email: str = "skipped"

    def any_ok(self) -> bool:
        return "ok" in (self.telegram, self.discord, self.email)

    def summary(self) -> str:
        return f"tg={self.telegram} discord={self.discord} email={self.email}"


# -------------------------------------------------------------------------
# Channels
# -------------------------------------------------------------------------

def send_telegram(bot_token: str, chat_id: str, text: str, timeout: float = 8.0) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": "true",
    }).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
    obj = json.loads(body)
    if not obj.get("ok"):
        raise RuntimeError(f"telegram: {obj}")


def send_discord(webhook_url: str, text: str, timeout: float = 8.0) -> None:
    payload = json.dumps({"content": text[:1900]}).encode()
    req = urllib.request.Request(
        webhook_url, data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        code = resp.status
    if code >= 300:
        raise RuntimeError(f"discord HTTP {code}")


def send_email(host: str, port: int, user: str, password: str,
               to: str, subject: str, body: str,
               timeout: float = 10.0) -> None:
    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    ctx = ssl.create_default_context()
    # Try STARTTLS first (587), fall back to SSL (465) based on port.
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=timeout, context=ctx) as s:
            s.login(user, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=timeout) as s:
            s.ehlo()
            s.starttls(context=ctx)
            s.ehlo()
            s.login(user, password)
            s.send_message(msg)


# -------------------------------------------------------------------------
# Orchestration
# -------------------------------------------------------------------------

def dispatch(subject: str, body: str, env: dict | None = None) -> DispatchResult:
    """Send `body` to every configured channel. Never raises."""
    e = env if env is not None else os.environ
    out = DispatchResult()

    tg_tok = e.get("TELEGRAM_BOT_TOKEN")
    tg_chat = e.get("TELEGRAM_CHAT_ID")
    if tg_tok and tg_chat:
        try:
            send_telegram(tg_tok, tg_chat, f"*{subject}*\n\n{body}")
            out.telegram = "ok"
        except Exception as ex:
            out.telegram = f"error:{type(ex).__name__}:{ex}"[:200]

    disc = e.get("DISCORD_WEBHOOK_URL")
    if disc:
        try:
            send_discord(disc, f"**{subject}**\n{body}")
            out.discord = "ok"
        except Exception as ex:
            out.discord = f"error:{type(ex).__name__}:{ex}"[:200]

    smtp_host = e.get("SMTP_HOST")
    smtp_port = e.get("SMTP_PORT")
    smtp_user = e.get("SMTP_USER")
    smtp_pass = e.get("SMTP_PASS")
    smtp_to = e.get("ALERT_EMAIL_TO")
    if all((smtp_host, smtp_port, smtp_user, smtp_pass, smtp_to)):
        try:
            send_email(smtp_host, int(smtp_port), smtp_user, smtp_pass,
                       smtp_to, subject, body)
            out.email = "ok"
        except Exception as ex:
            out.email = f"error:{type(ex).__name__}:{ex}"[:200]

    return out
