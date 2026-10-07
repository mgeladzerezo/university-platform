from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.content.models import ContentKind, ContentStatus, DegreeLevel, StudyMode

Locale = Literal["pl", "en"]
Slug = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)


class FacultyOut(BaseModel):
    id: int
    slug: str
    name: str
    description: str


class ProgramOut(BaseModel):
    id: int
    slug: str
    name: str
    description: str
    degree_level: DegreeLevel
    mode: StudyMode
    teaching_language: str
    semesters: int
    faculty_slug: str
    faculty_name: str


class StaffOut(BaseModel):
    id: int
    full_name: str
    academic_title: str
    position: str
    email: str
    phone: str
    faculty_name: str


class FacultyIn(BaseModel):
    slug: str = Slug
    name_pl: str = Field(min_length=1, max_length=200)
    name_en: str = Field(min_length=1, max_length=200)
    description_pl: str = ""
    description_en: str = ""


class ProgramIn(BaseModel):
    faculty_id: int
    slug: str = Slug
    name_pl: str = Field(min_length=1, max_length=200)
    name_en: str = Field(min_length=1, max_length=200)
    description_pl: str = ""
    description_en: str = ""
    degree_level: DegreeLevel
    mode: StudyMode
    teaching_language: Locale = "pl"
    semesters: int = Field(ge=1, le=12)


class StaffIn(BaseModel):
    faculty_id: int
    full_name: str = Field(min_length=1, max_length=200)
    academic_title: str = ""
    position_pl: str = Field(min_length=1, max_length=200)
    position_en: str = Field(min_length=1, max_length=200)
    email: EmailStr
    phone: str = ""


class CreatedId(BaseModel):
    id: int


class ContentIn(BaseModel):
    kind: ContentKind
    slug: str = Slug
    locale: Locale
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=500)
    body_html: str = Field(default="", max_length=200_000)
    event_starts_at: datetime | None = None
    event_ends_at: datetime | None = None
    event_location: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def check_event_fields(self):
        if self.kind == ContentKind.EVENT and self.event_starts_at is None:
            raise ValueError("An event needs event_starts_at")
        if (
            self.event_starts_at
            and self.event_ends_at
            and self.event_ends_at < self.event_starts_at
        ):
            raise ValueError("event_ends_at is before event_starts_at")
        return self


class ContentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: ContentKind
    slug: str
    locale: str
    title: str
    summary: str
    body_html: str
    published_at: datetime | None
    event_starts_at: datetime | None
    event_ends_at: datetime | None
    event_location: str | None


class ContentEditorial(ContentPublic):
    status: ContentStatus
    author_sub: str
    created_at: datetime
    updated_at: datetime


class WorkflowAction(StrEnum):
    SUBMIT = "submit"
    REQUEST_CHANGES = "request_changes"
    PUBLISH = "publish"
    UNPUBLISH = "unpublish"
    ARCHIVE = "archive"
    RESTORE = "restore"


class TransitionIn(BaseModel):
    action: WorkflowAction
    comment: str = Field(default="", max_length=500)


class WorkflowEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_status: ContentStatus
    to_status: ContentStatus
    actor_sub: str
    comment: str
    created_at: datetime


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=10, max_length=5000)
    locale: Locale = "pl"
