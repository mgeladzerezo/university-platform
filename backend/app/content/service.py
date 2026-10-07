import nh3
from sqlalchemy import ColumnElement, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import Principal, Role
from app.content.models import ContentItem, ContentKind, ContentStatus, Program, WorkflowEvent
from app.content.schemas import ContentIn, WorkflowAction
from app.db import utcnow
from app.errors import Conflict, Forbidden, NotFound

ALLOWED_TAGS = {
    "p", "br", "h2", "h3", "h4", "ul", "ol", "li", "strong", "em", "u", "s",
    "blockquote", "a", "code", "pre", "hr",
}  # fmt: skip

# action -> (allowed source statuses, target status)
TRANSITIONS: dict[WorkflowAction, tuple[frozenset[ContentStatus], ContentStatus]] = {
    WorkflowAction.SUBMIT: (frozenset({ContentStatus.DRAFT}), ContentStatus.IN_REVIEW),
    WorkflowAction.REQUEST_CHANGES: (frozenset({ContentStatus.IN_REVIEW}), ContentStatus.DRAFT),
    WorkflowAction.PUBLISH: (frozenset({ContentStatus.IN_REVIEW}), ContentStatus.PUBLISHED),
    WorkflowAction.UNPUBLISH: (frozenset({ContentStatus.PUBLISHED}), ContentStatus.DRAFT),
    WorkflowAction.ARCHIVE: (
        frozenset({ContentStatus.DRAFT, ContentStatus.PUBLISHED}),
        ContentStatus.ARCHIVED,
    ),
    WorkflowAction.RESTORE: (frozenset({ContentStatus.ARCHIVED}), ContentStatus.DRAFT),
}


def sanitize_html(html: str) -> str:
    return nh3.clean(html, tags=ALLOWED_TAGS, attributes={"a": {"href"}})


def create_content(session: Session, data: ContentIn, author: Principal) -> ContentItem:
    item = ContentItem(author_sub=author.sub, **_content_fields(data))
    session.add(item)
    _flush_unique(session)
    return item


def update_content(session: Session, item: ContentItem, data: ContentIn) -> ContentItem:
    # Only drafts are editable, so what reviewers approved is what gets published.
    if item.status != ContentStatus.DRAFT:
        raise Conflict("Only drafts can be edited; unpublish or request changes first")
    for field, value in _content_fields(data).items():
        setattr(item, field, value)
    _flush_unique(session)
    return item


def _content_fields(data: ContentIn) -> dict:
    fields = data.model_dump()
    fields["body_html"] = sanitize_html(data.body_html)
    return fields


def _flush_unique(session: Session) -> None:
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise Conflict("Content with this kind, slug and locale already exists") from exc


def apply_transition(
    session: Session,
    item: ContentItem,
    action: WorkflowAction,
    actor: Principal,
    comment: str,
    chunk_store,
) -> ContentItem:
    sources, target = TRANSITIONS[action]
    if item.status not in sources:
        raise Conflict(f"Cannot {action.value} content in status {item.status}")
    if (
        action == WorkflowAction.PUBLISH
        and item.author_sub == actor.sub
        and Role.ADMIN not in actor.roles
    ):
        raise Forbidden("Content must be published by someone other than its author")

    was_published = item.status == ContentStatus.PUBLISHED
    session.add(
        WorkflowEvent(
            content_item_id=item.id,
            from_status=item.status,
            to_status=target,
            actor_sub=actor.sub,
            comment=comment,
        )
    )
    item.status = target
    if target == ContentStatus.PUBLISHED:
        item.published_at = utcnow()
    if was_published:
        # Same transaction as the status change: the assistant must stop
        # seeing this text the moment it stops being public.
        item.published_at = None
        chunk_store.delete_for_item(session, item.id)
    return item


def get_content(session: Session, content_id: int) -> ContentItem:
    item = session.get(ContentItem, content_id)
    if item is None:
        raise NotFound("Content not found")
    return item


def published_query(kind: ContentKind, locale: str):
    return select(ContentItem).where(
        ContentItem.status == ContentStatus.PUBLISHED,
        ContentItem.kind == kind,
        ContentItem.locale == locale,
    )


def content_search_filter(session: Session, query: str) -> ColumnElement[bool]:
    if session.get_bind().dialect.name == "postgresql":
        # search_vector is a generated tsvector column created by the migration.
        return text(
            "content_items.search_vector @@ plainto_tsquery('simple', :content_q)"
        ).bindparams(content_q=query)
    pattern = f"%{_escape_like(query)}%"
    return or_(
        ContentItem.title.ilike(pattern, escape="\\"),
        ContentItem.summary.ilike(pattern, escape="\\"),
        ContentItem.body_html.ilike(pattern, escape="\\"),
    )


def program_search_filter(session: Session, query: str) -> ColumnElement[bool]:
    if session.get_bind().dialect.name == "postgresql":
        return text("programs.search_vector @@ plainto_tsquery('simple', :program_q)").bindparams(
            program_q=query
        )
    pattern = f"%{_escape_like(query)}%"
    return or_(
        Program.name_pl.ilike(pattern, escape="\\"),
        Program.name_en.ilike(pattern, escape="\\"),
        Program.description_pl.ilike(pattern, escape="\\"),
        Program.description_en.ilike(pattern, escape="\\"),
    )


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
