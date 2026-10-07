import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.content.models import DegreeLevel, Program
from app.db import Base, UtcDateTime, utcnow


class ApplicationStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class DocumentType(StrEnum):
    IDENTITY = "identity"
    DIPLOMA = "diploma"
    TRANSCRIPT = "transcript"
    PHOTO = "photo"
    OTHER = "other"


class ScanStatus(StrEnum):
    AWAITING_UPLOAD = "awaiting_upload"
    PENDING_SCAN = "pending_scan"
    CLEAN = "clean"
    INFECTED = "infected"


class AccessAction(StrEnum):
    VIEW_APPLICATION = "view_application"
    UPLOAD_DOCUMENT = "upload_document"
    DOWNLOAD_DOCUMENT = "download_document"
    DELETE_DOCUMENT = "delete_document"
    AI_SUMMARY = "ai_summary"
    RETENTION_DELETE = "retention_delete"


REQUIRED_DOCUMENTS: dict[DegreeLevel, tuple[DocumentType, ...]] = {
    DegreeLevel.BACHELOR: (DocumentType.IDENTITY, DocumentType.DIPLOMA, DocumentType.PHOTO),
    DegreeLevel.MASTER: (
        DocumentType.IDENTITY,
        DocumentType.DIPLOMA,
        DocumentType.TRANSCRIPT,
        DocumentType.PHOTO,
    ),
    DegreeLevel.DOCTORAL: (
        DocumentType.IDENTITY,
        DocumentType.DIPLOMA,
        DocumentType.TRANSCRIPT,
        DocumentType.PHOTO,
    ),
}


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("applicant_sub", "program_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    applicant_sub: Mapped[str] = mapped_column(String(64), index=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id"))
    status: Mapped[ApplicationStatus] = mapped_column(
        String(16), default=ApplicationStatus.DRAFT, index=True
    )
    locale: Mapped[str] = mapped_column(String(2), default="pl")
    personal: Mapped[dict | None] = mapped_column(JSON)
    education: Mapped[dict | None] = mapped_column(JSON)
    statement: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    decided_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    decided_by_sub: Mapped[str | None] = mapped_column(String(64))
    decision_note: Mapped[str | None] = mapped_column(Text)

    program: Mapped[Program] = relationship()
    documents: Mapped[list["ApplicationDocument"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="ApplicationDocument.created_at",
    )
    history: Mapped[list["ApplicationStatusEvent"]] = relationship(
        cascade="all, delete-orphan", order_by="ApplicationStatusEvent.id"
    )


class ApplicationDocument(Base):
    __tablename__ = "application_documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    doc_type: Mapped[DocumentType] = mapped_column(String(16))
    filename: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int]
    storage_key: Mapped[str] = mapped_column(String(300), unique=True)
    scan_status: Mapped[ScanStatus] = mapped_column(String(16), default=ScanStatus.AWAITING_UPLOAD)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)

    application: Mapped[Application] = relationship(back_populates="documents")


class ApplicationStatusEvent(Base):
    __tablename__ = "application_status_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[ApplicationStatus] = mapped_column(String(16))
    to_status: Mapped[ApplicationStatus] = mapped_column(String(16))
    actor_sub: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class DocumentAccessLog(Base):
    """Append-only record of who touched an application or its documents.

    No foreign keys on purpose: entries must outlive the application when the
    retention job deletes it.
    """

    __tablename__ = "document_access_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    actor_sub: Mapped[str] = mapped_column(String(64))
    actor_roles: Mapped[str] = mapped_column(String(200))
    action: Mapped[AccessAction] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
