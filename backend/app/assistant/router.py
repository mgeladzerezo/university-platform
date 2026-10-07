import json
import uuid
from collections.abc import Iterator
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admissions.service import get_application_for
from app.assistant import service
from app.assistant.llm import LlmUnavailable
from app.assistant.store import AiAuditLog
from app.auth import Principal, Role, require_roles
from app.db import get_session
from app.ratelimit import enforce_rate_limit

router = APIRouter(prefix="/assistant", tags=["assistant"])

officer_only = require_roles(Role.ADMISSIONS_OFFICER)
admin_only = require_roles(Role.ADMIN)


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    locale: Literal["pl", "en"] = "pl"


class ApplicationSummary(BaseModel):
    summary: str
    missing_documents: list[str]
    model: str


class AuditEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    actor_sub: str
    action: str
    subject_id: str
    model: str
    outcome: str
    created_at: datetime


def _sse(events: Iterator[tuple[str, dict]]) -> Iterator[str]:
    for event, data in events:
        yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat", response_class=StreamingResponse)
def chat(data: ChatRequest, request: Request, session: Session = Depends(get_session)):
    """Public endpoint. It takes no credentials on purpose: the request never
    carries a user identity, so nothing about the caller can reach the model."""
    services = request.app.state.services
    enforce_rate_limit(request, "chat", services.settings.chat_rate_limit_per_minute, 60)
    # Retrieval happens here so the database session is not held during streaming.
    plan = service.plan_chat(session, services, data.question, data.locale)
    return StreamingResponse(
        _sse(service.chat_events(plan, services.llm)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/applications/{application_id}/summary", response_model=ApplicationSummary)
def application_summary(
    application_id: uuid.UUID,
    request: Request,
    officer: Principal = Depends(officer_only),
    session: Session = Depends(get_session),
):
    llm = request.app.state.services.llm
    application = get_application_for(session, application_id, officer)
    try:
        summary, missing = service.summarize_application(session, llm, application, officer)
    except LlmUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return ApplicationSummary(summary=summary, missing_documents=missing, model=llm.model)


@router.get("/audit", response_model=list[AuditEntry])
def audit_log(_admin: Principal = Depends(admin_only), session: Session = Depends(get_session)):
    return session.scalars(select(AiAuditLog).order_by(AiAuditLog.id.desc()).limit(200)).all()
