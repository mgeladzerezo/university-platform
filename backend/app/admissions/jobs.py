import uuid

from sqlalchemy.orm import Session

from app.admissions.models import ApplicationDocument, ScanStatus
from app.admissions.service import (
    PURGE_REJECTED_JOB,
    SCAN_DOCUMENT_JOB,
    purge_rejected_applications,
)
from app.db import utcnow
from app.jobs import job


@job(SCAN_DOCUMENT_JOB)
def scan_document(session: Session, services, document_id: str) -> None:
    document = session.get(ApplicationDocument, uuid.UUID(document_id))
    if document is None or document.scan_status != ScanStatus.PENDING_SCAN:
        return
    if services.scanner.is_clean(services.storage.read(document.storage_key)):
        document.scan_status = ScanStatus.CLEAN
    else:
        document.scan_status = ScanStatus.INFECTED
        services.storage.delete(document.storage_key)
    session.commit()


@job(PURGE_REJECTED_JOB)
def purge_rejected(session: Session, services) -> None:
    purge_rejected_applications(
        session, services.storage, utcnow(), services.settings.rejected_retention_days
    )
