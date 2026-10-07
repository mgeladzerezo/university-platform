"""pgvector column for assistant chunks

Revision ID: 0003
Revises: 0002
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # 384 dimensions = multilingual-e5-small.
    op.execute("ALTER TABLE content_chunks ADD COLUMN embedding_vec vector(384)")
    op.execute(
        "CREATE INDEX ix_content_chunks_embedding ON content_chunks "
        "USING hnsw (embedding_vec vector_cosine_ops)"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE content_chunks DROP COLUMN embedding_vec")
