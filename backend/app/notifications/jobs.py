from sqlalchemy.orm import Session

from app.db import utcnow
from app.jobs import job
from app.notifications.models import EmailMessage, EmailStatus
from app.notifications.service import SEND_EMAIL_JOB
from app.notifications.templates import render


@job(SEND_EMAIL_JOB)
def send_email(session: Session, services, message_id: int) -> None:
    message = session.get(EmailMessage, message_id)
    if message is None or message.status == EmailStatus.SENT:
        return
    rendered = render(message.template, message.locale, message.context)
    try:
        services.email.send(message.recipient, rendered.subject, rendered.body)
    except Exception as exc:
        message.status = EmailStatus.FAILED
        message.error = str(exc)[:500]
        session.commit()
        raise
    message.status = EmailStatus.SENT
    message.error = None
    message.sent_at = utcnow()
    session.commit()
