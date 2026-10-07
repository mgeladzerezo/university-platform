import os
import time
from dataclasses import dataclass

import fakeredis
import jwt
import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.assistant.embeddings import HashingEmbedder
from app.assistant.store import JsonChunkStore
from app.auth import Role, TokenVerifier
from app.config import Settings, get_settings
from app.content.models import DegreeLevel, Faculty, Program, StudyMode
from app.db import Base, make_engine, make_session_factory
from app.main import create_app
from app.ratelimit import RedisRateLimiter
from app.services import Services
from tests.fakes import (
    FakeLlm,
    InlineJobQueue,
    InMemoryStorage,
    RecordingEmailSender,
    SignatureScanner,
)

ISSUER = "https://sso.test/realms/kalinowo"
AUDIENCE = "uni-api"


@pytest.fixture(scope="session")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def make_token(signing_key):
    def build(
        sub: str = "user-1",
        roles: tuple[Role | str, ...] = (),
        email: str | None = None,
        name: str | None = None,
        key=None,
        **claim_overrides,
    ) -> str:
        now = int(time.time())
        claims = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": sub,
            "iat": now,
            "exp": now + 300,
            "email": email or f"{sub}@students.test",
            "name": name or sub.replace("-", " ").title(),
            "realm_access": {"roles": [str(role) for role in roles]},
            **claim_overrides,
        }
        return jwt.encode(claims, key or signing_key, algorithm="RS256")

    return build


@dataclass
class Context:
    client: TestClient
    services: Services
    session_factory: sessionmaker[Session]
    make_token: callable

    def auth(self, sub: str, *roles: Role, **kwargs) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.make_token(sub=sub, roles=roles, **kwargs)}"}

    def run_jobs(self) -> int:
        return self.services.jobs.run_pending(self.session_factory, self.services)

    def session(self) -> Session:
        return self.session_factory()


@pytest.fixture(scope="session")
def postgres_url() -> str | None:
    """Set TEST_DATABASE_URL to run the suite against PostgreSQL instead of SQLite.

    The schema is then built by the Alembic migrations, so they are tested too.
    TEST_MIGRATION_TARGET (default "head") allows stopping before the pgvector
    revision on a server without that extension.
    """
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        return None
    engine = make_engine(url)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    engine.dispose()
    os.environ["UNI_DATABASE_URL"] = url
    get_settings.cache_clear()
    command.upgrade(Config("alembic.ini"), os.environ.get("TEST_MIGRATION_TARGET", "head"))
    return url


def _empty_tables(engine) -> None:
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def ctx(tmp_path, signing_key, make_token, postgres_url):
    if postgres_url:
        url = postgres_url
        engine = make_engine(url)
        _empty_tables(engine)
    else:
        url = f"sqlite:///{tmp_path / 'test.db'}"
        engine = make_engine(url)
        Base.metadata.create_all(engine)
    session_factory = make_session_factory(engine)

    settings = Settings(
        environment="test",
        database_url=url,
        oidc_issuer=ISSUER,
        oidc_audience=AUDIENCE,
        assistant_min_score=0.2,
        chat_rate_limit_per_minute=5,
        rejected_retention_days=30,
        max_upload_bytes=1024,
    )
    public_key = signing_key.public_key()
    services = Services(
        settings=settings,
        token_verifier=TokenVerifier(ISSUER, AUDIENCE, lambda _token: public_key),
        storage=InMemoryStorage(),
        email=RecordingEmailSender(),
        scanner=SignatureScanner(),
        jobs=InlineJobQueue(),
        rate_limiter=RedisRateLimiter(fakeredis.FakeRedis()),
        embedder=HashingEmbedder(),
        chunk_store=JsonChunkStore(),
        llm=FakeLlm(),
    )
    with TestClient(create_app(services, session_factory)) as client:
        yield Context(client, services, session_factory, make_token)
    engine.dispose()


@pytest.fixture
def program_id(ctx) -> int:
    with ctx.session() as session:
        faculty = Faculty(slug="inf", name_pl="Wydział Informatyki", name_en="Computer Science")
        session.add(faculty)
        session.flush()
        program = Program(
            faculty_id=faculty.id,
            slug="informatyka",
            name_pl="Informatyka",
            name_en="Computer Science",
            degree_level=DegreeLevel.BACHELOR,
            mode=StudyMode.FULL_TIME,
            semesters=7,
        )
        session.add(program)
        session.commit()
        return program.id


@pytest.fixture
def applicant(ctx):
    return ctx.auth("maja", Role.APPLICANT, email="maja@mail.test")


@pytest.fixture
def officer(ctx):
    return ctx.auth("officer-1", Role.ADMISSIONS_OFFICER)
