from datetime import datetime, time
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, UtcDateTime, utcnow


class EnrollmentStatus(StrEnum):
    ENROLLED = "enrolled"
    WAITLISTED = "waitlisted"
    DROPPED = "dropped"


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    title_pl: Mapped[str] = mapped_column(String(200))
    title_en: Mapped[str] = mapped_column(String(200))
    ects: Mapped[int]


class CourseOffering(Base):
    __tablename__ = "course_offerings"
    __table_args__ = (
        # Backstop for the conditional UPDATE in the enrollment service.
        CheckConstraint(
            "enrolled_count >= 0 AND enrolled_count <= capacity", name="ck_offering_seats"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    semester: Mapped[str] = mapped_column(String(10), index=True)
    lecturer_sub: Mapped[str] = mapped_column(String(64), index=True)
    lecturer_name: Mapped[str] = mapped_column(String(200))
    capacity: Mapped[int]
    enrolled_count: Mapped[int] = mapped_column(default=0)
    enrollment_open: Mapped[bool] = mapped_column(default=True)

    course: Mapped[Course] = relationship()
    sessions: Mapped[list["ClassSession"]] = relationship(
        cascade="all, delete-orphan", order_by="ClassSession.weekday, ClassSession.starts_at"
    )


class ClassSession(Base):
    __tablename__ = "class_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    offering_id: Mapped[int] = mapped_column(
        ForeignKey("course_offerings.id", ondelete="CASCADE"), index=True
    )
    weekday: Mapped[int]
    starts_at: Mapped[time]
    ends_at: Mapped[time]
    room: Mapped[str] = mapped_column(String(40))


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("offering_id", "student_sub"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    offering_id: Mapped[int] = mapped_column(ForeignKey("course_offerings.id"), index=True)
    student_sub: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[EnrollmentStatus] = mapped_column(String(16))
    waitlisted_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)

    offering: Mapped[CourseOffering] = relationship()
    grade: Mapped["Grade | None"] = relationship(back_populates="enrollment")


class Grade(Base):
    __tablename__ = "grades"

    id: Mapped[int] = mapped_column(primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("enrollments.id"), unique=True)
    value: Mapped[float]
    graded_by_sub: Mapped[str] = mapped_column(String(64))
    graded_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)

    enrollment: Mapped[Enrollment] = relationship(back_populates="grade")


class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(primary_key=True)
    # NULL means a university-wide announcement.
    offering_id: Mapped[int | None] = mapped_column(ForeignKey("course_offerings.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    author_sub: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
