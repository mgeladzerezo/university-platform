from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.assistant.jobs import INDEX_CONTENT_JOB
from app.auth import Principal, Role, require_roles
from app.content import service
from app.content.models import (
    ContactMessage,
    ContentItem,
    ContentKind,
    ContentStatus,
    DegreeLevel,
    Faculty,
    Program,
    StaffMember,
    WorkflowEvent,
)
from app.content.schemas import (
    ContactIn,
    ContentEditorial,
    ContentIn,
    ContentPublic,
    CreatedId,
    FacultyIn,
    FacultyOut,
    Locale,
    ProgramIn,
    ProgramOut,
    StaffIn,
    StaffOut,
    TransitionIn,
    WorkflowEventOut,
)
from app.db import get_session
from app.errors import Conflict, NotFound
from app.notifications.service import SEND_EMAIL_JOB, queue_email
from app.ratelimit import enforce_rate_limit

public = APIRouter(prefix="/public", tags=["public"])
cms = APIRouter(prefix="/cms", tags=["cms"])
catalogue_admin = APIRouter(prefix="/admin/catalogue", tags=["catalogue-admin"])

editor_only = require_roles(Role.EDITOR)
admin_only = require_roles(Role.ADMIN)


def _localized(obj, field: str, locale: str) -> str:
    return getattr(obj, f"{field}_{locale}")


def _program_out(program: Program, locale: str) -> ProgramOut:
    return ProgramOut(
        id=program.id,
        slug=program.slug,
        name=_localized(program, "name", locale),
        description=_localized(program, "description", locale),
        degree_level=program.degree_level,
        mode=program.mode,
        teaching_language=program.teaching_language,
        semesters=program.semesters,
        faculty_slug=program.faculty.slug,
        faculty_name=_localized(program.faculty, "name", locale),
    )


@public.get("/faculties", response_model=list[FacultyOut])
def list_faculties(locale: Locale = "pl", session: Session = Depends(get_session)):
    faculties = session.scalars(select(Faculty).order_by(Faculty.slug)).all()
    return [
        FacultyOut(
            id=f.id,
            slug=f.slug,
            name=_localized(f, "name", locale),
            description=_localized(f, "description", locale),
        )
        for f in faculties
    ]


@public.get("/programs", response_model=list[ProgramOut])
def list_programs(
    locale: Locale = "pl",
    q: str | None = Query(default=None, max_length=100),
    faculty: str | None = None,
    level: DegreeLevel | None = None,
    session: Session = Depends(get_session),
):
    query = select(Program).join(Program.faculty).order_by(Program.slug)
    if q and q.strip():
        query = query.where(service.program_search_filter(session, q.strip()))
    if faculty:
        query = query.where(Faculty.slug == faculty)
    if level:
        query = query.where(Program.degree_level == level)
    return [_program_out(p, locale) for p in session.scalars(query).all()]


@public.get("/programs/{slug}", response_model=ProgramOut)
def get_program(slug: str, locale: Locale = "pl", session: Session = Depends(get_session)):
    program = session.scalar(select(Program).where(Program.slug == slug))
    if program is None:
        raise NotFound("Program not found")
    return _program_out(program, locale)


@public.get("/staff", response_model=list[StaffOut])
def list_staff(
    locale: Locale = "pl",
    q: str | None = Query(default=None, max_length=100),
    faculty: str | None = None,
    session: Session = Depends(get_session),
):
    query = select(StaffMember).join(StaffMember.faculty).order_by(StaffMember.full_name)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        query = query.where(
            or_(StaffMember.full_name.ilike(pattern), StaffMember.position_pl.ilike(pattern))
        )
    if faculty:
        query = query.where(Faculty.slug == faculty)
    return [
        StaffOut(
            id=s.id,
            full_name=s.full_name,
            academic_title=s.academic_title,
            position=_localized(s, "position", locale),
            email=s.email,
            phone=s.phone,
            faculty_name=_localized(s.faculty, "name", locale),
        )
        for s in session.scalars(query).all()
    ]


