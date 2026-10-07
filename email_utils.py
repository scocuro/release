"""SMTP mail delivery with stage logs and bounded retries."""
from __future__ import annotations
import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import make_msgid


def send_email(subject: str, html: str, text: str, config: dict,
               inline_images: dict[str, bytes] | None = None,
               attachments: list[tuple[str, bytes, str]] | None = None) -> bool:
    missing = [k for k in ('host', 'port', 'user', 'password', 'sender') if not config.get(k)]
    if missing or not config.get('to'):
        print(f"[mail] 설정 누락으로 전송 생략: {missing or 'to'}", flush=True)
        return False
    try:
        port = int(config['port'])
        if not 1 <= port <= 65535:
            raise ValueError('port out of range')
    except (ValueError, TypeError):
        print('[mail] SMTP 포트 설정 오류', flush=True)
        return False
    recipients = config['to']
    if isinstance(recipients, str):
        recipients = [x.strip() for x in recipients.split(',') if x.strip()]
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = config['sender']
    msg['To'] = ', '.join(recipients)
    msg['Message-ID'] = make_msgid()
    msg.set_content(text)
    msg.add_alternative(html, subtype='html')
    if inline_images:
        html_part = msg.get_payload()[-1]
        for cid, data in inline_images.items():
            html_part.add_related(data, 'image', 'png', cid=f'<{cid}>', filename=f'{cid}.png')
    for name, data, subtype in (attachments or []):
        maintype = 'text' if subtype in ('csv', 'plain') else 'application'
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    ctx = ssl.create_default_context()
    for attempt in range(1, 4):
        s = None
        stage = '접속'
        accepted = False
        try:
            print(f'[mail] 시도 {attempt}/3 · 접속 · port={port}', flush=True)
            if port == 465:
                s = smtplib.SMTP_SSL(config['host'], port, context=ctx, timeout=30)
            else:
                s = smtplib.SMTP(config['host'], port, timeout=30)
                stage = 'STARTTLS'
                print('[mail] STARTTLS', flush=True)
                s.ehlo()
                s.starttls(context=ctx)
                s.ehlo()
            stage = '로그인'
            print('[mail] 로그인', flush=True)
            s.login(config['user'], config['password'])
            stage = '메시지 전송'
            print('[mail] 메시지 전송', flush=True)
            refused = s.send_message(msg)
            accepted = True
            if refused:
                print(f'[mail] 일부 수신자 거절 ({len(refused)}명); 중복 방지를 위해 재시도하지 않음', flush=True)
                return False
            print('[mail] SMTP 서버 수락 완료', flush=True)
            return True
        except Exception as e:
            print(f'[mail] 실패 {attempt}/3 · 단계={stage} · {type(e).__name__}: {e}', flush=True)
            transient = isinstance(e, (smtplib.SMTPServerDisconnected, TimeoutError, ConnectionError, OSError))
            if isinstance(e, smtplib.SMTPResponseException):
                transient = 400 <= e.smtp_code < 500
            if not transient or attempt == 3 or accepted:
                return False
            if stage == '메시지 전송':
                print('[mail] 수락 여부 불명확: 재시도 시 중복 메일 가능', flush=True)
            wait = attempt * 10
            print(f'[mail] {wait}초 후 재시도', flush=True)
        finally:
            if s is not None:
                try:
                    s.close()
                except Exception:
                    pass
        time.sleep(wait)
    return False


def new_cid() -> str:
    return make_msgid()[1:-1]
