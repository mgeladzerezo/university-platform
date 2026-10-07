from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.academics import service
from app.academics.models import (
    Announcement,
    ClassSession,
    Course,
    CourseOffering,
    Enrollment,
    EnrollmentStatus,
)
from app.academics.schemas import (
    AnnouncementIn,
    AnnouncementOut,
    CourseIn,
    EnrollmentOut,
    GradeIn,
    GradeOut,
    OfferingIn,
    OfferingOut,
    OfferingPatch,
    RosterEntry,
    SessionOut,
    TimetableEntry,
)
from app.auth import Principal, Role, UserProfile, require_roles
from app.content.schemas import CreatedId, Locale
from app.db import get_session
from app.errors import Conflict, NotFound
from app.notifications.service import SEND_EMAIL_JOB, queue_email

router = APIRouter(prefix="/academics", tags=["academics"])

student_only = require_roles(Role.STUDENT)
lecturer_only = require_roles(Role.LECTURER)
admin_only = require_roles(Role.ADMIN)
student_or_lecturer = require_roles(Role.STUDENT, Role.LECTURER)


def _title(course: Course, locale: str) -> str:
    return course.title_en if locale == "en" else course.title_pl


def _offering_out(
    offering: CourseOffering, locale: str, my_status: EnrollmentStatus | None = None
) -> OfferingOut:
    return OfferingOut(
        id=offering.id,
        course_code=offering.course.code,
        course_title=_title(offering.course, locale),
        ects=offering.course.ects,
        semester=offering.semester,
        lecturer_name=offering.lecturer_name,
        capacity=offering.capacity,
        enrolled_count=offering.enrolled_count,
        enrollment_open=offering.enrollment_open,
        sessions=[SessionOut.model_validate(s) for s in offering.sessions],
        my_status=my_status,
    )


def _enrollment_out(session: Session, enrollment: Enrollment) -> EnrollmentOut:
    position = None
    if enrollment.status == EnrollmentStatus.WAITLISTED:
        ahead = session.scalar(
            select(func.count())
            .select_from(Enrollment)
            .where(
                Enrollment.offering_id == enrollment.offering_id,
                Enrollment.status == EnrollmentStatus.WAITLISTED,
                or_(
                    Enrollment.waitlisted_at < enrollment.waitlisted_at,
                    (Enrollment.waitlisted_at == enrollment.waitlisted_at)
                    & (Enrollment.id < enrollment.id),
                ),
            )
        )
        position = ahead + 1
    return EnrollmentOut(
        offering_id=enrollment.offering_id, status=enrollment.status, waitlist_position=position
    )


def _active_enrollments(session: Session, student_sub: str) -> list[Enrollment]:
    return list(
        session.scalars(
            select(Enrollment).where(
                Enrollment.student_sub == student_sub,
                Enrollment.status != EnrollmentStatus.DROPPED,
            )
        )
    )


@router.get("/offerings", response_model=list[OfferingOut])
def list_offerings(
    semester: str | None = None,
    locale: Locale = "pl",
    principal: Principal = Depends(student_or_lecturer),
    session: Session = Depends(get_session),
):
    query = select(CourseOffering).join(CourseOffering.course).order_by(Course.code)
    if semester:
        query = query.where(CourseOffering.semester == semester)
    statuses = {e.offering_id: e.status for e in _active_enrollments(session, principal.sub)}
    return [_offering_out(o, locale, statuses.get(o.id)) for o in session.scalars(query)]


@router.post("/offerings/{offering_id}/enrollment", response_model=EnrollmentOut)
def enroll(
    offering_id: int,
    student: Principal = Depends(student_only),
    session: Session = Depends(get_session),
):
    enrollment = service.enroll(session, offering_id, student)
    session.commit()
    return _enrollment_out(session, enrollment)


@router.delete("/offerings/{offering_id}/enrollment", status_code=status.HTTP_204_NO_CONTENT)
def drop(
    offering_id: int,
    request: Request,
    student: Principal = Depends(student_only),
    session: Session = Depends(get_session),
) -> None:
    promoted = service.drop(session, offering_id, student.sub)
    emails = _queue_promotion_emails(session, [promoted] if promoted else [])
    session.commit()
    _send(request, emails)


