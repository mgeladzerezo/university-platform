from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import String
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db import Base


class Role(StrEnum):
    APPLICANT = "applicant"
    STUDENT = "student"
    LECTURER = "lecturer"
    EDITOR = "editor"
    ADMISSIONS_OFFICER = "admissions_officer"
    ADMIN = "admin"


@dataclass(frozen=True)
class Principal:
    sub: str
    email: str
    name: str
    roles: frozenset[Role]

    def has_any(self, *roles: Role) -> bool:
        return Role.ADMIN in self.roles or bool(self.roles.intersection(roles))


class InvalidToken(Exception):
    pass


KeyResolver = Callable[[str], Any]


class TokenVerifier:
    """Validates Keycloak access tokens: signature, issuer, audience, expiry."""

    def __init__(self, issuer: str, audience: str, resolve_key: KeyResolver):
        self._issuer = issuer
        self._audience = audience
        self._resolve_key = resolve_key

    def verify(self, token: str) -> Principal:
        try:
            claims = jwt.decode(
                token,
                self._resolve_key(token),
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise InvalidToken(str(exc)) from exc
        return Principal(
            sub=claims["sub"],
            email=claims.get("email", ""),
            name=claims.get("name") or claims.get("preferred_username", ""),
            roles=_known_roles(claims.get("realm_access", {}).get("roles", [])),
        )


def _known_roles(raw_roles: list[str]) -> frozenset[Role]:
    known = {role.value for role in Role}
    return frozenset(Role(role) for role in raw_roles if role in known)


def jwks_key_resolver(jwks_url: str) -> KeyResolver:
    client = jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)
    return lambda token: client.get_signing_key_from_jwt(token).key


_bearer = HTTPBearer(auto_error=False)


def current_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    if credentials is None:
        raise _unauthorized("Missing bearer token")
    try:
        return request.app.state.services.token_verifier.verify(credentials.credentials)
    except InvalidToken as exc:
        raise _unauthorized("Invalid token") from exc


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_roles(*allowed: Role) -> Callable[..., Principal]:
    """Dependency factory. Admin passes every role check."""

    def dependency(principal: Principal = Depends(current_principal)) -> Principal:
        if not principal.has_any(*allowed):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return principal

    dependency.allowed_roles = frozenset(allowed)  # read by the route coverage test
    return dependency


class UserProfile(Base):
    """Local copy of the few identity fields other modules need (e-mail, name).

    Keycloak stays the source of truth; rows are refreshed from token claims.
    """

    __tablename__ = "user_profiles"

    sub: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(254))
    full_name: Mapped[str] = mapped_column(String(200))


def remember_user(session: Session, principal: Principal) -> None:
    profile = session.get(UserProfile, principal.sub)
    if profile is None:
        session.add(UserProfile(sub=principal.sub, email=principal.email, full_name=principal.name))
    else:
        profile.email = principal.email
        profile.full_name = principal.name
