from sqlalchemy.orm import Session

from app.notifications.models import EmailMessage

SEND_EMAIL_JOB = "notifications.send_email"


def queue_email(
    session: Session, recipient: str, template: str, locale: str, context: dict
) -> EmailMessage:
    """Add an outbox row. The caller commits, then enqueues SEND_EMAIL_JOB."""
    message = EmailMessage(recipient=recipient, template=template, locale=locale, context=context)
    session.add(message)
    return message
