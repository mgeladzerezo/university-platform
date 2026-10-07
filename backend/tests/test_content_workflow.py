import pytest
from sqlalchemy import func, select

from app.assistant.store import ContentChunk
from app.auth import Role

CMS = "/api/v1/cms/content"
PUBLIC = "/api/v1/public/content"

NEWS = {
    "kind": "news",
    "slug": "nowy-kampus",
    "locale": "pl",
    "title": "Nowy kampus",
    "summary": "Otwieramy nowy budynek.",
    "body_html": "<p>Nowy budynek dydaktyczny zostanie otwarty w październiku.</p>",
}


@pytest.fixture
def author(ctx):
    return ctx.auth("editor-anna", Role.EDITOR)


@pytest.fixture
def reviewer(ctx):
    return ctx.auth("editor-piotr", Role.EDITOR)


def create(ctx, headers, **overrides) -> dict:
    response = ctx.client.post(CMS, json={**NEWS, **overrides}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def transition(ctx, content_id: int, action: str, headers):
    return ctx.client.post(
        f"{CMS}/{content_id}/transitions", json={"action": action}, headers=headers
    )


def publish(ctx, author, reviewer, **overrides) -> dict:
    item = create(ctx, author, **overrides)
    assert transition(ctx, item["id"], "submit", author).status_code == 200
    response = transition(ctx, item["id"], "publish", reviewer)
    assert response.status_code == 200, response.text
    return response.json()


def public_slugs(ctx, **params) -> list[str]:
    response = ctx.client.get(PUBLIC, params={"kind": "news", "locale": "pl", **params})
    assert response.status_code == 200
    return [item["slug"] for item in response.json()]


def chunk_count(ctx) -> int:
    with ctx.session() as session:
        return session.scalar(select(func.count()).select_from(ContentChunk))


def test_new_content_starts_as_draft(ctx, author):
    assert create(ctx, author)["status"] == "draft"


def test_full_workflow_draft_review_publish(ctx, author, reviewer):
    item = create(ctx, author)

    assert transition(ctx, item["id"], "submit", author).json()["status"] == "in_review"
    published = transition(ctx, item["id"], "publish", reviewer).json()

    assert published["status"] == "published"
    assert published["published_at"] is not None
    history = ctx.client.get(f"{CMS}/{item['id']}/history", headers=author).json()
    assert [(e["from_status"], e["to_status"]) for e in history] == [
        ("draft", "in_review"),
        ("in_review", "published"),
    ]
    assert history[1]["actor_sub"] == "editor-piotr"


@pytest.mark.parametrize(
    ("steps", "illegal"),
    [
        ([], "publish"),
        ([], "request_changes"),
        ([], "unpublish"),
        ([], "restore"),
        (["submit"], "submit"),
        (["submit"], "unpublish"),
        (["submit"], "archive"),
        (["submit", "publish"], "submit"),
        (["submit", "publish"], "publish"),
        (["submit", "publish"], "request_changes"),
        (["archive"], "submit"),
        (["archive"], "publish"),
    ],
)
def test_illegal_transitions_are_rejected(ctx, author, reviewer, steps, illegal):
    item = create(ctx, author)
    for step in steps:
        assert transition(ctx, item["id"], step, reviewer).status_code == 200

    response = transition(ctx, item["id"], illegal, reviewer)

    assert response.status_code == 409


@pytest.mark.parametrize(
    ("steps", "expected"),
    [
        (["submit", "request_changes"], "draft"),
        (["submit", "publish", "unpublish"], "draft"),
        (["submit", "publish", "archive"], "archived"),
        (["archive", "restore"], "draft"),
    ],
)
def test_legal_side_paths(ctx, author, reviewer, steps, expected):
    item = create(ctx, author)
    for step in steps:
        response = transition(ctx, item["id"], step, reviewer)
        assert response.status_code == 200, response.text

    assert response.json()["status"] == expected


def test_author_cannot_publish_own_content(ctx, author):
    item = create(ctx, author)
    transition(ctx, item["id"], "submit", author)

    response = transition(ctx, item["id"], "publish", author)

    assert response.status_code == 403


def test_admin_may_publish_own_content(ctx):
    admin = ctx.auth("root", Role.ADMIN)
    item = create(ctx, admin)
    transition(ctx, item["id"], "submit", admin)

    assert transition(ctx, item["id"], "publish", admin).status_code == 200


def test_only_published_content_is_public(ctx, author, reviewer):
    draft = create(ctx, author, slug="szkic")
    in_review = create(ctx, author, slug="w-recenzji")
    transition(ctx, in_review["id"], "submit", author)
    archived = create(ctx, author, slug="archiwum")
    transition(ctx, archived["id"], "archive", author)
    publish(ctx, author, reviewer, slug="opublikowane")

    assert public_slugs(ctx) == ["opublikowane"]
    for hidden in (draft, in_review, archived):
        response = ctx.client.get(f"{PUBLIC}/news/{hidden['slug']}", params={"locale": "pl"})
        assert response.status_code == 404
    visible = ctx.client.get(f"{PUBLIC}/news/opublikowane", params={"locale": "pl"})
    assert visible.status_code == 200
    assert "status" not in visible.json()
    assert "author_sub" not in visible.json()


def test_unpublished_content_disappears_from_public_site(ctx, author, reviewer):
    item = publish(ctx, author, reviewer)
    assert public_slugs(ctx) == ["nowy-kampus"]

    transition(ctx, item["id"], "unpublish", reviewer)

    assert public_slugs(ctx) == []


def test_published_content_cannot_be_edited_in_place(ctx, author, reviewer):
    item = publish(ctx, author, reviewer)

    response = ctx.client.put(f"{CMS}/{item['id']}", json={**NEWS, "title": "X"}, headers=author)

    assert response.status_code == 409


def test_draft_can_be_edited_and_html_is_sanitized(ctx, author):
    item = create(ctx, author)
    body = '<p onclick="steal()">Tekst</p><script>alert(1)</script><a href="https://ukal.example">x</a>'

    response = ctx.client.put(
        f"{CMS}/{item['id']}", json={**NEWS, "body_html": body}, headers=author
    )

    assert response.status_code == 200
    saved = response.json()["body_html"]
    assert "<script" not in saved
    assert "onclick" not in saved
    assert 'href="https://ukal.example"' in saved


def test_duplicate_slug_in_same_locale_conflicts(ctx, author):
    create(ctx, author)

    response = ctx.client.post(CMS, json=NEWS, headers=author)

    assert response.status_code == 409
    assert ctx.client.post(CMS, json={**NEWS, "locale": "en"}, headers=author).status_code == 201


def test_event_requires_start_time(ctx, author):
    response = ctx.client.post(CMS, json={**NEWS, "kind": "event"}, headers=author)

    assert response.status_code == 422


def test_public_search_matches_published_content_only(ctx, author, reviewer):
    publish(ctx, author, reviewer, slug="stypendia", title="Stypendia naukowe")
    publish(ctx, author, reviewer, slug="sport", title="Zawody sportowe")
    create(ctx, author, slug="szkic-stypendia", title="Stypendia - szkic")

    assert public_slugs(ctx, q="stypendia") == ["stypendia"]
    assert public_slugs(ctx, q="100%") == []


def test_content_is_indexed_only_after_publication(ctx, author, reviewer):
    item = create(ctx, author)
    transition(ctx, item["id"], "submit", author)
    assert ctx.run_jobs() == 0
    assert chunk_count(ctx) == 0

    transition(ctx, item["id"], "publish", reviewer)

    assert ctx.services.jobs.pending == [
        ("assistant.index_content", {"content_item_id": item["id"]})
    ]
    ctx.run_jobs()
    assert chunk_count(ctx) > 0


def test_unpublishing_removes_chunks_immediately(ctx, author, reviewer):
    item = publish(ctx, author, reviewer)
    ctx.run_jobs()
    assert chunk_count(ctx) > 0

    transition(ctx, item["id"], "unpublish", reviewer)

    assert chunk_count(ctx) == 0


def test_index_job_skips_content_unpublished_while_queued(ctx, author, reviewer):
    item = publish(ctx, author, reviewer)
    transition(ctx, item["id"], "unpublish", reviewer)

    ctx.run_jobs()

    assert chunk_count(ctx) == 0


def test_republishing_replaces_chunks_instead_of_duplicating(ctx, author, reviewer):
    item = publish(ctx, author, reviewer)
    ctx.run_jobs()
    first = chunk_count(ctx)
    transition(ctx, item["id"], "unpublish", reviewer)
    transition(ctx, item["id"], "submit", author)
    transition(ctx, item["id"], "publish", reviewer)
    ctx.run_jobs()

    assert chunk_count(ctx) == first
