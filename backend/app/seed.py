"""Development data: `python -m app.seed` (run after `alembic upgrade head`)."""

from datetime import time
from types import SimpleNamespace

from sqlalchemy import select

from app.academics.models import ClassSession, Course, CourseOffering
from app.assistant.embeddings import E5Embedder, HashingEmbedder
from app.assistant.evaluation.runner import publish_corpus
from app.assistant.store import JsonChunkStore, PgVectorChunkStore
from app.config import get_settings
from app.content.models import DegreeLevel, Faculty, Program, StaffMember, StudyMode
from app.db import make_engine, make_session_factory

# Matches the `lecturer` user in deploy/keycloak/realm.json.
LECTURER_SUB = "00000000-0000-0000-0000-000000000003"


def seed() -> None:
    settings = get_settings()
    services = SimpleNamespace(
        embedder=E5Embedder() if settings.embedder == "e5" else HashingEmbedder(),
        chunk_store=PgVectorChunkStore()
        if settings.vector_store == "pgvector"
        else JsonChunkStore(),
    )
    with make_session_factory(make_engine(settings.database_url))() as session:
        if session.scalar(select(Faculty.id).limit(1)) is not None:
            print("Database already seeded")
            return

        informatics = Faculty(
            slug="informatyka",
            name_pl="Wydział Informatyki",
            name_en="Faculty of Computer Science",
            description_pl="Kształcenie i badania w zakresie informatyki i analizy danych.",
            description_en="Teaching and research in computer science and data analysis.",
        )
        economics = Faculty(
            slug="ekonomia",
            name_pl="Wydział Ekonomii",
            name_en="Faculty of Economics",
            description_pl="Ekonomia, finanse i zarządzanie.",
            description_en="Economics, finance and management.",
        )
        session.add_all([informatics, economics])
        session.flush()
        session.add_all(
            [
                Program(
                    faculty_id=informatics.id,
                    slug="informatyka-inz",
                    name_pl="Informatyka",
                    name_en="Computer Science",
                    description_pl="Studia inżynierskie: programowanie, sieci, bazy danych.",
                    description_en="Engineering degree: programming, networks, databases.",
                    degree_level=DegreeLevel.BACHELOR,
                    mode=StudyMode.FULL_TIME,
                    semesters=7,
                ),
                Program(
                    faculty_id=informatics.id,
                    slug="data-science-mgr",
                    name_pl="Analiza danych",
                    name_en="Data Science",
                    description_pl="Studia magisterskie z uczenia maszynowego i statystyki.",
                    description_en="Master's degree in machine learning and statistics.",
                    degree_level=DegreeLevel.MASTER,
                    mode=StudyMode.FULL_TIME,
                    teaching_language="en",
                    semesters=3,
                ),
                Program(
                    faculty_id=economics.id,
                    slug="ekonomia-lic",
                    name_pl="Ekonomia",
                    name_en="Economics",
                    description_pl="Studia licencjackie z mikro- i makroekonomii.",
                    description_en="Bachelor's degree in micro- and macroeconomics.",
                    degree_level=DegreeLevel.BACHELOR,
                    mode=StudyMode.PART_TIME,
                    semesters=6,
                ),
                StaffMember(
                    faculty_id=informatics.id,
                    full_name="Helena Wrzosek",
                    academic_title="dr hab.",
                    position_pl="Dziekan",
                    position_en="Dean",
                    email="h.wrzosek@ukal.example",
                    phone="+48 00 000 01 01",
                ),
                StaffMember(
                    faculty_id=economics.id,
                    full_name="Tymon Baranowski",
                    academic_title="dr",
                    position_pl="Adiunkt",
                    position_en="Assistant Professor",
                    email="t.baranowski@ukal.example",
                ),
            ]
        )

        algorithms = Course(code="INF101", title_pl="Algorytmy", title_en="Algorithms", ects=6)
        databases = Course(code="INF202", title_pl="Bazy danych", title_en="Databases", ects=5)
        session.add_all([algorithms, databases])
        session.flush()
        session.add_all(
            [
                CourseOffering(
                    course_id=algorithms.id,
                    semester="2026Z",
                    lecturer_sub=LECTURER_SUB,
                    lecturer_name="dr Lena Wykładowska",
                    capacity=30,
                    sessions=[
                        ClassSession(
                            weekday=0, starts_at=time(8, 15), ends_at=time(9, 45), room="A1"
                        )
                    ],
                ),
                CourseOffering(
                    course_id=databases.id,
                    semester="2026Z",
                    lecturer_sub=LECTURER_SUB,
                    lecturer_name="dr Lena Wykładowska",
                    capacity=2,
                    sessions=[
                        ClassSession(
                            weekday=2, starts_at=time(10, 0), ends_at=time(11, 30), room="B7"
                        )
                    ],
                ),
            ]
        )
        publish_corpus(session, services)
        session.commit()
        print("Seeded")


if __name__ == "__main__":
    seed()