def _queue_promotion_emails(session: Session, promoted: list[Enrollment]) -> list:
    emails = []
    for enrollment in promoted:
        profile = session.get(UserProfile, enrollment.student_sub)
        if profile and profile.email:
            emails.append(
                queue_email(
                    session,
                    profile.email,
                    "waitlist_promoted",
                    "pl",
                    {"name": profile.full_name, "course": enrollment.offering.course.title_pl},
                )
            )
    return emails


def _send(request: Request, emails: list) -> None:
    for email in emails:
        request.app.state.services.jobs.enqueue(SEND_EMAIL_JOB, message_id=email.id)


@router.get("/me/enrollments", response_model=list[EnrollmentOut])
def my_enrollments(
    student: Principal = Depends(student_only), session: Session = Depends(get_session)
):
    return [_enrollment_out(session, e) for e in _active_enrollments(session, student.sub)]


@router.get("/me/timetable", response_model=list[TimetableEntry])
def my_timetable(
    locale: Locale = "pl",
    student: Principal = Depends(student_only),
    session: Session = Depends(get_session),
):
    rows = session.execute(
        select(ClassSession, CourseOffering)
        .join(CourseOffering, ClassSession.offering_id == CourseOffering.id)
        .join(Enrollment, Enrollment.offering_id == CourseOffering.id)
        .where(
            Enrollment.student_sub == student.sub,
            Enrollment.status == EnrollmentStatus.ENROLLED,
        )
        .order_by(ClassSession.weekday, ClassSession.starts_at)
    ).all()
    return [
        TimetableEntry(
            offering_id=offering.id,
            course_code=offering.course.code,
            course_title=_title(offering.course, locale),
            weekday=slot.weekday,
            starts_at=slot.starts_at,
            ends_at=slot.ends_at,
            room=slot.room,
        )
        for slot, offering in rows
    ]


@router.get("/me/grades", response_model=list[GradeOut])
def my_grades(
    locale: Locale = "pl",
    student: Principal = Depends(student_only),
    session: Session = Depends(get_session),
):
    enrollments = session.scalars(
        select(Enrollment).where(
            Enrollment.student_sub == student.sub,
            Enrollment.status == EnrollmentStatus.ENROLLED,
        )
    ).all()
    return [
        GradeOut(
            offering_id=e.offering_id,
            course_code=e.offering.course.code,
            course_title=_title(e.offering.course, locale),
            ects=e.offering.course.ects,
            semester=e.offering.semester,
            grade=e.grade.value if e.grade else None,
            graded_at=e.grade.graded_at if e.grade else None,
        )
        for e in enrollments
    ]


@router.get("/me/announcements", response_model=list[AnnouncementOut])
def my_announcements(
    student: Principal = Depends(student_only), session: Session = Depends(get_session)
):
    enrolled_ids = [
        e.offering_id
        for e in _active_enrollments(session, student.sub)
        if e.status == EnrollmentStatus.ENROLLED
    ]
    announcements = session.scalars(
        select(Announcement)
        .where(or_(Announcement.offering_id.is_(None), Announcement.offering_id.in_(enrolled_ids)))
        .order_by(Announcement.created_at.desc())
        .limit(50)
    ).all()
    return [_announcement_out(session, a) for a in announcements]


def _announcement_out(session: Session, announcement: Announcement) -> AnnouncementOut:
    offering = (
        session.get(CourseOffering, announcement.offering_id) if announcement.offering_id else None
    )
    return AnnouncementOut(
        id=announcement.id,
        offering_id=announcement.offering_id,
        course_code=offering.course.code if offering else None,
        title=announcement.title,
        body=announcement.body,
        created_at=announcement.created_at,
    )


@router.get("/teaching/offerings", response_model=list[OfferingOut])
def my_taught_offerings(
    locale: Locale = "pl",
    lecturer: Principal = Depends(lecturer_only),
    session: Session = Depends(get_session),
):
    offerings = session.scalars(
        select(CourseOffering).where(CourseOffering.lecturer_sub == lecturer.sub)
    ).all()
    return [_offering_out(o, locale) for o in offerings]


