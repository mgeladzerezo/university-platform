import smtplib
from email.message import EmailMessage as MimeMessage
from typing import Protocol


class EmailSender(Protocol):
    def send(self, recipient: str, subject: str, body: str) -> None: ...


class SesEmailSender:
    def __init__(self, region: str, sender: str):
        import boto3

        self._client = boto3.client("sesv2", region_name=region)
        self._sender = sender

    def send(self, recipient: str, subject: str, body: str) -> None:
        self._client.send_email(
            FromEmailAddress=self._sender,
            Destination={"ToAddresses": [recipient]},
            Content={
                "Simple": {
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
                }
            },
        )


class SmtpEmailSender:
    """Used with Mailpit in local development."""

    def __init__(self, host: str, port: int, sender: str):
        self._host = host
        self._port = port
        self._sender = sender

    def send(self, recipient: str, subject: str, body: str) -> None:
        message = MimeMessage()
        message["From"] = self._sender
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        with smtplib.SMTP(self._host, self._port, timeout=10) as smtp:
            smtp.send_message(message)
