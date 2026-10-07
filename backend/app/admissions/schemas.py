import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.admissions.models import AccessAction, ApplicationStatus, DocumentType, ScanStatus


class ApplicationCreate(BaseModel):
    program_id: int
    locale: Literal["pl", "en"] = "pl"


class PersonalStep(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    birth_date: date
    citizenship: str = Field(min_length=2, max_length=60)
    phone: str = Field(min_length=6, max_length=30)
    address_line: str = Field(min_length=1, max_length=200)
    city: str = Field(min_length=1, max_length=80)
    postal_code: str = Field(min_length=3, max_length=12)


class ExamResult(BaseModel):
    subject: str = Field(min_length=1, max_length=80)
    score_percent: int = Field(ge=0, le=100)


class EducationStep(BaseModel):
    school_name: str = Field(min_length=1, max_length=200)
    graduation_year: int = Field(ge=1950, le=2100)
    exam_results: list[ExamResult] = Field(min_length=1, max_length=12)


class StatementStep(BaseModel):
    statement: str = Field(min_length=50, max_length=5000)


class DocumentCreate(BaseModel):
    doc_type: DocumentType
    filename: str = Field(min_length=1, max_length=200)
    content_type: Literal["application/pdf", "image/jpeg", "image/png"]
    size_bytes: int = Field(gt=0)


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    doc_type: DocumentType
    filename: str
    content_type: str
    size_bytes: int
    scan_status: ScanStatus
    created_at: datetime


class UploadTicket(BaseModel):
    document: DocumentOut
    upload_url: str
    upload_fields: dict[str, str]


class DownloadLink(BaseModel):
    url: str


class StatusEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_status: ApplicationStatus
    to_status: ApplicationStatus
    created_at: datetime


class ApplicationOut(BaseModel):
    id: uuid.UUID
    program_id: int
    program_name: str
    status: ApplicationStatus
    personal: PersonalStep | None
    education: EducationStep | None
    statement: str | None
    documents: list[DocumentOut]
    missing_documents: list[DocumentType]
    history: list[StatusEventOut]
    created_at: datetime
    submitted_at: datetime | None
    decided_at: datetime | None
    decision_note: str | None


class QueueItem(BaseModel):
    id: uuid.UUID
    applicant_name: str
    program_name: str
    status: ApplicationStatus
    submitted_at: datetime | None


class DecisionIn(BaseModel):
    decision: Literal["accepted", "rejected"]
    note: str = Field(default="", max_length=2000)


class AccessLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    application_id: uuid.UUID
    document_id: uuid.UUID | None
    actor_sub: str
    actor_roles: str
    action: AccessAction
    created_at: datetime
