from app.auth import Role

PUBLIC = "/api/v1/public"
ADMIN = "/api/v1/admin/catalogue"

CONTACT = {
    "name": "Jan Pytający",
    "email": "jan@mail.example",
    "subject": "Rekrutacja",
    "message": "Czy mogę złożyć dokumenty osobiście?",
}


def seed_catalogue(ctx) -> None:
    admin = ctx.auth("root", Role.ADMIN)
    faculty_id = ctx.client.post(
        f"{ADMIN}/faculties",
        json={
            "slug": "informatyka",
            "name_pl": "Wydział Informatyki",
            "name_en": "Computer Science",
        },
        headers=admin,
    ).json()["id"]
    programs = [
        ("informatyka-inz", "Informatyka", "Computer Science", "bachelor"),
        ("analiza-danych", "Analiza danych", "Data Science", "master"),
    ]
    for slug, name_pl, name_en, level in programs:
        response = ctx.client.post(
            f"{ADMIN}/programs",
            json={
                "faculty_id": faculty_id,
                "slug": slug,
                "name_pl": name_pl,
                "name_en": name_en,
                "degree_level": level,
                "mode": "full_time",
                "semesters": 6,
            },
            headers=admin,
        )
        assert response.status_code == 201, response.text
    ctx.client.post(
        f"{ADMIN}/staff",
        json={
            "faculty_id": faculty_id,
            "full_name": "Helena Wrzosek",
            "position_pl": "Dziekan",
            "position_en": "Dean",
            "email": "h.wrzosek@ukal.example",
        },
        headers=admin,
    )


def test_catalogue_is_localized(ctx):
    seed_catalogue(ctx)

    polish = ctx.client.get(f"{PUBLIC}/programs").json()
    english = ctx.client.get(f"{PUBLIC}/programs", params={"locale": "en"}).json()

    assert [p["name"] for p in polish] == ["Analiza danych", "Informatyka"]
    assert [p["name"] for p in english] == ["Data Science", "Computer Science"]
    assert english[0]["faculty_name"] == "Computer Science"


def test_catalogue_search_and_filters(ctx):
    seed_catalogue(ctx)

    by_text = ctx.client.get(f"{PUBLIC}/programs", params={"q": "danych"}).json()
    by_level = ctx.client.get(f"{PUBLIC}/programs", params={"level": "bachelor"}).json()
    no_match = ctx.client.get(f"{PUBLIC}/programs", params={"q": "prawo"}).json()

    assert [p["slug"] for p in by_text] == ["analiza-danych"]
    assert [p["slug"] for p in by_level] == ["informatyka-inz"]
    assert no_match == []


def test_program_detail_and_missing_program(ctx):
    seed_catalogue(ctx)

    assert ctx.client.get(f"{PUBLIC}/programs/informatyka-inz").json()["semesters"] == 6
    assert ctx.client.get(f"{PUBLIC}/programs/nope").status_code == 404


def test_staff_directory_search(ctx):
    seed_catalogue(ctx)

    found = ctx.client.get(f"{PUBLIC}/staff", params={"q": "wrzos", "locale": "en"}).json()

    assert [(s["full_name"], s["position"]) for s in found] == [("Helena Wrzosek", "Dean")]
    assert ctx.client.get(f"{PUBLIC}/staff", params={"q": "nowak"}).json() == []


def test_duplicate_faculty_slug_conflicts(ctx):
    seed_catalogue(ctx)

    response = ctx.client.post(
        f"{ADMIN}/faculties",
        json={"slug": "informatyka", "name_pl": "X", "name_en": "X"},
        headers=ctx.auth("root", Role.ADMIN),
    )

    assert response.status_code == 409


def test_contact_form_is_emailed_to_the_office(ctx):
    response = ctx.client.post(f"{PUBLIC}/contact", json=CONTACT)

    assert response.status_code == 202
    ctx.run_jobs()
    [email] = ctx.services.email.sent
    assert email.recipient == "rektorat@ukal.example"
    assert "jan@mail.example" in email.body


def test_contact_form_is_rate_limited(ctx):
    statuses = [ctx.client.post(f"{PUBLIC}/contact", json=CONTACT).status_code for _ in range(6)]

    assert statuses == [202] * 5 + [429]


def test_health_and_metrics_endpoints(ctx):
    assert ctx.client.get("/healthz").json() == {"status": "ok"}
    assert ctx.client.get("/readyz").status_code == 200
    ctx.client.get(f"{PUBLIC}/programs/some-slug")

    metrics = ctx.client.get("/metrics").text

    # Labelled by route template, so slugs and ids do not create new series.
    assert 'route="/public/programs/{slug}"' in metrics
    assert "some-slug" not in metrics
    assert "enrollment_attempts_total" in metrics
