import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.admissions.models import (
    REQUIRED_DOCUMENTS,
    AccessAction,
    Application,
    ApplicationDocument,
    ApplicationStatus,
    ApplicationStatusEvent,
    DocumentAccessLog,
    DocumentType,
    ScanStatus,
)
from app.admissions.schemas import ApplicationOut, DocumentCreate
from app.auth import Principal, Role, remember_user
from app.content.models import Program
from app.db import utcnow
from app.errors import Conflict, InvalidInput, NotFound
from app.metrics import RETENTION_PURGED
from app.notifications.models import EmailMessage
from app.notifications.service import queue_email
from app.storage import ObjectStorage, PresignedUpload

SCAN_DOCUMENT_JOB = "admissions.scan_document"
PURGE_REJECTED_JOB = "admissions.purge_rejected"
RETENTION_ACTOR = "system:retention"

STAFF_ROLES = (Role.ADMISSIONS_OFFICER,)
WITHDRAWABLE = {
    ApplicationStatus.DRAFT,
    ApplicationStatus.SUBMITTED,
    ApplicationStatus.UNDER_REVIEW,
}


def create_application(
    session: Session, applicant: Principal, program_id: int, locale: str
) -> Application:
    if session.get(Program, program_id) is None:
        raise NotFound("Program not found")
    remember_user(session, applicant)
    application = Application(applicant_sub=applicant.sub, program_id=program_id, locale=locale)
    session.add(application)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise Conflict("You already have an application for this program") from exc
    return application


def get_application_for(
    session: Session, application_id: uuid.UUID, principal: Principal
) -> Application:
    """Staff may load any application; applicants only their own.

    A foreign application is reported as missing so ids cannot be probed.
    """
    application = session.get(Application, application_id)
    is_staff = principal.has_any(*STAFF_ROLES)
    if application is None or (not is_staff and application.applicant_sub != principal.sub):
        raise NotFound("Application not found")
    return application


def get_own_application(
    session: Session, application_id: uuid.UUID, applicant: Principal
) -> Application:
    application = session.get(Application, application_id)
    if application is None or application.applicant_sub != applicant.sub:
        raise NotFound("Application not found")
    return application


def log_access(
    session: Session,
    application_id: uuid.UUID,
    actor: Principal,
    action: AccessAction,
    document_id: uuid.UUID | None = None,
) -> None:
    session.add(
        DocumentAccessLog(
            application_id=application_id,
            document_id=document_id,
            actor_sub=actor.sub,
            actor_roles=",".join(sorted(actor.roles)),
            action=action,
        )
    )


def save_step(application: Application, field: str, value) -> None:
    _require_draft(application)
    setattr(application, field, value)


def _require_draft(application: Application) -> None:
    if application.status != ApplicationStatus.DRAFT:
        raise Conflict("The application can only be changed while it is a draft")


def request_upload(
    session: Session,
    application: Application,
    data: DocumentCreate,
    actor: Principal,
    storage: ObjectStorage,
    max_bytes: int,
) -> tuple[ApplicationDocument, PresignedUpload]:
    _require_draft(application)
    if data.size_bytes > max_bytes:
        raise InvalidInput(f"File is larger than {max_bytes} bytes")
    document_id = uuid.uuid4()
    document = ApplicationDocument(
        id=document_id,
        application_id=application.id,
        doc_type=data.doc_type,
        filename=data.filename,
        content_type=data.content_type,
        size_bytes=data.size_bytes,
        # The key never contains the user-supplied filename.
        storage_key=f"applications/{application.id}/{document_id}",
    )
    session.add(document)
    log_access(session, application.id, actor, AccessAction.UPLOAD_DOCUMENT, document_id)
    upload = storage.presign_upload(document.storage_key, data.content_type, max_bytes)
    return document, upload


def get_document(application: Application, document_id: uuid.UUID) -> ApplicationDocument:
    for document in application.documents:
        if document.id == document_id:
            return document
    raise NotFound("Document not found")


def complete_upload(document: ApplicationDocument, storage: ObjectStorage, max_bytes: int) -> None:
    if document.scan_status != ScanStatus.AWAITING_UPLOAD:
        raise Conflict("Upload already completed")
    size = storage.size(document.storage_key)
    if size is None:
        raise Conflict("The file has not been uploaded yet")
    if size > max_bytes:
        storage.delete(document.storage_key)
        raise InvalidInput("Uploaded file exceeds the size limit")
    document.size_bytes = size
    document.scan_status = ScanStatus.PENDING_SCAN


