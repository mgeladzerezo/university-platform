"""Retrieval evaluation for the public assistant.

Loads the bundled corpus into an in-memory database, indexes it and checks, for
each question, that the expected page is among the retrieved sources, or that
the assistant refuses before calling the model when nothing should match.

    python -m app.assistant.evaluation.runner --embedder hashing --min-score 0.2
    python -m app.assistant.evaluation.runner --embedder e5 --min-score 0.8
"""

import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime
from importlib import resources
from types import SimpleNamespace

from sqlalchemy.orm import Session

from app.assistant.embeddings import E5Embedder, Embedder, HashingEmbedder
from app.assistant.jobs import index_content
from app.assistant.service import plan_chat
from app.assistant.store import JsonChunkStore
from app.content.models import ContentItem, ContentStatus
from app.db import Base, make_engine, make_session_factory, utcnow

_PACKAGE = "app.assistant.evaluation"


@dataclass
class EvalReport:
    total: int = 0
    passed: int = 0
    failures: list[str] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.passed / self.total if self.total else 0.0


def load_corpus() -> list[dict]:
    return json.loads(resources.files(_PACKAGE).joinpath("corpus.json").read_text("utf-8"))


def load_dataset() -> list[dict]:
    lines = resources.files(_PACKAGE).joinpath("dataset.jsonl").read_text("utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def publish_corpus(session: Session, services, author_sub: str = "seed") -> None:
    """Insert the corpus as published content and index it for the assistant."""
    for entry in load_corpus():
        fields = dict(entry)
        if "event_starts_at" in fields:
            fields["event_starts_at"] = datetime.fromisoformat(fields["event_starts_at"])
        item = ContentItem(
            **fields, status=ContentStatus.PUBLISHED, author_sub=author_sub, published_at=utcnow()
        )
        session.add(item)
        session.flush()
        index_content(session, services, content_item_id=item.id)


def run(embedder: Embedder, min_score: float, top_k: int = 4) -> EvalReport:
    services = SimpleNamespace(
        embedder=embedder,
        chunk_store=JsonChunkStore(),
        settings=SimpleNamespace(assistant_min_score=min_score, assistant_top_k=top_k),
    )
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    report = EvalReport()
    with make_session_factory(engine)() as session:
        publish_corpus(session, services)
        for case in load_dataset():
            plan = plan_chat(session, services, case["question"], case["locale"])
            found = [source.path for source in plan.sources]
            ok = case["expected"] in found if case["expected"] else plan.prompt is None
            report.total += 1
            report.passed += ok
            if not ok:
                report.failures.append(
                    f"{case['question']!r}: expected {case['expected']}, got {found or 'refusal'}"
                )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--embedder", choices=["hashing", "e5"], default="hashing")
    parser.add_argument("--min-score", type=float, default=0.2)
    args = parser.parse_args()

    embedder = E5Embedder() if args.embedder == "e5" else HashingEmbedder()
    report = run(embedder, args.min_score)
    for failure in report.failures:
        print(f"FAIL {failure}")
    print(f"{report.passed}/{report.total} passed ({report.accuracy:.0%})")
    raise SystemExit(0 if not report.failures else 1)


if __name__ == "__main__":
    main()
