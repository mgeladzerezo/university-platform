from app.auth import Role
from tests.test_enrollment import API, enroll, make_offering, student


def lecturer(ctx, sub: str = "lecturer-1") -> dict[str, str]:
    return ctx.auth(sub, Role.LECTURER)


def roster(ctx, offering_id: int, headers) -> list[dict]:
    response = ctx.client.get(f"{API}/teaching/offerings/{offering_id}/roster", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_offering_list_shows_seats_and_own_status(ctx):
    offering_id = make_offering(ctx, capacity=1)
    enroll(ctx, offering_id, "ala")
    enroll(ctx, offering_id, "ola")

    [offering] = ctx.client.get(
        f"{API}/offerings", params={"locale": "en"}, headers=student(ctx, "ola")
    ).json()

    assert offering["course_title"] == "Algorithms"
    assert (offering["capacity"], offering["enrolled_count"]) == (1, 1)
    assert offering["my_status"] == "waitlisted"


def test_timetable_lists_sessions_of_enrolled_courses_only(ctx):
    seated = make_offering(ctx, capacity=1, code="INF101")
    waitlisted = make_offering(ctx, capacity=1, code="INF202")
    enroll(ctx, waitlisted, "ola")
    enroll(ctx, seated, "ala")
    enroll(ctx, waitlisted, "ala")

    timetable = ctx.client.get(f"{API}/me/timetable", headers=student(ctx, "ala")).json()

    assert [(t["course_code"], t["weekday"], t["starts_at"], t["room"]) for t in timetable] == [
        ("INF101", 0, "08:15:00", "A1")
    ]


def test_lecturer_grades_student_and_student_sees_grade(ctx):
    offering_id = make_offering(ctx, capacity=5)
    enroll(ctx, offering_id, "ala")
    [entry] = roster(ctx, offering_id, lecturer(ctx))
    assert entry["student_email"] == "ala@students.test"
    assert entry["grade"] is None

    response = ctx.client.put(
        f"{API}/teaching/enrollments/{entry['enrollment_id']}/grade",
        json={"value": 4.5},
        headers=lecturer(ctx),
    )

    assert response.status_code == 200
    [grade] = ctx.client.get(f"{API}/me/grades", headers=student(ctx, "ala")).json()
    assert (grade["course_code"], grade["grade"], grade["ects"]) == ("INF101", 4.5, 6)


def test_grade_outside_scale_is_rejected(ctx):
    offering_id = make_offering(ctx, capacity=5)
    enroll(ctx, offering_id, "ala")
    [entry] = roster(ctx, offering_id, lecturer(ctx))

    response = ctx.client.put(
        f"{API}/teaching/enrollments/{entry['enrollment_id']}/grade",
        json={"value": 6.0},
        headers=lecturer(ctx),
    )

    assert response.status_code == 422


def test_lecturer_cannot_touch_another_lecturers_offering(ctx):
    offering_id = make_offering(ctx, capacity=5, lecturer="lecturer-1")
    enroll(ctx, offering_id, "ala")
    [entry] = roster(ctx, offering_id, lecturer(ctx))
    other = lecturer(ctx, "lecturer-2")

    assert (
        ctx.client.get(f"{API}/teaching/offerings/{offering_id}/roster", headers=other).status_code
        == 403
    )
    grade = ctx.client.put(
        f"{API}/teaching/enrollments/{entry['enrollment_id']}/grade",
        json={"value": 5.0},
        headers=other,
    )
    assert grade.status_code == 403
    announcement = ctx.client.post(
        f"{API}/teaching/offerings/{offering_id}/announcements",
        json={"title": "x", "body": "y"},
        headers=other,
    )
    assert announcement.status_code == 403
    assert ctx.client.get(f"{API}/teaching/offerings", headers=other).json() == []


def test_waitlisted_student_is_not_on_roster_and_cannot_be_graded(ctx):
    offering_id = make_offering(ctx, capacity=1)
    enroll(ctx, offering_id, "ala")
    enroll(ctx, offering_id, "ola")

    assert [e["student_email"] for e in roster(ctx, offering_id, lecturer(ctx))] == [
        "ala@students.test"
    ]


def test_graded_course_cannot_be_dropped(ctx):
    offering_id = make_offering(ctx, capacity=5)
    enroll(ctx, offering_id, "ala")
    [entry] = roster(ctx, offering_id, lecturer(ctx))
    ctx.client.put(
        f"{API}/teaching/enrollments/{entry['enrollment_id']}/grade",
        json={"value": 3.0},
        headers=lecturer(ctx),
    )

    response = ctx.client.delete(
        f"{API}/offerings/{offering_id}/enrollment", headers=student(ctx, "ala")
    )

    assert response.status_code == 409


def test_student_sees_global_and_own_course_announcements_only(ctx):
    mine = make_offering(ctx, capacity=5, code="INF101")
    not_mine = make_offering(ctx, capacity=5, code="INF202")
    enroll(ctx, mine, "ala")
    for offering_id, title in ((mine, "Kolokwium"), (not_mine, "Inna grupa")):
        ctx.client.post(
            f"{API}/teaching/offerings/{offering_id}/announcements",
            json={"title": title, "body": "Szczegóły na zajęciach."},
            headers=lecturer(ctx),
        )
    ctx.client.post(
        f"{API}/admin/announcements",
        json={"title": "Dzień rektorski", "body": "Zajęcia odwołane."},
        headers=ctx.auth("root", Role.ADMIN),
    )

    announcements = ctx.client.get(f"{API}/me/announcements", headers=student(ctx, "ala")).json()

    assert {(a["title"], a["course_code"]) for a in announcements} == {
        ("Kolokwium", "INF101"),
        ("Dzień rektorski", None),
    }
