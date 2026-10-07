from datetime import datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.academics.models import EnrollmentStatus


class SessionIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    starts_at: time
    ends_at: time
    room: str = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def check_order(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    weekday: int
    starts_at: time
    ends_at: time
    room: str


class CourseIn(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    title_pl: str = Field(min_length=1, max_length=200)
    title_en: str = Field(min_length=1, max_length=200)
    ects: int = Field(ge=1, le=30)


class OfferingIn(BaseModel):
    course_id: int
    semester: str = Field(pattern=r"^\d{4}[ZL]$")
    lecturer_sub: str = Field(min_length=1, max_length=64)
    lecturer_name: str = Field(min_length=1, max_length=200)
    capacity: int = Field(ge=1, le=1000)
    sessions: list[SessionIn] = []


class OfferingPatch(BaseModel):
    capacity: int | None = Field(default=None, ge=1, le=1000)
    enrollment_open: bool | None = None


class OfferingOut(BaseModel):
    id: int
    course_code: str
    course_title: str
    ects: int
    semester: str
    lecturer_name: str
    capacity: int
    enrolled_count: int
    enrollment_open: bool
    sessions: list[SessionOut]
    my_status: EnrollmentStatus | None = None


class EnrollmentOut(BaseModel):
    offering_id: int
    status: EnrollmentStatus
    waitlist_position: int | None


class TimetableEntry(BaseModel):
    offering_id: int
    course_code: str
    course_title: str
    weekday: int
    starts_at: time
    ends_at: time
    room: str


class GradeOut(BaseModel):
    offering_id: int
    course_code: str
    course_title: str
    ects: int
    semester: str
    grade: float | None
    graded_at: datetime | None


class AnnouncementIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)


class AnnouncementOut(BaseModel):
    id: int
    offering_id: int | None
    course_code: str | None
    title: str
    body: str
    created_at: datetime


class RosterEntry(BaseModel):
    enrollment_id: int
    student_name: str
    student_email: str
    grade: float | None


class GradeIn(BaseModel):
    value: Literal[2.0, 3.0, 3.5, 4.0, 4.5, 5.0]
