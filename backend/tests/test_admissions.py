from datetime import timedelta

import pytest
from sqlalchemy import select

from app.admissions.models import (
    AccessAction,
    Application,
    ApplicationDocument,
    ApplicationStatus,
    DocumentAccessLog,
)
from app.admissions.service import purge_rejected_applications
from app.auth import Role
from app.db import utcnow

API = "/api/v1/admissions"

PERSONAL = {
    "first_name": "Maja",
    "last_name": "Kandydatka",
    "birth_date": "2007-03-14",
    "citizenship": "PL",
    "phone": "+48 600 000 000",
    "address_line": "ul. Lipowa 1",
    "city": "Kalinowo",
    "postal_code": "00-001",
}
EDUCATION = {
    "school_name": "I LO w Kalinowie",
    "graduation_year": 2026,
    "exam_results": [{"subject": "matematyka", "score_percent": 84}],
}
STATEMENT = {
    "statement": "Od lat interesuję się programowaniem i chcę rozwijać się w tym kierunku."
}


def start_application(ctx, headers, program_id: int) -> str:
    response = ctx.client.post(
        f"{API}/applications", json={"program_id": program_id}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def upload(
    ctx, headers, application_id: str, doc_type: str, content: bytes = b"%PDF-1.7 ok"
) -> str:
    ticket = ctx.client.post(
        f"{API}/applications/{application_id}/documents",
        json={
            "doc_type": doc_type,
            "filename": f"{doc_type}.pdf",
            "content_type": "application/pdf",
            "size_bytes": len(content),
        },
        headers=headers,
    )
    assert ticket.status_code == 201, ticket.text
    # The browser would POST the file to upload_url; the fake storage takes it directly.
    ctx.services.storage.objects[ticket.json()["upload_fields"]["key"]] = content
    document_id = ticket.json()["document"]["id"]
    done = ctx.client.post(
        f"{API}/applications/{application_id}/documents/{document_id}/complete", headers=headers
    )
    assert done.status_code == 200, done.text
    return document_id


def fill_and_submit(ctx, headers, program_id: int) -> str:
    application_id = start_application(ctx, headers, program_id)
    base = f"{API}/applications/{application_id}"
    assert ctx.client.put(f"{base}/personal", json=PERSONAL, headers=headers).status_code == 200
    assert ctx.client.put(f"{base}/education", json=EDUCATION, headers=headers).status_code == 200
    assert ctx.client.put(f"{base}/statement", json=STATEMENT, headers=headers).status_code == 200
    for doc_type in ("identity", "diploma", "photo"):
        upload(ctx, headers, application_id, doc_type)
    ctx.run_jobs()
    response = ctx.client.post(f"{base}/submit", headers=headers)
    assert response.status_code == 200, response.text
    return application_id


def decide(ctx, officer, application_id: str, decision: str):
    ctx.client.post(f"{API}/review/applications/{application_id}/start", headers=officer)
    return ctx.client.post(
        f"{API}/review/applications/{application_id}/decision",
        json={"decision": decision, "note": "Decyzja komisji."},
        headers=officer,
    )


def access_log(ctx, application_id: str) -> list[tuple[str, str]]:
    with ctx.session() as session:
        rows = session.scalars(select(DocumentAccessLog).order_by(DocumentAccessLog.id)).all()
        return [(r.actor_sub, r.action) for r in rows if str(r.application_id) == application_id]


def test_application_goes_from_draft_to_decision_with_emails(ctx, applicant, officer, program_id):
    application_id = fill_and_submit(ctx, applicant, program_id)
    ctx.run_jobs()
    assert ctx.services.email.sent[-1].subject == "Potwierdzenie złożenia wniosku"

    queue = ctx.client.get(f"{API}/review/applications", headers=officer).json()
    assert [(q["id"], q["applicant_name"]) for q in queue] == [(application_id, "Maja Kandydatka")]

    response = decide(ctx, officer, application_id, "accepted")

    assert response.status_code == 200
    ctx.run_jobs()
    email = ctx.services.email.sent[-1]
    assert email.recipient == "maja@mail.test"
    assert email.subject == "Decyzja rekrutacyjna: przyjęcie"
    assert "Informatyka" in email.body
    tracked = ctx.client.get(f"{API}/applications/{application_id}", headers=applicant).json()
    assert tracked["status"] == "accepted"
    assert [e["to_status"] for e in tracked["history"]] == ["submitted", "under_review", "accepted"]


def test_rejection_sends_rejection_email(ctx, applicant, officer, program_id):
    application_id = fill_and_submit(ctx, applicant, program_id)

    decide(ctx, officer, application_id, "rejected")
    ctx.run_jobs()

    assert ctx.services.email.sent[-1].subject == "Decyzja rekrutacyjna"


def test_submit_reports_incomplete_steps(ctx, applicant, program_id):
    application_id = start_application(ctx, applicant, program_id)

    response = ctx.client.post(f"{API}/applications/{application_id}/submit", headers=applicant)

    assert response.status_code == 422
    assert "personal" in response.json()["detail"]


def test_submit_requires_all_documents_to_be_scanned_clean(ctx, applicant, program_id):
    application_id = start_application(ctx, applicant, program_id)
    base = f"{API}/applications/{application_id}"
    ctx.client.put(f"{base}/personal", json=PERSONAL, headers=applicant)
    ctx.client.put(f"{base}/education", json=EDUCATION, headers=applicant)
    ctx.client.put(f"{base}/statement", json=STATEMENT, headers=applicant)
    upload(ctx, applicant, application_id, "identity")
    upload(ctx, applicant, application_id, "diploma")
    ctx.run_jobs()
    upload(ctx, applicant, application_id, "photo")  # scan still pending

    response = ctx.client.post(f"{base}/submit", headers=applicant)

    assert response.status_code == 422
    assert response.json()["detail"] == "Missing or unscanned documents: photo"
    assert ctx.client.get(base, headers=applicant).json()["missing_documents"] == ["photo"]


def test_infected_upload_is_flagged_deleted_and_not_downloadable(ctx, applicant, program_id):
    application_id = start_application(ctx, applicant, program_id)
    document_id = upload(ctx, applicant, application_id, "identity", b"X5O!P%@AP EICAR test")

    ctx.run_jobs()

    application = ctx.client.get(f"{API}/applications/{application_id}", headers=applicant).json()
    assert application["documents"][0]["scan_status"] == "infected"
    assert ctx.services.storage.objects == {}
    download = ctx.client.get(
        f"{API}/applications/{application_id}/documents/{document_id}/download", headers=applicant
    )
    assert download.status_code == 409


def test_upload_larger_than_declared_limit_is_rejected(ctx, applicant, program_id):
    application_id = start_application(ctx, applicant, program_id)
    url = f"{API}/applications/{application_id}/documents"
    body = {"doc_type": "photo", "filename": "p.png", "content_type": "image/png"}

    too_big = ctx.client.post(url, json={**body, "size_bytes": 5000}, headers=applicant)
    assert too_big.status_code == 422

    # A client that lies about the size is caught when the upload is completed.
    ticket = ctx.client.post(url, json={**body, "size_bytes": 10}, headers=applicant).json()
    key = ticket["upload_fields"]["key"]
    ctx.services.storage.objects[key] = b"x" * 5000
    done = ctx.client.post(f"{url}/{ticket['document']['id']}/complete", headers=applicant)
    assert done.status_code == 422
    assert key not in ctx.services.storage.objects


def test_unsupported_file_type_is_rejected(ctx, applicant, program_id):
    application_id = start_application(ctx, applicant, program_id)

    response = ctx.client.post(
        f"{API}/applications/{application_id}/documents",
        json={
            "doc_type": "photo",
            "filename": "run.exe",
            "content_type": "application/x-msdownload",
            "size_bytes": 10,
        },
        headers=applicant,
    )

    assert response.status_code == 422


def test_storage_key_does_not_contain_user_supplied_filename(ctx, applicant, program_id):
    application_id = start_application(ctx, applicant, program_id)

    ticket = ctx.client.post(
        f"{API}/applications/{application_id}/documents",
        json={
            "doc_type": "photo",
            "filename": "../../etc/passwd.png",
            "content_type": "image/png",
            "size_bytes": 10,
        },
        headers=applicant,
    ).json()

    assert ticket["upload_fields"]["key"] == (
        f"applications/{application_id}/{ticket['document']['id']}"
    )


def test_applicant_cannot_see_or_change_someone_elses_application(ctx, applicant, program_id):
    application_id = fill_and_submit(ctx, applicant, program_id)
    other = ctx.auth("other", Role.APPLICANT)
    base = f"{API}/applications/{application_id}"
    with ctx.session() as session:
        document_id = session.scalar(select(ApplicationDocument.id).limit(1))

    assert ctx.client.get(base, headers=other).status_code == 404
    assert ctx.client.put(f"{base}/personal", json=PERSONAL, headers=other).status_code == 404
    assert ctx.client.post(f"{base}/withdraw", headers=other).status_code == 404
    assert (
        ctx.client.get(f"{base}/documents/{document_id}/download", headers=other).status_code == 404
    )
    assert ctx.client.get(f"{API}/applications", headers=other).json() == []


def test_submitted_application_is_read_only_for_the_applicant(ctx, applicant, program_id):
    application_id = fill_and_submit(ctx, applicant, program_id)

    response = ctx.client.put(
        f"{API}/applications/{application_id}/personal", json=PERSONAL, headers=applicant
    )

    assert response.status_code == 409


def test_second_application_for_same_program_conflicts(ctx, applicant, program_id):
    start_application(ctx, applicant, program_id)

    response = ctx.client.post(
        f"{API}/applications", json={"program_id": program_id}, headers=applicant
    )

    assert response.status_code == 409


def test_decision_requires_review_to_be_started(ctx, applicant, officer, program_id):
    application_id = fill_and_submit(ctx, applicant, program_id)

    response = ctx.client.post(
        f"{API}/review/applications/{application_id}/decision",
        json={"decision": "accepted"},
        headers=officer,
    )

    assert response.status_code == 409


def test_withdrawn_application_cannot_be_reviewed(ctx, applicant, officer, program_id):
    application_id = fill_and_submit(ctx, applicant, program_id)
    ctx.client.post(f"{API}/applications/{application_id}/withdraw", headers=applicant)

    response = ctx.client.post(f"{API}/review/applications/{application_id}/start", headers=officer)

    assert response.status_code == 409


def test_access_log_records_who_did_what(ctx, applicant, officer, program_id):
    application_id = fill_and_submit(ctx, applicant, program_id)
    base = f"{API}/applications/{application_id}"
    document_id = ctx.client.get(base, headers=applicant).json()["documents"][0]["id"]

    ctx.client.get(base, headers=officer)
    link = ctx.client.get(f"{base}/documents/{document_id}/download", headers=officer)
    ctx.client.get(f"{base}/documents/{document_id}/download", headers=applicant)

    assert link.json()["url"].startswith("https://storage.test/download/applications/")
    assert access_log(ctx, application_id) == [
        ("maja", AccessAction.UPLOAD_DOCUMENT),
        ("maja", AccessAction.UPLOAD_DOCUMENT),
        ("maja", AccessAction.UPLOAD_DOCUMENT),
        ("officer-1", AccessAction.VIEW_APPLICATION),
        ("officer-1", AccessAction.DOWNLOAD_DOCUMENT),
        ("maja", AccessAction.DOWNLOAD_DOCUMENT),
    ]
    via_api = ctx.client.get(
        f"{API}/review/applications/{application_id}/access-log", headers=officer
    ).json()
    assert via_api[4]["actor_roles"] == "admissions_officer"
    assert via_api[4]["document_id"] == document_id


def test_failed_download_attempt_is_not_logged_as_access(ctx, applicant, program_id):
    application_id = start_application(ctx, applicant, program_id)
    document_id = upload(ctx, applicant, application_id, "identity")  # scan pending

    response = ctx.client.get(
        f"{API}/applications/{application_id}/documents/{document_id}/download", headers=applicant
    )

    assert response.status_code == 409
    assert (("maja", AccessAction.DOWNLOAD_DOCUMENT)) not in access_log(ctx, application_id)


def _backdate_decision(ctx, application_id: str, days: int) -> None:
    with ctx.session() as session:
        application = session.scalars(select(Application)).all()
        target = next(a for a in application if str(a.id) == application_id)
        target.decided_at = utcnow() - timedelta(days=days)
        session.commit()


def test_retention_job_deletes_only_old_rejected_applications(ctx, officer, program_id):
    old_rejected = fill_and_submit(ctx, ctx.auth("a1", Role.APPLICANT), program_id)
    recent_rejected = fill_and_submit(ctx, ctx.auth("a2", Role.APPLICANT), program_id)
    old_accepted = fill_and_submit(ctx, ctx.auth("a3", Role.APPLICANT), program_id)
    decide(ctx, officer, old_rejected, "rejected")
    decide(ctx, officer, recent_rejected, "rejected")
    decide(ctx, officer, old_accepted, "accepted")
    _backdate_decision(ctx, old_rejected, days=31)
    _backdate_decision(ctx, recent_rejected, days=29)
    _backdate_decision(ctx, old_accepted, days=400)
    assert len(ctx.services.storage.objects) == 9

    ctx.services.jobs.enqueue("admissions.purge_rejected")
    ctx.run_jobs()

    with ctx.session() as session:
        remaining = {str(a.id): a.status for a in session.scalars(select(Application))}
        documents = session.scalars(select(ApplicationDocument)).all()
    assert remaining == {
        recent_rejected: ApplicationStatus.REJECTED,
        old_accepted: ApplicationStatus.ACCEPTED,
    }
    assert len(documents) == 6
    assert len(ctx.services.storage.objects) == 6
    assert not any(old_rejected in key for key in ctx.services.storage.objects)


def test_retention_keeps_the_audit_trail_and_records_the_deletion(ctx, officer, program_id):
    application_id = fill_and_submit(ctx, ctx.auth("a1", Role.APPLICANT), program_id)
    decide(ctx, officer, application_id, "rejected")
    _backdate_decision(ctx, application_id, days=31)

    with ctx.session() as session:
        purged = purge_rejected_applications(session, ctx.services.storage, utcnow(), 30)

    assert purged == 1
    log = access_log(ctx, application_id)
    assert log[0] == ("a1", AccessAction.UPLOAD_DOCUMENT)
    assert log[-1] == ("system:retention", AccessAction.RETENTION_DELETE)


def test_retention_period_is_configurable(ctx, officer, program_id):
    application_id = fill_and_submit(ctx, ctx.auth("a1", Role.APPLICANT), program_id)
    decide(ctx, officer, application_id, "rejected")
    _backdate_decision(ctx, application_id, days=31)

    with ctx.session() as session:
        assert purge_rejected_applications(session, ctx.services.storage, utcnow(), 90) == 0
        assert purge_rejected_applications(session, ctx.services.storage, utcnow(), 7) == 1


def test_retention_keeps_database_rows_when_storage_delete_fails(ctx, officer, program_id):
    application_id = fill_and_submit(ctx, ctx.auth("a1", Role.APPLICANT), program_id)
    decide(ctx, officer, application_id, "rejected")
    _backdate_decision(ctx, application_id, days=31)

    class BrokenStorage:
        def delete(self, key: str) -> None:
            raise ConnectionError("S3 unavailable")

    with ctx.session() as session, pytest.raises(ConnectionError):
        purge_rejected_applications(session, BrokenStorage(), utcnow(), 30)

    with ctx.session() as session:
        assert session.scalar(select(Application.id)) is not None
