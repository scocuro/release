import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

def send_email(subject: str, body: str, attachments: list, config: dict):
    try:
        print("Attempting to send email...")
        msg = MIMEMultipart()
        msg['From'] = config['FROM_ADDR']
        msg['To'] = ', '.join(config['TO_ADDRS'])
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        for fname, data in attachments:
            part = MIMEBase('application', 'octet-stream')
            if hasattr(data, 'read'):  # 파일 객체일 경우
                file_bytes = data.read()
            else:  # 파일 경로일 경우
                with open(data, 'rb') as file:
                    file_bytes = file.read()

            part.set_payload(file_bytes)
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{fname}"')
            msg.attach(part)

        with smtplib.SMTP(config['SMTP_SERVER'], config['SMTP_PORT']) as server:
            server.ehlo()
            server.starttls()
            server.login(config['USERNAME'], config['PASSWORD'])
            server.send_message(msg)

        print(f"Email sent successfully to {', '.join(config['TO_ADDRS'])}")

    except Exception as e:
        print(f"Failed to send email: {e}")
