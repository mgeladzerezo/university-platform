from collections.abc import Iterator
from dataclasses import dataclass, field

from app.assistant.llm import LlmUnavailable
from app.jobs import JOBS
from app.storage import PresignedUpload


class InMemoryStorage:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def presign_upload(self, key: str, content_type: str, max_bytes: int) -> PresignedUpload:
        return PresignedUpload(url="https://storage.test/upload", fields={"key": key})

    def presign_download(self, key: str, filename: str) -> str:
        return f"https://storage.test/download/{key}?signature=test"

    def size(self, key: str) -> int | None:
        return len(self.objects[key]) if key in self.objects else None

    def read(self, key: str) -> bytes:
        return self.objects[key]

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


@dataclass
class SentEmail:
    recipient: str
    subject: str
    body: str


class RecordingEmailSender:
    def __init__(self):
        self.sent: list[SentEmail] = []

    def send(self, recipient: str, subject: str, body: str) -> None:
        self.sent.append(SentEmail(recipient, subject, body))


class SignatureScanner:
    """Flags content containing the EICAR marker, like a real scanner would."""

    def is_clean(self, data: bytes) -> bool:
        return b"EICAR" not in data


class InlineJobQueue:
    """Records enqueued jobs; `run_pending` executes them like a worker would."""

    def __init__(self):
        self.pending: list[tuple[str, dict]] = []

    def enqueue(self, name: str, **kwargs) -> None:
        self.pending.append((name, kwargs))

    def run_pending(self, session_factory, services) -> int:
        jobs, self.pending = self.pending, []
        for name, kwargs in jobs:
            with session_factory() as session:
                JOBS[name](session, services, **kwargs)
        return len(jobs)


@dataclass
class FakeLlm:
    model: str = "fake-model"
    reply: str = "Rejestracja trwa do 10 lipca [1]."
    fail: bool = False
    calls: list[tuple[str, str]] = field(default_factory=list)

    def stream(self, system: str, user: str) -> Iterator[str]:
        self.calls.append((system, user))
        if self.fail:
            raise LlmUnavailable("down")
        # Three-character pieces, so sentinel detection is exercised across chunks.
        for start in range(0, len(self.reply), 3):
            yield self.reply[start : start + 3]

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if self.fail:
            raise LlmUnavailable("down")
        return self.reply
