from datetime import datetime
from enum import StrEnum

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, UtcDateTime, utcnow


class ContentKind(StrEnum):
    PAGE = "page"
    NEWS = "news"
    EVENT = "event"


class ContentStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class DegreeLevel(StrEnum):
    BACHELOR = "bachelor"
    MASTER = "master"
    DOCTORAL = "doctoral"


class StudyMode(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"


class Faculty(Base):
    __tablename__ = "faculties"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name_pl: Mapped[str] = mapped_column(String(200))
    name_en: Mapped[str] = mapped_column(String(200))
    description_pl: Mapped[str] = mapped_column(Text, default="")
    description_en: Mapped[str] = mapped_column(Text, default="")


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(primary_key=True)
    faculty_id: Mapped[int] = mapped_column(ForeignKey("faculties.id"))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name_pl: Mapped[str] = mapped_column(String(200))
    name_en: Mapped[str] = mapped_column(String(200))
    description_pl: Mapped[str] = mapped_column(Text, default="")
    description_en: Mapped[str] = mapped_column(Text, default="")
    degree_level: Mapped[DegreeLevel] = mapped_column(String(16))
    mode: Mapped[StudyMode] = mapped_column(String(16))
    teaching_language: Mapped[str] = mapped_column(String(2), default="pl")
    semesters: Mapped[int]

    faculty: Mapped[Faculty] = relationship()


class StaffMember(Base):
    __tablename__ = "staff_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    faculty_id: Mapped[int] = mapped_column(ForeignKey("faculties.id"))
    full_name: Mapped[str] = mapped_column(String(200))
    academic_title: Mapped[str] = mapped_column(String(80), default="")
    position_pl: Mapped[str] = mapped_column(String(200))
    position_en: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(254))
    phone: Mapped[str] = mapped_column(String(40), default="")

    faculty: Mapped[Faculty] = relationship()


class ContentItem(Base):
    __tablename__ = "content_items"
    __table_args__ = (
        UniqueConstraint("kind", "slug", "locale"),
        Index("ix_content_public_listing", "status", "kind", "locale", "published_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[ContentKind] = mapped_column(String(16))
    slug: Mapped[str] = mapped_column(String(120))
    locale: Mapped[str] = mapped_column(String(2))
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(String(500), default="")
    body_html: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[ContentStatus] = mapped_column(String(16), default=ContentStatus.DRAFT)
    author_sub: Mapped[str] = mapped_column(String(64))
    event_starts_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    event_ends_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    event_location: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow, onupdate=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(UtcDateTime)


class WorkflowEvent(Base):
    __tablename__ = "content_workflow_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_item_id: Mapped[int] = mapped_column(
        ForeignKey("content_items.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[ContentStatus] = mapped_column(String(16))
    to_status: Mapped[ContentStatus] = mapped_column(String(16))
    actor_sub: Mapped[str] = mapped_column(String(64))
    comment: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254))
    subject: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
