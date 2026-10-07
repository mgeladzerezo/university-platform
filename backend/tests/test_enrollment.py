import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from app.academics import service
from app.academics.models import CourseOffering, Enrollment, EnrollmentStatus
from app.auth import Principal, Role
from app.errors import Conflict

API = "/api/v1/academics"


def make_offering(ctx, capacity: int, code: str = "INF101", lecturer: str = "lecturer-1") -> int:
    admin = ctx.auth("root", Role.ADMIN)
    course = ctx.client.post(
        f"{API}/admin/courses",
        json={"code": code, "title_pl": "Algorytmy", "title_en": "Algorithms", "ects": 6},
        headers=admin,
    )
    assert course.status_code == 201, course.text
    offering = ctx.client.post(
        f"{API}/admin/offerings",
        json={
            "course_id": course.json()["id"],
            "semester": "2026Z",
            "lecturer_sub": lecturer,
            "lecturer_name": "dr Lena Lecturer",
            "capacity": capacity,
            "sessions": [{"weekday": 0, "starts_at": "08:15", "ends_at": "09:45", "room": "A1"}],
        },
        headers=admin,
    )
    assert offering.status_code == 201, offering.text
    return offering.json()["id"]


def student(ctx, name: str) -> dict[str, str]:
    return ctx.auth(name, Role.STUDENT)


def enroll(ctx, offering_id: int, name: str):
    return ctx.client.post(f"{API}/offerings/{offering_id}/enrollment", headers=student(ctx, name))


def drop(ctx, offering_id: int, name: str):
    return ctx.client.delete(
        f"{API}/offerings/{offering_id}/enrollment", headers=student(ctx, name)
    )


def seat_state(ctx, offering_id: int) -> tuple[int, int, int]:
    """(enrolled_count column, enrolled rows, waitlisted rows)"""
    with ctx.session() as session:
        counter = session.get(CourseOffering, offering_id).enrolled_count
        rows = dict(
            session.execute(
                select(Enrollment.status, func.count())
                .where(Enrollment.offering_id == offering_id)
                .group_by(Enrollment.status)
            ).all()
        )
    return counter, rows.get("enrolled", 0), rows.get("waitlisted", 0)


def status_of(ctx, offering_id: int, name: str) -> str | None:
    mine = ctx.client.get(f"{API}/me/enrollments", headers=student(ctx, name)).json()
    return next((e["status"] for e in mine if e["offering_id"] == offering_id), None)


def test_enrolls_until_full_then_waitlists_in_order(ctx):
    offering_id = make_offering(ctx, capacity=2)

    results = [enroll(ctx, offering_id, name).json() for name in ("ala", "ola", "ela", "iza")]

    assert [r["status"] for r in results] == ["enrolled", "enrolled", "waitlisted", "waitlisted"]
    assert [r["waitlist_position"] for r in results] == [None, None, 1, 2]
    assert seat_state(ctx, offering_id) == (2, 2, 2)


def test_enrolling_twice_conflicts_and_takes_no_extra_seat(ctx):
    offering_id = make_offering(ctx, capacity=3)
    enroll(ctx, offering_id, "ala")

    assert enroll(ctx, offering_id, "ala").status_code == 409
    assert seat_state(ctx, offering_id) == (1, 1, 0)


def test_drop_promotes_first_waitlisted_student_and_notifies(ctx):
    offering_id = make_offering(ctx, capacity=1)
    for name in ("ala", "ola", "ela"):
        enroll(ctx, offering_id, name)

    assert drop(ctx, offering_id, "ala").status_code == 204

    assert status_of(ctx, offering_id, "ola") == "enrolled"
    assert status_of(ctx, offering_id, "ela") == "waitlisted"
    assert seat_state(ctx, offering_id) == (1, 1, 1)
    ctx.run_jobs()
    [email] = ctx.services.email.sent
    assert email.recipient == "ola@students.test"
    assert "Algorytmy" in email.body


def test_drop_without_waitlist_frees_the_seat(ctx):
    offering_id = make_offering(ctx, capacity=1)
    enroll(ctx, offering_id, "ala")

    drop(ctx, offering_id, "ala")

    assert seat_state(ctx, offering_id) == (0, 0, 0)
    assert enroll(ctx, offering_id, "ola").json()["status"] == "enrolled"


def test_waitlisted_student_can_leave_without_affecting_seats(ctx):
    offering_id = make_offering(ctx, capacity=1)
    enroll(ctx, offering_id, "ala")
    enroll(ctx, offering_id, "ola")

    assert drop(ctx, offering_id, "ola").status_code == 204

    assert seat_state(ctx, offering_id) == (1, 1, 0)


def test_dropped_student_can_enroll_again(ctx):
    offering_id = make_offering(ctx, capacity=1)
    enroll(ctx, offering_id, "ala")
    drop(ctx, offering_id, "ala")

    assert enroll(ctx, offering_id, "ala").json()["status"] == "enrolled"
    assert seat_state(ctx, offering_id) == (1, 1, 0)


