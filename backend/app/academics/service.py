from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.academics.models import CourseOffering, Enrollment, EnrollmentStatus, Grade
from app.auth import Principal, Role, remember_user
from app.db import utcnow
from app.errors import Conflict, Forbidden, NotFound
from app.metrics import ENROLLMENTS, WAITLIST_PROMOTIONS


def get_offering(session: Session, offering_id: int) -> CourseOffering:
    offering = session.get(CourseOffering, offering_id)
    if offering is None:
        raise NotFound("Course offering not found")
    return offering


def enroll(session: Session, offering_id: int, student: Principal) -> Enrollment:
    """Give the student a seat, or a waitlist place when the offering is full.

    Two things keep this correct under concurrency:
    - the seat itself is taken by one conditional UPDATE (`_take_seat`), so the
      counter can never pass capacity even if a caller forgets the lock;
    - every seat or waitlist change for an offering runs under that offering's
      row lock, so a drop and an enrollment cannot interleave in a way that
      leaves someone on the waitlist next to a free seat.
    """
    offering = _lock_offering(session, offering_id)
    if not offering.enrollment_open:
        raise Conflict("Enrollment is closed for this offering")
    remember_user(session, student)

    enrollment = _find_enrollment(session, offering_id, student.sub)
    if enrollment is not None and enrollment.status != EnrollmentStatus.DROPPED:
        raise Conflict("Already enrolled or waitlisted")
    if enrollment is None:
        enrollment = _insert_enrollment(session, offering_id, student.sub)

    if _take_seat(session, offering_id):
        enrollment.status = EnrollmentStatus.ENROLLED
        enrollment.waitlisted_at = None
    else:
        enrollment.status = EnrollmentStatus.WAITLISTED
        enrollment.waitlisted_at = utcnow()
    ENROLLMENTS.labels(enrollment.status).inc()
    return enrollment


def drop(session: Session, offering_id: int, student_sub: str) -> Enrollment | None:
    """Drop the student; returns the enrollment promoted from the waitlist, if any."""
    _lock_offering(session, offering_id)
    enrollment = _find_enrollment(session, offering_id, student_sub)
    if enrollment is None or enrollment.status == EnrollmentStatus.DROPPED:
        raise NotFound("Not enrolled in this offering")
    if enrollment.grade is not None:
        raise Conflict("A graded course cannot be dropped")

    had_seat = enrollment.status == EnrollmentStatus.ENROLLED
    enrollment.status = EnrollmentStatus.DROPPED
    enrollment.waitlisted_at = None
    return _release_seat(session, offering_id) if had_seat else None


def change_capacity(session: Session, offering_id: int, capacity: int) -> list[Enrollment]:
    """Set a new capacity; returns enrollments promoted into the added seats."""
    offering = _lock_offering(session, offering_id)
    if capacity < offering.enrolled_count:
        raise Conflict("Capacity cannot be lower than the number of enrolled students")
    offering.capacity = capacity
    session.flush()

    promoted = []
    for enrollment in _waitlist(session, offering_id):
        if not _take_seat(session, offering_id):
            break
        _promote(enrollment)
        promoted.append(enrollment)
    return promoted


def set_grade(
    session: Session, enrollment_id: int, value: float, lecturer: Principal
) -> Enrollment:
    enrollment = session.get(Enrollment, enrollment_id)
    if enrollment is None:
        raise NotFound("Enrollment not found")
    require_own_offering(enrollment.offering, lecturer)
    if enrollment.status != EnrollmentStatus.ENROLLED:
        raise Conflict("Only enrolled students can be graded")
    if enrollment.grade is None:
        enrollment.grade = Grade(value=value, graded_by_sub=lecturer.sub)
    else:
        enrollment.grade.value = value
        enrollment.grade.graded_by_sub = lecturer.sub
        enrollment.grade.graded_at = utcnow()
    return enrollment


def require_own_offering(offering: CourseOffering, lecturer: Principal) -> None:
    if offering.lecturer_sub != lecturer.sub and Role.ADMIN not in lecturer.roles:
        raise Forbidden("This offering is taught by another lecturer")


def _find_enrollment(session: Session, offering_id: int, student_sub: str) -> Enrollment | None:
    return session.scalar(
        select(Enrollment).where(
            Enrollment.offering_id == offering_id, Enrollment.student_sub == student_sub
        )
    )


def _insert_enrollment(session: Session, offering_id: int, student_sub: str) -> Enrollment:
    enrollment = Enrollment(
        offering_id=offering_id, student_sub=student_sub, status=EnrollmentStatus.WAITLISTED
    )
    session.add(enrollment)
    try:
        # The offering lock already serialises duplicates; the unique
        # constraint is the backstop if a caller ever skips the lock.
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise Conflict("Already enrolled or waitlisted") from exc
    return enrollment


def _take_seat(session: Session, offering_id: int) -> bool:
    result = session.execute(
        update(CourseOffering)
        .where(
            CourseOffering.id == offering_id,
            CourseOffering.enrolled_count < CourseOffering.capacity,
        )
        .values(enrolled_count=CourseOffering.enrolled_count + 1)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


def _lock_offering(session: Session, offering_id: int) -> CourseOffering:
    """Lock the offering row until commit and return its current state.

    FOR NO KEY UPDATE rather than FOR UPDATE: inserting an enrollment takes a
    FOR KEY SHARE lock on the offering through the foreign key, and FOR UPDATE
    conflicts with that lock. SQLite ignores the clause; there every
    transaction already holds the database write lock.
    """
    offering = session.scalar(
        select(CourseOffering)
        .where(CourseOffering.id == offering_id)
        .with_for_update(key_share=True)
        .execution_options(populate_existing=True)
    )
    if offering is None:
        raise NotFound("Course offering not found")
    return offering


def _waitlist(session: Session, offering_id: int) -> list[Enrollment]:
    return list(
        session.scalars(
            select(Enrollment)
            .where(
                Enrollment.offering_id == offering_id,
                Enrollment.status == EnrollmentStatus.WAITLISTED,
            )
            .order_by(Enrollment.waitlisted_at, Enrollment.id)
        )
    )


def _release_seat(session: Session, offering_id: int) -> Enrollment | None:
    waitlist = _waitlist(session, offering_id)
    if waitlist:
        # The freed seat goes straight to the first waitlisted student, so the
        # counter does not change.
        _promote(waitlist[0])
        return waitlist[0]
    session.execute(
        update(CourseOffering)
        .where(CourseOffering.id == offering_id)
        .values(enrolled_count=CourseOffering.enrolled_count - 1)
        .execution_options(synchronize_session=False)
    )
    return None


def _promote(enrollment: Enrollment) -> None:
    enrollment.status = EnrollmentStatus.ENROLLED
    enrollment.waitlisted_at = None
    WAITLIST_PROMOTIONS.inc()
