from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import JSON, ForeignKey, String, Text, delete, select, text
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.assistant.embeddings import cosine
from app.content.models import ContentItem, ContentStatus
from app.db import Base, UtcDateTime, utcnow


class ContentChunk(Base):
    __tablename__ = "content_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_item_id: Mapped[int] = mapped_column(
        ForeignKey("content_items.id", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(JSON)
    # On PostgreSQL the migration adds an `embedding_vec vector(384)` column that
    # only PgVectorChunkStore touches, so the ORM needs no pgvector dependency.


class AiAuditLog(Base):
    __tablename__ = "ai_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_sub: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(40))
    subject_id: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(80))
    outcome: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


@dataclass(frozen=True)
class ScoredChunk:
    content_item_id: int
    kind: str
    slug: str
    locale: str
    title: str
    text: str
    score: float


class ChunkStore(Protocol):
    def replace_for_item(
        self, session: Session, content_item_id: int, texts: list[str], vectors: list[list[float]]
    ) -> None: ...

    def delete_for_item(self, session: Session, content_item_id: int) -> None: ...

    def search(
        self, session: Session, query_vector: list[float], locale: str, limit: int
    ) -> list[ScoredChunk]:
        """Best-matching chunks of published content in the given locale."""


class JsonChunkStore:
    """Stores vectors as JSON and ranks in Python. Used with SQLite and in tests."""

    def replace_for_item(
        self, session: Session, content_item_id: int, texts: list[str], vectors: list[list[float]]
    ) -> None:
        self.delete_for_item(session, content_item_id)
        session.add_all(
            ContentChunk(
                content_item_id=content_item_id, ordinal=ordinal, text=chunk, embedding=vector
            )
            for ordinal, (chunk, vector) in enumerate(zip(texts, vectors, strict=True))
        )
        session.flush()

    def delete_for_item(self, session: Session, content_item_id: int) -> None:
        session.execute(delete(ContentChunk).where(ContentChunk.content_item_id == content_item_id))

    def search(
        self, session: Session, query_vector: list[float], locale: str, limit: int
    ) -> list[ScoredChunk]:
        rows = session.execute(
            select(ContentChunk, ContentItem)
            .join(ContentItem, ContentItem.id == ContentChunk.content_item_id)
            # Filtering on status here, not only at indexing time, means a
            # leftover chunk can never surface unpublished text.
            .where(ContentItem.status == ContentStatus.PUBLISHED, ContentItem.locale == locale)
        ).all()
        scored = [
            ScoredChunk(
                content_item_id=item.id,
                kind=item.kind,
                slug=item.slug,
                locale=item.locale,
                title=item.title,
                text=chunk.text,
                score=cosine(query_vector, chunk.embedding),
            )
            for chunk, item in rows
        ]
        return sorted(scored, key=lambda c: c.score, reverse=True)[:limit]


class PgVectorChunkStore(JsonChunkStore):
    """Same table, but similarity search runs in PostgreSQL through pgvector."""

    def replace_for_item(
        self, session: Session, content_item_id: int, texts: list[str], vectors: list[list[float]]
    ) -> None:
        super().replace_for_item(session, content_item_id, texts, vectors)
        # A JSON array literal is also a valid pgvector literal.
        session.execute(
            text(
                "UPDATE content_chunks SET embedding_vec = CAST(CAST(embedding AS text) AS vector) "
                "WHERE content_item_id = :item_id"
            ),
            {"item_id": content_item_id},
        )

    def search(
        self, session: Session, query_vector: list[float], locale: str, limit: int
    ) -> list[ScoredChunk]:
        rows = session.execute(
            text(
                "SELECT i.id, i.kind, i.slug, i.locale, i.title, c.text, "
                "1 - (c.embedding_vec <=> CAST(:query AS vector)) AS score "
                "FROM content_chunks c JOIN content_items i ON i.id = c.content_item_id "
                "WHERE i.status = 'published' AND i.locale = :locale "
                "ORDER BY c.embedding_vec <=> CAST(:query AS vector) LIMIT :limit"
            ),
            {"query": str(query_vector), "locale": locale, "limit": limit},
        ).all()
        return [ScoredChunk(*row) for row in rows]
