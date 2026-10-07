import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth import InvalidToken, Role, TokenVerifier
from tests.conftest import AUDIENCE, ISSUER

PROTECTED = "/api/v1/academics/me/enrollments"


@pytest.fixture
def verifier(signing_key):
    public_key = signing_key.public_key()
    return TokenVerifier(ISSUER, AUDIENCE, lambda _token: public_key)


def test_valid_token_yields_principal_with_known_roles_only(verifier, make_token):
    token = make_token(sub="abc", roles=("student", "offline_access", "uma_authorization"))

    principal = verifier.verify(token)

    assert principal.sub == "abc"
    assert principal.roles == frozenset({Role.STUDENT})


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": 1},
        {"iss": "https://evil.test/realms/kalinowo"},
        {"aud": "another-client"},
    ],
    ids=["expired", "wrong-issuer", "wrong-audience"],
)
def test_token_with_bad_claims_is_rejected(verifier, make_token, overrides):
    with pytest.raises(InvalidToken):
        verifier.verify(make_token(**overrides))


def test_token_signed_with_another_key_is_rejected(verifier, make_token):
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    with pytest.raises(InvalidToken):
        verifier.verify(make_token(key=other_key))


def test_unsigned_token_is_rejected(verifier):
    # header {"alg":"none"} + payload, no signature
    unsigned = "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJ4In0."

    with pytest.raises(InvalidToken):
        verifier.verify(unsigned)


def test_request_without_token_gets_401(ctx):
    response = ctx.client.get(PROTECTED)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_request_with_garbage_token_gets_401(ctx):
    response = ctx.client.get(PROTECTED, headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401


def test_admin_passes_role_checks_of_other_roles(ctx):
    response = ctx.client.get(PROTECTED, headers=ctx.auth("root", Role.ADMIN))

    assert response.status_code == 200
