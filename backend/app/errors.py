from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    status_code = 400

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class NotFound(DomainError):
    status_code = 404


class Conflict(DomainError):
    status_code = 409


class Forbidden(DomainError):
    status_code = 403


class InvalidInput(DomainError):
    status_code = 422


class TooManyRequests(DomainError):
    status_code = 429


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(_request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
