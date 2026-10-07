"""Tests for the production adapters that can be exercised without a network."""

import socket
import struct
import threading

import fakeredis
import pytest

from app.assistant.chunking import chunk_text, chunks_for_content, html_to_text
from app.assistant.embeddings import EMBEDDING_DIMENSIONS, HashingEmbedder, cosine
from app.jobs import JOBS, CeleryJobQueue
from app.notifications.models import EmailMessage, EmailStatus
from app.notifications.templates import render
from app.ratelimit import RedisRateLimiter
from app.scanning import ClamAvScanner, parse_clamd_reply
from app.storage import S3Storage


@pytest.fixture
def s3(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    return S3Storage("uni-documents", "eu-central-1", ttl_seconds=300)


def test_s3_presigned_upload_enforces_size_and_content_type(s3):
    upload = s3.presign_upload("applications/a/b", "application/pdf", max_bytes=1024)

    assert upload.url == "https://uni-documents.s3.amazonaws.com/"
    assert upload.fields["key"] == "applications/a/b"
    assert upload.fields["Content-Type"] == "application/pdf"
    assert "policy" in upload.fields
    assert "x-amz-signature" in upload.fields


def test_s3_presigned_download_is_short_lived_attachment(s3):
    url = s3.presign_download("applications/a/b", 'dyplom "final".pdf')

    assert "X-Amz-Expires=300" in url
    assert "response-content-disposition=attachment" in url
    assert "%22%22" not in url


def test_clamd_replies_are_parsed():
    assert parse_clamd_reply("stream: OK") is True
    assert parse_clamd_reply("stream: Win.Test.EICAR_HDB-1 FOUND") is False
    with pytest.raises(RuntimeError):
        parse_clamd_reply("INSTREAM size limit exceeded. ERROR")


def _fake_clamd(reply: bytes) -> tuple[int, list[bytes]]:
    """A one-connection clamd speaking the INSTREAM protocol; returns (port, received)."""
    server = socket.create_server(("127.0.0.1", 0))
    received: list[bytes] = []

    def serve():
        conn, _ = server.accept()
        with conn, server:
            command = conn.recv(10)
            received.append(command)
            while True:
                (length,) = struct.unpack(">I", _read_exact(conn, 4))
                if length == 0:
                    break
                received.append(_read_exact(conn, length))
            conn.sendall(reply)

    threading.Thread(target=serve, daemon=True).start()
    return server.getsockname()[1], received


def _read_exact(conn: socket.socket, count: int) -> bytes:
    data = b""
    while len(data) < count:
        data += conn.recv(count - len(data))
    return data


def test_clamav_client_streams_file_and_reads_verdict():
    port, received = _fake_clamd(b"stream: OK\0")
    payload = b"x" * 150_000

    assert ClamAvScanner("127.0.0.1", port).is_clean(payload) is True
    assert received[0] == b"zINSTREAM\0"
    assert b"".join(received[1:]) == payload
    assert len(received) == 4


def test_clamav_client_reports_infected_file():
    port, _ = _fake_clamd(b"stream: Eicar-Signature FOUND\0")

    assert ClamAvScanner("127.0.0.1", port).is_clean(b"EICAR") is False


def test_redis_rate_limiter_counts_per_key_within_window():
    limiter = RedisRateLimiter(fakeredis.FakeRedis())

    assert [limiter.allow("chat:1.2.3.4", 3, 60) for _ in range(4)] == [True, True, True, False]
    assert limiter.allow("chat:5.6.7.8", 3, 60) is True


def test_every_job_is_registered_as_a_celery_task():
    from app import worker

    assert set(JOBS) == {
        "notifications.send_email",
        "admissions.scan_document",
        "admissions.purge_rejected",
        "assistant.index_content",
    }
    assert set(JOBS) <= set(worker.celery_app.tasks)
    assert worker.celery_app.conf.beat_schedule["purge-rejected-applications"]["task"] in JOBS


def test_celery_queue_refuses_unknown_job_names():
    with pytest.raises(KeyError):
        CeleryJobQueue(celery_app=None).enqueue("no.such.job")


def test_email_templates_render_in_both_languages():
    polish = render("decision_accepted", "pl", {"name": "Maja", "program": "Informatyka"})
    english = render("decision_accepted", "en", {"name": "Maja", "program": "Computer Science"})

    assert "Maja" in polish.body and "Informatyka" in polish.body
    assert english.subject == "Admission decision: accepted"


def test_failed_email_is_marked_failed_and_job_raises_for_retry(ctx):
    class BrokenSender:
        def send(self, *_args) -> None:
            raise ConnectionError("SMTP down")

    ctx.services.email = BrokenSender()
    with ctx.session() as session:
        message = EmailMessage(
            recipient="a@b.test", template="waitlist_promoted", locale="pl",
            context={"name": "Ala", "course": "Algorytmy"},
        )  # fmt: skip
        session.add(message)
        session.commit()
        message_id = message.id

    ctx.services.jobs.enqueue("notifications.send_email", message_id=message_id)
    with pytest.raises(ConnectionError):
        ctx.run_jobs()

    with ctx.session() as session:
        assert session.get(EmailMessage, message_id).status == EmailStatus.FAILED


def test_html_is_reduced_to_text_paragraphs():
    text = html_to_text(
        "<h2>Opłaty</h2><p>Czesne: <strong>2400&nbsp;zł</strong></p><ul><li>raty</li></ul>"
    )

    assert text == "Opłaty\nCzesne: 2400 zł\nraty"


def test_chunks_respect_size_limit_and_carry_the_title():
    body = "".join(f"<p>{'słowo ' * 40}</p>" for _ in range(6))

    chunks = chunks_for_content("Regulamin", "", body)

    assert len(chunks) > 1
    assert all(chunk.startswith("Regulamin\n") for chunk in chunks)
    assert all(len(chunk) <= 600 + len("Regulamin\n") for chunk in chunks)
    assert chunk_text("a" * 1500, max_chars=600) == ["a" * 600, "a" * 600, "a" * 300]


def test_hashing_embedder_is_deterministic_and_ranks_by_overlap():
    embedder = HashingEmbedder()
    query = embedder.embed_query("opłata rekrutacyjna")
    related, unrelated = embedder.embed_documents(
        ["Opłata rekrutacyjna wynosi 85 zł.", "Biblioteka jest otwarta w soboty."]
    )

    assert len(query) == EMBEDDING_DIMENSIONS
    assert query == embedder.embed_query("OPŁATA rekrutacyjna")
    assert cosine(query, related) > 0.5 > cosine(query, unrelated)
