from sqlalchemy.orm import Session

from app.assistant.chunking import chunks_for_content
from app.content.models import ContentItem, ContentStatus
from app.jobs import job

INDEX_CONTENT_JOB = "assistant.index_content"


@job(INDEX_CONTENT_JOB)
def index_content(session: Session, services, content_item_id: int) -> None:
    item = session.get(ContentItem, content_item_id)
    # The item may have been unpublished or deleted while the job was queued.
    if item is None or item.status != ContentStatus.PUBLISHED:
        services.chunk_store.delete_for_item(session, content_item_id)
        session.commit()
        return
    texts = chunks_for_content(item.title, item.summary, item.body_html)
    vectors = services.embedder.embed_documents(texts)
    services.chunk_store.replace_for_item(session, item.id, texts, vectors)
    session.commit()
