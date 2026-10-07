"""full-text search columns

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# The 'simple' configuration is used because PostgreSQL ships no Polish
# dictionary; it lowercases and tokenizes without stemming.


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        ALTER TABLE content_items ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('simple', title), 'A')
            || setweight(to_tsvector('simple', summary), 'B')
            || setweight(to_tsvector('simple', body_html), 'C')
        ) STORED
        """
    )
    op.execute("CREATE INDEX ix_content_items_search ON content_items USING gin (search_vector)")
    op.execute(
        """
        ALTER TABLE programs ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            to_tsvector(
                'simple',
                name_pl || ' ' || name_en || ' ' || description_pl || ' ' || description_en
            )
        ) STORED
        """
    )
    op.execute("CREATE INDEX ix_programs_search ON programs USING gin (search_vector)")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE programs DROP COLUMN search_vector")
    op.execute("ALTER TABLE content_items DROP COLUMN search_vector")
