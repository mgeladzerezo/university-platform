"""Role enforcement for every route, driven by the application's own route table.

A new endpoint is covered automatically: it must either be listed in
PUBLIC_ROUTES or declare `require_roles`, otherwise the first test fails.
"""

import re

import pytest
from fastapi.routing import APIRoute

from app.auth import Role
from app.db import make_engine, make_session_factory
from app.main import API_PREFIX, ROUTERS, create_app

PUBLIC_ROUTES = {
    ("GET", "/api/v1/public/faculties"),
    ("GET", "/api/v1/public/programs"),
    ("GET", "/api/v1/public/programs/{slug}"),
    ("GET", "/api/v1/public/staff"),
    ("GET", "/api/v1/public/content"),
    ("GET", "/api/v1/public/content/{kind}/{slug}"),
    ("POST", "/api/v1/public/contact"),
    ("POST", "/api/v1/assistant/chat"),
    ("GET", "/healthz"),
    ("GET", "/readyz"),
    ("GET", "/metrics"),
}

# Roles each area is meant for; the test below compares this to the code.
EXPECTED_ROLES = {
    "/api/v1/cms/": {Role.EDITOR},
    "/api/v1/admin/catalogue/": {Role.ADMIN},
    "/api/v1/admissions/review/": {Role.ADMISSIONS_OFFICER},
    "/api/v1/academics/me/": {Role.STUDENT},
    "/api/v1/academics/teaching/": {Role.LECTURER},
    "/api/v1/academics/admin/": {Role.ADMIN},
    "/api/v1/assistant/applications/": {Role.ADMISSIONS_OFFICER},
    "/api/v1/assistant/audit": {Role.ADMIN},
}


def _allowed_roles(dependant) -> frozenset[Role] | None:
    """Find the `require_roles` dependency anywhere in a route's dependency tree."""
    for dependency in dependant.dependencies:
        roles = getattr(dependency.call, "allowed_roles", None)
        if roles is not None:
            return roles
        nested = _allowed_roles(dependency)
        if nested is not None:
            return nested
    return None


def _routes():
    # Only the route table is needed here, so no services are wired in.
    app = create_app(_NoServices(), make_session_factory(make_engine("sqlite://")))
    # ROUTERS is the same tuple create_app mounts under API_PREFIX; routes
    # defined directly on the app (health, metrics) come from app.routes.
    sources = [("", app.routes)] + [(API_PREFIX, router.routes) for router in ROUTERS]
    for prefix, routes in sources:
        for route in routes:
            if isinstance(route, APIRoute):
                for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
                    yield method, prefix + route.path, _allowed_roles(route.dependant)


class _NoServices:
    class settings:
        cors_origins: list[str] = []


ROUTES = list(_routes())
PROTECTED = [(m, p, roles) for m, p, roles in ROUTES if (m, p) not in PUBLIC_ROUTES]
ROUTE_IDS = [f"{m} {p}" for m, p, _ in PROTECTED]


def _concrete(path: str) -> str:
    def fill(match: re.Match) -> str:
        name = match.group(1)
        if name in ("application_id", "document_id"):
            return "00000000-0000-0000-0000-000000000000"
        return "1"

    return re.sub(r"\{(\w+)\}", fill, path)


def test_route_table_is_not_empty():
    assert len(PROTECTED) > 30


def test_every_route_is_public_on_purpose_or_declares_roles():
    undeclared = [(m, p) for m, p, roles in PROTECTED if roles is None]

    assert undeclared == []


def test_public_allowlist_has_no_stale_entries():
    assert {(m, p) for m, p, _ in ROUTES} >= PUBLIC_ROUTES


@pytest.mark.parametrize(("prefix", "expected"), EXPECTED_ROLES.items())
def test_area_is_restricted_to_its_role(prefix, expected):
    area = [(m, p, roles) for m, p, roles in PROTECTED if p.startswith(prefix)]

    assert area, f"no routes under {prefix}"
    for method, path, roles in area:
        assert roles == expected, f"{method} {path}"


@pytest.mark.parametrize(("method", "path", "allowed"), PROTECTED, ids=ROUTE_IDS)
def test_protected_route_rejects_anonymous_and_wrong_roles(ctx, method, path, allowed):
    url = _concrete(path)

    assert ctx.client.request(method, url).status_code == 401

    for role in set(Role) - set(allowed) - {Role.ADMIN}:
        response = ctx.client.request(method, url, headers=ctx.auth("intruder", role))
        assert response.status_code == 403, f"{role} reached {method} {path}"

    no_roles = ctx.client.request(method, url, headers=ctx.auth("nobody"))
    assert no_roles.status_code == 403


@pytest.mark.parametrize(("method", "path", "allowed"), PROTECTED, ids=ROUTE_IDS)
def test_protected_route_lets_allowed_roles_past_the_role_check(ctx, method, path, allowed):
    url = _concrete(path)

    for role in set(allowed) | {Role.ADMIN}:
        response = ctx.client.request(method, url, headers=ctx.auth("member", role))
        # 404/409/422 are fine: the request got past authorization.
        assert response.status_code not in (401, 403), f"{role} blocked on {method} {path}"
