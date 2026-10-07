import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admissions import service
from app.admissions.models import AccessAction, Application, ApplicationStatus, DocumentAccessLog
from app.admissions.schemas import (
    AccessLogOut,
    ApplicationCreate,
    ApplicationOut,
    DecisionIn,
    DocumentCreate,
    DocumentOut,
    DownloadLink,
    EducationStep,
    PersonalStep,
    QueueItem,
    StatementStep,
    UploadTicket,
)
from app.auth import Principal, Role, UserProfile, require_roles
from app.db import get_session
from app.notifications.service import SEND_EMAIL_JOB

router = APIRouter(prefix="/admissions", tags=["admissions"])

applicant_only = require_roles(Role.APPLICANT)
officer_only = require_roles(Role.ADMISSIONS_OFFICER)
applicant_or_officer = require_roles(Role.APPLICANT, Role.ADMISSIONS_OFFICER)


@router.post("/applications", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
def create_application(
    data: ApplicationCreate,
    applicant: Principal = Depends(applicant_only),
    session: Session = Depends(get_session),
):
    application = service.create_application(session, applicant, data.program_id, data.locale)
    session.commit()
    return service.to_out(application)


@router.get("/applications", response_model=list[ApplicationOut])
def list_own_applications(
    applicant: Principal = Depends(applicant_only), session: Session = Depends(get_session)
):
    applications = session.scalars(
        select(Application)
        .where(Application.applicant_sub == applicant.sub)
        .order_by(Application.created_at.desc())
    ).all()
    return [service.to_out(a) for a in applications]


@router.get("/applications/{application_id}", response_model=ApplicationOut)
def get_application(
    application_id: uuid.UUID,
    principal: Principal = Depends(applicant_or_officer),
    session: Session = Depends(get_session),
):
    application = service.get_application_for(session, application_id, principal)
    if application.applicant_sub != principal.sub:
        service.log_access(session, application.id, principal, AccessAction.VIEW_APPLICATION)
        session.commit()
    return service.to_out(application)


@router.put("/applications/{application_id}/personal", response_model=ApplicationOut)
def save_personal_step(
    application_id: uuid.UUID,
    data: PersonalStep,
    applicant: Principal = Depends(applicant_only),
    session: Session = Depends(get_session),
):
    application = service.get_own_application(session, application_id, applicant)
    service.save_step(application, "personal", data.model_dump(mode="json"))
    session.commit()
    return service.to_out(application)


@router.put("/applications/{application_id}/education", response_model=ApplicationOut)
def save_education_step(
    application_id: uuid.UUID,
    data: EducationStep,
    applicant: Principal = Depends(applicant_only),
    session: Session = Depends(get_session),
):
    application = service.get_own_application(session, application_id, applicant)
    service.save_step(application, "education", data.model_dump(mode="json"))
    session.commit()
    return service.to_out(application)


@router.put("/applications/{application_id}/statement", response_model=ApplicationOut)
def save_statement_step(
    application_id: uuid.UUID,
    data: StatementStep,
    applicant: Principal = Depends(applicant_only),
    session: Session = Depends(get_session),
):
    application = service.get_own_application(session, application_id, applicant)
    service.save_step(application, "statement", data.statement)
    session.commit()
    return service.to_out(application)


@router.post(
    "/applications/{application_id}/documents",
    response_model=UploadTicket,
    status_code=status.HTTP_201_CREATED,
)
def request_document_upload(
    application_id: uuid.UUID,
    data: DocumentCreate,
    request: Request,
    applicant: Principal = Depends(applicant_only),
    session: Session = Depends(get_session),
):
    services = request.app.state.services
    application = service.get_own_application(session, application_id, applicant)
    document, upload = service.request_upload(
        session, application, data, applicant, services.storage, services.settings.max_upload_bytes
    )
    session.commit()
    return UploadTicket(
        document=DocumentOut.model_validate(document),
        upload_url=upload.url,
        upload_fields=upload.fields,
    )


@router.post(
    "/applications/{application_id}/documents/{document_id}/complete",
    response_model=DocumentOut,
)
def complete_document_upload(
    application_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    applicant: Principal = Depends(applicant_only),
    session: Session = Depends(get_session),
):
    services = request.app.state.services
    application = service.get_own_application(session, application_id, applicant)
    document = service.get_document(application, document_id)
    service.complete_upload(document, services.storage, services.settings.max_upload_bytes)
    session.commit()
    services.jobs.enqueue(service.SCAN_DOCUMENT_JOB, document_id=str(document.id))
    return document


@router.get(
    "/applications/{application_id}/documents/{document_id}/download",
    response_model=DownloadLink,
)
def get_document_download_link(
    application_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(applicant_or_officer),
    session: Session = Depends(get_session),
):
    application = service.get_application_for(session, application_id, principal)
    document = service.get_document(application, document_id)
    url = service.download_url(
        session, application, document, principal, request.app.state.services.storage
    )
    session.commit()
    return DownloadLink(url=url)


@router.delete(
    "/applications/{application_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_document(
    application_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    applicant: Principal = Depends(applicant_only),
    session: Session = Depends(get_session),
) -> None:
    application = service.get_own_application(session, application_id, applicant)
    document = service.get_document(application, document_id)
    service.delete_document(
        session, application, document, applicant, request.app.state.services.storage
    )
    session.commit()


@router.post("/applications/{application_id}/submit", response_model=ApplicationOut)
def submit_application(
    application_id: uuid.UUID,
    request: Request,
    applicant: Principal = Depends(applicant_only),
    session: Session = Depends(get_session),
):
    application = service.get_own_application(session, application_id, applicant)
    email = service.submit(session, application, applicant)
    session.commit()
    request.app.state.services.jobs.enqueue(SEND_EMAIL_JOB, message_id=email.id)
    return service.to_out(application)


@router.post("/applications/{application_id}/withdraw", response_model=ApplicationOut)
def withdraw_application(
    application_id: uuid.UUID,
    applicant: Principal = Depends(applicant_only),
    session: Session = Depends(get_session),
):
    application = service.get_own_application(session, application_id, applicant)
    service.withdraw(application, applicant)
    session.commit()
    return service.to_out(application)


@router.get("/review/applications", response_model=list[QueueItem])
def review_queue(
    status_filter: ApplicationStatus = Query(default=ApplicationStatus.SUBMITTED, alias="status"),
    _officer: Principal = Depends(officer_only),
    session: Session = Depends(get_session),
):
    applications = session.scalars(
        select(Application)
        .where(Application.status == status_filter)
        .order_by(Application.submitted_at)
    ).all()
    return [
        QueueItem(
            id=a.id,
            applicant_name=_applicant_name(a),
            program_name=a.program.name_pl,
            status=a.status,
            submitted_at=a.submitted_at,
        )
        for a in applications
    ]


def _applicant_name(application: Application) -> str:
    personal = application.personal or {}
    return f"{personal.get('first_name', '')} {personal.get('last_name', '')}".strip()


@router.post("/review/applications/{application_id}/start", response_model=ApplicationOut)
def start_review(
    application_id: uuid.UUID,
    officer: Principal = Depends(officer_only),
    session: Session = Depends(get_session),
):
    application = service.get_application_for(session, application_id, officer)
    service.start_review(application, officer)
    session.commit()
    return service.to_out(application)


@router.post("/review/applications/{application_id}/decision", response_model=ApplicationOut)
def decide_application(
    application_id: uuid.UUID,
    data: DecisionIn,
    request: Request,
    officer: Principal = Depends(officer_only),
    session: Session = Depends(get_session),
):
    application = service.get_application_for(session, application_id, officer)
    profile = session.get(UserProfile, application.applicant_sub)
    email = service.decide(session, application, officer, data.decision, data.note, profile.email)
    session.commit()
    request.app.state.services.jobs.enqueue(SEND_EMAIL_JOB, message_id=email.id)
    return service.to_out(application)


@router.get("/review/applications/{application_id}/access-log", response_model=list[AccessLogOut])
def application_access_log(
    application_id: uuid.UUID,
    _officer: Principal = Depends(officer_only),
    session: Session = Depends(get_session),
):
    return session.scalars(
        select(DocumentAccessLog)
        .where(DocumentAccessLog.application_id == application_id)
        .order_by(DocumentAccessLog.id)
    ).all()
