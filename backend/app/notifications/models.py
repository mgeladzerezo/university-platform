from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UtcDateTime, utcnow


class EmailStatus(StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"


class EmailMessage(Base):
    """Outbox row, written in the same transaction as the event that causes it."""

    __tablename__ = "email_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipient: Mapped[str] = mapped_column(String(254))
    template: Mapped[str] = mapped_column(String(64))
    locale: Mapped[str] = mapped_column(String(2))
    context: Mapped[dict] = mapped_column(JSON)
    status: Mapped[EmailStatus] = mapped_column(String(16), default=EmailStatus.QUEUED)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
