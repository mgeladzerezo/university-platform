from logging.config import fileConfig

from alembic import context

# Importing the modules registers every table on Base.metadata.
import app.academics.models
import app.admissions.models
import app.assistant.store
import app.auth
import app.content.models
import app.notifications.models  # noqa: F401
from app.config import get_settings
from app.db import Base, make_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Created by hand-written PostgreSQL-only migrations and used through raw SQL,
# so they are absent from the ORM models and must not be reported as drift.
DATABASE_ONLY = {
    ("column", "search_vector"),
    ("column", "embedding_vec"),
    ("index", "ix_content_items_search"),
    ("index", "ix_programs_search"),
    ("index", "ix_content_chunks_embedding"),
}


def include_object(_object, name, type_, reflected, _compare_to) -> bool:
    return not (reflected and (type_, name) in DATABASE_ONLY)


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = make_engine(get_settings().database_url)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, include_object=include_object
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
