"""
Mail sending.

Inline images must be attached via Content-ID, not as regular attachments,
or the chart lands in the attachment tray instead of the message body.
Build multipart/alternative(text, html) first, then add_related() on the
html part. Getting the order wrong breaks the inline image.
"""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid


def send_email(subject: str, html: str, text: str, config: dict,
               inline_images: dict[str, bytes] | None = None,
               attachments: list[tuple[str, bytes, str]] | None = None) -> bool:
    """
    inline_images: {cid_without_brackets: png_bytes}
    attachments:   [(filename, data, subtype)]
    """
    missing = [k for k in ("host", "port", "user", "password", "sender") if not config.get(k)]
    if missing or not config.get("to"):
        print(f"[mail] 설정 누락으로 전송 생략: {missing or 'to'}")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config["sender"]
    msg["To"] = ", ".join(config["to"])

    msg.set_content(text)                          # text/plain
    msg.add_alternative(html, subtype="html")      # text/html

    if inline_images:
        html_part = msg.get_payload()[-1]
        for cid, data in inline_images.items():
            html_part.add_related(data, "image", "png", cid=f"<{cid}>",
                                  filename=f"{cid}.png")

    for name, data, subtype in (attachments or []):
        maintype = "text" if subtype in ("csv", "plain") else "application"
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)

    ctx = ssl.create_default_context()
    try:
        if int(config["port"]) == 465:
            with smtplib.SMTP_SSL(config["host"], int(config["port"]), context=ctx) as s:
                s.login(config["user"], config["password"])
                s.send_message(msg)
        else:
            with smtplib.SMTP(config["host"], int(config["port"])) as s:
                s.starttls(context=ctx)
                s.login(config["user"], config["password"])
                s.send_message(msg)
        print(f"[mail] 전송 완료 -> {msg['To']}")
        return True
    except Exception as e:                        # noqa: BLE001
        print(f"[mail] 전송 실패: {type(e).__name__}: {e}")
        return False


def new_cid() -> str:
    return make_msgid()[1:-1]