@router.get("/teaching/offerings/{offering_id}/roster", response_model=list[RosterEntry])
def roster(
    offering_id: int,
    lecturer: Principal = Depends(lecturer_only),
    session: Session = Depends(get_session),
):
    service.require_own_offering(service.get_offering(session, offering_id), lecturer)
    rows = session.execute(
        select(Enrollment, UserProfile)
        .outerjoin(UserProfile, UserProfile.sub == Enrollment.student_sub)
        .where(
            Enrollment.offering_id == offering_id,
            Enrollment.status == EnrollmentStatus.ENROLLED,
        )
        .order_by(UserProfile.full_name)
    ).all()
    return [
        RosterEntry(
            enrollment_id=enrollment.id,
            student_name=profile.full_name if profile else "",
            student_email=profile.email if profile else "",
            grade=enrollment.grade.value if enrollment.grade else None,
        )
        for enrollment, profile in rows
    ]


@router.put("/teaching/enrollments/{enrollment_id}/grade", response_model=RosterEntry)
def enter_grade(
    enrollment_id: int,
    data: GradeIn,
    lecturer: Principal = Depends(lecturer_only),
    session: Session = Depends(get_session),
):
    enrollment = service.set_grade(session, enrollment_id, data.value, lecturer)
    session.commit()
    profile = session.get(UserProfile, enrollment.student_sub)
    return RosterEntry(
        enrollment_id=enrollment.id,
        student_name=profile.full_name if profile else "",
        student_email=profile.email if profile else "",
        grade=enrollment.grade.value,
    )


@router.post(
    "/teaching/offerings/{offering_id}/announcements",
    response_model=AnnouncementOut,
    status_code=status.HTTP_201_CREATED,
)
def post_announcement(
    offering_id: int,
    data: AnnouncementIn,
    lecturer: Principal = Depends(lecturer_only),
    session: Session = Depends(get_session),
):
    service.require_own_offering(service.get_offering(session, offering_id), lecturer)
    announcement = Announcement(
        offering_id=offering_id, author_sub=lecturer.sub, **data.model_dump()
    )
    session.add(announcement)
    session.commit()
    return _announcement_out(session, announcement)


@router.post("/admin/courses", response_model=CreatedId, status_code=status.HTTP_201_CREATED)
def create_course(
    data: CourseIn,
    _admin: Principal = Depends(admin_only),
    session: Session = Depends(get_session),
):
    course = Course(**data.model_dump())
    session.add(course)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise Conflict("A course with this code already exists") from exc
    return CreatedId(id=course.id)


@router.post("/admin/offerings", response_model=CreatedId, status_code=status.HTTP_201_CREATED)
def create_offering(
    data: OfferingIn,
    _admin: Principal = Depends(admin_only),
    session: Session = Depends(get_session),
):
    if session.get(Course, data.course_id) is None:
        raise NotFound("Course not found")
    offering = CourseOffering(
        **data.model_dump(exclude={"sessions"}),
        sessions=[ClassSession(**s.model_dump()) for s in data.sessions],
    )
    session.add(offering)
    session.commit()
    return CreatedId(id=offering.id)


@router.patch("/admin/offerings/{offering_id}", response_model=OfferingOut)
def update_offering(
    offering_id: int,
    data: OfferingPatch,
    request: Request,
    _admin: Principal = Depends(admin_only),
    session: Session = Depends(get_session),
):
    offering = service.get_offering(session, offering_id)
    promoted = []
    if data.capacity is not None:
        promoted = service.change_capacity(session, offering_id, data.capacity)
    if data.enrollment_open is not None:
        offering.enrollment_open = data.enrollment_open
    emails = _queue_promotion_emails(session, promoted)
    session.commit()
    _send(request, emails)
    session.refresh(offering)
    return _offering_out(offering, "pl")


@router.post(
    "/admin/announcements", response_model=AnnouncementOut, status_code=status.HTTP_201_CREATED
)
def post_global_announcement(
    data: AnnouncementIn,
    admin: Principal = Depends(admin_only),
    session: Session = Depends(get_session),
):
    announcement = Announcement(offering_id=None, author_sub=admin.sub, **data.model_dump())
    session.add(announcement)
    session.commit()
    return _announcement_out(session, announcement)