@public.get("/content", response_model=list[ContentPublic])
def list_published_content(
    kind: ContentKind,
    locale: Locale = "pl",
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    query = service.published_query(kind, locale)
    if q and q.strip():
        query = query.where(service.content_search_filter(session, q.strip()))
    if kind == ContentKind.EVENT:
        query = query.order_by(ContentItem.event_starts_at)
    else:
        query = query.order_by(ContentItem.published_at.desc())
    return session.scalars(query.limit(limit).offset(offset)).all()


@public.get("/content/{kind}/{slug}", response_model=ContentPublic)
def get_published_content(
    kind: ContentKind, slug: str, locale: Locale = "pl", session: Session = Depends(get_session)
):
    item = session.scalar(service.published_query(kind, locale).where(ContentItem.slug == slug))
    if item is None:
        raise NotFound("Content not found")
    return item


@public.post("/contact", status_code=status.HTTP_202_ACCEPTED)
def send_contact_message(
    data: ContactIn, request: Request, session: Session = Depends(get_session)
) -> dict[str, str]:
    services = request.app.state.services
    enforce_rate_limit(request, "contact", services.settings.contact_rate_limit_per_hour, 3600)
    session.add(ContactMessage(**data.model_dump(exclude={"locale"})))
    email = queue_email(
        session,
        services.settings.contact_inbox,
        "contact_message",
        data.locale,
        data.model_dump(include={"name", "email", "subject", "message"}),
    )
    session.commit()
    services.jobs.enqueue(SEND_EMAIL_JOB, message_id=email.id)
    return {"status": "accepted"}


@cms.get("/content", response_model=list[ContentEditorial])
def list_content(
    status_filter: ContentStatus | None = Query(default=None, alias="status"),
    kind: ContentKind | None = None,
    _editor: Principal = Depends(editor_only),
    session: Session = Depends(get_session),
):
    query = select(ContentItem).order_by(ContentItem.updated_at.desc())
    if status_filter:
        query = query.where(ContentItem.status == status_filter)
    if kind:
        query = query.where(ContentItem.kind == kind)
    return session.scalars(query).all()


@cms.post("/content", response_model=ContentEditorial, status_code=status.HTTP_201_CREATED)
def create_content(
    data: ContentIn,
    editor: Principal = Depends(editor_only),
    session: Session = Depends(get_session),
):
    item = service.create_content(session, data, editor)
    session.commit()
    return item


@cms.get("/content/{content_id}", response_model=ContentEditorial)
def get_content(
    content_id: int,
    _editor: Principal = Depends(editor_only),
    session: Session = Depends(get_session),
):
    return service.get_content(session, content_id)


@cms.put("/content/{content_id}", response_model=ContentEditorial)
def update_content(
    content_id: int,
    data: ContentIn,
    _editor: Principal = Depends(editor_only),
    session: Session = Depends(get_session),
):
    item = service.update_content(session, service.get_content(session, content_id), data)
    session.commit()
    return item


@cms.post("/content/{content_id}/transitions", response_model=ContentEditorial)
def transition_content(
    content_id: int,
    data: TransitionIn,
    request: Request,
    editor: Principal = Depends(editor_only),
    session: Session = Depends(get_session),
):
    services = request.app.state.services
    item = service.apply_transition(
        session,
        service.get_content(session, content_id),
        data.action,
        editor,
        data.comment,
        services.chunk_store,
    )
    session.commit()
    if item.status == ContentStatus.PUBLISHED:
        services.jobs.enqueue(INDEX_CONTENT_JOB, content_item_id=item.id)
    return item


@cms.get("/content/{content_id}/history", response_model=list[WorkflowEventOut])
def content_history(
    content_id: int,
    _editor: Principal = Depends(editor_only),
    session: Session = Depends(get_session),
):
    service.get_content(session, content_id)
    return session.scalars(
        select(WorkflowEvent)
        .where(WorkflowEvent.content_item_id == content_id)
        .order_by(WorkflowEvent.id)
    ).all()


@catalogue_admin.post("/faculties", response_model=CreatedId, status_code=status.HTTP_201_CREATED)
def create_faculty(
    data: FacultyIn,
    _admin: Principal = Depends(admin_only),
    session: Session = Depends(get_session),
):
    return _create(session, Faculty(**data.model_dump()))


@catalogue_admin.post("/programs", response_model=CreatedId, status_code=status.HTTP_201_CREATED)
def create_program(
    data: ProgramIn,
    _admin: Principal = Depends(admin_only),
    session: Session = Depends(get_session),
):
    if session.get(Faculty, data.faculty_id) is None:
        raise NotFound("Faculty not found")
    return _create(session, Program(**data.model_dump()))


@catalogue_admin.post("/staff", response_model=CreatedId, status_code=status.HTTP_201_CREATED)
def create_staff_member(
    data: StaffIn,
    _admin: Principal = Depends(admin_only),
    session: Session = Depends(get_session),
):
    if session.get(Faculty, data.faculty_id) is None:
        raise NotFound("Faculty not found")
    return _create(session, StaffMember(**data.model_dump()))


def _create(session: Session, entity) -> CreatedId:
    session.add(entity)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise Conflict("An entry with this slug already exists") from exc
    return CreatedId(id=entity.id)