def test_drop_when_not_enrolled_is_404(ctx):
    offering_id = make_offering(ctx, capacity=1)

    assert drop(ctx, offering_id, "ala").status_code == 404


def test_closed_offering_rejects_enrollment(ctx):
    offering_id = make_offering(ctx, capacity=5)
    ctx.client.patch(
        f"{API}/admin/offerings/{offering_id}",
        json={"enrollment_open": False},
        headers=ctx.auth("root", Role.ADMIN),
    )

    assert enroll(ctx, offering_id, "ala").status_code == 409


def test_raising_capacity_promotes_from_waitlist(ctx):
    offering_id = make_offering(ctx, capacity=1)
    for name in ("ala", "ola", "ela", "iza"):
        enroll(ctx, offering_id, name)

    response = ctx.client.patch(
        f"{API}/admin/offerings/{offering_id}",
        json={"capacity": 3},
        headers=ctx.auth("root", Role.ADMIN),
    )

    assert response.json()["enrolled_count"] == 3
    assert status_of(ctx, offering_id, "ela") == "enrolled"
    assert status_of(ctx, offering_id, "iza") == "waitlisted"
    assert seat_state(ctx, offering_id) == (3, 3, 1)


def test_capacity_cannot_drop_below_enrolled_count(ctx):
    offering_id = make_offering(ctx, capacity=2)
    enroll(ctx, offering_id, "ala")
    enroll(ctx, offering_id, "ola")

    response = ctx.client.patch(
        f"{API}/admin/offerings/{offering_id}",
        json={"capacity": 1},
        headers=ctx.auth("root", Role.ADMIN),
    )

    assert response.status_code == 409


def _principal(name: str) -> Principal:
    return Principal(
        sub=name, email=f"{name}@students.test", name=name, roles=frozenset({Role.STUDENT})
    )


def _run_together(tasks) -> list:
    """Run callables in threads, released at the same instant."""
    barrier = threading.Barrier(len(tasks))

    def run(task):
        barrier.wait()
        return task()

    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        return [future.result() for future in [pool.submit(run, task) for task in tasks]]


@pytest.mark.concurrency
def test_concurrent_enrollment_never_oversubscribes(ctx):
    offering_id = make_offering(ctx, capacity=5)

    def attempt(name: str) -> str:
        with ctx.session() as session:
            enrollment = service.enroll(session, offering_id, _principal(name))
            session.commit()
            return enrollment.status

    statuses = _run_together([lambda n=f"student-{i}": attempt(n) for i in range(40)])

    assert statuses.count(EnrollmentStatus.ENROLLED) == 5
    assert statuses.count(EnrollmentStatus.WAITLISTED) == 35
    assert seat_state(ctx, offering_id) == (5, 5, 35)


@pytest.mark.concurrency
def test_concurrent_http_requests_never_oversubscribe(ctx):
    offering_id = make_offering(ctx, capacity=3)
    headers = [student(ctx, f"student-{i}") for i in range(24)]

    responses = _run_together(
        [
            lambda h=h: ctx.client.post(f"{API}/offerings/{offering_id}/enrollment", headers=h)
            for h in headers
        ]
    )

    assert {r.status_code for r in responses} == {200}
    assert sorted(r.json()["status"] for r in responses).count("enrolled") == 3
    assert seat_state(ctx, offering_id) == (3, 3, 21)


@pytest.mark.concurrency
def test_same_student_enrolling_twice_at_once_gets_one_seat(ctx):
    offering_id = make_offering(ctx, capacity=5)

    def attempt() -> str:
        with ctx.session() as session:
            try:
                service.enroll(session, offering_id, _principal("ala"))
                session.commit()
                return "ok"
            except Conflict:
                return "conflict"

    outcomes = _run_together([attempt] * 6)

    assert outcomes.count("ok") == 1
    assert seat_state(ctx, offering_id) == (1, 1, 0)


@pytest.mark.concurrency
def test_concurrent_drops_and_enrollments_keep_seats_consistent(ctx):
    capacity = 4
    offering_id = make_offering(ctx, capacity=capacity)
    for i in range(8):
        enroll(ctx, offering_id, f"early-{i}")

    def do_drop(name: str):
        with ctx.session() as session:
            service.drop(session, offering_id, name)
            session.commit()

    def do_enroll(name: str):
        with ctx.session() as session:
            service.enroll(session, offering_id, _principal(name))
            session.commit()

    tasks = [lambda n=f"early-{i}": do_drop(n) for i in range(6)]
    tasks += [lambda n=f"late-{i}": do_enroll(n) for i in range(6)]
    _run_together(tasks)

    counter, enrolled, waitlisted = seat_state(ctx, offering_id)
    assert counter == enrolled <= capacity
    # 8 + 6 - 6 students remain; nobody may wait while a seat is free.
    assert enrolled + waitlisted == 8
    assert enrolled == capacity