def delete_document(
    session: Session,
    application: Application,
    document: ApplicationDocument,
    actor: Principal,
    storage: ObjectStorage,
) -> None:
    _require_draft(application)
    storage.delete(document.storage_key)
    log_access(session, application.id, actor, AccessAction.DELETE_DOCUMENT, document.id)
    application.documents.remove(document)


def download_url(
    session: Session,
    application: Application,
    document: ApplicationDocument,
    actor: Principal,
    storage: ObjectStorage,
) -> str:
    if document.scan_status != ScanStatus.CLEAN:
        raise Conflict("The document is not available for download")
    log_access(session, application.id, actor, AccessAction.DOWNLOAD_DOCUMENT, document.id)
    return storage.presign_download(document.storage_key, document.filename)


def missing_documents(application: Application) -> list[DocumentType]:
    clean = {d.doc_type for d in application.documents if d.scan_status == ScanStatus.CLEAN}
    required = REQUIRED_DOCUMENTS[application.program.degree_level]
    return [doc_type for doc_type in required if doc_type not in clean]


def submit(session: Session, application: Application, applicant: Principal) -> EmailMessage:
    _require_draft(application)
    incomplete = [
        step for step in ("personal", "education", "statement") if not getattr(application, step)
    ]
    if incomplete:
        raise InvalidInput(f"Incomplete steps: {', '.join(incomplete)}")
    missing = missing_documents(application)
    if missing:
        raise InvalidInput(f"Missing or unscanned documents: {', '.join(missing)}")
    _change_status(application, ApplicationStatus.SUBMITTED, applicant.sub)
    application.submitted_at = utcnow()
    remember_user(session, applicant)
    return queue_email(
        session,
        applicant.email,
        "application_submitted",
        application.locale,
        _email_context(application),
    )


def withdraw(application: Application, applicant: Principal) -> None:
    if application.status not in WITHDRAWABLE:
        raise Conflict("The application can no longer be withdrawn")
    _change_status(application, ApplicationStatus.WITHDRAWN, applicant.sub)


def start_review(application: Application, officer: Principal) -> None:
    if application.status != ApplicationStatus.SUBMITTED:
        raise Conflict("Only submitted applications can be taken into review")
    _change_status(application, ApplicationStatus.UNDER_REVIEW, officer.sub)


def decide(
    session: Session,
    application: Application,
    officer: Principal,
    decision: str,
    note: str,
    applicant_email: str,
) -> EmailMessage:
    if application.status != ApplicationStatus.UNDER_REVIEW:
        raise Conflict("Only applications under review can be decided")
    _change_status(application, ApplicationStatus(decision), officer.sub)
    application.decided_at = utcnow()
    application.decided_by_sub = officer.sub
    application.decision_note = note
    return queue_email(
        session,
        applicant_email,
        f"decision_{decision}",
        application.locale,
        _email_context(application),
    )


def _change_status(application: Application, target: ApplicationStatus, actor_sub: str) -> None:
    application.history.append(
        ApplicationStatusEvent(
            from_status=application.status, to_status=target, actor_sub=actor_sub
        )
    )
    application.status = target


def _email_context(application: Application) -> dict:
    personal = application.personal or {}
    program = application.program
    return {
        "name": personal.get("first_name", ""),
        "program": program.name_en if application.locale == "en" else program.name_pl,
    }


def to_out(application: Application) -> ApplicationOut:
    program = application.program
    return ApplicationOut(
        id=application.id,
        program_id=application.program_id,
        program_name=program.name_en if application.locale == "en" else program.name_pl,
        status=application.status,
        personal=application.personal,
        education=application.education,
        statement=application.statement,
        documents=application.documents,
        missing_documents=missing_documents(application),
        history=application.history,
        created_at=application.created_at,
        submitted_at=application.submitted_at,
        decided_at=application.decided_at,
        decision_note=application.decision_note,
    )


def purge_rejected_applications(
    session: Session, storage: ObjectStorage, now: datetime, retention_days: int
) -> int:
    """Delete rejected applications decided more than `retention_days` ago.

    Stored files go first; if that fails the rows stay and the next run retries,
    so a file never ends up without a database record pointing at it.
    """
    cutoff = now - timedelta(days=retention_days)
    expired = session.scalars(
        select(Application).where(
            Application.status == ApplicationStatus.REJECTED,
            Application.decided_at < cutoff,
        )
    ).all()
    for application in expired:
        for document in application.documents:
            storage.delete(document.storage_key)
        session.add(
            DocumentAccessLog(
                application_id=application.id,
                actor_sub=RETENTION_ACTOR,
                actor_roles="",
                action=AccessAction.RETENTION_DELETE,
            )
        )
        session.delete(application)
        session.commit()
        RETENTION_PURGED.inc()
    return len(expired)
